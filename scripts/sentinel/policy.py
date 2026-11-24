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
    "reliability-events.jsonl",
    "hooks.json",
    "hooks.json.portable",
    "sentinel.py",
    "acceptance.lock.json",
    ".env",
    "agents.md",
    "gemini.md",
}

PROTECTED_REL_PREFIXES = (
    ".git",
    ".agents/hooks.json",
    ".agents/acceptance.lock.json",
    "scripts/sentinel",
)

CATASTROPHIC_SHELL_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:Remove-Item\s+.*-(?:Recurse|Force)\s+.*\.git|\.git.*Remove-Item)\b|"
    r"\brm\s+-[a-z]*r[a-z]*f[a-z]*\s+.*\.git\b|"
    r"\bgit\s+clean\s+-[a-z]*f|"
    r"\bformat(?:\.com)?\s+[A-Z]:|"
    r"\bdiskpart\b|"
    r"\bDROP\s+(?:DATABASE|SCHEMA)\b"
    r")"
)

TIER_1_2_SHELL_RE = re.compile(
    r"(?i)(?:"
    r"\brm\s+-(?:[a-z]*r[a-z]*f|[a-z]*f[a-z]*r)\b|"
    r"(?:^|[;&|]\s*)(?:rmdir|Remove-Item|rm|del|unlink)\b|"
    r"\bgit\s+(?:reset\s+--hard|restore\s+\.|checkout\s+--\s+\.|branch\s+-[a-z]*d|push)\b|"
    r"\bgh\s+(?:pr\s+merge|release)\b|"
    r"\b(?:npm\s+publish|twine\s+upload|terraform\s+apply|kubectl\s+(?:apply|delete|create))\b|"
    r"\b(?:pip\s+install|npm\s+(?:install|i|uninstall|remove)|poetry\s+add)\b|"
    r"\bDROP\s+TABLE\b"
    r")"
)

SHELL_MUTATION_RE = re.compile(
    r"(?i)(?:>|>>|\b(?:set-content|add-content|out-file|remove-item|move-item|copy-item)\b|"
    r"\bsed\s+-i|\bwrite_text\b|\bwrite_bytes\b|\bos\.replace\b|\bshutil\.|"
    r"\bopen\s*\([^)]*,\s*['\"][wa+])"
)

GOV_COMMAND_TOKENS = (
    ".agents/hooks.json",
    ".agents/acceptance.lock.json",
    ".gemini/config/hooks.json",
    "sentinel.py",
    "scripts/sentinel",
    "sentinel-state.json",
    "reliability-events.jsonl",
)

MCP_MUTATING_TOKENS = (
    "deploy", "delete", "create", "update", "reset", "stop", "start", "set_", "init", "upload",
)


def is_subagent(payload: dict[str, Any]) -> bool:
    return bool(payload.get("parentConversationId") or os.environ.get("ANTIGRAVITY_SUBAGENT"))


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


def resolve_target(target: Any, workspace_paths: Any) -> tuple[str, str, str | None] | None:
    """Return (norm_rel_or_abs, full_abs, matched_root_or_None)."""
    if not isinstance(target, str) or not target.strip():
        return None
    roots = effective_roots(workspace_paths)
    cand = os.path.expanduser(target.strip())
    if not os.path.isabs(cand):
        if len(roots) != 1:
            return None
        cand = os.path.join(roots[0], cand)
    full = os.path.realpath(os.path.abspath(cand))
    for r in roots:
        try:
            if os.path.commonpath([os.path.normcase(r), os.path.normcase(full)]) == os.path.normcase(r):
                rel = os.path.relpath(full, r).replace("\\", "/").lower()
                return rel, full, r
        except ValueError:
            continue
    norm_full = full.replace("\\", "/").lower()
    if "/.gemini/antigravity/brain/" in norm_full or "/.gemini/antigravity/scratch/" in norm_full:
        return norm_full, full, None
    return None


def is_protected_path(rel_or_abs: str, full_abs: str) -> bool:
    norm = rel_or_abs.replace("\\", "/").lower().lstrip("./")
    base = os.path.basename(full_abs).lower()
    if base in HARD_PROTECTED_BASENAMES:
        return True
    return any(norm == p or norm.startswith(p + "/") or ("/" + p + "/") in ("/" + norm + "/") for p in PROTECTED_REL_PREFIXES)


def is_code_file(full_abs: str) -> bool:
    norm = full_abs.replace("\\", "/").lower()
    if "/.gemini/antigravity/" in norm:
        return False
    return norm.endswith(CODE_EXTS)


def is_test_file(full_abs: str) -> bool:
    norm = full_abs.replace("\\", "/").lower()
    base = os.path.basename(norm)
    return (
        base.startswith("test_")
        or base.endswith(("_test.py", ".test.ts", ".test.js", ".spec.ts", ".spec.js"))
        or "/tests/" in norm
    )


def domain_bucket(rel: str) -> str | None:
    first = rel.replace("\\", "/").split("/", 1)[0].lower()
    return first if first in DOMAIN_DIRS else None


def is_meaningful_verification_command(cmd: Any) -> bool:
    """RW-13: True for real test/gate commands; False for version/status probes."""
    if not isinstance(cmd, str) or not cmd.strip():
        return False
    c = cmd.strip().lower()
    if re.search(r"(?:^|\s)(?:--version|-v|--help|-h)(?:\s|$)", c):
        return False
    if re.match(r"^(?:echo|dir|ls|pwd|whoami|get-childitem|get-content|type|cat|git\s+(?:status|diff|log|branch|show))\b", c):
        return False
    return bool(
        re.search(r"\b(?:pytest|unittest|verify_all\.ps1|crucible_gate\.py\s+(?:check|doctor)|python3?|py|npm\s+(?:test|run)|cargo\s+test|go\s+test)\b", c)
    )


def check_shell_command(cmd: str, cwd: Any, roots: Any, subagent: bool) -> dict[str, str]:
    if isinstance(cwd, str) and cwd.strip() and resolve_target(cwd, roots) is None:
        return {"decision": "deny" if subagent else "ask", "reason": "Command working directory is outside the workspace."}

    if CATASTROPHIC_SHELL_RE.search(cmd):
        return {"decision": "deny", "reason": f"Catastrophic destructive command denied: {cmd}"}

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

    has_env = bool(re.search(r"(?:^|[\s'\"/\\])\.env(?:\b|$)", norm_cmd))
    has_gov = any(tok in norm_cmd for tok in GOV_COMMAND_TOKENS)
    if has_env or (has_gov and SHELL_MUTATION_RE.search(norm_cmd)):
        if subagent:
            return {"decision": "deny", "reason": "RW-04: Subagents cannot access .env or mutate protected governance/hook files."}
        return {"decision": "force_ask", "reason": "RW-04: Command references .env or mutates protected governance/hook files."}

    return {"decision": "allow", "reason": "Command passed safety checks."}


def check_mcp_call(name: str, args: dict[str, Any], subagent: bool) -> dict[str, str]:
    tool_name = str(args.get("ToolName") or name).lower()
    if any(tok in tool_name for tok in MCP_MUTATING_TOKENS):
        if subagent:
            return {"decision": "deny", "reason": f"Tier 2 MCP External Gate prohibited in subagent: `{tool_name}`."}
        return {"decision": "force_ask", "reason": f"Tier 2 MCP External Gate: `{tool_name}` mutates external state; confirm first."}
    return {"decision": "allow", "reason": "Read-only or local spoke MCP tool permitted."}
