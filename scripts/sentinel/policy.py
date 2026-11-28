"""Tier 0/1/2 reversibility, workspace path containment, and governance boundary rules."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

CODE_EXTS = (
    ".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java", ".cpp", ".c",
    ".cs", ".html", ".css", ".scss", ".sql", ".ps1", ".sh",
)

DOMAIN_DIRS = ("calgary public library", "personal work", "graphs")

HARD_PROTECTED_BASENAMES = {
    "sentinel-state.json",
    "operator-router-seen.json",
    "hook-events.jsonl",
    "reliability-events.jsonl",
    "hooks.json",
    "hooks.json.portable",
    "policy.json",
    "sentinel.py",
    "operator_router.py",
    "test_quality_gate.py",
    "crucible_gate.py",
    "acceptance.lock.json",
    ".env",
    "agents.md",
    "gemini.md",
}

PROTECTED_REL_PREFIXES = (
    ".git",
    ".agents/hooks.json",
    ".agents/acceptance.lock.json",
    ".agents/scripts/crucible_gate.py",
    "scripts/sentinel",
)

_GIT_GLOBAL_FLAGS = (
    r"(?:\s+--(?:git-dir|work-tree|namespace|super-prefix|config-env|exec-path|list-cmds)(?:=|\s+)\S+"
    r"|\s+-[Cc]\s*\S+"
    r"|\s+-[A-Za-z]\S*"
    r"|\s+--\S+)*"
)

CATASTROPHIC_SHELL_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:Remove-Item\s+.*-(?:Recurse|Force)\s+.*\.git|\.git.*Remove-Item)\b|"
    r"\brm\s+-[a-z]*r[a-z]*f[a-z]*\s+.*\.git\b|"
    r"\bgit" + _GIT_GLOBAL_FLAGS + r"\s+clean\s+-[a-z]*f|"
    r"\bformat(?:\.com)?\s+[A-Z]:|"
    r"\bdiskpart\b|"
    r"\bDROP\s+(?:DATABASE|SCHEMA)\b"
    r")"
)

_CMD_PREFIX = r"(?:^|[;&|\r\n]\s*)(?:[A-Za-z_]\w*=\S+\s+)*(?:(?:sudo|env|command)\s+)*(?:(?:/[^\s;&|\r\n]+/)?)?"

TIER_1_2_SHELL_RE = re.compile(
    r"(?i)(?:"
    r"\brm\s+-(?:[a-z]*r[a-z]*f|[a-z]*f[a-z]*r)\b|"
    + _CMD_PREFIX + r"(?:rmdir|Remove-Item|rm|del|unlink)\b|"
    + _CMD_PREFIX + r"git" + _GIT_GLOBAL_FLAGS + r"\s+(?:reset\s+--hard|restore\s+\.|checkout\s+--\s+\.|branch\s+-[a-z]*d|push)\b|"
    + _CMD_PREFIX + r"gh\s+(?:pr\s+merge|release)\b|"
    r"\b(?:npm\s+publish|twine\s+upload|terraform\s+apply|kubectl\s+(?:apply|delete|create))\b|"
    r"\b(?:pip\s+install|npm\s+(?:install|i|uninstall|remove)|poetry\s+add)\b|"
    r"\bDROP\s+TABLE\b"
    r")"
)

_HARMLESS_REDIRECT_RE = re.compile(r"(?:\d*>&\d+|(?:\d*)?>\s*/dev/null)", re.IGNORECASE)

SHELL_MUTATION_RE = re.compile(
    r"(?i)(?:>|>>|\b(?:set-content|add-content|out-file|remove-item|move-item|copy-item|cp|mv|tee|unlink|remove|truncate|chmod|chown|dd)\b|"
    r"\bln\s|\bsed\s+-i|\bwrite_text\b|\bwrite_bytes\b|\bos\.(?:replace|rename)\b|\bshutil\.|"
    r"\bopen\s*\([^)]*,\s*['\"][wa+]|mode\s*=\s*['\"][wa+])"
)

_INLINE_INTERPRETER_RE = re.compile(
    r"(?i)\b(?:python3?(?:\.\d+)?|py|node|pwsh|powershell|bash|sh)(?:\.exe)?(?:\s+-[A-Za-z0-9-]+)*\s+(?:-[a-z]*c|-e|--eval|-command|<<)"
)

GOV_COMMAND_TOKENS = (
    ".git",
    ".agents/hooks.json",
    ".agents/acceptance.lock.json",
    ".gemini/config/hooks.json",
    "hooks.json.portable",
    "hooks.json",
    "policy.json",
    "sentinel.py",
    "operator_router.py",
    "test_quality_gate.py",
    "crucible_gate.py",
    "scripts/sentinel",
    "sentinel-state.json",
    "operator-router-seen.json",
    "hook-events.jsonl",
    "reliability-events.jsonl",
    "agents.md",
    "gemini.md",
)

MCP_MUTATING_RE = re.compile(
    r"(?:^|[_\-/.])(?:deploy|delete|create|update|reset|stop|start|set|init|upload|"
    r"write|edit|patch|merge|push|send|move|rename|share|add|remove|comment|mutate|trash)(?:$|[_\-/.])",
    re.IGNORECASE,
)

BRAIN_PATH_RE = re.compile(r"/\.gemini/(?:antigravity|jetski)/(?:brain|scratch)/", re.IGNORECASE)
ENV_FILE_RE = re.compile(r"(?:^|[\s'\"/\\])\.env(?:\.(?:local|production|prod|development|dev|staging))?(?=$|[\s'\"/\\])", re.IGNORECASE)


def is_subagent(payload: dict[str, Any]) -> bool:
    return bool(payload.get("parentConversationId") or os.environ.get("ANTIGRAVITY_SUBAGENT"))


def is_brain_or_artifact_path(full_abs: str, artifact_dir: str | None = None) -> bool:
    norm_full = full_abs.replace("\\", "/").lower()
    if BRAIN_PATH_RE.search(norm_full):
        return True
    if isinstance(artifact_dir, str) and artifact_dir.strip():
        art_real = os.path.realpath(os.path.abspath(os.path.expanduser(artifact_dir.strip())))
        try:
            if os.path.commonpath([os.path.normcase(art_real), os.path.normcase(full_abs)]) == os.path.normcase(art_real):
                return True
        except ValueError:
            pass
    return False


def effective_roots(workspace_paths: Any) -> list[str]:
    roots: list[str] = []
    if isinstance(workspace_paths, list):
        for p in workspace_paths:
            if isinstance(p, str) and p.strip():
                roots.append(os.path.realpath(os.path.abspath(p)))
    if not roots:
        cwd = os.getcwd()
        if cwd:
            roots.append(os.path.realpath(os.path.abspath(cwd)))
    return roots


def resolve_target(
    target: Any,
    workspace_paths: Any,
    *,
    artifact_dir: str | None = None,
    cwd: str | None = None,
) -> tuple[str, str, str | None] | None:
    """Return (norm_rel_or_abs, full_abs, matched_root_or_None)."""
    if not isinstance(target, str) or not target.strip():
        return None
    roots = effective_roots(workspace_paths)
    cand = os.path.expanduser(target.strip())
    if not os.path.isabs(cand):
        if isinstance(cwd, str) and cwd.strip():
            cand = os.path.join(os.path.expanduser(cwd.strip()), cand)
        elif len(roots) == 1:
            cand = os.path.join(roots[0], cand)
        else:
            return None
    full = os.path.realpath(os.path.abspath(cand))
    for r in roots:
        try:
            if os.path.commonpath([os.path.normcase(r), os.path.normcase(full)]) == os.path.normcase(r):
                rel = os.path.relpath(full, r).replace("\\", "/").lower()
                return rel, full, r
        except ValueError:
            continue
    if is_brain_or_artifact_path(full, artifact_dir):
        return full.replace("\\", "/").lower(), full, None
    return None


def is_protected_path(rel_or_abs: str, full_abs: str) -> bool:
    norm = rel_or_abs.replace("\\", "/").lower().lstrip("./")
    base = os.path.basename(full_abs).lower()
    if base in HARD_PROTECTED_BASENAMES:
        return True
    return any(norm == p or norm.startswith(p + "/") or ("/" + p + "/") in ("/" + norm + "/") for p in PROTECTED_REL_PREFIXES)


def is_code_file(full_abs: str, artifact_dir: str | None = None) -> bool:
    if is_brain_or_artifact_path(full_abs, artifact_dir):
        return False
    norm = full_abs.replace("\\", "/").lower()
    return norm.endswith(CODE_EXTS)


def is_test_file(full_abs: str) -> bool:
    base = os.path.basename(full_abs.replace("\\", "/")).lower()
    return base.startswith("test_") or base.endswith(("_test.py", ".test.ts", ".test.js", ".spec.ts", ".spec.js"))


def domain_bucket(rel: str) -> str | None:
    first = rel.replace("\\", "/").split("/", 1)[0].lower()
    return first if first in DOMAIN_DIRS else None


def _strip_shell_comments(raw: str) -> str:
    out: list[str] = []
    in_s = False
    in_d = False
    in_comment = False
    for i, ch in enumerate(raw):
        if ch in ("\n", "\r"):
            in_comment = False
            out.append(ch)
            continue
        if in_comment:
            continue
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "#" and not in_s and not in_d and (i == 0 or raw[i - 1].isspace()):
            in_comment = True
            continue
        out.append(ch)
    return "".join(out)


def _split_shell_segments(raw: str) -> list[tuple[str, str]]:
    """Split shell command into (segment_text, following_operator) tuples outside quotes."""
    segs: list[tuple[str, str]] = []
    buf: list[str] = []
    in_s = False
    in_d = False
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == "'" and not in_d:
            in_s = not in_s
            buf.append(ch)
            i += 1
        elif ch == '"' and not in_s:
            in_d = not in_d
            buf.append(ch)
            i += 1
        elif not in_s and not in_d:
            two = raw[i : i + 2]
            if two in ("&&", "||"):
                segs.append(("".join(buf).strip(), two))
                buf = []
                i += 2
            elif ch in (";", "|", "\n", "\r"):
                segs.append(("".join(buf).strip(), ";" if ch in ("\n", "\r") else ch))
                buf = []
                i += 1
            else:
                buf.append(ch)
                i += 1
        else:
            buf.append(ch)
            i += 1
    segs.append(("".join(buf).strip(), ""))
    return [(s, op) for s, op in segs if s or op]


_VERIFY_SEGMENT_RE = re.compile(
    r"^(?:[a-z_]\w*=\S+\s+)*"
    r"(?:(?:uv\s+run|poetry\s+run|npx|&\s*)\s+)?"
    r"(?:"
    r"(?:[^\s;&|]*[/\\])?(?:pytest|verify_all\.ps1)\b|"
    r"(?:[^\s;&|]*[/\\])?(?:python3?(?:\.\d+)?|py)(?:\.exe)?\s+(?:-m\s+(?:pytest|unittest)\b|(?:[^\s;&|]*[/\\])?(?:crucible_gate\.py\s+(?:check|doctor)|test_quality_gate\.py)\b)|"
    r"(?:[^\s;&|]*[/\\])?(?:pwsh|powershell)(?:\.exe)?\s+(?:-\S+\s+)*(?:[^\s;&|]*[/\\])?verify_all\.ps1\b|"
    r"(?:npm\s+(?:test|run\s+test)|cargo\s+test|go\s+test)\b"
    r")",
    re.IGNORECASE,
)


def _strip_quoted_strings(raw: str) -> str:
    """Replace single/double-quoted string interiors with spaces so `>` inside Python/echo strings is not treated as shell redirection."""
    out: list[str] = []
    in_s = False
    in_d = False
    for ch in raw:
        if ch == "'" and not in_d:
            in_s = not in_s
            out.append(ch)
        elif ch == '"' and not in_s:
            in_d = not in_d
            out.append(ch)
        elif in_s or in_d:
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def is_mutating_shell_cmd(cmd: str) -> bool:
    """True if shell command performs file mutation/redirection (ignoring `>` inside quotes and harmless redirects)."""
    uncommented = _strip_shell_comments(cmd)
    cleaned = _HARMLESS_REDIRECT_RE.sub("", uncommented.lower().replace("\\", "/"))
    if SHELL_MUTATION_RE.search(_strip_quoted_strings(cleaned)):
        return True
    # Also check unstripped text for in-process file mutators (`sed -i`, `write_text`, `os.replace`, `open(..., 'w')`)
    return bool(
        re.search(
            r"(?i)(?:\bsed\s+-i|\bwrite_text\b|\bwrite_bytes\b|\bos\.(?:replace|rename|unlink|remove)\b|\bshutil\.|"
            r"\bopen\s*\([^)]*,\s*['\"][wa+]|mode\s*=\s*['\"][wa+])",
            cleaned,
        )
    )


def is_crucible_strict_cmd(cmd: str) -> bool:
    """True only when an unquoted shell segment actually invokes `crucible_gate.py check --strict` or `verify_all.ps1`."""
    raw = _strip_shell_comments(cmd).strip()
    if not raw:
        return False
    for seg, _ in _split_shell_segments(raw):
        low = _strip_quoted_strings(seg).lower()
        if re.search(r"(?:^|\s|[/\\])verify_all\.ps1\b", low):
            return True
        if re.search(r"crucible_gate\.py\s+check\b", low) and "--strict" in low:
            return True
    return False


def is_meaningful_verification_command(cmd: Any) -> bool:
    """RW-13: True for real test/gate commands; False for comments, masked exits, or version/help probes."""
    if not isinstance(cmd, str) or not cmd.strip():
        return False
    raw = _strip_shell_comments(cmd).strip()
    if not raw:
        return False
    # Reject --version / -V / --help / -h case-sensitively so verbose -v (unittest -v, pytest -v) passes
    if re.search(r"(?:^|\s)(?:--version|-V|--help|-h)(?:\s|$)", raw):
        return False
    segs = _split_shell_segments(raw)
    # Reject any `||` branch (short-circuit bypass `true || pytest` or failure masking `pytest || echo ok`)
    if any(op == "||" for _, op in segs):
        return False
    matched_idx = -1
    for idx, (s, _) in enumerate(segs):
        if s and _VERIFY_SEGMENT_RE.match(s):
            matched_idx = idx
    if matched_idx < 0:
        return False
    # Reject trailing `;` or `|` after the verification command (masks non-zero exit code via `pytest; true` or `pytest | true`)
    for idx in range(matched_idx, len(segs) - 1):
        if segs[idx][1] in (";", "|"):
            return False
    return True


def check_shell_command(
    cmd: str,
    cwd: Any,
    roots: Any,
    subagent: bool,
    *,
    artifact_dir: str | None = None,
) -> dict[str, str]:
    if isinstance(cwd, str) and cwd.strip() and resolve_target(cwd, roots, artifact_dir=artifact_dir) is None:
        return {"decision": "deny" if subagent else "ask", "reason": "Command working directory is outside the workspace."}

    if CATASTROPHIC_SHELL_RE.search(cmd):
        return {"decision": "deny", "reason": f"Catastrophic destructive command denied: {cmd}"}

    from .ast_gate import detect_secret_leak

    secret_hit = detect_secret_leak(cmd)
    if secret_hit is not None:
        return {
            "decision": "deny",
            "reason": f"RW-18 (Secret Leak Blocked): Detected {secret_hit} in shell command. Store secrets in env vars, never inline.",
        }

    norm_cmd = cmd.lower().replace("\\", "/")
    is_wsl = bool(re.match(r"^\s*wsl(?:\.exe)?\b", norm_cmd))
    if os.name == "nt" and not is_wsl and re.search(r"(?:^|[|;&]\s*)grep\s+", cmd):
        return {
            "decision": "deny",
            "reason": "FM-H06 (Windows Shell Trap): Raw `grep` is not in Windows PATH. Use `Select-String` or native tools.",
        }

    if TIER_1_2_SHELL_RE.search(cmd):
        if subagent:
            return {"decision": "deny", "reason": f"Tier-1/Tier-2 destructive or external command prohibited in subagent: {cmd}"}
        return {"decision": "force_ask", "reason": "Tier-1/Tier-2 destructive or external command; requires explicit human approval."}

    has_env = bool(ENV_FILE_RE.search(norm_cmd))
    has_gov = any(tok in norm_cmd for tok in GOV_COMMAND_TOKENS)
    cleaned_for_mut = _HARMLESS_REDIRECT_RE.sub("", norm_cmd)
    if has_env or (has_gov and (SHELL_MUTATION_RE.search(cleaned_for_mut) or _INLINE_INTERPRETER_RE.search(cleaned_for_mut))):
        if subagent:
            return {"decision": "deny", "reason": "RW-04: Subagents cannot access .env or mutate protected governance/hook files."}
        return {"decision": "force_ask", "reason": "RW-04: Command references .env or mutates protected governance/hook files."}

    return {"decision": "allow", "reason": "Command passed safety checks."}


def check_mcp_call(name: str, args: dict[str, Any], subagent: bool) -> dict[str, str]:
    raw_tool = args.get("ToolName") or args.get("tool_name") or args.get("toolName") or args.get("name") or name
    tool_name = str(raw_tool).lower()
    if MCP_MUTATING_RE.search(tool_name):
        if subagent:
            return {"decision": "deny", "reason": f"Tier 2 MCP External Gate prohibited in subagent: `{tool_name}`."}
        return {"decision": "force_ask", "reason": f"Tier 2 MCP External Gate: `{tool_name}` mutates external state; confirm first."}
    return {"decision": "allow", "reason": "Read-only or local spoke MCP tool permitted."}


_DEFAULT_POLICY: dict[str, Any] = {
    "version": "1.0",
    "sprawl": {"enabled": True, "max_new_prod_files": 3},
    "deliverable_hygiene": [],
}


def load_user_policy(policy_path: Path | None = None) -> dict[str, Any]:
    """Load adaptable policy.json from config root (or env override) with safe defaults."""
    import json
    import sys

    override = os.environ.get("ANTIGRAVITY_POLICY_PATH", "").strip()
    target = policy_path or (Path(override).expanduser() if override else Path(__file__).resolve().parents[2] / "policy.json")
    if not target.is_file():
        return dict(_DEFAULT_POLICY)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else dict(_DEFAULT_POLICY)
    except (OSError, ValueError) as exc:
        print(f"sentinel policy load error ({target.name}): {type(exc).__name__}", file=sys.stderr)
        return dict(_DEFAULT_POLICY)


def check_deliverable_hygiene(abs_path: str, text: str, *, policy: dict[str, Any] | None = None) -> str | None:
    """Return RW-20 hygiene violation message if text violates an active policy.json deliverable profile."""
    pol = policy if policy is not None else load_user_policy()
    profiles = pol.get("deliverable_hygiene")
    if not isinstance(profiles, list):
        return None
    norm_path = abs_path.replace("\\", "/")
    base = os.path.basename(norm_path)
    ext = os.path.splitext(base)[1].lower()
    haystack = f"{norm_path}\n{text}"

    for prof in profiles:
        if not isinstance(prof, dict):
            continue
        exts = [str(e).lower() for e in (prof.get("file_extensions") or [])]
        if exts and ext not in exts:
            continue
        excludes = {str(b).lower() for b in (prof.get("exclude_basenames") or [])}
        if base.lower() in excludes:
            continue
        ctx_pat = str(prof.get("context_pattern") or "")
        if ctx_pat and not re.search(ctx_pat, haystack):
            continue
        for rule in prof.get("rules") or []:
            if not isinstance(rule, dict):
                continue
            pat = str(rule.get("pattern") or "")
            if pat and re.search(pat, text):
                msg = str(rule.get("message") or "Deliverable hygiene violation.")
                prof_name = str(prof.get("name") or "deliverable")
                return f"RW-20 (Deliverable Hygiene [{prof_name}]): {msg}"
    return None
