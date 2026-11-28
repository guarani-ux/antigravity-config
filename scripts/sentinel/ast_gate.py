"""Single-pass Python AST & semantic violation-identity inspector for Sentinel PreToolUse."""

from __future__ import annotations

import ast
import hashlib
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Hashable, Sequence, TypeVar

from .policy import is_brain_or_artifact_path, is_test_file

FORBIDDEN_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
LAZY_PLACEHOLDER_RE = re.compile(r"(?i)(?://|#)\s*\.\.\.\s*(?:existing|unchanged|rest\s+of)\s+code")

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GitHub token", re.compile(r"(?<![A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,})(?![A-Za-z0-9_])")),
    ("AWS access key", re.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Za-z0-9])")),
    ("Google API key", re.compile(r"(?<![A-Za-z0-9\-_])AIza[0-9A-Za-z\-_]{35}(?![A-Za-z0-9\-_])")),
    ("OpenAI/Anthropic API key", re.compile(r"(?<![A-Za-z0-9\-_])sk-(?:(?:proj-|svcacct-|ant-api\d+-)[A-Za-z0-9\-_]{20,}|[A-Za-z0-9]{48})(?![A-Za-z0-9\-_])")),
    ("Stripe live key", re.compile(r"(?<![A-Za-z0-9_])(?:sk|rk)_live_[0-9A-Za-z]{24,}(?![A-Za-z0-9_])")),
    ("Slack token", re.compile(r"(?<![A-Za-z0-9\-])xox[baprs]-[0-9A-Za-z\-]{10,}(?![A-Za-z0-9\-])|(?<![A-Za-z0-9\-])xapp-\d-[A-Za-z0-9\-]{10,}(?![A-Za-z0-9\-])")),
    ("HuggingFace/PyPI token", re.compile(r"(?<![A-Za-z0-9_])(?:hf_[A-Za-z0-9]{30,}|pypi-[A-Za-z0-9\-_]{50,})(?![A-Za-z0-9\-_])")),
    ("database URI credential", re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^/\s:@]+:([^/\s@]{8,})@[^/\s]+", re.IGNORECASE)),
    ("private key PEM block", re.compile(r"-----BEGIN (?:PGP PRIVATE KEY BLOCK|(?:RSA |EC |ECDSA |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY)-----")),
)

_PLACEHOLDER_SECRET_RE = re.compile(r"(?:EXAMPLE|DUMMY|PLACEHOLDER|FAKE_?KEY|YOUR_?(?:KEY|TOKEN|PASS)|CHANGE_?ME|XXXX+|000000)", re.IGNORECASE)

_SCRIPTS_ROOT = str(Path(__file__).resolve().parents[1])

T = TypeVar("T")


@dataclass(frozen=True)
class AstViolation:
    rule_id: str
    symbol: str
    kind: str
    decision: str
    message: str
    line: int = 1
    scope_target: str = "all"  # "all" | "test" | "prod"

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.rule_id, self.symbol, self.kind)


def _newly_introduced(
    new_items: Sequence[T],
    old_items: Sequence[T],
    key_fn: Callable[[T], Hashable],
) -> list[T]:
    """Multiset subtraction by semantic identity: catches equal-count swaps and boolean collapse."""
    budget = Counter(key_fn(x) for x in old_items)
    added: list[T] = []
    for item in new_items:
        k = key_fn(item)
        if budget[k] > 0:
            budget[k] -= 1
        else:
            added.append(item)
    return added


def _secret_matches(text: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for label, pat in SECRET_PATTERNS:
        for m in pat.finditer(text):
            tok = m.group(0)
            check_val = m.group(1) if m.lastindex else tok
            if label != "private key PEM block" and _PLACEHOLDER_SECRET_RE.search(check_val):
                continue
            hits.append((label, tok))
    return hits


def detect_secret_leak(text: str) -> str | None:
    """Return secret category label if text contains a live-looking credential, else None."""
    hits = _secret_matches(text)
    return hits[0][0] if hits else None


def _is_noop_stmt(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return True
    if isinstance(stmt, ast.Assign) and all(
        isinstance(t, ast.Name) and t.id.startswith("_") for t in stmt.targets
    ):
        return True
    return False


def _is_constant_expr(expr: ast.expr) -> bool:
    return not any(isinstance(n, (ast.Name, ast.Call, ast.Attribute, ast.Subscript)) for n in ast.walk(expr))


def _decorator_short_name(dec: ast.expr) -> str:
    if isinstance(dec, ast.Attribute):
        return dec.attr
    if isinstance(dec, ast.Name):
        return dec.id
    if isinstance(dec, ast.Call):
        if isinstance(dec.func, ast.Attribute):
            return dec.func.attr
        if isinstance(dec.func, ast.Name):
            return dec.func.id
    return ""


class _PythonAuditVisitor(ast.NodeVisitor):
    """Collects all AST anti-tampering and quality signals with lexical scope identities in a single O(N) walk."""

    def __init__(self) -> None:
        self._scope: list[str] = []
        self.violations: list[AstViolation] = []

    @property
    def _current_scope(self) -> str:
        return ".".join(self._scope) if self._scope else "<module>"

    def _add(
        self,
        rule_id: str,
        kind: str,
        decision: str,
        message: str,
        line: int,
        scope_target: str = "all",
    ) -> None:
        self.violations.append(AstViolation(rule_id, self._current_scope, kind, decision, message, line, scope_target))

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        is_broad = node.type is None or (
            isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException")
        )
        effective = [s for s in node.body if not _is_noop_stmt(s)]
        if node.body and not effective:
            self._add(
                "RW-08",
                "except_noop",
                "ask",
                "RW-08 (Swallowed Exception): Edit introduces silent exception suppression (`except: pass`, `return None`, or `suppress`).",
                node.lineno,
            )
        elif is_broad and len(effective) == 1 and isinstance(effective[0], ast.Return):
            val = effective[0].value
            if val is None or (isinstance(val, ast.Constant) and val.value in (None, False)) or (
                isinstance(val, (ast.List, ast.Dict, ast.Tuple)) and not getattr(val, "elts", getattr(val, "keys", None))
            ):
                self._add(
                    "RW-08",
                    "except_broad_return_empty",
                    "ask",
                    "RW-08 (Swallowed Exception): Edit introduces silent exception suppression (`except: pass`, `return None`, or `suppress`).",
                    node.lineno,
                )
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            call = item.context_expr
            if isinstance(call, ast.Call):
                fn = call.func
                if (isinstance(fn, ast.Name) and fn.id == "suppress") or (
                    isinstance(fn, ast.Attribute) and fn.attr == "suppress"
                ):
                    self._add(
                        "RW-08",
                        "contextlib_suppress",
                        "ask",
                        "RW-08 (Swallowed Exception): Edit introduces silent exception suppression (`except: pass`, `return None`, or `suppress`).",
                        node.lineno,
                    )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scope.append(node.name)
        for dec in node.decorator_list:
            short = _decorator_short_name(dec).lower()
            if short in ("skip", "skipif", "skipunless", "xfail"):
                self._add(
                    "RW-01-SKIP",
                    f"decorator:{short}",
                    "ask",
                    "RW-01 (Test Skip Introduced): Adding `@skip` / `skipTest` / `xfail` requires review.",
                    dec.lineno,
                    scope_target="test",
                )
        self.generic_visit(node)
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._scope.append(node.name)
        if node.name == "__eq__" and len(node.args.args) >= 2:
            effective = [s for s in node.body if not _is_noop_stmt(s)]
            if len(effective) == 1 and isinstance(effective[0], ast.Return):
                val = effective[0].value
                if isinstance(val, ast.Constant) and val.value is True:
                    self._add(
                        "RW-02",
                        "always_true_eq",
                        "deny",
                        "RW-02 (Reward Hacking Blocked): Defining `def __eq__(self, other): return True` is prohibited.",
                        node.lineno,
                    )
        for dec in node.decorator_list:
            short = _decorator_short_name(dec).lower()
            if short in ("skip", "skipif", "skipunless", "xfail"):
                self._add(
                    "RW-01-SKIP",
                    f"decorator:{short}",
                    "ask",
                    "RW-01 (Test Skip Introduced): Adding `@skip` / `skipTest` / `xfail` requires review.",
                    dec.lineno,
                    scope_target="test",
                )
        self.generic_visit(node)
        self._scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "unittest.mock" or alias.name.startswith("unittest.mock."):
                self._add(
                    "RW-11",
                    f"import:{alias.name}",
                    "ask",
                    "RW-11 (Production Mock Injection): Importing `unittest.mock` inside production module.",
                    node.lineno,
                    scope_target="prod",
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and (node.module == "unittest.mock" or node.module.startswith("unittest.mock.")):
            self._add(
                "RW-11",
                f"import:{node.module}",
                "ask",
                "RW-11 (Production Mock Injection): Importing `unittest.mock` inside production module.",
                node.lineno,
                scope_target="prod",
            )
        elif node.module == "unittest" and any(alias.name == "mock" for alias in node.names):
            self._add(
                "RW-11",
                "import:unittest.mock",
                "ask",
                "RW-11 (Production Mock Injection): Importing `unittest.mock` inside production module.",
                node.lineno,
                scope_target="prod",
            )

    def visit_Assert(self, node: ast.Assert) -> None:
        if not (isinstance(node.test, ast.Constant) and bool(node.test.value) is False) and _is_constant_expr(node.test):
            self._add(
                "RW-01",
                "const_assert",
                "deny",
                "RW-01 (Test Tampering Blocked): Test introduces `assert True`, `assertTrue(True)`, or `sys.exit(0)`.",
                node.lineno,
                scope_target="test",
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        fn = node.func
        if isinstance(fn, ast.Attribute):
            if fn.attr == "assertTrue" and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value is True:
                self._add(
                    "RW-01",
                    "assert_true_const",
                    "deny",
                    "RW-01 (Test Tampering Blocked): Test introduces `assert True`, `assertTrue(True)`, or `sys.exit(0)`.",
                    node.lineno,
                    scope_target="test",
                )
            elif fn.attr == "skipTest":
                self._add(
                    "RW-01-SKIP",
                    "call:skipTest",
                    "ask",
                    "RW-01 (Test Skip Introduced): Adding `@skip` / `skipTest` / `xfail` requires review.",
                    node.lineno,
                    scope_target="test",
                )
            elif fn.attr == "exit" and isinstance(fn.value, ast.Name) and fn.value.id == "sys":
                if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 0:
                    self._add(
                        "RW-01",
                        "sys_exit_0",
                        "deny",
                        "RW-01 (Test Tampering Blocked): Test introduces `assert True`, `assertTrue(True)`, or `sys.exit(0)`.",
                        node.lineno,
                        scope_target="test",
                    )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if node.value == "PYTEST_CURRENT_TEST":
            self._add(
                "RW-17",
                "pytest_current_test",
                "deny",
                "RW-17 (Test-Harness Detection Blocked): Production code inspects test runner environment.",
                node.lineno,
                scope_target="prod",
            )


def _audit_py(source: str, filename: str = "<candidate>") -> tuple[ast.AST, _PythonAuditVisitor]:
    tree = ast.parse(source, filename=filename)
    visitor = _PythonAuditVisitor()
    visitor.visit(tree)
    return tree, visitor


def _extract_write_text(args: dict[str, Any]) -> str | None:
    for key in ("Content", "CodeContent", "content"):
        val = args.get(key)
        if isinstance(val, str):
            return val
    return None


def _extract_edit_pairs(args: dict[str, Any]) -> list[tuple[str, str]] | None:
    chunks = args.get("ReplacementChunks")
    if isinstance(chunks, list) and chunks:
        pairs: list[tuple[str, str]] = []
        for ch in chunks:
            if not isinstance(ch, dict):
                return None
            old_t = ch.get("TargetContent") if "TargetContent" in ch else ch.get("Target")
            new_t = ch.get("ReplacementContent") if "ReplacementContent" in ch else ch.get("Replacement")
            if not isinstance(old_t, str) or not isinstance(new_t, str):
                return None
            pairs.append((old_t, new_t))
        return pairs
    old_t = args.get("Target") if "Target" in args else args.get("TargetContent")
    new_t = args.get("Replacement") if "Replacement" in args else args.get("ReplacementContent")
    if isinstance(old_t, str) and isinstance(new_t, str):
        return [(old_t, new_t)]
    return None


def check_write_integrity(
    tool_name: str,
    args: dict[str, Any],
    abs_path: str,
    *,
    artifact_dir: str | None = None,
) -> tuple[str, str] | None:
    in_brain = is_brain_or_artifact_path(abs_path, artifact_dir)
    if args.get("ArtifactMetadata") is not None and not in_brain:
        return ("deny", "FM-H08 (ArtifactMetadata Misuse): Omit ArtifactMetadata for files outside the artifact brain directory.")

    existing: str | None = None
    existing_read_err = False
    if os.path.isfile(abs_path):
        try:
            existing = Path(abs_path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            existing = None
            existing_read_err = True

    if tool_name in ("write_file", "write_to_file"):
        new_text = _extract_write_text(args)
        if new_text is None:
            return ("ask", "Could not inspect write content arguments; review required.")
        secret_hit = detect_secret_leak(new_text)
        if secret_hit is not None:
            return ("deny", f"RW-18 (Secret Leak Blocked): Detected {secret_hit} in file write. Store secrets in env vars, never in files.")
        m = FORBIDDEN_CONTROL_RE.search(new_text)
        if m:
            return ("deny", f"FM-H02 (Control-Byte Corruption): Forbidden ASCII byte 0x{ord(m.group(0)):02x} at offset {m.start()}.")
        if LAZY_PLACEHOLDER_RE.search(new_text):
            return ("force_ask", "Lazy placeholder comment (`# ... existing code`) detected; write complete code.")
        if not args.get("Append") and len(new_text.strip()) == 0:
            return ("ask", "Empty file write blocked; truncating to 0 bytes requires review.")
        if not args.get("Append") and existing is not None:
            old_lines = len(existing.replace("\r\n", "\n").splitlines())
            new_lines = len(new_text.replace("\r\n", "\n").splitlines())
            if old_lines >= 20 and (old_lines - new_lines) > old_lines // 2:
                return ("ask", "Broad deletion (>50% of existing lines); review proposed diff.")
        candidate: str | None = (existing + new_text) if (args.get("Append") and existing) else new_text
    elif tool_name in ("edit_file", "replace_file_content", "multi_replace_file_content"):
        if existing_read_err:
            return ("ask", "Existing target file is unreadable or non-UTF-8; review required.")
        pairs = _extract_edit_pairs(args)
        if not pairs:
            return ("ask", "Could not inspect edit target/replacement arguments; review required.")
        candidate = existing
        total_deleted = 0
        for old_text, new_text in pairs:
            if not old_text:
                return ("deny", "FM-H03 (Empty Target): Empty edit target is prohibited.")
            if old_text == new_text:
                return ("deny", "Exact no-op edit (`Target == Replacement`); change the target logic.")
            secret_hit = detect_secret_leak(new_text)
            if secret_hit is not None:
                return ("deny", f"RW-18 (Secret Leak Blocked): Detected {secret_hit} in file edit. Store secrets in env vars, never in files.")
            m = FORBIDDEN_CONTROL_RE.search(new_text)
            if m:
                return ("deny", f"FM-H02 (Control-Byte Corruption): Forbidden ASCII byte 0x{ord(m.group(0)):02x} at offset {m.start()}.")
            if LAZY_PLACEHOLDER_RE.search(new_text):
                return ("force_ask", "Lazy placeholder comment (`# ... existing code`) detected; write complete code.")
            if candidate is not None:
                norm_ex = candidate.replace("\r\n", "\n")
                norm_old = old_text.replace("\r\n", "\n")
                if norm_old not in norm_ex:
                    return ("deny", "FM-H03 (Target Not Found): `Target` does not match existing file text. Read exact target lines first.")
                total_deleted += max(0, len(norm_old.splitlines()) - len(new_text.splitlines()))
                if old_text in candidate:
                    candidate = candidate.replace(old_text, new_text, 1)
                else:
                    candidate = norm_ex.replace(norm_old, new_text.replace("\r\n", "\n"), 1)
        if existing is not None:
            total = len(existing.replace("\r\n", "\n").splitlines())
            if total >= 20 and total_deleted > total // 2:
                return ("ask", "Broad deletion (>50% of existing lines); review proposed diff.")
    else:
        return None

    # Catch split-write (Append=True) and split-edit secret assembly via semantic secret identity
    if isinstance(candidate, str):
        old_hits = _secret_matches(existing) if existing else []
        new_hits = _secret_matches(candidate)
        added_secrets = _newly_introduced(
            new_hits,
            old_hits,
            lambda h: (h[0], hashlib.sha256(h[1].encode("utf-8")).hexdigest()[:16]),
        )
        if added_secrets:
            return ("deny", f"RW-18 (Secret Leak Blocked): Detected {added_secrets[0][0]} in assembled file content. Store secrets in env vars, never in files.")
        if not in_brain:
            from .policy import check_deliverable_hygiene

            hygiene_msg = check_deliverable_hygiene(abs_path, candidate)
            if hygiene_msg is not None:
                return ("ask", hygiene_msg)

    if not abs_path.lower().endswith(".py") or not isinstance(candidate, str):
        return None

    try:
        new_tree, new_audit = _audit_py(candidate, abs_path)
    except SyntaxError as exc:
        return ("deny", f"FM-H02 (Python SyntaxError): Invalid Python syntax at line {exc.lineno}: {exc.msg}.")

    old_tree: ast.AST | None = None
    old_violations: list[AstViolation] = []
    if existing:
        try:
            old_tree, old_audit = _audit_py(existing, abs_path)
            old_violations = old_audit.violations
        except SyntaxError:
            old_tree = None
            old_violations = []

    added_ast = _newly_introduced(new_audit.violations, old_violations, lambda v: v.identity)

    # Preserve exact enforcement precedence: RW-08 -> RW-02 -> (brain exit) -> test/prod rules
    for rule_id in ("RW-08", "RW-02"):
        for v in added_ast:
            if v.rule_id == rule_id:
                return (v.decision, v.message)

    if in_brain:
        return None

    if is_test_file(abs_path):
        for rule_id in ("RW-01", "RW-01-SKIP"):
            for v in added_ast:
                if v.scope_target == "test" and v.rule_id == rule_id:
                    return (v.decision, v.message)
        if _SCRIPTS_ROOT not in sys.path:
            sys.path.insert(0, _SCRIPTS_ROOT)
        try:
            import test_quality_gate

            new_tq = test_quality_gate.check_test_source(candidate, abs_path, tree=new_tree)
            old_tq = (
                test_quality_gate.check_test_source(existing, abs_path, tree=old_tree)
                if existing and old_tree is not None
                else []
            )
            added_tq = _newly_introduced(new_tq, old_tq, lambda f: f.identity)
            if added_tq:
                f0 = added_tq[0]
                return ("deny", f"{f0.rule_id} (Test Quality Gate, line {f0.line}): {f0.message}")
        except ImportError as exc:
            print(f"sentinel ast_gate warning: could not import test_quality_gate ({exc})", file=sys.stderr)
    else:
        for rule_id in ("RW-11", "RW-17"):
            for v in added_ast:
                if v.scope_target == "prod" and v.rule_id == rule_id:
                    return (v.decision, v.message)

    return None
