"""Single-pass Python AST & write-integrity inspector for Sentinel PreToolUse."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Any

from .policy import is_test_file

FORBIDDEN_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
LAZY_PLACEHOLDER_RE = re.compile(r"(?i)(?://|#)\s*\.\.\.\s*(?:existing|unchanged|rest\s+of)\s+code")


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
            if val is None or (isinstance(val, ast.Constant) and val.value in (None, False)) or isinstance(val, (ast.List, ast.Dict, ast.Tuple)) and not getattr(val, "elts", getattr(val, "keys", None)):
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

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name == "__eq__" and len(node.args.args) >= 2:
            other_name = node.args.args[1].arg
            if len(node.body) == 1 and isinstance(node.body[0], ast.Return):
                ret = node.body[0].value
                if isinstance(ret, ast.Constant) and ret.value is True:
                    self.always_true_eq = True
                elif ret is not None and not any(
                    isinstance(sub, ast.Name) and sub.id == other_name for sub in ast.walk(ret)
                ):
                    self.always_true_eq = True
        for dec in node.decorator_list:
            dec_src = ast.unparse(dec) if hasattr(ast, "unparse") else ""
            if any(tok in dec_src for tok in ("skip", "xfail")):
                self.skip_count += 1
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "unittest.mock" or alias.name.startswith("unittest.mock."):
                self.prod_mock_import = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and (node.module == "unittest.mock" or node.module.startswith("unittest.mock.")):
            self.prod_mock_import = True
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self.assert_count += 1
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            self.has_test_cheat = True
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        fn = node.func
        attr = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
        if attr.startswith("assert") or attr == "raises":
            self.assert_count += 1
            if attr == "assertTrue" and len(node.args) == 1 and isinstance(node.args[0], ast.Constant) and node.args[0].value is True:
                self.has_test_cheat = True
        if attr in ("skipTest", "skip", "xfail"):
            self.skip_count += 1
        if attr == "exit" and isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "sys":
            if not node.args or (isinstance(node.args[0], ast.Constant) and node.args[0].value == 0):
                self.has_test_cheat = True
        if attr == "_getframe" and isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "sys":
            self.harness_detection = True
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if node.value == "PYTEST_CURRENT_TEST":
            self.harness_detection = True


def _audit_py(source: str, filename: str = "<candidate>") -> _PythonAuditVisitor:
    tree = ast.parse(source, filename=filename)
    visitor = _PythonAuditVisitor()
    visitor.visit(tree)
    return visitor


def check_write_integrity(tool_name: str, args: dict[str, Any], abs_path: str) -> tuple[str, str] | None:
    if args.get("ArtifactMetadata") is not None and "/.gemini/antigravity/brain/" not in abs_path.replace("\\", "/").lower():
        return ("deny", "FM-H08 (ArtifactMetadata Misuse): Omit ArtifactMetadata for files outside .gemini/antigravity/brain/.")

    existing: str | None = None
    if os.path.isfile(abs_path):
        try:
            existing = Path(abs_path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            existing = None

    if tool_name == "write_file":
        new_text = args.get("Content")
        if not isinstance(new_text, str):
            return None
        m = FORBIDDEN_CONTROL_RE.search(new_text)
        if m:
            return ("deny", f"FM-H02 (Control-Byte Corruption): Forbidden ASCII byte 0x{ord(m.group(0)):02x} at offset {m.start()}.")
        if LAZY_PLACEHOLDER_RE.search(new_text):
            return ("force_ask", "Lazy placeholder comment (`# ... existing code`) detected; write complete code.")
        if not args.get("Append") and len(new_text.strip()) == 0:
            return ("ask", "Empty file write blocked; truncating to 0 bytes requires review.")
        candidate = (existing + new_text) if (args.get("Append") and existing) else new_text
    elif tool_name == "edit_file":
        old_text = args.get("Target")
        new_text = args.get("Replacement")
        if not isinstance(old_text, str) or not isinstance(new_text, str):
            return None
        if old_text == new_text:
            return ("deny", "Exact no-op edit (`Target == Replacement`); change the target logic.")
        m = FORBIDDEN_CONTROL_RE.search(new_text)
        if m:
            return ("deny", f"FM-H02 (Control-Byte Corruption): Forbidden ASCII byte 0x{ord(m.group(0)):02x} at offset {m.start()}.")
        if LAZY_PLACEHOLDER_RE.search(new_text):
            return ("force_ask", "Lazy placeholder comment (`# ... existing code`) detected; write complete code.")
        if existing is not None:
            norm_ex = existing.replace("\r\n", "\n")
            norm_old = old_text.replace("\r\n", "\n")
            if norm_old not in norm_ex:
                return ("deny", "FM-H03 (Target Not Found): `Target` does not match existing file text. Read exact target lines first.")
            deleted = max(0, len(norm_old.splitlines()) - len(new_text.splitlines()))
            total = len(norm_ex.splitlines())
            if total >= 20 and deleted > total // 2:
                return ("ask", "Broad deletion (>50% of existing lines); review proposed diff.")
            candidate = existing.replace(old_text, new_text) if old_text in existing else norm_ex.replace(norm_old, new_text.replace("\r\n", "\n"))
        else:
            candidate = None
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

    in_brain = "/.gemini/antigravity/" in abs_path.replace("\\", "/").lower()
    if in_brain:
        return None

    if is_test_file(abs_path):
        if new_audit.has_test_cheat:
            return ("deny", "RW-01 (Test Tampering Blocked): Test introduces `assert True`, `assertTrue(True)`, or `sys.exit(0)`.")
        if new_audit.skip_count > (old_audit.skip_count if old_audit else 0):
            return ("ask", "RW-01 (Test Skip Introduced): Adding `@skip` / `skipTest` / `xfail` requires review.")
        if old_audit and new_audit.assert_count < old_audit.assert_count:
            return ("ask", f"RW-01 (Assertion Weakening): Reduces assertions from {old_audit.assert_count} to {new_audit.assert_count}.")
        try:
            import test_quality_gate
            findings = test_quality_gate.check_test_source(candidate, abs_path)
            if findings:
                f0 = findings[0]
                return ("deny", f"{f0.rule_id} (Test Quality Gate, line {f0.line}): {f0.message}")
        except ImportError:
            pass
    else:
        if new_audit.prod_mock_import and not (old_audit and old_audit.prod_mock_import):
            return ("ask", "RW-11 (Production Mock Injection): Importing `unittest.mock` inside production module.")
        if new_audit.harness_detection and not (old_audit and old_audit.harness_detection):
            return ("deny", "RW-17 (Test-Harness Detection Blocked): Production code inspects test runner environment.")

    return None
