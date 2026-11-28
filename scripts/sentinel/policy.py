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

from .state import STATE_PROTECTED_BASENAMES

HARD_PROTECTED_BASENAMES = set(STATE_PROTECTED_BASENAMES) | {
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

_HARMLESS_REDIRECT_RE = re.compile(r"(?:\d*>&\d+|(?:\d*)?>\s*/dev/null(?=$|[\s;|&)]))", re.IGNORECASE)

SHELL_MUTATION_RE = re.compile(
    r"(?i)(?:>|>>|\b(?:set-content|add-content|out-file|remove-item|move-item|copy-item|cp|mv|tee|unlink|remove|truncate|chmod|chown|dd)\b|"
    r"\bln\s|\bsed\s+-i|\bwrite_text\b|\bwrite_bytes\b|\bos\.(?:replace|rename)\b|\bshutil\.|"
    r"\bopen\s*\([^)]*,\s*['\"][wa+]|mode\s*=\s*['\"][wa+])"
)

_INLINE_INTERPRETER_RE = re.compile(
    r"(?i)\b(?:python3?(?:\.\d+)?|py|node|pwsh|powershell|bash|sh)(?:\.exe)?(?:\s+-[A-Za-z0-9-]+)*\s+(?:-[a-z]*c|-e|--eval|-command|<<)"
)

GOV_COMMAND_TOKENS = tuple(
    sorted((HARD_PROTECTED_BASENAMES - {".env"}) | (set(PROTECTED_REL_PREFIXES) - {".git"}) | {".git/", ".gemini/config/hooks.json"})
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


def _scan_shell(raw: str) -> tuple[str, list[tuple[str, str]]]:
    """Single escape-aware finite-state shell lexer.

    Returns (unquoted_uncommented_text, [(segment_text, following_operator), ...]).
    Handles backslash escapes (outside single quotes), single/double quotes,
    per-line `#` comments, and `&&`, `||`, `&`, `;`, `|`, `\\n`, `\\r` operators.
    """
    unquoted_buf: list[str] = []
    segs: list[tuple[str, str]] = []
    seg_buf: list[str] = []
    in_s = False
    in_d = False
    in_comment = False
    i = 0
    n = len(raw)

    while i < n:
        ch = raw[i]
        if ch in ("\n", "\r"):
            if not in_s and not in_d:
                in_comment = False
                segs.append(("".join(seg_buf).strip(), ";"))
                seg_buf = []
                unquoted_buf.append(ch)
            else:
                seg_buf.append(ch)
                unquoted_buf.append(" ")
            i += 1
            continue

        if in_comment:
            i += 1
            continue

        if ch == "\\" and not in_s and i + 1 < n:
            nxt = raw[i + 1]
            seg_buf.append(ch)
            seg_buf.append(nxt)
            unquoted_buf.append("  " if in_d else nxt)
            i += 2
            continue

        if ch == "'" and not in_d:
            in_s = not in_s
            seg_buf.append(ch)
            unquoted_buf.append(ch)
            i += 1
            continue

        if ch == '"' and not in_s:
            in_d = not in_d
            seg_buf.append(ch)
            unquoted_buf.append(ch)
            i += 1
            continue

        if in_s or in_d:
            seg_buf.append(ch)
            unquoted_buf.append(" ")
            i += 1
            continue

        if ch == "#" and (i == 0 or raw[i - 1].isspace() or raw[i - 1] in ";|&()"):
            in_comment = True
            i += 1
            continue

        two = raw[i : i + 2]
        if two in ("&&", "||"):
            segs.append(("".join(seg_buf).strip(), two))
            seg_buf = []
            unquoted_buf.append(two)
            i += 2
            continue

        if ch == "&" and ((i > 0 and raw[i - 1] in (">", "|")) or (i + 1 < n and raw[i + 1] == ">")):
            seg_buf.append(ch)
            unquoted_buf.append(ch)
            i += 1
            continue

        if ch in (";", "|", "&"):
            segs.append(("".join(seg_buf).strip(), ch))
            seg_buf = []
            unquoted_buf.append(ch)
            i += 1
            continue

        seg_buf.append(ch)
        unquoted_buf.append(ch)
        i += 1

    segs.append(("".join(seg_buf).strip(), ""))
    return "".join(unquoted_buf), [(s, op) for s, op in segs if s or op]


def _strip_quoted_strings(raw: str) -> str:
    unquoted, _ = _scan_shell(raw)
    return unquoted


def is_mutating_shell_cmd(cmd: str) -> bool:
    """True if shell command performs file mutation/redirection (ignoring `>` inside quotes and harmless redirects)."""
    unquoted, segs = _scan_shell(cmd)
    cleaned_unquoted = _HARMLESS_REDIRECT_RE.sub("", unquoted.lower().replace("\\", "/"))
    if SHELL_MUTATION_RE.search(cleaned_unquoted):
        return True
    joined_segs = " ; ".join(s for s, _ in segs).lower().replace("\\", "/")
    return bool(
        re.search(
            r"(?i)(?:\bsed\s+-i|\bwrite_text\b|\bwrite_bytes\b|\bos\.(?:replace|rename|unlink|remove)\b|\bshutil\.|"
            r"\bopen\s*\([^)]*,\s*['\"][wa+]|mode\s*=\s*['\"][wa+])",
            joined_segs,
        )
    )


def is_code_mutating_shell_cmd(cmd: str) -> bool:
    """True only if a mutating shell command targets a code extension or uses an inline code interpreter."""
    if not is_mutating_shell_cmd(cmd):
        return False
    low = cmd.lower().replace("\\", "/")
    if _INLINE_INTERPRETER_RE.search(low):
        return True
    return any(re.search(rf"{re.escape(ext)}(?=$|[\s'\"`;&|)])", low) for ext in CODE_EXTS)


def is_crucible_strict_cmd(cmd: str) -> bool:
    """True only when an unquoted shell segment actually invokes `crucible_gate.py check --strict` or `verify_all.ps1`."""
    _, segs = _scan_shell(cmd)
    for seg, _ in segs:
        low = _strip_quoted_strings(seg).lower()
        if re.search(r"(?:^|\s|[/\\])verify_all\.ps1\b", low):
            return True
        if re.search(r"crucible_gate\.py\s+check\b", low) and "--strict" in low:
            return True
    return False


import shlex as _shlex
from dataclasses import dataclass as _dataclass


@_dataclass(frozen=True)
class VerificationCmd:
    runner: str  # pytest | unittest | cargo | go | js | custom_gate
    scope: str  # tests | crucible_strict | gate
    dry_run: bool = False
    targets: tuple[str, ...] = ()
    filters: tuple[str, ...] = ()
    pre_mutated: bool = False


_DRY_RUN_FLAGS_RE = re.compile(
    r"(?i)(?:^|\s)(?:--collect-only|--co|--setup-only|--setup-plan|--fixtures|--markers|--cache-show|--list|-list|--no-run|--listtests|--list-tests)(?=$|\s|=)"
)
_GO_COMPILE_ONLY_RE = re.compile(r"(?:^|\s)-c(?=$|\s)")

_RUNNER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("custom_gate", re.compile(r"^(?:[a-z_]\w*=\S+\s+)*(?:&\s+)?(?:(?:[^\s;&|]*[/\\])?(?:pwsh|powershell|python3?(?:\.\d+)?|py)(?:\.exe)?\s+(?:-\S+\s+)*)?(?:[^\s;&|]*[/\\])?(?:verify_all\.ps1|crucible_gate\.py\s+check)\b", re.IGNORECASE)),
    ("pytest", re.compile(r"^(?:[a-z_]\w*=\S+\s+)*(?:(?:uv\s+run|poetry\s+run)\s+)?(?:(?:[^\s;&|]*[/\\])?pytest\b|(?:[^\s;&|]*[/\\])?(?:python3?(?:\.\d+)?|py)(?:\.exe)?\s+-m\s+pytest\b)", re.IGNORECASE)),
    ("unittest", re.compile(r"^(?:[a-z_]\w*=\S+\s+)*(?:(?:uv\s+run|poetry\s+run)\s+)?(?:(?:[^\s;&|]*[/\\])?(?:python3?(?:\.\d+)?|py)(?:\.exe)?\s+-m\s+unittest\b)", re.IGNORECASE)),
    ("cargo", re.compile(r"^(?:[a-z_]\w*=\S+\s+)*cargo\s+test\b", re.IGNORECASE)),
    ("go", re.compile(r"^(?:[a-z_]\w*=\S+\s+)*go\s+test\b", re.IGNORECASE)),
    ("js", re.compile(r"^(?:[a-z_]\w*=\S+\s+)*(?:npx\s+)?npm\s+(?:test|run\s+test)\b", re.IGNORECASE)),
)


_PYTEST_VALUE_FLAGS = frozenset(
    {
        "-o", "-c", "-n", "-W", "-p", "-r", "--rootdir", "--confcutdir", "--maxfail", "--tb",
        "--junitxml", "--junit-prefix", "--cov", "--cov-report", "--log-cli-level", "--basetemp",
        "--import-mode", "--durations", "--timeout", "--color", "--capture", "--assert",
        "--show-capture", "--verbosity", "--override-ini", "--lfnf", "--last-failed-no-failures",
    }
)
_PYTEST_EXCLUDE_FLAGS = frozenset({"--ignore", "--ignore-glob", "--deselect"})
_UNITTEST_VALUE_FLAGS = frozenset({"-s", "--start-directory", "-t", "--top-level-directory"})
_GO_VALUE_FLAGS = frozenset(
    {
        "-count", "-timeout", "-tags", "-bench", "-benchtime", "-cpu", "-parallel", "-fuzz",
        "-fuzztime", "-coverpkg", "-covermode", "-coverprofile", "-cpuprofile", "-memprofile",
        "-outputdir", "-o", "-exec", "-gcflags", "-ldflags", "-mod", "-vet",
    }
)
_CARGO_VALUE_FLAGS = frozenset(
    {
        "-j", "--jobs", "--features", "-F", "--target", "--target-dir", "--profile",
        "--manifest-path", "--color", "--message-format", "--bin", "--example", "--bench",
    }
)
_CARGO_HARNESS_VALUE_FLAGS = frozenset({"--test-threads", "--color", "--format", "--logfile"})
_JS_VALUE_FLAGS = frozenset({"-c", "--config", "--reporter", "--reporters", "--maxWorkers", "--timeout", "--testTimeout"})
_GENERIC_SUITE_DIRS = frozenset({".", "./", "tests", "test", "scripts/tests"})
_REDIR_TOKEN_RE = re.compile(r"^(?:\d*[<>].*|&>.*)$")


def _extract_runner_scope(runner: str, seg: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Extract explicit file/package targets and filter expressions from a single test command segment."""
    if runner == "custom_gate":
        return (), ()
    try:
        tokens = _shlex.split(seg, posix=(os.name != "nt"))
    except ValueError:
        tokens = seg.split()
    i = 0
    while i < len(tokens) and "=" in tokens[i] and not tokens[i].startswith("-"):
        i += 1
    if i + 1 < len(tokens) and tokens[i].lower() in ("uv", "poetry", "npx") and tokens[i + 1].lower() in ("run", "npm"):
        i += 2
    if i < len(tokens):
        low0 = os.path.basename(tokens[i].replace("\\", "/")).lower()
        if runner == "pytest":
            if low0.startswith("pytest"):
                i += 1
            elif i + 2 < len(tokens) and tokens[i + 1] == "-m" and tokens[i + 2].lower() == "pytest":
                i += 3
        elif runner == "unittest":
            if i + 2 < len(tokens) and tokens[i + 1] == "-m" and tokens[i + 2].lower() == "unittest":
                i += 3
        elif runner in ("cargo", "go"):
            if i + 1 < len(tokens) and tokens[i + 1].lower() == "test":
                i += 2
        elif runner == "js":
            if i + 2 < len(tokens) and tokens[i + 1].lower() == "run" and tokens[i + 2].lower() == "test":
                i += 3
            elif i + 1 < len(tokens) and tokens[i + 1].lower() == "test":
                i += 2

    rest = [t for t in tokens[i:] if not _REDIR_TOKEN_RE.match(t)]
    targets: list[str] = []
    filters: list[str] = []
    idx = 0

    if runner == "pytest":
        while idx < len(rest):
            tok = rest[idx]
            if tok in ("-k", "-m") and idx + 1 < len(rest):
                filters.append(rest[idx + 1])
                idx += 2
                continue
            if tok.startswith(("-k=", "-m=")):
                filters.append(tok[3:])
                idx += 1
                continue
            if tok in _PYTEST_EXCLUDE_FLAGS and idx + 1 < len(rest):
                filters.append("__partial_exclude__")
                idx += 2
                continue
            if any(tok.startswith(f"{ef}=") for ef in _PYTEST_EXCLUDE_FLAGS):
                filters.append("__partial_exclude__")
                idx += 1
                continue
            if tok in _PYTEST_VALUE_FLAGS and idx + 1 < len(rest):
                idx += 2
                continue
            if tok.startswith("-"):
                idx += 1
                continue
            norm = tok.replace("\\", "/").rstrip("/") or "."
            if norm not in _GENERIC_SUITE_DIRS:
                targets.append(tok)
            idx += 1
    elif runner == "unittest":
        is_discover = bool(rest and rest[0] == "discover")
        if is_discover:
            idx = 1
        while idx < len(rest):
            tok = rest[idx]
            if tok == "-k" and idx + 1 < len(rest):
                filters.append(rest[idx + 1])
                idx += 2
                continue
            if tok in ("-p", "--pattern") and idx + 1 < len(rest):
                pat = rest[idx + 1]
                if "*" not in pat and "?" not in pat:
                    targets.append(pat)
                idx += 2
                continue
            if tok in _UNITTEST_VALUE_FLAGS and idx + 1 < len(rest):
                idx += 2
                continue
            if tok.startswith("-"):
                idx += 1
                continue
            if not is_discover:
                targets.append(tok)
            idx += 1
    elif runner == "go":
        while idx < len(rest):
            tok = rest[idx]
            if tok == "-run" and idx + 1 < len(rest):
                filters.append(rest[idx + 1])
                idx += 2
                continue
            if tok.startswith("-run="):
                filters.append(tok[5:])
                idx += 1
                continue
            if tok in _GO_VALUE_FLAGS and idx + 1 < len(rest):
                idx += 2
                continue
            if tok.startswith("-"):
                idx += 1
                continue
            if tok not in ("./...", ".", "..."):
                targets.append(tok)
            idx += 1
    elif runner == "cargo":
        after_dd = False
        while idx < len(rest):
            tok = rest[idx]
            if tok == "--" and not after_dd:
                after_dd = True
                idx += 1
                continue
            if after_dd:
                if tok == "--skip" and idx + 1 < len(rest):
                    filters.append("__partial_exclude__")
                    idx += 2
                    continue
                if tok.startswith("--skip="):
                    filters.append("__partial_exclude__")
                    idx += 1
                    continue
                if tok in _CARGO_HARNESS_VALUE_FLAGS and idx + 1 < len(rest):
                    idx += 2
                    continue
                if tok.startswith("-"):
                    idx += 1
                    continue
                filters.append(tok)
                idx += 1
                continue
            if tok == "--test" and idx + 1 < len(rest):
                targets.append(rest[idx + 1])
                idx += 2
                continue
            if tok in ("-p", "--package") and idx + 1 < len(rest):
                targets.append(rest[idx + 1])
                idx += 2
                continue
            if tok in _CARGO_VALUE_FLAGS and idx + 1 < len(rest):
                idx += 2
                continue
            if tok.startswith("-"):
                idx += 1
                continue
            filters.append(tok)
            idx += 1
    elif runner == "js":
        while idx < len(rest):
            tok = rest[idx]
            if tok == "--":
                idx += 1
                continue
            if tok in ("-t", "--testNamePattern", "--grep", "-g") and idx + 1 < len(rest):
                filters.append(rest[idx + 1])
                idx += 2
                continue
            if tok.startswith(("-t=", "--testNamePattern=", "--grep=")):
                filters.append(tok.split("=", 1)[1])
                idx += 1
                continue
            if tok in _JS_VALUE_FLAGS and idx + 1 < len(rest):
                idx += 2
                continue
            if tok.startswith("-"):
                idx += 1
                continue
            norm = tok.replace("\\", "/").rstrip("/") or "."
            if norm not in _GENERIC_SUITE_DIRS:
                targets.append(tok)
            idx += 1

    return tuple(targets), tuple(filters)


def classify_verification_command(cmd: Any) -> VerificationCmd | None:
    """Classify a verification command into (runner, scope, dry_run, targets, filters, pre_mutated)."""
    if not isinstance(cmd, str) or not cmd.strip():
        return None
    unquoted, segs = _scan_shell(cmd)
    if not segs:
        return None
    # Reject --version / -V / --help / -h only on unquoted tokens
    if re.search(r"(?:^|\s)(?:--version|-V|--help|-h)(?:\s|$)", unquoted):
        return None
    # Reject any `||` or `&` branch (short-circuit/background masking)
    if any(op in ("||", "&") for _, op in segs):
        return None

    matched: list[tuple[int, str, str, bool]] = []
    matched_indices: set[int] = set()
    for idx, (s, _) in enumerate(segs):
        if not s:
            continue
        for runner_name, pat in _RUNNER_PATTERNS:
            if pat.match(s):
                seg_unquoted = _strip_quoted_strings(s)
                is_dry = bool(_DRY_RUN_FLAGS_RE.search(seg_unquoted)) or (
                    runner_name == "go" and bool(_GO_COMPILE_ONLY_RE.search(seg_unquoted))
                )
                matched.append((idx, runner_name, s, is_dry))
                matched_indices.add(idx)
                break
    if not matched:
        return None

    first_idx = matched[0][0]
    last_idx = matched[-1][0]
    # Reject trailing `;` or `|` after any matched verification command
    for idx in range(first_idx, len(segs) - 1):
        if segs[idx][1] in (";", "|"):
            return None
    # Reject any post-verification `&& <code_mutating_cmd>` (mutation after verification cannot discharge!)
    for idx in range(last_idx + 1, len(segs)):
        if is_code_mutating_shell_cmd(segs[idx][0]):
            return None

    pre_mutated = any(
        is_code_mutating_shell_cmd(segs[idx][0])
        for idx in range(0, last_idx)
        if idx not in matched_indices
    )

    live_matches = [m for m in matched if not m[3]]
    if not live_matches:
        _, runner_name, seg_text, _ = matched[-1]
        t, f = _extract_runner_scope(runner_name, seg_text)
        scope = "crucible_strict" if is_crucible_strict_cmd(cmd) else ("gate" if runner_name == "custom_gate" else "tests")
        return VerificationCmd(
            runner=runner_name,
            scope=scope,
            dry_run=True,
            targets=t,
            filters=f,
            pre_mutated=pre_mutated,
        )

    all_targets: list[str] = []
    all_filters: list[str] = []
    any_suite_wide = False
    for _, runner_name, seg_text, _ in live_matches:
        t, f = _extract_runner_scope(runner_name, seg_text)
        if not t and not f:
            any_suite_wide = True
        else:
            all_targets.extend(t)
            all_filters.extend(f)

    primary_runner = live_matches[-1][1]
    scope = "crucible_strict" if is_crucible_strict_cmd(cmd) else ("gate" if primary_runner == "custom_gate" else "tests")
    return VerificationCmd(
        runner=primary_runner,
        scope=scope,
        dry_run=False,
        targets=() if any_suite_wide else tuple(all_targets),
        filters=() if any_suite_wide else tuple(all_filters),
        pre_mutated=pre_mutated,
    )


def is_meaningful_verification_command(cmd: Any) -> bool:
    """RW-13: True for real executing test/gate commands; False for dry-runs, comments, masked exits, or probes."""
    vc = classify_verification_command(cmd)
    return vc is not None and not vc.dry_run


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
    if has_env or (has_gov and (is_mutating_shell_cmd(cmd) or _INLINE_INTERPRETER_RE.search(norm_cmd))):
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
    "verification": {"require_output_evidence": False},
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
