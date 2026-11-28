#!/usr/bin/env python3
"""Mechanical AST quality gate for Python tests (TQ-01..TQ-05).

Enforces structural test rigor at write/edit time (PreToolUse) and via CLI:
- TQ-01: No zero-assertion or tautological tests (assert True, assert x == x).
- TQ-02: No unconditional skips (@unittest.skip / @pytest.mark.skip) or hidden dead tests.
- TQ-03: No machine-coupled user home paths or hardcoded local session UUIDs.
- TQ-04: No skipped execution flags (execute_hooks=False) without live execution tests,
         and no mocking out integration/end-to-end boundaries.
- TQ-05: Every test module (>=2 tests) must include negative/failure-path assertions.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

TEST_FILENAME_RE = re.compile(r"^(?:test_.*|.*_test)\.py$", re.IGNORECASE)
USER_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[/\\]{1,2}Users[/\\]{1,2}[^/\\\s'\"]+|/home/[^/\s'\"]+/|[A-Za-z]:[/\\]{1,2}Kageyoni\b)",
    re.IGNORECASE,
)
SESSION_UUID_RE = re.compile(
    r"(?:session_id|conversation_id|brain[/\\])\s*[=:/\\]?\s*['\"]?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
NEGATIVE_TOKEN_RE = re.compile(
    r"\b(?:assertFalse|assertNotEqual|assertNotIn|assertIsNone|assertRaises|raises|fail|"
    r"BLOCKED|FAIL|deny|abstained|invalid|missing|error|mismatch|"
    r"returncode\s*!=\s*0|returncode,\s*[1-9])\b"
)

ASSERT_METHOD_NAMES = {
    "assertEqual",
    "assertNotEqual",
    "assertTrue",
    "assertFalse",
    "assertIs",
    "assertIsNot",
    "assertIsNone",
    "assertIsNotNone",
    "assertIn",
    "assertNotIn",
    "assertIsInstance",
    "assertNotIsInstance",
    "assertRaises",
    "assertRaisesRegex",
    "assertWarns",
    "assertAlmostEqual",
    "assertGreater",
    "assertGreaterEqual",
    "assertLess",
    "assertLessEqual",
    "assertRegex",
    "assertCountEqual",
    "fail",
    "raises",
}


@dataclass(frozen=True)
class TestQualityFinding:
    rule_id: str
    file: str
    line: int
    message: str
    symbol: str = "<module>"
    kind: str = ""

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.rule_id, self.symbol, self.kind or self.message)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def is_test_file(path: str | Path) -> bool:
    return bool(TEST_FILENAME_RE.match(Path(path).name))


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    if isinstance(node, ast.Attribute):
        parent = _decorator_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _call_name(node: ast.Call) -> str:
    return _decorator_name(node.func)


def _is_constant_expr(expr: ast.expr) -> bool:
    return not any(isinstance(n, (ast.Name, ast.Call, ast.Attribute, ast.Subscript)) for n in ast.walk(expr))


def _is_tautological_compare(expr: ast.expr) -> bool:
    if isinstance(expr, ast.Constant):
        return bool(expr.value) is True
    if _is_constant_expr(expr):
        return True
    if isinstance(expr, ast.BoolOp) and isinstance(expr.op, ast.Or):
        if any(isinstance(v, ast.Constant) and bool(v.value) is True for v in expr.values):
            return True
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1 and len(expr.comparators) == 1:
        if isinstance(expr.ops[0], (ast.Eq, ast.Is)):
            return ast.dump(expr.left) == ast.dump(expr.comparators[0])
    return False


def _is_tautological_assert_call(call: ast.Call) -> bool:
    cname = _call_name(call)
    tail = cname.split(".")[-1]
    if tail == "fail":
        return False
    if tail in ASSERT_METHOD_NAMES and call.args and all(_is_constant_expr(a) for a in call.args):
        return True
    if tail == "assertTrue" and call.args and _is_tautological_compare(call.args[0]):
        return True
    if cname.endswith(("assertEqual", "assertIs")) and len(call.args) >= 2:
        return ast.dump(call.args[0]) == ast.dump(call.args[1])
    return False


def _inspect_assertions(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[bool, list[int]]:
    assertion_count = 0
    tautology_lines: list[int] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            if _is_tautological_compare(node.test):
                tautology_lines.append(node.lineno)
            else:
                assertion_count += 1
        elif isinstance(node, ast.Call):
            cname = _call_name(node)
            tail = cname.split(".")[-1]
            if tail in ASSERT_METHOD_NAMES or tail.startswith(("assert_", "check_", "verify_")):
                if _is_tautological_assert_call(node):
                    tautology_lines.append(node.lineno)
                else:
                    assertion_count += 1
    return assertion_count > 0, tautology_lines


def _is_unconditional_skip_decorator(dec: ast.expr) -> bool:
    dname = _decorator_name(dec)
    if dname in ("unittest.skip", "skip", "pytest.mark.skip"):
        return True
    if isinstance(dec, ast.Call) and dec.args and isinstance(dec.args[0], ast.Constant):
        if dname in ("unittest.skipIf", "skipIf", "pytest.mark.skipif") and dec.args[0].value is True:
            return True
        if dname in ("unittest.skipUnless", "skipUnless") and dec.args[0].value is False:
            return True
    return False


def _find_unconditional_skip_in_stmts(stmts: list[ast.stmt]) -> int | None:
    for stmt in stmts:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            if _call_name(stmt.value) in ("pytest.skip", "self.skipTest"):
                return stmt.lineno
        elif isinstance(stmt, ast.If) and isinstance(stmt.test, ast.Constant) and bool(stmt.test.value) is True:
            hit = _find_unconditional_skip_in_stmts(stmt.body)
            if hit is not None:
                return hit
    return None


def _has_unconditional_skip(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    for dec in fn.decorator_list:
        if _is_unconditional_skip_decorator(dec):
            return dec.lineno
    return _find_unconditional_skip_in_stmts(fn.body)


def _strip_comments(source: str) -> str:
    import io
    import tokenize

    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        kept = [tok for tok in tokens if tok.type != tokenize.COMMENT]
        return tokenize.untokenize(kept)
    except (tokenize.TokenError, IndentationError):
        return "\n".join(line.split("#", 1)[0] for line in source.splitlines())


def _collect_scoped_tests(
    node: ast.AST,
    prefix: str = "",
) -> tuple[list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]], list[tuple[str, ast.ClassDef]]]:
    funcs: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    classes: list[tuple[str, ast.ClassDef]] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            cls_scope = f"{prefix}.{child.name}" if prefix else child.name
            classes.append((cls_scope, child))
            sub_f, sub_c = _collect_scoped_tests(child, cls_scope)
            funcs.extend(sub_f)
            classes.extend(sub_c)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_scope = f"{prefix}.{child.name}" if prefix else child.name
            if child.name.startswith("test_"):
                funcs.append((fn_scope, child))
            sub_f, sub_c = _collect_scoped_tests(child, fn_scope)
            funcs.extend(sub_f)
            classes.extend(sub_c)
        else:
            sub_f, sub_c = _collect_scoped_tests(child, prefix)
            funcs.extend(sub_f)
            classes.extend(sub_c)
    return funcs, classes


def check_test_source(
    source: str,
    filename: str = "test_unknown.py",
    *,
    tree: ast.AST | None = None,
) -> list[TestQualityFinding]:
    """Audit Python test source text and return TQ-01..TQ-05 violations with semantic identities."""
    findings: list[TestQualityFinding] = []
    if tree is None:
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as exc:
            findings.append(
                TestQualityFinding("TQ-SYNTAX", filename, exc.lineno or 1, f"Invalid Python syntax: {exc.msg}", "<module>", "syntax")
            )
            return findings

    scoped_funcs, scoped_classes = _collect_scoped_tests(tree)
    for cls_scope, cls_node in scoped_classes:
        has_tests = any(
            isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)) and b.name.startswith("test_")
            for b in ast.walk(cls_node)
            if b is not cls_node
        )
        if has_tests:
            for dec in cls_node.decorator_list:
                if _is_unconditional_skip_decorator(dec):
                    findings.append(
                        TestQualityFinding(
                            "TQ-02",
                            filename,
                            dec.lineno,
                            f"Test class `{cls_node.name}` uses an unconditional skip; remove or gate on a real platform/capability predicate.",
                            cls_scope,
                            "unconditional_skip",
                        )
                    )

    if not scoped_funcs:
        findings.append(
            TestQualityFinding("TQ-01", filename, 1, "Test file defines zero `test_*` functions.", "<module>", "zero_test_funcs")
        )
        return findings

    # TQ-01 & TQ-02 per test function
    for fn_scope, fn in scoped_funcs:
        skip_line = _has_unconditional_skip(fn)
        if skip_line is not None:
            findings.append(
                TestQualityFinding(
                    "TQ-02",
                    filename,
                    skip_line,
                    f"`{fn.name}` uses an unconditional skip; remove or gate on a real platform/capability predicate.",
                    fn_scope,
                    "unconditional_skip",
                )
            )
        has_assert, tautology_lines = _inspect_assertions(fn)
        if tautology_lines:
            for tline in tautology_lines:
                findings.append(
                    TestQualityFinding(
                        "TQ-01",
                        filename,
                        tline,
                        f"`{fn.name}` contains a tautological assertion (e.g. `assert True` or `x == x`).",
                        fn_scope,
                        "tautology",
                    )
                )
        elif not has_assert:
            findings.append(
                TestQualityFinding(
                    "TQ-01",
                    filename,
                    fn.lineno,
                    f"`{fn.name}` has zero assertions or failure expectations.",
                    fn_scope,
                    "zero_assertions",
                )
            )

    # TQ-03: Machine-coupled paths or local session UUIDs
    code_only = _strip_comments(source)
    for ln, line in enumerate(code_only.splitlines(), 1):
        m_path = USER_PATH_RE.search(line)
        if m_path:
            findings.append(
                TestQualityFinding(
                    "TQ-03",
                    filename,
                    ln,
                    f"Hardcoded machine-specific path `{m_path.group(0)}`; use tempdir/tmp_path fixtures for portability.",
                    "<module>",
                    f"user_path:{m_path.group(0).lower()}",
                )
            )
        m_uuid = SESSION_UUID_RE.search(line)
        if m_uuid:
            findings.append(
                TestQualityFinding(
                    "TQ-03",
                    filename,
                    ln,
                    "Hardcoded local session UUID; build a synthetic session fixture inside tempdir/tmp_path.",
                    "<module>",
                    f"session_uuid:{m_uuid.group(0).lower()}",
                )
            )

    # TQ-04: Skipped live hook execution without sibling real execution, or mocked e2e claims
    has_exec_false = False
    has_exec_true = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "execute_hooks" and isinstance(kw.value, ast.Constant):
                    if kw.value.value is False:
                        has_exec_false = True
                    elif kw.value.value is True:
                        has_exec_true = True
    if not has_exec_false and re.search(r"--skip-exec", code_only):
        has_exec_false = True
    if has_exec_false and not has_exec_true:
        findings.append(
            TestQualityFinding(
                "TQ-04",
                filename,
                1,
                "Tests pass `execute_hooks=False` / `--skip-exec` without any sibling test executing `execute_hooks=True`.",
                "<module>",
                "skip_exec_without_live",
            )
        )

    for fn_scope, fn in scoped_funcs:
        if "live" not in fn.name.lower():
            continue
        fn_exec_false = False
        fn_exec_true = False
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "execute_hooks" and isinstance(kw.value, ast.Constant):
                        if kw.value.value is False:
                            fn_exec_false = True
                        elif kw.value.value is True:
                            fn_exec_true = True
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "--skip-exec" in node.value:
                fn_exec_false = True
        if fn_exec_false and not fn_exec_true:
            findings.append(
                TestQualityFinding(
                    "TQ-04",
                    filename,
                    fn.lineno,
                    f"`{fn.name}` claims live coverage while passing `execute_hooks=False` / `--skip-exec`.",
                    fn_scope,
                    "live_test_skip_exec",
                )
            )

    lower_name = Path(filename).name.lower()
    claims_e2e = any(tok in lower_name for tok in ("e2e", "end_to_end", "integration")) or bool(
        re.search(r"end-to-end|integration", (ast.get_docstring(tree) or ""), re.IGNORECASE)
    )
    uses_mock = bool(re.search(r"\b(?:unittest\.mock|MagicMock|monkeypatch\.setattr)\b", code_only))
    if not uses_mock:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "unittest" and any(a.name == "mock" for a in node.names):
                uses_mock = True
                break
    if claims_e2e and uses_mock:
        findings.append(
            TestQualityFinding(
                "TQ-04",
                filename,
                1,
                "Test module claims end-to-end/integration coverage while importing mock/monkeypatch.",
                "<module>",
                "e2e_uses_mock",
            )
        )

    # TQ-05: Falsifiability — >=2 tests must include at least one negative/rejection check in assertions or raises
    if len(scoped_funcs) >= 2:
        has_negative = False
        neg_parts: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                t = node.test
                if isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not):
                    has_negative = True
                    break
                if isinstance(t, ast.Compare) and any(isinstance(op, (ast.NotEq, ast.NotIn, ast.IsNot)) for op in t.ops):
                    has_negative = True
                    break
                if isinstance(t, ast.Compare) and any(isinstance(op, ast.Is) for op in t.ops) and any(
                    isinstance(c, ast.Constant) and c.value in (False, None) for c in t.comparators
                ):
                    has_negative = True
                    break
                seg = ast.get_source_segment(source, node)
                if seg:
                    neg_parts.append(seg)
            elif isinstance(node, ast.Call):
                seg = ast.get_source_segment(source, node)
                if seg:
                    neg_parts.append(seg)
        if not has_negative and not NEGATIVE_TOKEN_RE.search("\n".join(neg_parts)):
            findings.append(
                TestQualityFinding(
                    "TQ-05",
                    filename,
                    1,
                    "Test suite only exercises positive/happy paths; add at least one negative/rejection/failure-path test.",
                    "<module>",
                    "missing_negative_test",
                )
            )

    return findings


def audit_paths(paths: Iterable[Path]) -> list[TestQualityFinding]:
    all_findings: list[TestQualityFinding] = []
    for p in paths:
        target = p.resolve()
        files = (
            sorted(f for f in target.rglob("*.py") if is_test_file(f) and ".git" not in f.parts)
            if target.is_dir()
            else ([target] if target.is_file() else [])
        )
        for f in files:
            text = f.read_text(encoding="utf-8", errors="replace")
            all_findings.extend(check_test_source(text, str(f)))
    return all_findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mechanical AST quality gate for Python tests.")
    parser.add_argument("targets", nargs="+", type=Path, help="Test files or directories to audit.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    findings = audit_paths(args.targets)
    if args.json:
        print(
            json.dumps(
                {"ok": not findings, "count": len(findings), "findings": [f.to_dict() for f in findings]},
                indent=2,
            )
        )
    else:
        if not findings:
            print("PASS: All audited test files satisfy TQ-01..TQ-05.")
        else:
            for f in findings:
                print(f"[{f.rule_id}] {f.file}:{f.line}: {f.message}")
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
