"""Single-pass Python AST & write-integrity inspector for Sentinel PreToolUse."""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import Any

from .policy import is_brain_or_artifact_path, is_test_file

FORBIDDEN_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
LAZY_PLACEHOLDER_RE = re.compile(r"(?i)(?://|#)\s*\.\.\.\s*(?:existing|unchanged|rest\s+of)\s+code")

_SCRIPTS_ROOT = str(Path(__file__).resolve().parents[1])


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


class _PythonAuditVisitor(ast.NodeVisitor):
    """Collects all AST anti-tampering and quality signals in a single O(N) tree walk."""

    def __init__(self) -> None:
        self.swallowed_exceptions = 0
        self.always_true_eq = False
        self.prod_mock_import = False
        self.harness_detection = False
        self.assert_count = 0
        self.skip_count = 0
        self.has_test_cheat = False

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        is_broad = node.type is None or (
            isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException")
        )
        if node.body and all(_is_noop_stmt(s) for s in node.body):
            self.swallowed_exceptions += 1
        elif is_broad and len(node.body) == 1 and isinstance(node.body[0], ast.Return):
            val = node.body[0].value
            if val is None or (isinstance(val, ast.Constant) and val.value in (None, False)) or (
                isinstance(val, (ast.List, ast.Dict, ast.Tuple)) and not getattr(val, "elts", getattr(val, "keys", None))
            ):
                self.swallowed_exceptions += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            call = item.context_expr
            if isinstance(call, ast.Call):
                fn = call.func
                if (isinstance(fn, ast.Name) and fn.id == "suppress") or (
                    isinstance(fn, ast.Attribute) and fn.attr == "suppress"
                ):
                    self.swallowed_exceptions += 1
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if node.name == "__eq__" and len(node.args.args) >= 2:
            if len(node.body) == 1 and isinstance(node.body[0], ast.Return):
                val = node.body[0].value
                if isinstance(val, ast.Constant) and val.value is True:
                    self.always_true_eq = True
        for dec in node.decorator_list:
            dname = ""
            if isinstance(dec, ast.Attribute):
                dname = dec.attr
            elif isinstance(dec, ast.Name):
                dname = dec.id
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Attribute):
                    dname = dec.func.attr
                elif isinstance(dec.func, ast.Name):
                    dname = dec.func.id
            if dname.lower() in ("skip", "skipif", "skipunless", "xfail"):
                self.skip_count += 1
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "unittest.mock" or alias.name.startswith("unittest.mock."):
                self.prod_mock_import = True

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and (node.module == "unittest.mock" or node.module.startswith("unittest.mock.")):
            self.prod_mock_import = True

    def visit_Assert(self, node: ast.Assert) -> None:
        self.assert_count += 1
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            self.has_test_cheat = True
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        fn = node.func
        if isinstance(fn, ast.Attribute):
            if fn.attr.startswith("assert"):
                self.assert_count += 1
                if fn.attr == "assertTrue" and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value is True:
                    self.has_test_cheat = True
            elif fn.attr == "skipTest":
                self.skip_count += 1
            elif fn.attr == "exit" and isinstance(fn.value, ast.Name) and fn.value.id == "sys":
                if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 0:
                    self.has_test_cheat = True
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if node.value == "PYTEST_CURRENT_TEST":
            self.harness_detection = True


def _audit_py(source: str, filename: str = "<candidate>") -> _PythonAuditVisitor:
    tree = ast.parse(source, filename=filename)
    visitor = _PythonAuditVisitor()
    visitor.visit(tree)
    return visitor


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
    if os.path.isfile(abs_path):
        try:
            existing = Path(abs_path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            existing = None

    if tool_name in ("write_file", "write_to_file"):
        new_text = _extract_write_text(args)
        if new_text is None:
            return ("ask", "Could not inspect write content arguments; review required.")
        m = FORBIDDEN_CONTROL_RE.search(new_text)
        if m:
            return ("deny", f"FM-H02 (Control-Byte Corruption): Forbidden ASCII byte 0x{ord(m.group(0)):02x} at offset {m.start()}.")
        if LAZY_PLACEHOLDER_RE.search(new_text):
            return ("force_ask", "Lazy placeholder comment (`# ... existing code`) detected; write complete code.")
        if not args.get("Append") and len(new_text.strip()) == 0:
            return ("ask", "Empty file write blocked; truncating to 0 bytes requires review.")
        candidate: str | None = (existing + new_text) if (args.get("Append") and existing) else new_text
    elif tool_name in ("edit_file", "replace_file_content", "multi_replace_file_content"):
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

    if not abs_path.lower().endswith(".py") or not isinstance(candidate, str):
        return None

    try:
        new_audit = _audit_py(candidate, abs_path)
    except SyntaxError as exc:
        return ("deny", f"FM-H02 (Python SyntaxError): Invalid Python syntax at line {exc.lineno}: {exc.msg}.")

    old_audit: _PythonAuditVisitor | None = None
    if existing:
        try:
            old_audit = _audit_py(existing, abs_path)
        except SyntaxError:
            old_audit = None

    if new_audit.swallowed_exceptions > (old_audit.swallowed_exceptions if old_audit else 0):
        return ("ask", "RW-08 (Swallowed Exception): Edit introduces silent exception suppression (`except: pass`, `return None`, or `suppress`).")

    if new_audit.always_true_eq and not (old_audit and old_audit.always_true_eq):
        return ("deny", "RW-02 (Reward Hacking Blocked): Defining `def __eq__(self, other): return True` is prohibited.")

    if in_brain:
        return None

    if is_test_file(abs_path):
        if new_audit.has_test_cheat:
            return ("deny", "RW-01 (Test Tampering Blocked): Test introduces `assert True`, `assertTrue(True)`, or `sys.exit(0)`.")
        if new_audit.skip_count > (old_audit.skip_count if old_audit else 0):
            return ("ask", "RW-01 (Test Skip Introduced): Adding `@skip` / `skipTest` / `xfail` requires review.")
        if _SCRIPTS_ROOT not in sys.path:
            sys.path.insert(0, _SCRIPTS_ROOT)
        try:
            import test_quality_gate
            findings = test_quality_gate.check_test_source(candidate, abs_path)
            if findings:
                f0 = findings[0]
                return ("deny", f"{f0.rule_id} (Test Quality Gate, line {f0.line}): {f0.message}")
        except ImportError as exc:
            print(f"sentinel ast_gate warning: could not import test_quality_gate ({exc})", file=sys.stderr)
    else:
        if new_audit.prod_mock_import and not (old_audit and old_audit.prod_mock_import):
            return ("ask", "RW-11 (Production Mock Injection): Importing `unittest.mock` inside production module.")
        if new_audit.harness_detection and not (old_audit and old_audit.harness_detection):
            return ("deny", "RW-17 (Test-Harness Detection Blocked): Production code inspects test runner environment.")

    return None
