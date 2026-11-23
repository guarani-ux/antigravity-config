#!/usr/bin/env python3
"""Antigravity 2.0 Windows-Grounded Reliability Hook (Staged v4 — Red-Team Hardened).

Combines:
- All 5 Linux->Windows Antigravity 2.0 host schema fixes (`hook_v2.py`)
- All 8 empirical guards from mining 501 historical conversations (`hook_v3.py`)
- All 12 Adversarial Red-Team / Anti-Reward-Hacking defenses (`hook_v4.py`) based on
  ImpossibleBench, EvilGenie, METR coding-agent specification gaming research, and
  PowerShell/Antigravity 2.0 tool-bypass analysis:

Red-Team / Anti-Reward-Hacking Defenses Added in v4:
- RW-01 (Test Suite Tampering / EvilGenie): Blocks adding `@unittest.skip`,
  `@pytest.mark.skip`, `@pytest.mark.xfail`, `self.skipTest()`, `sys.exit(0)`, or
  reducing assertion counts / inserting tautological `assertTrue(True)` in test files.
- RW-02 (`__eq__` Always-True Overload / ImpossibleBench): AST detector blocks
  `def __eq__(self, other): return True` reward hacks in production classes.
- RW-03 (PowerShell / Shell File-Write Bypass): Blocks `Set-Content`, `Add-Content`,
  `Out-File`, `[System.IO.File]::Write*`, `Copy-Item`, `Move-Item`, `sed -i`,
  `node -e "...writeFileSync..."`, and shell redirection (`>` / `>>`) to code/config files.
- RW-04 (Expanded Protected Governance List in Shell & Writes): Protects `GEMINI.md`,
  `AGENTS.md`, `.env`, `.git/hooks`, `.git/config`, `reliability-events.jsonl`, and
  `db-baseline.json` across both file tools and shell commands.
- RW-05 (Overlapping Line-Range Read-Thrashing Detector): Defeats 1-line offset
  shifting (`StartLine: 1..11, 2..12, 3..13`) by detecting >= 3 overlapping reads on
  the same file without an intervening edit, while still allowing sequential non-overlapping
  pagination of large files.
- RW-06 (Hook State Self-Protection): Hard-denies any attempt to write, overwrite, or
  truncate `reliability-events.jsonl` or `db-baseline.json` inside `brain/<id>/`.
- RW-07 (`multi_replace_file_content` Chunk Inspection): Unpacks `ReplacementChunks`
  so multi-chunk edits cannot bypass control-byte, placeholder, target-existence,
  deletion-ratio, or in-memory Python AST checks.
- RW-08 (Broad Exception Swallowing & `contextlib.suppress`): AST check catches
  `except (Exception|BaseException|<bare>): return None/[]/{}/False` and
  `contextlib.suppress(Exception)` in addition to `except: pass`.
- RW-09 (Scratch Script Relative-Path Workspace Mutation Bypass): Blocks `scratch/*.py`
  scripts that call file-writing APIs (`write_text`, `open(..., 'w')`, `shutil.*`)
  unless every write path is explicitly scoped to `__file__` or `scratch/`.
- RW-10 (Unverified Code Edit on `Stop`): If workspace source code was edited during
  the session, `Stop` requires at least one verification `run_command` to have been
  executed *after* the last workspace code edit before allowing completion.
- RW-11 (Production Mock Injection): Blocks importing `unittest.mock` (`Mock`,
  `MagicMock`, `patch`) inside non-test production Python modules.
"""
import ast
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

WRITE_TOOLS = {
    "write_to_file",
    "replace_file_content",
    "multi_replace_file_content",
    "write_file",
    "edit_file",
}

READ_TOOLS = {
    "read_file",
    "view_file",
}

WORKSPACE_CODE_EXTS = (
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".cpp",
    ".c",
    ".cs",
    ".html",
    ".css",
    ".scss",
    ".vue",
    ".svelte",
    ".sql",
    ".ps1",
    ".sh",
)

SKIP_WALK_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "external_repos",
    "artifacts",
    "logs",
    "output",
}

MAX_WALK_FILES = 10000

ONE_OFF_ROOT_SCRIPT_RE = re.compile(
    r"(?i)^(?:tmp|temp|quick|fix|patch|debug|probe|diag|run_diag|verify_tmp|update_|rewrite_|scratch_).*\.py$"
)

PROTECTED_PREFIXES = (
    ".git",
    ".agents/reliability",
    "governance/hooks",
    ".gemini/config",
)

PROTECTED_FILES = (
    ".agents/hooks.json",
    ".agents/acceptance.lock.json",
    "pre_tool_guard.js",
    "hooks.json",
    "hook_v4.py",
    "code_graph.py",
    "agents.md",
    "gemini.md",
    ".env",
    "reliability-events.jsonl",
    "db-baseline.json",
    "test-baseline.json",
    "root-files-baseline.json",
    "workspace-symbols.json",
)

FORBIDDEN_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

CATASTROPHIC_DENY_SHELL = (
    r"(?i)\b(?:Remove-Item\s+.*-(?:Recurse|Force)\s+.*\.git|\.git.*Remove-Item)\b",
    r"(?i)\brm\s+-[a-z]*r[a-z]*f[a-z]*\s+.*\.git\b",
    r"(?i)\bgit\s+clean\s+-[a-z]*f",
    r"(?i)\bformat(?:\.com)?\s+[A-Z]:",
    r"(?i)\bdiskpart\b",
    r"(?i)\bDROP\s+(?:DATABASE|SCHEMA)\b",
)

HIGH_RISK_SHELL = (
    r"(?i)\brm\s+-[a-z]*r[a-z]*f\b",
    r"(?i)\brm\s+-[a-z]*f[a-z]*r\b",
    r"(?i)(?:^|[;&|]\s*)(?:rmdir|Remove-Item|rm|del|unlink)\b",
    r"(?i)\bgit\s+(?:reset\s+--hard|restore\s+\.|checkout\s+--\s+\.|branch\s+-[a-z]*d)\b",
    r"(?i)\bgit\s+push\b",
    r"(?i)\bgh\s+(?:pr\s+merge|release)\b",
    r"(?i)\b(?:npm\s+publish|twine\s+upload|terraform\s+apply|kubectl\s+(?:apply|delete|create))\b",
    r"(?i)\b(?:pip\s+install|npm\s+(?:install|i|uninstall|remove)|poetry\s+add)\b",
    r"(?i)\bDROP\s+TABLE\b",
)

# RW-03: Shell file-writing cmdlets, .NET file writers, and inline redirection to source/config files
SHELL_FILE_WRITE_BYPASS_PATTERNS = (
    r"(?i)\b(?:Set-Content|Add-Content|Out-File|Copy-Item|Move-Item)\b",
    r"(?i)\[System\.IO\.File\]::(?:WriteAllText|WriteAllLines|WriteAllBytes|AppendAllText|Copy|Move|Delete)",
    r"(?i)New-Object\s+System\.IO\.StreamWriter",
    r"(?i)\bnode(?:\.exe)?\s+(?:-e|--eval)\s+.*(?:writeFileSync|writeFile|appendFileSync|unlinkSync|rmSync)",
    r"(?i)\b(?:sed|perl)\s+-[a-z]*i\b",
    r"(?i)(?:^|[^0-9])>>?\s*['\"]?[^\s|;&'\"]+\.(?:py|js|ts|tsx|json|md|yaml|yml|toml|sql|sh|ps1|db|sqlite)\b",
)


def out(data):
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")


def effective_roots(workspace_paths):
    roots = []
    if isinstance(workspace_paths, list):
        for p in workspace_paths:
            if isinstance(p, str) and p.strip():
                roots.append(os.path.realpath(os.path.abspath(p)))
    if not roots:
        cwd = os.getcwd()
        if cwd:
            roots.append(os.path.realpath(os.path.abspath(cwd)))
    return roots


def normalized_path(target, workspace_paths):
    if not isinstance(target, str) or not target.strip():
        return None
    raw_norm = target.replace("\\", "/").strip()
    # Cross-platform WSL / Linux path conversion on Windows:
    if os.name == "nt" and (raw_norm.startswith("/home/") or raw_norm.startswith("/mnt/")):
        unc_candidate = f"\\\\wsl.localhost\\Ubuntu{target.replace('/', chr(92))}"
        return unc_candidate.replace("\\", "/").lower(), unc_candidate
    roots = effective_roots(workspace_paths)
    if not roots:
        return None
    candidate = os.path.expanduser(target)
    if not os.path.isabs(candidate):
        if len(roots) != 1:
            return None
        candidate = os.path.join(roots[0], candidate)
    candidate = os.path.realpath(os.path.abspath(candidate))
    for root in roots:
        try:
            if os.path.commonpath([os.path.normcase(root), os.path.normcase(candidate)]) == os.path.normcase(root):
                rel = os.path.relpath(candidate, root).replace("\\", "/").lower()
                return rel, candidate
        except ValueError:
            pass
    norm_cand = candidate.replace("\\", "/").lower()
    if "/.gemini/antigravity/brain/" in norm_cand or "/.gemini/antigravity/scratch/" in norm_cand:
        return norm_cand, candidate
    # Recognized external outposts and WSL mounts:
    if norm_cand.startswith(("//wsl.localhost/", "//wsl$/", "\\\\wsl.localhost\\", "\\\\wsl$\\")):
        return norm_cand, candidate
    if "/outposts/" in norm_cand or "/home/flowe/" in norm_cand:
        return norm_cand, candidate
    return None


def _git_stdout(args, cwd):
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _extract_stage4_contract_json(ideas_text):
    """Extract and validate the fenced ```contract JSON block inside Stage 4 of IDEAS.md."""
    stage4_lines = []
    in_stage4 = False
    for line in ideas_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_stage4:
                break
            if stripped.startswith("## Stage 4:"):
                in_stage4 = True
            continue
        if in_stage4:
            stage4_lines.append(line)
    if not in_stage4:
        return None

    in_fence = False
    buf = []
    closed = False
    for line in stage4_lines:
        stripped = line.strip()
        if not in_fence:
            if stripped == "```contract":
                in_fence = True
            continue
        if stripped == "```":
            closed = True
            break
        buf.append(line)
    if not closed:
        return None

    try:
        parsed = json.loads("\n".join(buf))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    intent = parsed.get("intent")
    if not isinstance(intent, str) or not intent.strip():
        return None
    for list_key in ("allowed_paths", "checks"):
        val = parsed.get(list_key)
        if not isinstance(val, list) or not val or not all(isinstance(x, str) and x.strip() for x in val):
            return None
    return parsed


def _resolve_git_session_base(root):
    git_dir_raw = _git_stdout(["rev-parse", "--git-dir"], root)
    if not git_dir_raw or not git_dir_raw.strip():
        return None
    git_dir = git_dir_raw.strip()
    if not os.path.isabs(git_dir):
        git_dir = os.path.join(root, git_dir)
    base_file = os.path.join(git_dir, "crucible-session-base")
    if os.path.isfile(base_file):
        try:
            with open(base_file, "r", encoding="utf-8", errors="replace") as f:
                candidate = f.read().strip()
        except OSError:
            candidate = ""
        if candidate:
            verified = _git_stdout(["rev-parse", "--verify", f"{candidate}^{{commit}}"], root)
            if verified and verified.strip():
                return verified.strip()
    head_out = _git_stdout(["rev-parse", "HEAD"], root)
    if head_out and head_out.strip():
        return head_out.strip()
    return None


def _committed_contract_allowed_paths(workspace_paths):
    """Return external allowed_paths from committed Stage 4 ```contract``` blocks matching working-tree IDEAS.md."""
    allowed = []
    for root in effective_roots(workspace_paths):
        ideas_path = os.path.join(root, "IDEAS.md")
        if not os.path.isfile(ideas_path):
            continue
        try:
            with open(ideas_path, "r", encoding="utf-8", errors="replace") as f:
                wt_text = f.read()
        except OSError:
            continue
        wt_contract = _extract_stage4_contract_json(wt_text)
        if wt_contract is None:
            continue
        # Fast path: only invoke git if at least one allowed_path is explicitly external/absolute.
        wt_paths = wt_contract["allowed_paths"]
        if not any(os.path.isabs(os.path.expanduser(p.strip())) for p in wt_paths):
            continue
        base_sha = _resolve_git_session_base(root)
        if not base_sha:
            continue
        base_text = _git_stdout(["show", f"{base_sha}:IDEAS.md"], root)
        if base_text is None:
            continue
        base_contract = _extract_stage4_contract_json(base_text)
        if base_contract is None or base_contract != wt_contract:
            continue
        allowed.extend(base_contract["allowed_paths"])
    return allowed


def _glob_to_regex(pattern):
    norm = pattern.strip().replace("\\", "/")
    regex_parts = ["^"]
    idx = 0
    n = len(norm)
    while idx < n:
        if norm[idx : idx + 3] == "**/":
            regex_parts.append("(?:.+/)?")
            idx += 3
        elif norm[idx : idx + 2] == "**":
            regex_parts.append(".*")
            idx += 2
        elif norm[idx] == "*":
            regex_parts.append("[^/]*")
            idx += 1
        elif norm[idx] == "?":
            regex_parts.append("[^/]")
            idx += 1
        else:
            regex_parts.append(re.escape(norm[idx]))
            idx += 1
    regex_parts.append("$")
    return re.compile("".join(regex_parts))


def _match_external_allowed_pattern(target_full, pattern):
    """Match canonicalized target_full against an explicitly absolute external allowed_paths entry."""
    pat_expanded = os.path.expanduser(pattern.strip())
    if not os.path.isabs(pat_expanded):
        return False

    if not any(ch in pat_expanded for ch in ("*", "?")):
        pat_full = os.path.realpath(os.path.abspath(pat_expanded))
        if Path(pat_full).parent == Path(pat_full):
            return False
        t_norm = os.path.normcase(target_full)
        p_norm = os.path.normcase(pat_full)
        if t_norm == p_norm:
            return True
        try:
            return os.path.commonpath([p_norm, t_norm]) == p_norm
        except ValueError:
            return False

    pat_fwd = pat_expanded.replace("\\", "/")
    first_wild = min(idx for idx in (pat_fwd.find("*"), pat_fwd.find("?")) if idx != -1)
    sep_idx = pat_fwd.rfind("/", 0, first_wild)
    if sep_idx <= 0:
        return False
    static_dir = pat_fwd[:sep_idx]
    if len(static_dir) == 2 and static_dir[1] == ":":
        static_dir += "/"
    wildcard_tail = pat_fwd[sep_idx + 1 :]
    if ".." in wildcard_tail.split("/"):
        return False
    static_real = os.path.realpath(os.path.abspath(static_dir))
    if Path(static_real).parent == Path(static_real):
        return False
    static_fwd = os.path.normcase(static_real).replace("\\", "/").rstrip("/")
    full_pattern = f"{static_fwd}/{os.path.normcase(wildcard_tail)}"
    target_fwd = os.path.normcase(target_full).replace("\\", "/")
    return _glob_to_regex(full_pattern).match(target_fwd) is not None


def authorized_contract_external_path(target, workspace_paths):
    """Return (norm_rel, full) if target matches an absolute allowed_paths entry in a committed Stage 4 ```contract```."""
    if not isinstance(target, str) or not target.strip():
        return None
    roots = effective_roots(workspace_paths)
    if not roots:
        return None
    candidate = os.path.expanduser(target.strip())
    if not os.path.isabs(candidate):
        if len(roots) != 1:
            return None
        candidate = os.path.join(roots[0], candidate)
    allowed = _committed_contract_allowed_paths(workspace_paths)
    if not allowed:
        return None
    target_full = os.path.realpath(os.path.abspath(candidate))
    if any(_match_external_allowed_pattern(target_full, pat) for pat in allowed):
        return target_full.replace("\\", "/").lower(), target_full
    return None


def is_protected(rel):
    rel = rel.replace("\\", "/").lower()
    while rel.startswith("./"):
        rel = rel[2:]
    base = os.path.basename(rel)
    if base in (
        "pre_tool_guard.js",
        "hooks.json",
        "hook_v4.py",
        "code_graph.py",
        "acceptance.lock.json",
        ".env",
        "gemini.md",
        "agents.md",
        "reliability-events.jsonl",
        "db-baseline.json",
        "test-baseline.json",
        "root-files-baseline.json",
        "workspace-symbols.json",
    ):
        return True
    return rel in PROTECTED_FILES or any(
        rel == p or rel.startswith(p + "/") or ("/" + p + "/") in ("/" + rel + "/")
        for p in PROTECTED_PREFIXES
    )


def is_workspace_code_file(path_str):
    if not isinstance(path_str, str) or not path_str.strip():
        return False
    norm = path_str.replace("\\", "/").lower()
    if "/.gemini/antigravity/" in norm:
        return False
    return norm.endswith(WORKSPACE_CODE_EXTS)


def is_test_file(abs_path):
    norm = abs_path.replace("\\", "/").lower()
    base = os.path.basename(norm)
    return (
        base.startswith("test_")
        or base.endswith("_test.py")
        or base == "conftest.py"
        or "/tests/" in norm
        or "/test/" in norm
    )


def file_edit_path(args):
    for k in ("Path", "TargetFile", "file_path", "path", "AbsolutePath"):
        if isinstance(args.get(k), str) and args[k].strip():
            return args[k]
    return None


def extract_edit_pairs(args):
    """RW-07: Extract list of (old_text, new_text) pairs across single edits, writes, and multi_replace_file_content."""
    chunks = args.get("ReplacementChunks")
    if isinstance(chunks, list) and chunks:
        pairs = []
        for ch in chunks:
            if isinstance(ch, dict):
                o = ch.get("Target") if isinstance(ch.get("Target"), str) else ch.get("TargetContent")
                n = ch.get("Replacement") if isinstance(ch.get("Replacement"), str) else ch.get("ReplacementContent")
                pairs.append((o, n))
        if pairs:
            return pairs
    old = args.get("Target") if isinstance(args.get("Target"), str) else args.get("TargetContent")
    new = (
        args.get("Replacement")
        if isinstance(args.get("Replacement"), str)
        else args.get("ReplacementContent")
    )
    if new is None:
        new = args.get("Content") if isinstance(args.get("Content"), str) else args.get("CodeContent")
    return [(old, new)]


def event_path(payload):
    directory = payload.get("artifactDirectoryPath")
    if not isinstance(directory, str) or not directory.strip():
        return None
    directory = os.path.realpath(os.path.expanduser(directory))
    if not os.path.isdir(directory):
        return None
    return os.path.join(directory, "reliability-events.jsonl")


def read_event_log(payload):
    path = event_path(payload)
    if not path or not os.path.isfile(path):
        return []
    events = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except (OSError, ValueError, TypeError):
        pass
    return events


def is_noop_stmt(stmt):
    """Return True if an AST statement is `pass`, a docstring/constant expression, or a dead `_ = ...` assignment."""
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return True
    if isinstance(stmt, ast.Assign) and all(
        isinstance(t, ast.Name) and t.id.startswith("_") for t in stmt.targets
    ):
        return True
    return False


def count_swallowed_exceptions(source_text):
    """RW-08 & RW-15: Count swallowed exceptions even when masked by docstrings or `_ = exc`."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            is_broad = node.type is None or (
                isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException")
            )
            effective_body = [s for s in node.body if not is_noop_stmt(s)]
            if len(effective_body) == 0:
                count += 1
            elif len(effective_body) == 1:
                stmt = effective_body[0]
                if isinstance(stmt, ast.Continue):
                    count += 1
                elif is_broad and isinstance(stmt, ast.Return):
                    val = stmt.value
                    if val is None or (isinstance(val, ast.Constant) and val.value in (None, False, "")):
                        count += 1
                    elif isinstance(val, (ast.List, ast.Dict, ast.Set)) and len(getattr(val, "elts", getattr(val, "keys", []))) == 0:
                        count += 1
        elif isinstance(node, ast.With):
            for item in node.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call):
                    func_name = ""
                    if isinstance(ctx.func, ast.Name):
                        func_name = ctx.func.id
                    elif isinstance(ctx.func, ast.Attribute):
                        func_name = ctx.func.attr
                    if func_name == "suppress":
                        count += 1
    return count


def has_always_true_eq(source_text):
    """RW-02 & RW-14: Detect `__eq__(self, other)` that returns True or ignores `other` completely."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "__eq__":
            if len(node.args.args) >= 2:
                other_arg = node.args.args[1].arg
                loaded_names = {
                    sub.id
                    for stmt in node.body
                    for sub in ast.walk(stmt)
                    if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load)
                }
                if other_arg not in loaded_names:
                    return True
            effective = [s for s in node.body if not is_noop_stmt(s)]
            if len(effective) == 1 and isinstance(effective[0], ast.Return):
                val = effective[0].value
                if isinstance(val, ast.Constant) and bool(val.value) is True:
                    return True
    return False


def has_production_mock_import(source_text):
    """RW-11: Detect importing `unittest.mock` inside production non-test modules."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "unittest.mock" or alias.name.startswith("unittest.mock."):
                    return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "unittest.mock" or node.module == "mock"):
                return True
    return False


def has_test_harness_detection(source_text):
    """RW-17: Detect production code checking `PYTEST_CURRENT_TEST`, `'unittest' in sys.modules`, or `sys._getframe`."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in ("PYTEST_CURRENT_TEST", "UNITTEST_RUNNING"):
                return True
        elif isinstance(node, ast.Compare):
            comp_str = ast.unparse(node) if hasattr(ast, "unparse") else ""
            if "sys.modules" in comp_str and ("pytest" in comp_str or "unittest" in comp_str):
                return True
        elif isinstance(node, ast.Attribute) and node.attr == "_getframe":
            return True
    return False


def has_unsafe_scratch_write(source_text):
    """RW-09 & RW-16: AST check for file-writing calls in scratch scripts that are not anchored to `__file__` or `tempfile`."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return False
    write_calls = 0
    has_ast_file_anchor = False
    has_ast_tempfile = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "__file__":
            has_ast_file_anchor = True
        elif isinstance(node, ast.Import) and any(a.name == "tempfile" for a in node.names):
            has_ast_tempfile = True
        elif isinstance(node, ast.ImportFrom) and node.module == "tempfile":
            has_ast_tempfile = True
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in (
                "write_text",
                "write_bytes",
                "copy",
                "move",
                "rmtree",
                "remove",
                "unlink",
                "replace",
            ):
                write_calls += 1
            elif isinstance(node.func, ast.Name) and node.func.id == "open":
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                    if any(m in node.args[1].value for m in ("w", "a", "+")):
                        write_calls += 1
    if write_calls == 0:
        return False
    return not (has_ast_file_anchor or has_ast_tempfile)


def count_test_assertions_and_skips(source_text):
    """RW-01: Count assertions, skip decorators/calls, and tautological asserts in test files."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return 0, 0, False
    assert_count = 0
    skip_count = 0
    has_cheat = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            assert_count += 1
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                has_cheat = True
        elif isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id
            if func_name.startswith("assert"):
                assert_count += 1
                if func_name == "assertTrue" and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value is True:
                    has_cheat = True
            elif func_name in ("skip", "skipTest", "xfail"):
                skip_count += 1
            elif func_name in ("exit", "_exit") and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id in ("sys", "os"):
                    has_cheat = True
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for dec in node.decorator_list:
                dec_str = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                if any(k in dec_str for k in ("skip", "xfail")):
                    skip_count += 1
    return assert_count, skip_count, has_cheat


def check_write_integrity(name, args, abs_path):
    """Comprehensive write integrity check (FM-H02..H04, FM-H08, FM-H13, RW-01, RW-02, RW-07..09, RW-11)."""
    if args.get("ArtifactMetadata") is not None:
        norm_abs = abs_path.replace("\\", "/").lower()
        if "/.gemini/antigravity/brain/" not in norm_abs:
            return (
                "deny",
                "FM-H08 (ArtifactMetadata Misuse): ArtifactMetadata was provided for a workspace file outside .gemini/antigravity/brain/. Omit ArtifactMetadata for non-artifact files.",
            )

    pairs = extract_edit_pairs(args)
    existing_text = None
    if os.path.isfile(abs_path):
        try:
            existing_text = Path(abs_path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            existing_text = None

    total_deleted_lines = 0
    for old, new in pairs:
        if isinstance(new, str):
            m = FORBIDDEN_CONTROL_RE.search(new)
            if m:
                byte_hex = f"0x{ord(m.group(0)):02x}"
                return (
                    "deny",
                    f"FM-H02 (Control-Byte Corruption): Payload contains forbidden ASCII control character {byte_hex} at offset {m.start()}.",
                )
            if re.search(r"(?i)(?:\/\/|#)\s*\.\.\.\s*(?:existing|unchanged|rest\s+of)\s+code", new):
                return ("force_ask", "Lazy placeholder comment (`// ... existing code`) detected; write complete code.")

        if name in ("write_file", "write_to_file") and not args.get("Append"):
            if isinstance(new, str) and len(new.strip()) == 0:
                return ("ask", "Empty file write blocked; truncating a file to 0 bytes requires review.")

        if isinstance(old, str) and isinstance(new, str):
            if old == new:
                return ("deny", "Exact no-op edit (`Target == Replacement`); change the target logic.")
            if existing_text is not None:
                norm_existing = existing_text.replace("\r\n", "\n")
                norm_old = old.replace("\r\n", "\n")
                if norm_old not in norm_existing:
                    return (
                        "deny",
                        "FM-H03 (Target Not Found): `Target` does not match existing text in the file. Read the exact target lines first.",
                    )
                total_deleted_lines += max(0, len(norm_old.splitlines()) - len(new.splitlines()))

    if existing_text is not None and total_deleted_lines > 0:
        total_lines = len(existing_text.splitlines())
        if total_lines >= 20 and total_deleted_lines > total_lines // 2:
            return ("ask", "Potentially broad deletion (>50% of existing file lines); review the proposed diff.")

    # In-memory Python AST & Reward-Hacking Inspection
    if abs_path.lower().endswith(".py"):
        candidate_py = None
        if name in ("write_file", "write_to_file") and not args.get("Append"):
            candidate_py = pairs[0][1]
        elif existing_text is not None:
            candidate_py = existing_text
            for old, new in pairs:
                if isinstance(old, str) and isinstance(new, str):
                    if old in candidate_py:
                        candidate_py = candidate_py.replace(old, new)
                    else:
                        candidate_py = candidate_py.replace("\r\n", "\n").replace(
                            old.replace("\r\n", "\n"), new.replace("\r\n", "\n")
                        )

        if isinstance(candidate_py, str):
            try:
                ast.parse(candidate_py, filename=abs_path)
            except SyntaxError as exc:
                return (
                    "deny",
                    f"FM-H02 (Python SyntaxError): Proposed edit produces invalid Python syntax at line {exc.lineno}: {exc.msg}.",
                )

            norm_abs = abs_path.replace("\\", "/").lower()
            in_brain = "/.gemini/antigravity/" in norm_abs

            # RW-08: Swallowed exceptions (`except: pass`, `except Exception: return None/[]`, `contextlib.suppress`)
            old_swallowed = count_swallowed_exceptions(existing_text) if existing_text else 0
            new_swallowed = count_swallowed_exceptions(candidate_py)
            if new_swallowed > old_swallowed:
                return (
                    "ask",
                    "FM-H04 (Swallowed Exception) / RW-08: Proposed edit introduces silent exception swallowing (`except: pass`, `except Exception: return None/[]`, or `contextlib.suppress`).",
                )

            # RW-02: ImpossibleBench `__eq__` always-True reward hack
            if not (existing_text and has_always_true_eq(existing_text)) and has_always_true_eq(candidate_py):
                return (
                    "deny",
                    "RW-02 (Reward Hacking Blocked): Defining `def __eq__(self, other): return True` is a known test-bypass exploit.",
                )

            # RW-01: EvilGenie / ImpossibleBench Test Suite Tampering
            if not in_brain and is_test_file(abs_path):
                old_asserts, old_skips, _ = count_test_assertions_and_skips(existing_text) if existing_text else (0, 0, False)
                new_asserts, new_skips, has_cheat = count_test_assertions_and_skips(candidate_py)
                if has_cheat:
                    return (
                        "deny",
                        "RW-01 (Test Tampering Blocked): Test file introduces `sys.exit(0)`, `assert True`, or `assertTrue(True)` reward hack.",
                    )
                if new_skips > old_skips:
                    return (
                        "ask",
                        "RW-01 (Test Skip Introduced): Proposed edit adds `@skip` / `skipTest` / `xfail` to a test file instead of fixing the underlying implementation.",
                    )
                if existing_text and new_asserts < old_asserts:
                    return (
                        "ask",
                        f"RW-01 (Assertion Weakening): Proposed edit reduces test assertion count from {old_asserts} to {new_asserts}. Do not delete assertions to make tests pass.",
                    )

            # RW-11 & RW-17: Production Mock Injection & Test-Harness Detection
            if not in_brain and not is_test_file(abs_path):
                if not (existing_text and has_production_mock_import(existing_text)) and has_production_mock_import(candidate_py):
                    return (
                        "ask",
                        "RW-11 (Production Mock Injection): Proposed edit imports `unittest.mock` inside a non-test production module.",
                    )
                if not (existing_text and has_test_harness_detection(existing_text)) and has_test_harness_detection(candidate_py):
                    return (
                        "deny",
                        "RW-17 (Test-Harness Detection Blocked): Production code checks `PYTEST_CURRENT_TEST`, `sys.modules` for test runners, or `sys._getframe`.",
                    )

            # Lean Option B: One-off root script & scratch write force_ask bottlenecks removed.

    return None


def phonetic_skeleton(word):
    w = word.lower().strip()
    w = re.sub(r"[aeiouy]+", "a", w)
    w = re.sub(r"(.)\1+", r"\1", w)
    return w


def check_phonetic_near_miss(name, rel, full, roots, payload=None):
    if name not in ("write_file", "write_to_file") or os.path.exists(full):
        return None
    if "/.gemini/antigravity/" in rel:
        return None
    eff = effective_roots(roots)
    if not eff:
        return None
    existing_symbols = None
    sym_file = None
    if isinstance(payload, dict):
        ev_path = event_path(payload)
        if ev_path:
            sym_file = os.path.join(os.path.dirname(ev_path), "workspace-symbols.json")
            if os.path.isfile(sym_file):
                try:
                    cached = json.loads(Path(sym_file).read_text(encoding="utf-8"))
                    if isinstance(cached, list):
                        existing_symbols = set(cached)
                except (OSError, ValueError, TypeError):
                    existing_symbols = None

    if existing_symbols is None:
        existing_symbols = set()
        scanned_files = 0
        for r in eff:
            if not os.path.isdir(r):
                continue
            for dirpath, dirnames, filenames in os.walk(r):
                dirnames[:] = [d for d in dirnames if d not in SKIP_WALK_DIRS and d != "scratch"]
                for d in dirnames:
                    if len(d) >= 3:
                        existing_symbols.add(d.lower())
                for fn in filenames:
                    scanned_files += 1
                    if scanned_files > MAX_WALK_FILES:
                        break
                    stem = Path(fn).stem.lower()
                    if len(stem) >= 3:
                        existing_symbols.add(stem)
                if scanned_files > MAX_WALK_FILES:
                    break
            if scanned_files > MAX_WALK_FILES:
                break
        if sym_file:
            try:
                with open(sym_file, "w", encoding="utf-8") as fh:
                    json.dump(sorted(existing_symbols), fh)
            except OSError:
                pass

    rel_parts = [Path(p).stem.lower() for p in rel.split("/") if p]
    for cand in rel_parts:
        if len(cand) < 3 or cand in existing_symbols or cand.startswith("test_"):
            continue
        cand_no_digits = re.sub(r"\d+", "", cand)
        cand_skel = phonetic_skeleton(cand)
        for ex in sorted(existing_symbols):
            if cand == ex or ex.startswith("test_"):
                continue
            if cand_no_digits == re.sub(r"\d+", "", ex):
                continue
            ex_skel = phonetic_skeleton(ex)
            ratio = difflib.SequenceMatcher(None, cand, ex).ratio()
            if (len(cand_skel) >= 3 and cand_skel == ex_skel) or ratio >= 0.84:
                return (
                    f"FM-H10 (Voice-Dictation Phonetic Near-Miss): New path token `{cand}` closely resembles "
                    f"existing workspace symbol `{ex}`. Verify this is not a speech-to-text transcription typo."
                )
    return None


def check_three_strike_file_churn(payload, rel, full):
    if "/.gemini/antigravity/" in rel:
        return None
    events = read_event_log(payload)
    norm_full = os.path.normcase(full)
    edit_count = 0
    errors_since_first_edit = 0
    for ev in events:
        if ev.get("edited_file") and os.path.normcase(str(ev.get("edited_file"))) == norm_full:
            edit_count += 1
        elif edit_count > 0 and ev.get("failed"):
            errors_since_first_edit += 1
    if edit_count >= 3 and errors_since_first_edit >= 1:
        return (
            f"FM-H12 (3-Strike Structural Repair Governor): `{os.path.basename(full)}` has already been patched "
            f"{edit_count} times across failing loops in this session. Halt local patching and escalate a Root Cause Architecture Assessment."
        )
    return None


def check_subagent_context_overload(payload, full):
    """FM-AUTO-01: Automatic Subagent Delegation & Context-Rot Overload Gate."""
    # Worktree & child subagents already operate under delegated authority:
    if payload.get("parentConversationId") or os.environ.get("ANTIGRAVITY_SUBAGENT"):
        return None
    if not is_workspace_code_file(full):
        return None
    events = read_event_log(payload)
    last_subagent_idx = -1
    for idx, ev in enumerate(events):
        if ev.get("subagent_delegated"):
            last_subagent_idx = idx
    events_after_last_subagent = events[last_subagent_idx + 1 :]
    unique_edited_since_delegation = set()
    edit_count_since_delegation = 0
    for ev in events_after_last_subagent:
        ef = ev.get("edited_file")
        if isinstance(ef, str):
            edit_count_since_delegation += 1
            if is_workspace_code_file(ef) and not is_test_file(ef):
                unique_edited_since_delegation.add(os.path.normcase(ef))
    step_idx = payload.get("stepIdx") if isinstance(payload.get("stepIdx"), int) else 0
    norm_target = os.path.normcase(full)
    if (
        (
            not is_test_file(full)
            and len(unique_edited_since_delegation) >= 2
            and norm_target not in unique_edited_since_delegation
        )
        or edit_count_since_delegation >= 35
        or (step_idx >= 60 and edit_count_since_delegation >= 15)
    ):
        return (
            "FM-AUTO-01 (Automatic Subagent & Context-Rot Gate): You are attempting to modify 3+ workspace code files or edit code after 35+ steps in a single context window without delegating. Stop coding directly in the main chat: warn the user about context load and automatically delegate bounded tasks via invoke_subagent()."
        )
    return None


def ranges_overlap(s1, e1, s2, e2):
    """Return True if two (StartLine, EndLine) ranges overlap."""
    a_start = s1 if isinstance(s1, int) else 1
    a_end = e1 if isinstance(e1, int) else 10**9
    b_start = s2 if isinstance(s2, int) else 1
    b_end = e2 if isinstance(e2, int) else 10**9
    return max(a_start, b_start) <= min(a_end, b_end)


def check_read_thrashing(payload, abs_path, args):
    """FM-H01 & RW-05: Detect >= 2 prior overlapping reads on the same file hash without an intervening edit."""
    start_line = args.get("StartLine")
    end_line = args.get("EndLine")
    current_hash = None
    try:
        current_hash = hashlib.sha256(Path(abs_path).read_bytes()).hexdigest()
    except OSError:
        pass
    events = read_event_log(payload)
    overlapping_reads = 0
    norm_target = os.path.normcase(abs_path)
    for ev in reversed(events):
        if ev.get("edited_file") and os.path.normcase(str(ev.get("edited_file"))) == norm_target:
            break
        if current_hash and ev.get("file_hash") and ev.get("file_hash") != current_hash:
            break
        if ev.get("read_file") and os.path.normcase(str(ev.get("read_file"))) == norm_target:
            if ranges_overlap(start_line, end_line, ev.get("start_line"), ev.get("end_line")):
                overlapping_reads += 1
    if overlapping_reads >= 2:
        return (
            f"FM-H01 / RW-05 (Read-Thrashing Loop Breaker): `{os.path.basename(abs_path)}` has already been read "
            f"{overlapping_reads} times over overlapping lines ({start_line}-{end_line}) without an intervening edit."
        )
    return None


def snapshot_workspace_dbs(payload):
    path = event_path(payload)
    if not path:
        return
    art_dir = os.path.dirname(path)
    snap_file = os.path.join(art_dir, "db-baseline.json")
    test_snap_file = os.path.join(art_dir, "test-baseline.json")
    root_snap_file = os.path.join(art_dir, "root-files-baseline.json")
    if (
        os.path.isfile(snap_file)
        and os.path.isfile(test_snap_file)
        and os.path.isfile(root_snap_file)
    ):
        return
    roots = effective_roots(payload.get("workspacePaths") or [])
    baseline = {}
    test_baseline = {}
    root_files = []
    for r in roots:
        if os.path.isdir(r):
            try:
                for entry in os.listdir(r):
                    if os.path.isfile(os.path.join(r, entry)):
                        root_files.append(entry)
            except OSError:
                pass
    scanned_files = 0
    for r in roots:
        if not os.path.isdir(r):
            continue
        for dirpath, dirnames, filenames in os.walk(r):
            dirnames[:] = [d for d in dirnames if d not in SKIP_WALK_DIRS]
            for fn in filenames:
                scanned_files += 1
                if scanned_files > MAX_WALK_FILES:
                    break
                full = os.path.join(dirpath, fn)
                if fn.lower().endswith((".db", ".sqlite", ".sqlite3")):
                    try:
                        st = os.stat(full)
                        baseline[full] = {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
                    except OSError:
                        pass
                if is_test_file(full) and "/.gemini/antigravity/" not in full.replace("\\", "/").lower():
                    try:
                        st = os.stat(full)
                        digest = hashlib.sha256(Path(full).read_bytes()).hexdigest()
                        test_baseline[full] = {"size": st.st_size, "sha256": digest}
                    except OSError:
                        pass
            if scanned_files > MAX_WALK_FILES:
                break
        if scanned_files > MAX_WALK_FILES:
            break
    if not os.path.isfile(snap_file):
        try:
            with open(snap_file, "w", encoding="utf-8") as fh:
                json.dump(baseline, fh)
        except OSError:
            pass
    if not os.path.isfile(test_snap_file):
        try:
            with open(test_snap_file, "w", encoding="utf-8") as fh:
                json.dump(test_baseline, fh)
        except OSError:
            pass
    if not os.path.isfile(root_snap_file):
        try:
            with open(root_snap_file, "w", encoding="utf-8") as fh:
                json.dump(sorted(set(root_files)), fh)
        except OSError:
            pass



def is_subagent_call(payload):
    """Detect whether this tool invocation originates from an autonomous child subagent."""
    if not isinstance(payload, dict):
        return False
    if payload.get("parentConversationId") or os.environ.get("ANTIGRAVITY_SUBAGENT"):
        return True
    tpath = payload.get("transcriptPath")
    if isinstance(tpath, str) and os.path.isfile(tpath):
        try:
            with open(tpath, "r", encoding="utf-8", errors="ignore") as fh:
                first_line = fh.readline()
                if any(k in first_line for k in ("SUBAGENT", "sender=", "P-N-S-C", "[Message]")):
                    return True
        except Exception:
            pass
    conv_id = payload.get("conversationId")
    if conv_id and isinstance(conv_id, str):
        for candidate in (
            "C:/Kageyoni/.state/subagents.json",
            "C:/Users/flowe/.gemini/antigravity/brain/.active_subagents.json",
        ):
            if os.path.isfile(candidate):
                try:
                    with open(candidate, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                        if conv_id in data:
                            return True
                except Exception:
                    pass
    return False


def pre(payload):
    """Lean safety-only PreToolUse guard (Option B).

    Preserves true Catastrophic/Tier-1/Tier-2 safety and anti-tampering gates while removing
    noisy force_ask bottlenecks so native Antigravity Always-Allow works normally.
    """
    snapshot_workspace_dbs(payload)
    tool = payload.get("toolCall") or {}
    name = tool.get("name")
    args = tool.get("args") or {}
    roots = payload.get("workspacePaths") or []
    is_subagent = is_subagent_call(payload)
    if not isinstance(args, dict):
        if is_subagent:
            return {"decision": "deny", "reason": "Cannot inspect tool arguments."}
        return {"decision": "ask", "reason": "Cannot inspect tool arguments."}

    # Always allow read operations without read-thrashing force_ask bottlenecks
    if name in READ_TOOLS:
        return {"decision": "allow", "reason": "Read operation permitted."}

    if name in WRITE_TOOLS:
        path = file_edit_path(args)
        result = normalized_path(path, roots)
        if result is None:
            result = authorized_contract_external_path(path, roots)
        if result is None:
            return {"decision": "ask", "reason": "File target outside mounted workspace; native permissions apply."}
        rel, full = result
        if is_protected(rel):
            return {
                "decision": "deny",
                "reason": "Protected governance, acceptance, hook state, or Git internals; direct modification prohibited.",
            }
        integrity_issue = check_write_integrity(name, args, full)
        if integrity_issue:
            decision, reason = integrity_issue
            if is_subagent and decision in ("force_ask", "ask"):
                return {"decision": "deny", "reason": reason}
            return {"decision": decision, "reason": reason}
        return {"decision": "allow", "reason": "Workspace edit verified."}

    if name in ("run_command", "command"):
        cmd = args.get("CommandLine") or args.get("command") or args.get("cmd")
        if not isinstance(cmd, str) or not cmd.strip():
            return {"decision": "ask", "reason": "Cannot verify command text."}

        cwd = args.get("Cwd") or args.get("cwd")
        if isinstance(cwd, str) and cwd.strip():
            if normalized_path(cwd, roots) is None:
                return {"decision": "ask", "reason": "Command working directory is outside the workspace."}

        if any(re.search(p, cmd) for p in CATASTROPHIC_DENY_SHELL):
            return {"decision": "deny", "reason": f"Catastrophic destructive command denied: {cmd}"}

        # FM-H06: Only block raw Windows grep outside WSL invocations
        normalized_command = cmd.lower().replace("\\", "/")
        is_wsl_cmd = bool(re.match(r"^\s*wsl(?:\.exe)?\b", normalized_command))
        if os.name == "nt" and not is_wsl_cmd and re.search(r"(?:^|[|;&]\s*)grep\s+", cmd):
            return {
                "decision": "deny",
                "reason": "FM-H06 (Windows Shell Trap): Raw `grep` is not in Windows PATH. Use `Select-String` or native tools.",
            }

        # Fix RW-03 bypass: ALWAYS evaluate HIGH_RISK_SHELL before allowing shell writes
        if any(re.search(p, cmd) for p in HIGH_RISK_SHELL):
            if is_subagent:
                return {"decision": "deny", "reason": f"Tier-1/Tier-2 destructive action prohibited in autonomous subagent: {cmd}"}
            return {"decision": "force_ask", "reason": "Tier-1/Tier-2 destructive or external command; requires explicit human approval."}

        # RW-04: Block/gate .env access OR mutating/deleting protected governance files; allow read-only inspection
        has_env_ref = bool(re.search(r"(?:^|[\s\'\"/\\])\.env(?:\b|$)", normalized_command))
        has_gov_ref = any(
            x in normalized_command
            for x in (
                ".agents/hooks.json",
                ".agents/acceptance.lock.json",
                ".agents/reliability/",
                "governance/hooks/",
                "pre_tool_guard.js",
                "hook_v4.py",
                ".gemini/config/hooks.json",
                "reliability-events.jsonl",
                "db-baseline.json",
                "test-baseline.json",
                "root-files-baseline.json",
            )
        )
        looks_mutating = bool(
            re.search(
                r"(?:>|>>|\bset-content\b|\badd-content\b|\bout-file\b|\bremove-item\b|\bmove-item\b|\bcopy-item\b|\bsed\s+-i|\bwrite_text\b|\bwrite_bytes\b|\bos\.replace\b|\bshutil\.|\bopen\s*\([^)]*,\s*[\'\"][wa+]|patch_|apply_option_b)",
                normalized_command,
            )
        )
        if has_env_ref or (has_gov_ref and looks_mutating):
            if is_subagent:
                return {"decision": "deny", "reason": "RW-04: Subagents cannot access .env or mutate protected governance/hook files."}
            return {"decision": "force_ask", "reason": "RW-04: Command references .env or mutates protected governance/hook files."}

        return {"decision": "allow", "reason": "Command passed lean safety checks."}

    if isinstance(name, str) and (name == "call_mcp_tool" or name.startswith("mcp_")):
        tool_name = str(args.get("ToolName") or name).lower()
        if any(
            v in tool_name
            for v in ("deploy", "delete", "create", "update", "reset", "stop", "start", "set_", "init", "upload")
        ):
            if is_subagent:
                return {
                    "decision": "deny",
                    "reason": f"Tier 2 MCP External Gate prohibited in autonomous subagent: MCP tool `{tool_name}` mutates external/cloud state.",
                }
            return {
                "decision": "force_ask",
                "reason": f"Tier 2 MCP External Gate: MCP tool `{tool_name}` mutates external/cloud state; requires human confirmation.",
            }

    return {"decision": "allow", "reason": "Unclassified tool: native permissions still apply."}

def is_meaningful_verification_command(cmd):
    """RW-13: Distinguish real test/execution commands from trivial probes (`python --version`, `git status`, `echo`)."""
    if not isinstance(cmd, str) or not cmd.strip():
        return False
    c = cmd.strip().lower()
    if re.search(r"(?:^|\s)(?:--version|-v|--help|-h)(?:\s|$)", c):
        return False
    if re.match(r"^(?:echo|dir|ls|pwd|whoami|get-childitem|get-content|type|cat|git\s+(?:status|diff|log|branch|show))\b", c):
        return False
    return bool(
        re.search(r"\b(?:pytest|unittest|python3?|py|node|npm\s+(?:test|run)|cargo\s+test|go\s+test)\b", c)
    )


def post(payload):
    path = event_path(payload)
    if path:
        tool = payload.get("toolCall") or {}
        name = str(tool.get("name") or "")[:100]
        args = tool.get("args") if isinstance(tool.get("args"), dict) else {}
        roots = payload.get("workspacePaths") or []
        item = {
            "stepIdx": payload.get("stepIdx"),
            "tool": name,
            "failed": bool(payload.get("error")),
        }
        if name == "invoke_subagent" and not item["failed"]:
            item["subagent_delegated"] = True
        elif name in READ_TOOLS and not item["failed"]:
            target = file_edit_path(args)
            res = normalized_path(target, roots)
            if res is not None:
                _, full = res
                item["read_file"] = full
                item["start_line"] = args.get("StartLine")
                item["end_line"] = args.get("EndLine")
                item["read_sig"] = f"{os.path.normcase(full)}:{args.get('StartLine')}:{args.get('EndLine')}"
                try:
                    item["file_hash"] = hashlib.sha256(Path(full).read_bytes()).hexdigest()
                except OSError:
                    pass
        elif name in WRITE_TOOLS and not item["failed"]:
            target = file_edit_path(args)
            res = normalized_path(target, roots) or authorized_contract_external_path(target, roots)
            if res is not None:
                _, full = res
                item["edited_file"] = full
        elif name in ("run_command", "command") and not item["failed"]:
            cmd = args.get("CommandLine") or args.get("command") or args.get("cmd") or ""
            if is_meaningful_verification_command(cmd):
                item["verified_cmd"] = True
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(item) + "\n")
        except OSError:
            pass
    return {}


def manifest_for(payload):
    roots = effective_roots(payload.get("workspacePaths") or [])
    if len(roots) != 1:
        return None, None
    root = Path(roots[0])
    manifest = root / ".agents" / "acceptance.lock.json"
    if not manifest.is_file():
        return root, None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return root, data if isinstance(data, dict) else {"__invalid__": True}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return root, {"__invalid__": True}


def check_session_edited_python_and_dbs(payload):
    """FM-H04, FM-H05, FM-BASE-01, and FM-H13: Verify session-edited Python files parse and check DBs/test baselines/root clutter."""
    problems = []
    events = read_event_log(payload)
    edited_py = {
        ev.get("edited_file")
        for ev in events
        if isinstance(ev.get("edited_file"), str) and ev.get("edited_file").lower().endswith(".py")
    }
    for py_path in sorted(edited_py):
        if os.path.isfile(py_path):
            try:
                ast.parse(Path(py_path).read_text(encoding="utf-8"), filename=py_path)
            except (SyntaxError, OSError, UnicodeError, ValueError) as ex:
                problems.append(f"Edited Python file failed AST parse: {os.path.basename(py_path)} ({type(ex).__name__})")

    ev_path = event_path(payload)
    if ev_path:
        art_dir = os.path.dirname(ev_path)
        snap_file = os.path.join(art_dir, "db-baseline.json")
        if os.path.isfile(snap_file):
            try:
                baseline = json.loads(Path(snap_file).read_text(encoding="utf-8"))
                for db_path, meta in baseline.items():
                    if not os.path.isfile(db_path):
                        problems.append(f"FM-H05: Baseline SQLite database was deleted: {os.path.basename(db_path)}")
                    elif meta.get("size", 0) > 0 and os.path.getsize(db_path) == 0:
                        problems.append(f"FM-H05: Baseline SQLite database was truncated to 0 bytes: {os.path.basename(db_path)}")
            except (OSError, ValueError, TypeError):
                pass

        test_snap_file = os.path.join(art_dir, "test-baseline.json")
        if os.path.isfile(test_snap_file):
            try:
                test_baseline = json.loads(Path(test_snap_file).read_text(encoding="utf-8"))
                audited_edited_norm = {
                    os.path.normcase(ev.get("edited_file"))
                    for ev in events
                    if isinstance(ev.get("edited_file"), str)
                }
                for test_path, meta in test_baseline.items():
                    if not os.path.isfile(test_path) or (meta.get("size", 0) > 0 and os.path.getsize(test_path) == 0):
                        problems.append(
                            f"FM-BASE-01: Baseline test file was deleted or truncated: {os.path.basename(test_path)}"
                        )
                    else:
                        current_sha = hashlib.sha256(Path(test_path).read_bytes()).hexdigest()
                        if (
                            meta.get("sha256")
                            and current_sha != meta.get("sha256")
                            and os.path.normcase(test_path) not in audited_edited_norm
                        ):
                            problems.append(
                                f"FM-BASE-01: Baseline test file was modified out-of-band (hash mismatch without audited edit_file/write_file): {os.path.basename(test_path)}"
                            )
            except (OSError, ValueError, TypeError):
                pass

        root_snap_file = os.path.join(art_dir, "root-files-baseline.json")
        if os.path.isfile(root_snap_file):
            try:
                baseline_root_files = set(json.loads(Path(root_snap_file).read_text(encoding="utf-8")))
                for r in effective_roots(payload.get("workspacePaths") or []):
                    if os.path.isdir(r):
                        for entry in sorted(os.listdir(r)):
                            if (
                                entry not in baseline_root_files
                                and os.path.isfile(os.path.join(r, entry))
                                and ONE_OFF_ROOT_SCRIPT_RE.match(entry)
                            ):
                                problems.append(
                                    f"FM-H13: Untracked one-off script left in workspace root at turn end: {entry}"
                                )
            except (OSError, ValueError, TypeError):
                pass
    return problems


def qualification(payload):
    session_problems = check_session_edited_python_and_dbs(payload)
    root, contract = manifest_for(payload)
    if contract is None:
        return session_problems, bool(session_problems)
    if contract.get("__invalid__"):
        return ["Acceptance contract cannot be parsed."] + session_problems, True
    problems = list(session_problems)
    paths = contract.get("required_files", [])
    if not isinstance(paths, list):
        return ["Acceptance required_files is not a list."], True
    for relative in paths[:100]:
        n = normalized_path(relative, [str(root)])
        if n is None:
            problems.append("Acceptance path escapes workspace.")
            continue
        _, full = n
        if not os.path.isfile(full) or os.path.getsize(full) == 0:
            problems.append(f"Missing or empty required file: {relative}")
    py_files = contract.get("python_syntax", [])
    if not isinstance(py_files, list):
        problems.append("Acceptance python_syntax is not a list.")
        py_files = []
    for relative in py_files[:100]:
        n = normalized_path(relative, [str(root)])
        if n is None:
            problems.append("Python syntax path escapes workspace.")
            continue
        _, full = n
        try:
            ast.parse(Path(full).read_text(encoding="utf-8"), filename=str(full))
        except (SyntaxError, OSError, UnicodeError, ValueError) as ex:
            problems.append(f"Python file did not parse: {relative} ({type(ex).__name__})")
    return problems, True


def recent_tool_errors(payload):
    events = read_event_log(payload)[-3:]
    return 3 if len(events) == 3 and all(x.get("failed") for x in events) else 0


def stop(payload):
    if payload.get("terminationReason") not in ("NO_TOOL_CALL", "model_stop", None):
        return {"decision": "allow"}
    attempt = payload.get("executionNum", 0)
    if not isinstance(attempt, int) or attempt >= 3:
        return {"decision": "allow"}
    # Note: Antigravity's subagents and background tasks rely on reactive wakeup.
    # Yielding tool execution (stopping) is required so the host can wait for subagent completion.
    problems, has_contract = qualification(payload)
    if has_contract and problems:
        return {"decision": "continue", "reason": "External acceptance check failed: " + "; ".join(problems[:6])}
    if recent_tool_errors(payload):
        return {
            "decision": "continue",
            "reason": "Last three tools failed. Change method or report an honest blocker; do not repeat the same call.",
        }
    return {"decision": "allow"}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("pre", "post", "stop"):
        out({"decision": "force_ask", "reason": "Invalid hook invocation."})
        return
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("Payload must be JSON object")
        out({"pre": pre, "post": post, "stop": stop}[sys.argv[1]](payload))
    except Exception as ex:
        if sys.argv[1] == "pre":
            out({"decision": "force_ask", "reason": "Guard could not inspect operation."})
        elif sys.argv[1] == "stop":
            out({"decision": "allow"})
        else:
            out({})
        print(f"hook error: {type(ex).__name__}", file=sys.stderr)


if __name__ == "__main__":
    main()
