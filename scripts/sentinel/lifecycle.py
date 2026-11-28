"""Mechanical GEMINI.md lifecycle controller (PreToolUse, PostToolUse, Stop)."""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .ast_gate import check_write_integrity
from .policy import (
    VerificationCmd,
    check_mcp_call,
    check_shell_command,
    classify_verification_command,
    domain_bucket,
    effective_roots,
    is_code_file,
    is_code_mutating_shell_cmd,
    is_mutating_shell_cmd,
    is_protected_path,
    is_subagent,
    is_test_file,
    load_user_policy,
    resolve_target,
)
from .state import (
    STATE_PROTECTED_BASENAMES,
    EvidenceRecord,
    SentinelState,
    compute_state_digest,
    file_digest,
    load_state,
    state_path,
    update_state,
)

READ_TOOLS = ("read_file", "view_file")
WRITE_TOOLS = ("write_file", "write_to_file")
EDIT_TOOLS = ("edit_file", "replace_file_content", "multi_replace_file_content")
MUTATE_FILE_TOOLS = WRITE_TOOLS + EDIT_TOOLS
SHELL_TOOLS = ("run_command", "command")

_OUTPUT_FAILURE_RE = re.compile(
    r"(?:\b[1-9]\d*\s+(?:failed|errors?|failing)\b"
    r"|^FAIL:\s+\S+\s+\("
    r"|^ERROR:\s+\S+\s+\("
    r"|\bFAILED\s*\("
    r"|\bunexpected\s+successes\s*=\s*[1-9]\d*"
    r"|^FAILED\s+\S+::\S+"
    r"|\bERROR\s+collecting\b"
    r"|\bInterrupted:\s+[1-9]\d*\s+errors?\b"
    r"|^FAIL\t"
    r"|^---\s+FAIL:"
    r"|^test result:\s+FAILED\.)",
    re.MULTILINE,
)
_GATE_FAILURE_RE = re.compile(r"(?:\bCUSTODY_FAIL\b|Traceback \(most recent call last\)|\bFAILED\s*\()")
_PASSED_COUNT_RE = re.compile(r"(?im)(?:\b(\d+)\s+(?:passed|passing)\b|^#\s+pass\s+(\d+)\b)")
_UNITTEST_OK_RE = re.compile(r"(?is)\bran\s+(\d+)\s+tests?\b.*?\bok(?:\s*\(([^)]*)\))?")
_GO_VERBOSE_PASS_RE = re.compile(r"(?m)^---\s+PASS:")
_GO_OK_PKG_RE = re.compile(r"(?m)^ok\s+\S+(?!.*\[no test(?:s to run| files)\])")
_GO_NO_TESTS_WARN_RE = re.compile(r"(?i)testing:\s+warning:\s+no\s+tests\s+to\s+run")
_VACUOUS_DETAIL_RE = re.compile(
    r"(?i)(?:\bran\s+0\s+tests?\b|\bcollected\s+\d+\s+items?\b|\bno\s+tests?\s+ran\b|\b0\s+passed\b|"
    r"\b\d+\s+(?:skipped|xfailed|deselected)\b|\[no test(?:s to run| files)\]|testing:\s+warning:\s+no\s+tests\s+to\s+run)"
)
_GENERIC_STEMS = frozenset({"__init__"})
_GENERIC_PKG_DIRS = frozenset({"src", "lib", "app", "scripts", "pkg", "internal", "cmd", "repo", "tests", "test"})
_TEST_TIER_DIRS = frozenset(
    {"tests", "test", "unit", "integration", "e2e", "functional", "unit_tests", "integration_tests", "specs", "spec"}
)


def _extract_path_arg(args: dict[str, Any]) -> Any:
    for k in ("Path", "TargetFile", "file_path", "path", "AbsolutePath"):
        if args.get(k) is not None:
            return args.get(k)
    return None


def _extract_cwd(payload: dict[str, Any], args: dict[str, Any]) -> str | None:
    for c in (args.get("Cwd"), args.get("cwd"), payload.get("cwd"), payload.get("Cwd")):
        if isinstance(c, str) and c.strip():
            return c.strip()
    return None


def _has_git_repo(root_path: str) -> bool:
    cur = Path(root_path).resolve()
    for parent in (cur, *cur.parents):
        if (parent / ".git").exists():
            return True
    return False


def _extract_artifact_dir(payload: dict[str, Any]) -> str | None:
    art = payload.get("artifactDirectoryPath")
    return art.strip() if isinstance(art, str) and art.strip() else None


def _extract_exit_code(payload: dict[str, Any]) -> int | None:
    for container in (payload, payload.get("toolResult"), payload.get("result")):
        if not isinstance(container, dict):
            continue
        for key in ("exitCode", "exit_code", "returncode"):
            val = container.get(key)
            if isinstance(val, int) and not isinstance(val, bool):
                return val
            if isinstance(val, str) and val.strip().lstrip("+-").isdigit():
                return int(val.strip())
    return None


def _is_tool_failed(payload: dict[str, Any]) -> bool:
    ec = _extract_exit_code(payload)
    if ec is not None and ec != 0:
        return True
    for container in (payload, payload.get("toolResult"), payload.get("result")):
        if not isinstance(container, dict):
            continue
        if container.get("error"):
            return True
        if container.get("isError") is True or container.get("success") is False:
            return True
        status = container.get("status")
        if isinstance(status, str) and status.strip().lower() in ("error", "failed", "failure"):
            return True
    return False


def _extract_output_channel(payload: dict[str, Any]) -> tuple[str, str]:
    """Return (channel='captured'|'absent', combined_output_text)."""
    chunks: list[str] = []
    captured = False
    for container in (payload, payload.get("toolResult"), payload.get("result")):
        if isinstance(container, str):
            captured = True
            chunks.append(container)
            continue
        if not isinstance(container, dict):
            continue
        for key in ("stdout", "stderr", "output", "text", "content"):
            val = container.get(key)
            if isinstance(val, str):
                captured = True
                chunks.append(val)
    return ("captured" if captured else "absent"), "\n".join(chunks)


def _count_effective_passes(runner: str, combined: str) -> int:
    if runner == "unittest":
        matches = list(_UNITTEST_OK_RE.finditer(combined))
        if matches:
            total = 0
            for m in matches:
                ran = int(m.group(1))
                meta = m.group(2) or ""
                m_skip = re.search(r"skipped\s*=\s*(\d+)", meta, re.IGNORECASE)
                m_xfail = re.search(r"expected\s+failures\s*=\s*(\d+)", meta, re.IGNORECASE)
                skipped = int(m_skip.group(1)) if m_skip else 0
                xfailed = int(m_xfail.group(1)) if m_xfail else 0
                total += max(0, ran - skipped - xfailed)
            return total
    if runner == "go":
        verbose_passes = len(_GO_VERBOSE_PASS_RE.findall(combined))
        if verbose_passes > 0:
            return verbose_passes
        ok_pkgs = len(_GO_OK_PKG_RE.findall(combined))
        empty_warns = len(_GO_NO_TESTS_WARN_RE.findall(combined))
        return max(0, ok_pkgs - empty_warns)
    return sum(int(m.group(1) or m.group(2)) for m in _PASSED_COUNT_RE.finditer(combined))


def _resolve_test_target_path(target: str, roots: list[str], cwd: str | None) -> str | None:
    clean = target.split("::", 1)[0].strip()
    if not clean:
        return None
    candidates: list[Path] = []
    p = Path(clean)
    if p.is_absolute():
        candidates.append(p)
    else:
        if cwd:
            candidates.append(Path(cwd) / clean)
        for r in roots:
            candidates.append(Path(r) / clean)
        # Support dotted Python unittest module specs (e.g. scripts.tests.test_sentinel)
        if "." in clean and "/" not in clean and "\\" not in clean and not clean.endswith(".py"):
            rel_py = clean.replace(".", "/") + ".py"
            if cwd:
                candidates.append(Path(cwd) / rel_py)
            for r in roots:
                candidates.append(Path(r) / rel_py)
    for cand in candidates:
        if cand.exists():
            return os.path.realpath(str(cand))
    return None


def _is_test_suite_dir(resolved_dir: str, raw_target: str) -> bool:
    parts = [p.lower() for p in Path(raw_target.replace("\\", "/")).parts if p not in (".", "/", "\\")]
    if Path(resolved_dir).name.lower() in _TEST_TIER_DIRS:
        return True
    return any(p in ("tests", "test", "specs", "spec") for p in parts)


def _obligation_covered(
    obl_path: str,
    cmd_info: VerificationCmd,
    roots: list[str],
    cwd: str | None,
) -> bool:
    """True when a passing verification command is scoped to cover the given obligation path."""
    if not cmd_info.targets and not cmd_info.filters:
        return True
    if "__partial_exclude__" in cmd_info.filters:
        return False

    obl_real = os.path.realpath(obl_path)
    obl_p = Path(obl_real)
    stem = obl_p.stem.lower()
    norm_roots = {os.path.realpath(r) for r in roots}

    if is_test_file(obl_real):
        base_stem = re.sub(r"^(?:test_|spec_)|(?:_test|_spec)$", "", stem)
        for t in cmd_info.targets:
            t_clean = t.split("::", 1)[0].strip()
            resolved = _resolve_test_target_path(t_clean, roots, cwd)
            if resolved:
                if resolved == obl_real or (os.path.isdir(resolved) and obl_real.startswith(resolved + os.sep)):
                    return True
            t_stem = Path(t_clean.replace("\\", "/")).stem.lower()
            if t_stem == stem or t_clean.lower().endswith(f".{stem}"):
                return True
        if not cmd_info.targets and cmd_info.filters:
            for flt in cmd_info.filters:
                flt_low = flt.lower()
                if stem in flt_low or (len(base_stem) >= 3 and base_stem in flt_low):
                    return True
                # Check if filter targets a test function defined inside this test file
                if os.path.isfile(obl_real) and os.path.getsize(obl_real) <= 524288:
                    try:
                        txt = Path(obl_real).read_text(encoding="utf-8", errors="ignore").lower()
                        tokens = [tok for tok in re.findall(r"[a-z0-9_]{3,}", flt_low) if tok not in ("and", "not", "or")]
                        if tokens and any(tok in txt for tok in tokens):
                            return True
                    except OSError:
                        pass
        return False

    idents: set[str] = set()
    if stem and stem not in _GENERIC_STEMS and len(stem) >= 2:
        idents.add(stem)
    parent = obl_p.parent
    parent_real = os.path.realpath(str(parent))
    if parent_real not in norm_roots:
        parent_name = parent.name.lower()
        if parent_name and (parent_name not in _GENERIC_PKG_DIRS or not idents) and len(parent_name) >= 2:
            idents.add(parent_name)
    if not idents and parent.name:
        idents.add(parent.name.lower())

    for t in cmd_info.targets:
        t_clean = t.split("::", 1)[0].strip()
        resolved = _resolve_test_target_path(t_clean, roots, cwd)
        if resolved and os.path.isdir(resolved):
            if obl_real.startswith(resolved + os.sep) or _is_test_suite_dir(resolved, t_clean):
                return True
        t_low = t_clean.replace("\\", "/").lower()
        if any(re.search(rf"(?:^|[^a-z0-9]){re.escape(ident)}(?:$|[^a-z0-9])", t_low) or ident in Path(t_low).stem for ident in idents):
            return True
        if resolved and os.path.isfile(resolved) and os.path.getsize(resolved) <= 524288:
            try:
                test_src = Path(resolved).read_text(encoding="utf-8", errors="ignore").lower()
                if any(re.search(rf"\b{re.escape(ident)}\b", test_src) for ident in idents):
                    return True
            except OSError:
                pass

    if not cmd_info.targets and cmd_info.filters:
        for flt in cmd_info.filters:
            flt_low = flt.lower()
            if any(ident in flt_low for ident in idents):
                return True

    return False


def evaluate_verification_evidence(
    payload: dict[str, Any],
    cmd_info: VerificationCmd,
    state_digest: str,
    *,
    require_output_evidence: bool = False,
) -> EvidenceRecord:
    """Classify observed verification execution into PASS | FAIL | VACUOUS | UNKNOWN."""
    channel, combined = _extract_output_channel(payload)
    if cmd_info.dry_run:
        return EvidenceRecord(
            state_digest=state_digest,
            outcome="VACUOUS",
            channel=channel,
            runner=cmd_info.runner,
            scope=cmd_info.scope,
            discharged=False,
            detail="dry_run_flag",
        )
    if _is_tool_failed(payload):
        return EvidenceRecord(
            state_digest=state_digest,
            outcome="FAIL",
            channel=channel,
            runner=cmd_info.runner,
            scope=cmd_info.scope,
            discharged=False,
            detail="tool_failed",
        )
    if channel == "absent":
        return EvidenceRecord(
            state_digest=state_digest,
            outcome="UNKNOWN",
            channel="absent",
            runner=cmd_info.runner,
            scope=cmd_info.scope,
            discharged=not require_output_evidence,
            detail="host_omitted_output",
        )

    if cmd_info.runner == "custom_gate":
        if _GATE_FAILURE_RE.search(combined):
            return EvidenceRecord(
                state_digest=state_digest,
                outcome="FAIL",
                channel="captured",
                runner=cmd_info.runner,
                scope=cmd_info.scope,
                discharged=False,
                detail="gate_failed",
            )
        if combined.strip():
            return EvidenceRecord(
                state_digest=state_digest,
                outcome="PASS",
                channel="captured",
                runner=cmd_info.runner,
                scope=cmd_info.scope,
                discharged=True,
                detail="gate_ok",
            )
        return EvidenceRecord(
            state_digest=state_digest,
            outcome="VACUOUS",
            channel="captured",
            runner=cmd_info.runner,
            scope=cmd_info.scope,
            discharged=False,
            detail="empty_output",
        )

    if _OUTPUT_FAILURE_RE.search(combined):
        return EvidenceRecord(
            state_digest=state_digest,
            outcome="FAIL",
            channel="captured",
            runner=cmd_info.runner,
            scope=cmd_info.scope,
            discharged=False,
            detail="output_failure",
        )

    effective_passed = _count_effective_passes(cmd_info.runner, combined)
    if effective_passed > 0:
        return EvidenceRecord(
            state_digest=state_digest,
            outcome="PASS",
            channel="captured",
            runner=cmd_info.runner,
            scope=cmd_info.scope,
            discharged=True,
            detail=f"passed={effective_passed}",
        )

    is_vacuous = (not combined.strip()) or bool(_VACUOUS_DETAIL_RE.search(combined))
    return EvidenceRecord(
        state_digest=state_digest,
        outcome="VACUOUS" if is_vacuous else "UNKNOWN",
        channel="captured",
        runner=cmd_info.runner,
        scope=cmd_info.scope,
        discharged=False,
        detail="zero_effective_passes" if is_vacuous else "no_positive_pass_evidence",
    )


def pre(payload: dict[str, Any]) -> dict[str, str]:
    tool = payload.get("toolCall") or {}
    name = str(tool.get("name") or "")
    args = tool.get("args")
    subagent = is_subagent(payload)
    if not isinstance(args, dict):
        return {"decision": "deny" if subagent else "ask", "reason": "Cannot inspect tool arguments."}

    if name in READ_TOOLS:
        return {"decision": "allow", "reason": "Read operation permitted."}

    roots = payload.get("workspacePaths") or []
    art_dir = _extract_artifact_dir(payload)
    cwd = _extract_cwd(payload, args)

    if name in MUTATE_FILE_TOOLS:
        raw_target = _extract_path_arg(args)
        if isinstance(raw_target, str) and os.path.basename(raw_target.strip()).lower() in STATE_PROTECTED_BASENAMES:
            return {"decision": "deny", "reason": "RW-06: Direct modification of hook state is prohibited."}

        resolved = resolve_target(raw_target, roots, artifact_dir=art_dir, cwd=cwd)
        if resolved is None:
            if subagent:
                return {"decision": "deny", "reason": "Subagent cannot write outside mounted workspace."}
            return {"decision": "ask", "reason": "File target outside mounted workspace; native permissions apply."}

        rel, full, matched_root = resolved
        if is_protected_path(rel, full):
            return {
                "decision": "deny",
                "reason": "RW-04: Protected governance, acceptance, hook state, or Git internals; direct modification prohibited.",
            }

        has_git = _has_git_repo(matched_root) if matched_root is not None else False
        if state_path(payload) is not None and matched_root is not None:
            st = load_state(payload)
            if st.repair_strikes >= 3:
                return {
                    "decision": "deny",
                    "reason": "LIFECYCLE (3-Strike Governor): 3 failed verification cycles after edits. Inspect root cause with read_file before patching again.",
                }
            if (
                not subagent
                and has_git
                and not st.oriented
                and (is_code_file(full, art_dir) or os.path.isfile(full))
            ):
                return {
                    "decision": "deny",
                    "reason": "LIFECYCLE (Orient-Before-Edit): Read an entry/target file or run an orientation check before mutating workspace files.",
                }

        issue = check_write_integrity(name, args, full, artifact_dir=art_dir)
        if issue is not None:
            dec, rsn = issue
            if subagent and dec in ("ask", "force_ask"):
                dec = "deny"
            return {"decision": dec, "reason": rsn}

        # RW-19: Stateless Git-based Anti-Sprawl Governor (new non-test prod code files only)
        if (
            matched_root is not None
            and not os.path.isfile(full)
            and is_code_file(full, art_dir)
            and not is_test_file(full)
            and "/tests/" not in f"/{rel}"
            and has_git
        ):
            raw_sprawl = load_user_policy().get("sprawl")
            sprawl_cfg = raw_sprawl if isinstance(raw_sprawl, dict) else {}
            if sprawl_cfg.get("enabled", True):
                max_new = int(sprawl_cfg.get("max_new_prod_files", 3))
                try:
                    proc = subprocess.run(
                        ["git", "status", "--porcelain", "-uall"],
                        cwd=matched_root,
                        capture_output=True,
                        text=True,
                        timeout=2,
                        check=False,
                    )
                    if proc.returncode == 0:
                        new_prod = 0
                        for ln in proc.stdout.splitlines():
                            if len(ln) < 4:
                                continue
                            code = ln[:2]
                            if "?" in code or "A" in code:
                                p_rel = ln[3:].strip().strip('"').replace("\\", "/")
                                if is_code_file(p_rel) and not is_test_file(p_rel) and "/tests/" not in f"/{p_rel.lower()}":
                                    new_prod += 1
                        if new_prod >= max_new:
                            dec = "deny" if subagent else "force_ask"
                            return {
                                "decision": dec,
                                "reason": f"RW-19 (Sprawl Governor): {new_prod} new production code files already uncommitted (limit {max_new}). Confirm this new file is needed or fold into existing modules.",
                            }
                except (OSError, subprocess.TimeoutExpired):
                    pass
        return {"decision": "allow", "reason": "Workspace edit verified."}

    if name in SHELL_TOOLS:
        cmd = args.get("CommandLine") or args.get("command") or args.get("cmd")
        if not isinstance(cmd, str) or not cmd.strip():
            return {"decision": "deny" if subagent else "ask", "reason": "Cannot verify command text."}
        shell_res = check_shell_command(cmd, cwd, roots, subagent, artifact_dir=art_dir)
        if shell_res.get("decision") == "allow" and state_path(payload) is not None:
            st = load_state(payload)
            if is_mutating_shell_cmd(cmd) and st.repair_strikes >= 3:
                return {
                    "decision": "deny",
                    "reason": "LIFECYCLE (3-Strike Governor): 3 failed verification cycles after edits. Inspect root cause with read_file before mutating via shell.",
                }
            if (
                not subagent
                and not st.oriented
                and is_code_mutating_shell_cmd(cmd)
                and any(_has_git_repo(r) for r in effective_roots(roots))
            ):
                return {
                    "decision": "deny",
                    "reason": "LIFECYCLE (Orient-Before-Edit): Read an entry/target file or run an orientation check before mutating workspace code via shell.",
                }
        return shell_res

    if name == "call_mcp_tool" or name.startswith("mcp_"):
        return check_mcp_call(name, args, subagent)

    return {"decision": "allow", "reason": "Unclassified tool permitted."}


def post(payload: dict[str, Any]) -> dict[str, Any]:
    if state_path(payload) is None:
        return {}
    failed = _is_tool_failed(payload)
    exit_code = _extract_exit_code(payload)
    tool = payload.get("toolCall") or {}
    name = str(tool.get("name") or "")
    args = tool.get("args") if isinstance(tool.get("args"), dict) else {}
    art_dir = _extract_artifact_dir(payload)
    subagent = is_subagent(payload)
    raw_ver = load_user_policy().get("verification")
    ver_cfg = raw_ver if isinstance(raw_ver, dict) else {}
    require_output = bool(ver_cfg.get("require_output_evidence", False))

    roots = effective_roots(payload.get("workspacePaths") or [])
    cwd = _extract_cwd(payload, args)

    def _mutate(st: SentinelState) -> None:
        st.consecutive_tool_errors = (st.consecutive_tool_errors + 1) if failed else 0

        if name in READ_TOOLS and not failed:
            if not subagent:
                st.oriented = True
                if st.repair_strikes >= 3:
                    st.repair_strikes = 2
        elif name in MUTATE_FILE_TOOLS and not failed:
            res = resolve_target(_extract_path_arg(args), payload.get("workspacePaths") or [], artifact_dir=art_dir, cwd=cwd)
            if res is not None:
                rel, full, matched_root = res
                if matched_root is not None:
                    if is_code_file(full, art_dir):
                        st.mutation_epoch += 1
                        st.obligations[full] = file_digest(full)
                        st.verified_files.pop(full, None)
                        if not is_test_file(full):
                            st.edited_since_last_fail = True
                    dom = domain_bucket(rel)
                    if dom and dom not in st.edited_domain_dirs:
                        st.edited_domain_dirs.append(dom)
        elif name in SHELL_TOOLS:
            if not failed and not subagent:
                st.oriented = True
            cmd = str(args.get("CommandLine") or args.get("command") or args.get("cmd") or "")
            cmd_info = classify_verification_command(cmd)
            if cmd_info is not None:
                if cmd_info.pre_mutated:
                    st.mutation_epoch += 1
                    st.shell_dirty = True
                    st.edited_since_last_fail = True
                tracked = set(st.obligations) | set(st.verified_files)
                live_hashes = {p: file_digest(p) for p in tracked}
                digest = compute_state_digest(st.mutation_epoch, live_hashes, st.shell_dirty)
                ev = evaluate_verification_evidence(payload, cmd_info, digest, require_output_evidence=require_output)
                if ev.outcome == "FAIL":
                    st.last_evidence = ev
                    if exit_code != 127 and st.has_open_obligations and st.edited_since_last_fail:
                        st.repair_strikes += 1
                        st.edited_since_last_fail = False
                elif ev.discharged:
                    is_suite_wide = not cmd_info.targets and not cmd_info.filters
                    if is_suite_wide:
                        st.repair_strikes = 0
                        st.edited_since_last_fail = False
                        st.corrupt = False
                        st.shell_dirty = False
                        st.verified_files = live_hashes
                        st.obligations = {}
                        if cmd_info.scope == "crucible_strict":
                            st.edited_domain_dirs = []
                        st.last_evidence = ev
                    else:
                        covered = [p for p in list(st.obligations) if _obligation_covered(p, cmd_info, roots, cwd)]
                        for p in covered:
                            st.obligations.pop(p, None)
                            st.verified_files[p] = live_hashes.get(p, file_digest(p))
                        if covered:
                            if not st.has_open_obligations:
                                st.repair_strikes = 0
                                st.edited_since_last_fail = False
                            st.last_evidence = ev
                        elif st.has_open_obligations:
                            st.last_evidence = EvidenceRecord(
                                state_digest=ev.state_digest,
                                outcome=ev.outcome,
                                channel=ev.channel,
                                runner=ev.runner,
                                scope=ev.scope,
                                discharged=False,
                                detail="unrelated_scope",
                            )
                        else:
                            st.last_evidence = ev
                else:
                    st.last_evidence = ev
            elif not failed and is_code_mutating_shell_cmd(cmd):
                st.mutation_epoch += 1
                st.shell_dirty = True
                st.edited_since_last_fail = True

    update_state(payload, _mutate)
    return {}


def _check_acceptance_and_edited_py(roots: list[str], edited_code_files: list[str]) -> list[str]:
    problems: list[str] = []
    for py_path in edited_code_files:
        if py_path.lower().endswith(".py") and os.path.isfile(py_path):
            try:
                ast.parse(Path(py_path).read_text(encoding="utf-8"), filename=py_path)
            except (SyntaxError, OSError, UnicodeError, ValueError) as exc:
                problems.append(f"Edited Python file failed AST parse: {os.path.basename(py_path)} ({type(exc).__name__})")

    for root_str in roots:
        root = Path(root_str)
        manifest = root / ".agents" / "acceptance.lock.json"
        if not manifest.is_file():
            continue
        try:
            contract = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(contract, dict):
                problems.append(f"Acceptance contract must be a JSON object ({manifest}).")
                continue
        except (OSError, UnicodeError, json.JSONDecodeError):
            problems.append(f"Acceptance contract cannot be parsed ({manifest}).")
            continue

        req_files = contract.get("required_files", [])
        if not isinstance(req_files, list):
            problems.append("Acceptance required_files is not a list.")
            continue
        for rel in req_files[:100]:
            res = resolve_target(rel, [str(root)])
            if res is None or res[2] is None:
                problems.append(f"Acceptance path escapes workspace: {rel}")
                continue
            if not os.path.isfile(res[1]) or os.path.getsize(res[1]) == 0:
                problems.append(f"Missing or empty required file: {rel}")

        py_files = contract.get("python_syntax", [])
        if isinstance(py_files, list):
            for rel in py_files[:100]:
                res = resolve_target(rel, [str(root)])
                if res is None or res[2] is None:
                    problems.append(f"Python syntax path escapes workspace: {rel}")
                    continue
                try:
                    ast.parse(Path(res[1]).read_text(encoding="utf-8"), filename=res[1])
                except (SyntaxError, OSError, UnicodeError, ValueError) as exc:
                    problems.append(f"Python file did not parse: {rel} ({type(exc).__name__})")
    return problems


def stop(payload: dict[str, Any]) -> dict[str, str]:
    if payload.get("terminationReason") not in ("NO_TOOL_CALL", "model_stop", None):
        return {"decision": "allow"}
    if payload.get("fullyIdle") is False:
        return {"decision": "allow"}

    roots = effective_roots(payload.get("workspacePaths") or [])
    st = load_state(payload)

    # Atomically detect and record out-of-band / post-verification disk mutations
    drifted: dict[str, str] = {}
    if st.verified_files and state_path(payload) is not None:
        def _check_and_record_drift(cur_st: SentinelState) -> tuple[SentinelState, dict[str, str]]:
            local_drift: dict[str, str] = {}
            for p, verified_hash in list(cur_st.verified_files.items()):
                cur_hash = file_digest(p)
                if cur_hash != verified_hash:
                    local_drift[p] = cur_hash
                    cur_st.obligations[p] = cur_hash
                    cur_st.verified_files.pop(p, None)
            if local_drift:
                cur_st.mutation_epoch += 1
            return cur_st, local_drift

        res_pair = update_state(payload, _check_and_record_drift)
        if res_pair is not None:
            st, drifted = res_pair

    raw_exec = payload.get("executionNum")
    exec_num = 0 if raw_exec is None else raw_exec
    if payload.get("continuationActive") or not isinstance(exec_num, int) or isinstance(exec_num, bool) or exec_num >= 2:
        if st.has_open_obligations or st.corrupt or st.edited_domain_dirs:
            return {
                "decision": "allow",
                "reason": "LIFECYCLE (Unresolved Obligations): Retry cap reached with unverified edits, pending custody checks, or corrupt state; report honestly as incomplete.",
            }
        return {"decision": "allow"}

    if st.corrupt:
        return {
            "decision": "continue",
            "reason": "LIFECYCLE (State Integrity): sentinel-state.json is corrupt; verify workspace tests before stopping.",
        }

    problems = _check_acceptance_and_edited_py(roots, list(st.obligations.keys()))
    if problems:
        return {"decision": "continue", "reason": "External acceptance check failed: " + "; ".join(problems[:6])}

    if st.has_open_obligations:
        ev_note = ""
        if st.last_evidence is not None and not st.last_evidence.discharged and st.last_evidence.detail:
            tracked = set(st.obligations) | set(st.verified_files)
            cur_digest = compute_state_digest(st.mutation_epoch, {p: file_digest(p) for p in tracked}, st.shell_dirty)
            if st.last_evidence.state_digest == cur_digest:
                ev_note = f" (last verification did not discharge: {st.last_evidence.outcome}/{st.last_evidence.detail})"
        if drifted:
            names = ", ".join(os.path.basename(p) for p in sorted(drifted)[:4])
            return {
                "decision": "continue",
                "reason": f"LIFECYCLE (Verify-Before-Stop): Previously verified files changed on disk ({names}). Re-run tests before finishing.",
            }
        if st.obligations:
            names = ", ".join(os.path.basename(p) for p in sorted(st.obligations)[:4])
            return {
                "decision": "continue",
                "reason": f"LIFECYCLE (Verify-Before-Stop): Workspace code ({names}) was modified without a passing verification command covering it{ev_note}. Run tests before finishing.",
            }
        return {
            "decision": "continue",
            "reason": f"LIFECYCLE (Verify-Before-Stop): Workspace code was modified without a passing verification command afterward{ev_note}. Run tests before finishing.",
        }

    if st.edited_domain_dirs:
        for root_str in roots:
            gate = Path(root_str) / ".agents" / "scripts" / "crucible_gate.py"
            if not gate.is_file():
                continue
            try:
                proc = subprocess.run(
                    [sys.executable, str(gate), "check", "--strict"],
                    cwd=root_str,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return {"decision": "continue", "reason": f"Outcome custody check failed ({type(exc).__name__})."}
            if proc.returncode != 0:
                lines = [ln.strip() for ln in (proc.stdout + "\n" + proc.stderr).splitlines() if ln.strip()]
                detail = lines[-1] if lines else f"exit {proc.returncode}"
                return {"decision": "continue", "reason": f"Outcome custody check failed: {detail}"}
        update_state(payload, lambda s: s.edited_domain_dirs.clear())

    if st.consecutive_tool_errors >= 3:
        return {
            "decision": "continue",
            "reason": "Last three tools failed. Change method or report an honest blocker; do not repeat the same call.",
        }

    return {"decision": "allow"}
