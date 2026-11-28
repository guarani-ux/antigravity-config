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
    SHELL_MUTATION_RE,
    _HARMLESS_REDIRECT_RE,
    _strip_shell_comments,
    check_mcp_call,
    check_shell_command,
    domain_bucket,
    effective_roots,
    is_code_file,
    is_meaningful_verification_command,
    is_protected_path,
    is_subagent,
    is_test_file,
    resolve_target,
)
from .state import STATE_FILENAME, load_state, save_state, state_path

READ_TOOLS = ("read_file", "view_file")
WRITE_TOOLS = ("write_file", "write_to_file")
EDIT_TOOLS = ("edit_file", "replace_file_content", "multi_replace_file_content")
MUTATE_FILE_TOOLS = WRITE_TOOLS + EDIT_TOOLS
SHELL_TOOLS = ("run_command", "command")
VACUOUS_TEST_OUTPUT_RE = re.compile(
    r"(?i)(?:\bran\s+0\s+tests\b|\bcollected\s+0\s+items\b|\bno\s+tests\s+ran\b|\b0\s+passed\b|\b[1-9]\d*\s+skipped\b)"
)
FAILED_TEST_OUTPUT_RE = re.compile(
    r"(?:\b[1-9]\d*\s+failed\b|\bFAILED\s*\(|^ERROR:\s+\S+\s+\()",
    re.MULTILINE,
)
NONZERO_TEST_OUTPUT_RE = re.compile(
    r"(?i)(?:\b[1-9]\d*\s+(?:passed|passing)\b|\bran\s+[1-9]\d*\s+tests?\b)"
)
UNITTEST_SKIPPED_RE = re.compile(
    r"(?is)\bran\s+([1-9]\d*)\s+tests?\b.*\bok\s*\(\s*skipped\s*=\s*(\d+)\s*\)"
)


def _extract_path_arg(args: dict[str, Any]) -> Any:
    for k in ("Path", "TargetFile", "file_path", "path", "AbsolutePath"):
        if args.get(k) is not None:
            return args.get(k)
    return None


def _extract_artifact_dir(payload: dict[str, Any]) -> str | None:
    art = payload.get("artifactDirectoryPath")
    return art.strip() if isinstance(art, str) and art.strip() else None


def _is_tool_failed(payload: dict[str, Any]) -> bool:
    if payload.get("error"):
        return True
    for container in (payload, payload.get("toolResult"), payload.get("result")):
        if not isinstance(container, dict):
            continue
        for key in ("exitCode", "exit_code", "returncode"):
            val = container.get(key)
            if isinstance(val, int) and not isinstance(val, bool) and val != 0:
                return True
    return False


def _is_vacuous_test_output(payload: dict[str, Any]) -> bool:
    """Return True if captured command output explicitly shows failures, 0 tests executed, or all tests skipped."""
    chunks: list[str] = []
    for container in (payload, payload.get("toolResult"), payload.get("result")):
        if not isinstance(container, dict):
            continue
        for key in ("stdout", "stderr", "output", "text"):
            val = container.get(key)
            if isinstance(val, str) and val.strip():
                chunks.append(val)
    if not chunks:
        return False
    combined = "\n".join(chunks)
    if FAILED_TEST_OUTPUT_RE.search(combined):
        return True
    m_unit = UNITTEST_SKIPPED_RE.search(combined)
    if m_unit and int(m_unit.group(2)) >= int(m_unit.group(1)):
        return True
    if NONZERO_TEST_OUTPUT_RE.search(combined):
        return False
    return bool(VACUOUS_TEST_OUTPUT_RE.search(combined))


def _is_mutating_shell_cmd(cmd: str) -> bool:
    cleaned = _HARMLESS_REDIRECT_RE.sub("", cmd.lower().replace("\\", "/"))
    return bool(SHELL_MUTATION_RE.search(cleaned))


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

    if name in MUTATE_FILE_TOOLS:
        raw_target = _extract_path_arg(args)
        if isinstance(raw_target, str) and os.path.basename(raw_target.strip()).lower() in (
            STATE_FILENAME,
            "operator-router-seen.json",
            "hook-events.jsonl",
            "reliability-events.jsonl",
        ):
            return {"decision": "deny", "reason": "RW-06: Direct modification of hook state is prohibited."}

        resolved = resolve_target(raw_target, roots, artifact_dir=art_dir)
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

        if state_path(payload) is not None and matched_root is not None:
            st = load_state(payload)
            if st.repair_strikes >= 3:
                return {
                    "decision": "deny",
                    "reason": "LIFECYCLE (3-Strike Governor): 3 failed verification cycles after edits. Inspect root cause with read_file before patching again.",
                }
            if (
                not subagent
                and (Path(matched_root) / ".git").exists()
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
            and "/tests/" not in rel
            and (Path(matched_root) / ".git").exists()
        ):
            from .policy import load_user_policy

            sprawl_cfg = load_user_policy().get("sprawl") or {}
            if sprawl_cfg.get("enabled", True):
                max_new = int(sprawl_cfg.get("max_new_prod_files", 3))
                try:
                    proc = subprocess.run(
                        ["git", "status", "--porcelain"],
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
        shell_res = check_shell_command(cmd, args.get("Cwd") or args.get("cwd"), roots, subagent, artifact_dir=art_dir)
        if shell_res.get("decision") == "allow" and _is_mutating_shell_cmd(cmd) and state_path(payload) is not None:
            st = load_state(payload)
            if st.repair_strikes >= 3:
                return {
                    "decision": "deny",
                    "reason": "LIFECYCLE (3-Strike Governor): 3 failed verification cycles after edits. Inspect root cause with read_file before mutating via shell.",
                }
        return shell_res

    if name == "call_mcp_tool" or name.startswith("mcp_"):
        return check_mcp_call(name, args, subagent)

    return {"decision": "allow", "reason": "Unclassified tool permitted."}


def post(payload: dict[str, Any]) -> dict[str, Any]:
    if state_path(payload) is None:
        return {}
    st = load_state(payload)
    failed = _is_tool_failed(payload)
    st.consecutive_tool_errors = (st.consecutive_tool_errors + 1) if failed else 0

    tool = payload.get("toolCall") or {}
    name = str(tool.get("name") or "")
    args = tool.get("args") if isinstance(tool.get("args"), dict) else {}
    art_dir = _extract_artifact_dir(payload)

    if name in READ_TOOLS and not failed:
        st.oriented = True
        if st.repair_strikes >= 3:
            st.repair_strikes = 2
    elif name in MUTATE_FILE_TOOLS and not failed:
        res = resolve_target(_extract_path_arg(args), payload.get("workspacePaths") or [], artifact_dir=art_dir)
        if res is not None:
            rel, full, matched_root = res
            if matched_root is not None:
                if is_code_file(full, art_dir):
                    if full not in st.edited_code_files:
                        st.edited_code_files.append(full)
                    st.unverified_code_edits = True
                    if not is_test_file(full):
                        st.edited_since_last_fail = True
                dom = domain_bucket(rel)
                if dom and dom not in st.edited_domain_dirs:
                    st.edited_domain_dirs.append(dom)
    elif name in SHELL_TOOLS:
        if not failed:
            st.oriented = True
        cmd = str(args.get("CommandLine") or args.get("command") or args.get("cmd") or "")
        if is_meaningful_verification_command(cmd):
            if failed:
                if st.unverified_code_edits and st.edited_since_last_fail:
                    st.repair_strikes += 1
                    st.edited_since_last_fail = False
            elif not _is_vacuous_test_output(payload):
                st.repair_strikes = 0
                st.unverified_code_edits = False
                st.edited_since_last_fail = False
                st.edited_code_files = []
                uncommented = _strip_shell_comments(cmd).lower()
                if "crucible_gate.py" in uncommented or "verify_all.ps1" in uncommented:
                    st.edited_domain_dirs = []
        elif not failed and _is_mutating_shell_cmd(cmd):
            st.unverified_code_edits = True
            st.edited_since_last_fail = True

    save_state(payload, st)
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
    exec_num = payload.get("executionNum", 0)
    if payload.get("continuationActive") or not isinstance(exec_num, int) or exec_num >= 2:
        return {"decision": "allow"}

    roots = effective_roots(payload.get("workspacePaths") or [])
    st = load_state(payload)
    problems = _check_acceptance_and_edited_py(roots, st.edited_code_files)
    if problems:
        return {"decision": "continue", "reason": "External acceptance check failed: " + "; ".join(problems[:6])}

    if st.unverified_code_edits:
        return {
            "decision": "continue",
            "reason": "LIFECYCLE (Verify-Before-Stop): Workspace code was modified without a passing verification command afterward. Run tests before finishing.",
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
            except subprocess.TimeoutExpired:
                return {"decision": "continue", "reason": "Outcome custody check timed out (>5s)."}
            if proc.returncode != 0:
                lines = [ln.strip() for ln in (proc.stdout + "\n" + proc.stderr).splitlines() if ln.strip()]
                detail = lines[-1] if lines else f"exit {proc.returncode}"
                return {"decision": "continue", "reason": f"Outcome custody check failed: {detail}"}
        st.edited_domain_dirs = []
        save_state(payload, st)

    if st.consecutive_tool_errors >= 3:
        return {
            "decision": "continue",
            "reason": "Last three tools failed. Change method or report an honest blocker; do not repeat the same call.",
        }

    return {"decision": "allow"}
