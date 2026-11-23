#!/usr/bin/env python3
"""
Fast, zero-dependency Python 3 AST Code Dependency Graph & Forensic Reality Scanner.

Provides:
- Module metadata extraction (relative path, line count, imports, syntax errors)
- Symbol definitions with line ranges and Forensic Status (WIRED vs HOLLOW_STUB)
- Bidirectional Call Graph index (calls & called_by with exact file and line numbers)
- CLI modes: --summary, --callers <symbol>, --forensic, --out <json_path>
"""

from __future__ import annotations

import argparse
import ast
import builtins
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

BUILTIN_NAMES: Set[str] = set(dir(builtins))

EXCLUDED_DIRS: Set[str] = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "external_repos",
    ".gemini",
}

DEFAULT_MAX_FILES = 2000
STUB_COMMENT_RE = re.compile(r"#.*\b(TODO|FIXME|STUB|HACK|XXX)\b", re.IGNORECASE)

BUILTIN_CONTAINER_ATTRS: Set[str] = {
    "get",
    "setdefault",
    "append",
    "extend",
    "insert",
    "pop",
    "remove",
    "clear",
    "copy",
    "update",
    "items",
    "keys",
    "values",
    "split",
    "rsplit",
    "splitlines",
    "strip",
    "lstrip",
    "rstrip",
    "join",
    "replace",
    "format",
    "lower",
    "upper",
    "startswith",
    "endswith",
    "find",
    "index",
    "count",
    "encode",
    "decode",
    "add",
    "discard",
    "union",
    "intersection",
    "difference",
    "sort",
    "reverse",
}


def discover_python_files(
    root: Path,
    excluded_dirs: Optional[Set[str]] = None,
    max_files: int = DEFAULT_MAX_FILES,
) -> Tuple[List[Path], bool]:
    """Walk root directory pruning excluded directories and return up to max_files .py files."""
    skip = excluded_dirs if excluded_dirs is not None else EXCLUDED_DIRS
    py_files: List[Path] = []
    capped = False

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        # Prune excluded directories in-place for speed
        dirnames[:] = sorted(
            d for d in dirnames if d not in skip and not d.startswith(".venv")
        )
        for fname in sorted(filenames):
            if fname.endswith(".py"):
                py_files.append(Path(dirpath) / fname)
                if len(py_files) >= max_files:
                    capped = True
                    return py_files, capped

    return py_files, capped


def _is_docstring_stmt(stmt: ast.stmt) -> bool:
    """Return True if stmt is a string literal expression (docstring)."""
    if isinstance(stmt, ast.Expr):
        val = stmt.value
        if isinstance(val, ast.Constant) and isinstance(val.value, str):
            return True
    return False


def _is_dead_underscore_assign(stmt: ast.stmt) -> bool:
    """Return True if stmt assigns purely to '_' (e.g. `_ = arg` or `_ = (a, b)`)."""
    if isinstance(stmt, ast.Assign):
        if all(
            isinstance(t, ast.Name) and t.id == "_"
            for t in stmt.targets
        ):
            return True
    elif isinstance(stmt, ast.AnnAssign):
        if isinstance(stmt.target, ast.Name) and stmt.target.id == "_":
            return True
    return False


def _is_ellipsis_stmt(stmt: ast.stmt) -> bool:
    """Return True if stmt is `...` (Ellipsis)."""
    if isinstance(stmt, ast.Expr):
        val = stmt.value
        if isinstance(val, ast.Constant) and val.value is Ellipsis:
            return True
    return False


def _is_not_implemented_raise(stmt: ast.stmt) -> bool:
    """Return True if stmt raises NotImplementedError or NotImplemented."""
    if not isinstance(stmt, ast.Raise) or stmt.exc is None:
        return False
    exc = stmt.exc
    if isinstance(exc, ast.Name) and exc.id in ("NotImplementedError", "NotImplemented"):
        return True
    if isinstance(exc, ast.Call):
        func = exc.func
        if isinstance(func, ast.Name) and func.id in ("NotImplementedError", "NotImplemented"):
            return True
        if isinstance(func, ast.Attribute) and func.attr in ("NotImplementedError", "NotImplemented"):
            return True
    return False


def _is_trivial_return_value(val: Optional[ast.expr]) -> bool:
    """Return True if return value is None, bool, 0, empty string, or empty literal container."""
    if val is None:
        return True
    if isinstance(val, ast.Constant):
        if val.value is None or isinstance(val.value, bool):
            return True
        if val.value in (0, 0.0, "", b""):
            return True
    if isinstance(val, (ast.List, ast.Tuple, ast.Set)) and len(val.elts) == 0:
        return True
    if isinstance(val, ast.Dict) and len(val.keys) == 0:
        return True
    return False


def _has_stub_comment_nearby(
    lines: List[str], start_lineno: int, end_lineno: int
) -> bool:
    """Check lines around [start_lineno - 1, end_lineno + 1] for TODO/FIXME/STUB comments."""
    lo = max(1, start_lineno - 1)
    hi = min(len(lines), end_lineno + 1)
    for idx in range(lo - 1, hi):
        if STUB_COMMENT_RE.search(lines[idx]):
            return True
    return False


def classify_function_forensic_status(
    node: ast.AST, source_lines: List[str]
) -> str:
    """
    Classify a FunctionDef or AsyncFunctionDef as 'HOLLOW_STUB' or 'WIRED'.

    HOLLOW_STUB criteria (after stripping leading docstring and dead `_ = ...` assignments):
    - Empty effective body (e.g. docstring only)
    - Consists only of `pass`, `...` (Ellipsis), or `raise NotImplementedError(...)`
    - Single return of a trivial constant with a TODO/FIXME/STUB comment inside the function
    """
    body: List[ast.stmt] = getattr(node, "body", [])
    effective_stmts: List[ast.stmt] = []
    for idx, stmt in enumerate(body):
        if idx == 0 and _is_docstring_stmt(stmt):
            continue
        if _is_dead_underscore_assign(stmt):
            continue
        effective_stmts.append(stmt)

    if not effective_stmts:
        return "HOLLOW_STUB"

    # Check if all effective statements are pass / ... / raise NotImplementedError
    all_noop = True
    for stmt in effective_stmts:
        if (
            isinstance(stmt, ast.Pass)
            or _is_ellipsis_stmt(stmt)
            or _is_not_implemented_raise(stmt)
        ):
            continue
        all_noop = False
        break

    if all_noop:
        return "HOLLOW_STUB"

    # Check if single trivial return accompanied by TODO/FIXME/STUB comment
    if len(effective_stmts) == 1 and isinstance(effective_stmts[0], ast.Return):
        ret_stmt = effective_stmts[0]
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)
        if _is_trivial_return_value(ret_stmt.value) and _has_stub_comment_nearby(
            source_lines, start_line, end_line
        ):
            return "HOLLOW_STUB"

    return "WIRED"


def classify_class_forensic_status(
    node: ast.ClassDef, method_statuses: List[str]
) -> str:
    """
    Classify a ClassDef as 'HOLLOW_STUB' or 'WIRED'.
    If a class has methods, it is WIRED if at least one method is WIRED, otherwise HOLLOW_STUB.
    If a class has no methods, check if its body has only docstring/pass/ellipsis.
    """
    if method_statuses:
        return "WIRED" if any(s == "WIRED" for s in method_statuses) else "HOLLOW_STUB"

    effective_stmts: List[ast.stmt] = []
    for idx, stmt in enumerate(node.body):
        if idx == 0 and _is_docstring_stmt(stmt):
            continue
        if isinstance(stmt, ast.Pass) or _is_ellipsis_stmt(stmt):
            continue
        effective_stmts.append(stmt)

    return "WIRED" if effective_stmts else "HOLLOW_STUB"


def _extract_call_name(func_expr: ast.expr) -> Optional[Tuple[str, Optional[str]]]:
    """
    Extract (short_name, receiver_or_prefix) from an ast.Call.func expression.
    Examples:
      foo() -> ("foo", None)
      self.bar() -> ("bar", "self")
      pkg.mod.baz() -> ("baz", "pkg.mod")
    """
    if isinstance(func_expr, ast.Name):
        return func_expr.id, None
    if isinstance(func_expr, ast.Attribute):
        attr = func_expr.attr
        prefix_parts: List[str] = []
        curr = func_expr.value
        while isinstance(curr, ast.Attribute):
            prefix_parts.append(curr.attr)
            curr = curr.value
        if isinstance(curr, ast.Name):
            prefix_parts.append(curr.id)
            prefix_parts.reverse()
            return attr, ".".join(prefix_parts)
        return attr, "<expr>"
    return None


class _CallCollector(ast.NodeVisitor):
    """Collect ast.Call expressions within a single scope without descending into nested defs."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, Optional[str], int]] = []

    def visit_Call(self, node: ast.Call) -> None:
        extracted = _extract_call_name(node.func)
        if extracted is not None:
            name, prefix = extracted
            self.calls.append((name, prefix, getattr(node, "lineno", 1)))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Do not descend into nested functions; they are visited as their own scopes
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return


def _collect_scope_calls(stmts: List[ast.stmt]) -> List[Tuple[str, Optional[str], int]]:
    collector = _CallCollector()
    for stmt in stmts:
        collector.visit(stmt)
    return collector.calls


def extract_imports(tree: ast.Module) -> List[Dict[str, Any]]:
    """Extract all import and from-import statements from an AST module."""
    imports: List[Dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    {
                        "type": "import",
                        "module": alias.name,
                        "name": alias.name,
                        "asname": alias.asname,
                        "lineno": getattr(node, "lineno", 1),
                    }
                )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            level = node.level or 0
            prefix = ("." * level) + mod
            for alias in node.names:
                imports.append(
                    {
                        "type": "from",
                        "module": prefix,
                        "name": alias.name,
                        "asname": alias.asname,
                        "lineno": getattr(node, "lineno", 1),
                    }
                )
    imports.sort(key=lambda x: x["lineno"])
    return imports


def parse_python_file(file_path: Path, rel_path: str) -> Dict[str, Any]:
    """Parse a single Python file and extract module metadata, symbols, and raw call sites."""
    try:
        raw_bytes = file_path.read_bytes()
        source = raw_bytes.decode("utf-8-sig", errors="replace")
    except Exception as exc:
        return {
            "path": rel_path,
            "line_count": 0,
            "imports": [],
            "syntax_error": f"IOError: {exc}",
            "symbols": [],
            "raw_calls": [],
        }

    source_lines = source.splitlines()
    line_count = len(source_lines)

    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as exc:
        return {
            "path": rel_path,
            "line_count": line_count,
            "imports": [],
            "syntax_error": f"SyntaxError at line {exc.lineno}: {exc.msg}",
            "symbols": [],
            "raw_calls": [],
        }
    except Exception as exc:
        return {
            "path": rel_path,
            "line_count": line_count,
            "imports": [],
            "syntax_error": f"ParseError: {exc}",
            "symbols": [],
            "raw_calls": [],
        }

    imports = extract_imports(tree)
    symbols: List[Dict[str, Any]] = []
    raw_calls: List[Dict[str, Any]] = []

    def process_function(
        fn_node: ast.AST,
        parent_class: Optional[str] = None,
        outer_func: Optional[str] = None,
    ) -> str:
        fn_name = getattr(fn_node, "name", "<anonymous>")
        is_async = isinstance(fn_node, ast.AsyncFunctionDef)
        if parent_class:
            qual_local = f"{parent_class}.{fn_name}"
            kind = "async_method" if is_async else "method"
        elif outer_func:
            qual_local = f"{outer_func}.{fn_name}"
            kind = "async_function" if is_async else "function"
        else:
            qual_local = fn_name
            kind = "async_function" if is_async else "function"

        qualified_name = f"{rel_path}::{qual_local}"
        lineno = getattr(fn_node, "lineno", 1)
        end_lineno = getattr(fn_node, "end_lineno", lineno)
        status = classify_function_forensic_status(fn_node, source_lines)

        body: List[ast.stmt] = getattr(fn_node, "body", [])
        scope_calls = _collect_scope_calls(body)
        fn_call_entries: List[Dict[str, Any]] = []
        for called_name, prefix, call_line in scope_calls:
            entry = {
                "caller_file": rel_path,
                "caller_symbol": qual_local,
                "caller_qualified": qualified_name,
                "caller_class": parent_class,
                "target_name": called_name,
                "target_prefix": prefix,
                "lineno": call_line,
            }
            raw_calls.append(entry)
            fn_call_entries.append(
                {
                    "target_name": called_name,
                    "target_prefix": prefix,
                    "lineno": call_line,
                }
            )

        symbols.append(
            {
                "name": fn_name,
                "symbol": qual_local,
                "qualified_name": qualified_name,
                "kind": kind,
                "file": rel_path,
                "lineno": lineno,
                "end_lineno": end_lineno,
                "status": status,
                "calls": fn_call_entries,
            }
        )

        # Also check nested functions inside this function
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                process_function(stmt, parent_class=None, outer_func=qual_local)

        return status

    # Walk top-level statements in module
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            process_function(stmt)
        elif isinstance(stmt, ast.ClassDef):
            cls_name = stmt.name
            cls_qual = f"{rel_path}::{cls_name}"
            cls_lineno = getattr(stmt, "lineno", 1)
            cls_end_lineno = getattr(stmt, "end_lineno", cls_lineno)
            method_statuses: List[str] = []

            for cls_stmt in stmt.body:
                if isinstance(cls_stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_status = process_function(cls_stmt, parent_class=cls_name)
                    method_statuses.append(m_status)

            cls_status = classify_class_forensic_status(stmt, method_statuses)
            cls_calls = _collect_scope_calls(stmt.body)
            cls_call_entries: List[Dict[str, Any]] = []
            for called_name, prefix, call_line in cls_calls:
                entry = {
                    "caller_file": rel_path,
                    "caller_symbol": cls_name,
                    "caller_qualified": cls_qual,
                    "caller_class": cls_name,
                    "target_name": called_name,
                    "target_prefix": prefix,
                    "lineno": call_line,
                }
                raw_calls.append(entry)
                cls_call_entries.append(
                    {
                        "target_name": called_name,
                        "target_prefix": prefix,
                        "lineno": call_line,
                    }
                )

            symbols.append(
                {
                    "name": cls_name,
                    "symbol": cls_name,
                    "qualified_name": cls_qual,
                    "kind": "class",
                    "file": rel_path,
                    "lineno": cls_lineno,
                    "end_lineno": cls_end_lineno,
                    "status": cls_status,
                    "calls": cls_call_entries,
                }
            )

    # Also collect module-level calls outside classes/functions
    module_calls = _collect_scope_calls(tree.body)
    for called_name, prefix, call_line in module_calls:
        raw_calls.append(
            {
                "caller_file": rel_path,
                "caller_symbol": "<module>",
                "caller_qualified": f"{rel_path}::<module>",
                "caller_class": None,
                "target_name": called_name,
                "target_prefix": prefix,
                "lineno": call_line,
            }
        )

    symbols.sort(key=lambda s: (s["lineno"], s["name"]))

    return {
        "path": rel_path,
        "line_count": line_count,
        "imports": imports,
        "syntax_error": None,
        "symbols": symbols,
        "raw_calls": raw_calls,
    }


def resolve_target_root(root_dir: str | Path) -> Path:
    """Resolve root directory, supporting kageyoni_v11 -> kageyoni alias if needed."""
    candidate = Path(root_dir)
    if candidate.exists():
        return candidate.resolve()
    # Handle common package-to-directory alias (e.g., c:\Kageyoni\kageyoni_v11 -> c:\Kageyoni\kageyoni)
    if candidate.name.lower().startswith("kageyoni_"):
        alt = candidate.parent / "kageyoni"
        if alt.exists() and alt.is_dir():
            return alt.resolve()
    raise FileNotFoundError(f"Root directory does not exist: {root_dir}")


def build_code_graph(
    root_dir: str | Path,
    max_files: int = DEFAULT_MAX_FILES,
) -> Dict[str, Any]:
    """
    Scan root_dir, parse ASTs for up to max_files Python files, and build the full
    bidirectional code graph and forensic reality audit report.
    """
    t0 = time.perf_counter()
    root_path = resolve_target_root(root_dir)
    py_files, capped = discover_python_files(root_path, max_files=max_files)

    modules: Dict[str, Dict[str, Any]] = {}
    all_symbols: Dict[str, Dict[str, Any]] = {}
    symbols_by_short_name: Dict[str, List[str]] = defaultdict(list)
    symbols_by_top_level: Dict[str, List[str]] = defaultdict(list)
    symbols_by_class_method: Dict[str, List[str]] = defaultdict(list)
    module_imported_names: Dict[str, Set[str]] = defaultdict(set)
    all_raw_calls: List[Dict[str, Any]] = []

    for fpath in py_files:
        try:
            rel_path = fpath.relative_to(root_path).as_posix()
        except ValueError:
            rel_path = fpath.name

        parsed = parse_python_file(fpath, rel_path)
        raw_calls = parsed.pop("raw_calls", [])
        all_raw_calls.extend(raw_calls)
        modules[rel_path] = parsed

        for imp in parsed.get("imports", []):
            bound_name = imp.get("asname") or imp.get("name", "").split(".")[0]
            if bound_name:
                module_imported_names[rel_path].add(bound_name)

        for sym in parsed["symbols"]:
            qname = sym["qualified_name"]
            all_symbols[qname] = sym
            symbols_by_short_name[sym["name"]].append(qname)
            if "." in sym["symbol"]:
                symbols_by_class_method[sym["symbol"]].append(qname)
            else:
                symbols_by_top_level[sym["name"]].append(qname)

    # Resolve call edges into bidirectional index
    calls_by_caller: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    called_by_target: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    callers_by_short_name: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for call in all_raw_calls:
        target_name = call["target_name"]
        target_prefix = call["target_prefix"]
        caller_file = call["caller_file"]
        caller_class = call["caller_class"]
        caller_qual = call["caller_qualified"]
        caller_sym = call["caller_symbol"]
        lineno = call["lineno"]

        resolved_targets: List[str] = []

        if target_prefix in ("self", "cls") and caller_class:
            cm_key = f"{caller_class}.{target_name}"
            same_file_qname = f"{caller_file}::{cm_key}"
            if same_file_qname in all_symbols:
                resolved_targets = [same_file_qname]
            elif cm_key in symbols_by_class_method:
                resolved_targets = list(symbols_by_class_method[cm_key])
        elif target_prefix:
            last_prefix = target_prefix.split(".")[-1]
            cm_key = f"{last_prefix}.{target_name}"
            if cm_key in symbols_by_class_method:
                resolved_targets = list(symbols_by_class_method[cm_key])
            elif target_name not in BUILTIN_CONTAINER_ATTRS:
                if target_name in symbols_by_top_level:
                    resolved_targets = list(symbols_by_top_level[target_name])
                elif len(symbols_by_short_name.get(target_name, ())) <= 4:
                    resolved_targets = list(symbols_by_short_name[target_name])
        else:
            same_file_fn = f"{caller_file}::{target_name}"
            if same_file_fn in all_symbols:
                resolved_targets = [same_file_fn]
            elif target_name in BUILTIN_NAMES:
                # Unprefixed Python builtin (e.g. list(), set(), dict(), type()):
                # Only resolve if explicitly imported in this module and defined as a top-level symbol.
                # Never fall back to matching arbitrary Class.<builtin_name> methods via symbols_by_short_name.
                if (
                    target_name in module_imported_names[caller_file]
                    and target_name in symbols_by_top_level
                ):
                    resolved_targets = list(symbols_by_top_level[target_name])
            elif target_name in symbols_by_top_level:
                resolved_targets = list(symbols_by_top_level[target_name])

        edge_record = {
            "caller_file": caller_file,
            "caller_symbol": caller_sym,
            "caller_qualified": caller_qual,
            "target_name": target_name,
            "target_prefix": target_prefix,
            "resolved_targets": resolved_targets,
            "lineno": lineno,
        }
        calls_by_caller[caller_qual].append(edge_record)
        if target_prefix is None:
            if target_name not in BUILTIN_NAMES or resolved_targets:
                callers_by_short_name[target_name].append(edge_record)
        elif target_name not in BUILTIN_CONTAINER_ATTRS:
            callers_by_short_name[target_name].append(edge_record)
        if target_prefix:
            callers_by_short_name[f"{target_prefix}.{target_name}"].append(edge_record)

        for r_target in resolved_targets:
            called_by_target[r_target].append(
                {
                    "caller_file": caller_file,
                    "caller_symbol": caller_sym,
                    "caller_qualified": caller_qual,
                    "lineno": lineno,
                }
            )

    # Annotate each symbol with its resolved incoming `called_by`
    for qname, sym in all_symbols.items():
        sym["called_by"] = called_by_target.get(qname, [])

    # Compute Forensic Audit classifications
    wired_modules: List[Dict[str, Any]] = []
    hollow_stubs: List[Dict[str, Any]] = []
    syntax_failures: List[Dict[str, Any]] = []

    for rel_path, mod in sorted(modules.items()):
        if mod["syntax_error"]:
            syntax_failures.append(
                {
                    "file": rel_path,
                    "error": mod["syntax_error"],
                }
            )
            continue

        mod_symbols = mod["symbols"]
        mod_wired_count = 0
        mod_stub_count = 0
        mod_outgoing_edges = 0
        mod_incoming_edges = 0

        for sym in mod_symbols:
            if sym["status"] == "HOLLOW_STUB" and sym["kind"] != "class":
                mod_stub_count += 1
                hollow_stubs.append(
                    {
                        "file": rel_path,
                        "symbol": sym["symbol"],
                        "qualified_name": sym["qualified_name"],
                        "kind": sym["kind"],
                        "lineno": sym["lineno"],
                        "end_lineno": sym["end_lineno"],
                    }
                )
            elif sym["status"] == "WIRED":
                mod_wired_count += 1

            mod_outgoing_edges += len(sym.get("calls", []))
            mod_incoming_edges += len(sym.get("called_by", []))

        # Module-level outgoing calls also count as active call edges
        mod_level_qname = f"{rel_path}::<module>"
        mod_outgoing_edges += len(calls_by_caller.get(mod_level_qname, []))

        if mod_wired_count > 0 and (mod_outgoing_edges > 0 or mod_incoming_edges > 0):
            wired_modules.append(
                {
                    "file": rel_path,
                    "line_count": mod["line_count"],
                    "wired_symbols": mod_wired_count,
                    "stub_symbols": mod_stub_count,
                    "outgoing_calls": mod_outgoing_edges,
                    "incoming_calls": mod_incoming_edges,
                }
            )

    elapsed_sec = round(time.perf_counter() - t0, 4)

    # Compute top 10 most-called hubs (resolved definitions ranked by incoming call count)
    hub_ranking = sorted(
        (
            {
                "qualified_name": qname,
                "symbol": sym["symbol"],
                "file": sym["file"],
                "lineno": sym["lineno"],
                "end_lineno": sym["end_lineno"],
                "status": sym["status"],
                "caller_count": len(sym.get("called_by", [])),
            }
            for qname, sym in all_symbols.items()
            if len(sym.get("called_by", [])) > 0
        ),
        key=lambda x: (-x["caller_count"], x["qualified_name"]),
    )[:10]

    total_defs = len(all_symbols)
    wired_defs = sum(1 for s in all_symbols.values() if s["status"] == "WIRED")
    stub_defs = sum(1 for s in all_symbols.values() if s["status"] == "HOLLOW_STUB")

    return {
        "metadata": {
            "root": root_path.as_posix(),
            "total_files": len(modules),
            "capped_at_max_files": capped,
            "max_files_limit": max_files,
            "total_definitions": total_defs,
            "wired_definitions": wired_defs,
            "hollow_stub_definitions": stub_defs,
            "syntax_failures_count": len(syntax_failures),
            "scan_duration_sec": elapsed_sec,
        },
        "top_hubs": hub_ranking,
        "forensic": {
            "WIRED_MODULES": wired_modules,
            "HOLLOW_STUBS": hollow_stubs,
            "SYNTAX_OR_PARSE_FAILURES": syntax_failures,
        },
        "modules": modules,
        "call_index": {
            "by_qualified_target": dict(called_by_target),
            "by_short_name": dict(callers_by_short_name),
        },
    }


def query_callers(graph: Dict[str, Any], symbol_query: str) -> Dict[str, Any]:
    """
    Find matching definition(s) and all callers for `symbol_query`.
    Supports querying by:
      - exact qualified_name (`path/file.py::Class.method` or `path/file.py::func`)
      - `Class.method`
      - bare symbol name (`func` or `method`)
    """
    matching_defs: List[Dict[str, Any]] = []
    seen_qnames: Set[str] = set()

    for mod in graph.get("modules", {}).values():
        for sym in mod.get("symbols", []):
            if (
                sym["qualified_name"] == symbol_query
                or sym["symbol"] == symbol_query
                or sym["name"] == symbol_query
            ):
                if sym["qualified_name"] not in seen_qnames:
                    seen_qnames.add(sym["qualified_name"])
                    matching_defs.append(sym)

    callers: List[Dict[str, Any]] = []
    seen_caller_sites: Set[Tuple[str, int, str]] = set()

    by_qual = graph.get("call_index", {}).get("by_qualified_target", {})
    by_short = graph.get("call_index", {}).get("by_short_name", {})

    for sym in matching_defs:
        for edge in by_qual.get(sym["qualified_name"], []):
            site_key = (edge["caller_file"], edge["lineno"], edge["caller_symbol"])
            if site_key not in seen_caller_sites:
                seen_caller_sites.add(site_key)
                callers.append(edge)

    # Also check raw short-name call index in case of dynamic/external or unresolved calls
    for edge in by_short.get(symbol_query, []):
        site_key = (edge["caller_file"], edge["lineno"], edge["caller_symbol"])
        if site_key not in seen_caller_sites:
            seen_caller_sites.add(site_key)
            callers.append(
                {
                    "caller_file": edge["caller_file"],
                    "caller_symbol": edge["caller_symbol"],
                    "caller_qualified": edge["caller_qualified"],
                    "lineno": edge["lineno"],
                }
            )

    callers.sort(key=lambda c: (c["caller_file"], c["lineno"]))
    return {
        "query": symbol_query,
        "definitions": matching_defs,
        "callers": callers,
    }


def format_summary_markdown(graph: Dict[str, Any]) -> str:
    """Format a concise Markdown summary of the code graph."""
    meta = graph["metadata"]
    lines = [
        "# AST Code Graph Summary",
        f"- **Root**: `{meta['root']}`",
        f"- **Total Python Files**: {meta['total_files']}"
        + (" (CAPPED)" if meta["capped_at_max_files"] else ""),
        f"- **Total Definitions**: {meta['total_definitions']}",
        f"- **Wired Definitions (`WIRED`)**: {meta['wired_definitions']}",
        f"- **Hollow Stubs (`HOLLOW_STUB`)**: {meta['hollow_stub_definitions']}",
        f"- **Syntax/Parse Failures**: {meta['syntax_failures_count']}",
        f"- **Scan Duration**: {meta['scan_duration_sec']:.4f}s",
        "",
        "## Top 10 Most-Called Hubs",
    ]
    hubs = graph.get("top_hubs", [])
    if not hubs:
        lines.append("- *(No resolved call hubs found)*")
    else:
        for idx, hub in enumerate(hubs, start=1):
            lines.append(
                f"{idx}. `{hub['qualified_name']}` "
                f"(`{hub['file']}:{hub['lineno']}-{hub['end_lineno']}`) "
                f"-- **{hub['caller_count']}** callers [{hub['status']}]"
            )
    return "\n".join(lines)


def format_callers_report(result: Dict[str, Any]) -> str:
    """Format `--callers <symbol>` output with exact file:start-end and caller locations."""
    query = result["query"]
    defs = result["definitions"]
    callers = result["callers"]

    lines = [f"# Callers Report for `{query}`", "", "## Definitions"]
    if not defs:
        lines.append(f"- *(No definition found in scanned files for `{query}`)*")
    else:
        for d in defs:
            lines.append(
                f"- `{d['file']}:{d['lineno']}-{d['end_lineno']}` "
                f"(`{d['qualified_name']}`) [{d['status']}]"
            )

    lines.append("")
    lines.append(f"## Callers ({len(callers)})")
    if not callers:
        lines.append(f"- *(No callers found for `{query}`)*")
    else:
        for c in callers:
            lines.append(
                f"- `{c['caller_file']}:{c['lineno']}` in `{c['caller_symbol']}`"
            )
    return "\n".join(lines)


def format_forensic_report(graph: Dict[str, Any]) -> str:
    """Format the Mode 3 Cold-Start Forensic Audit Report."""
    forensic = graph["forensic"]
    wired = forensic["WIRED_MODULES"]
    stubs = forensic["HOLLOW_STUBS"]
    failures = forensic["SYNTAX_OR_PARSE_FAILURES"]

    lines = [
        "# Mode 3 Cold-Start Forensic Audit Report",
        "",
        f"## 1. WIRED_MODULES ({len(wired)})",
    ]
    if not wired:
        lines.append("- *(None)*")
    else:
        for w in wired:
            lines.append(
                f"- `{w['file']}` ({w['line_count']} lines) -- "
                f"wired={w['wired_symbols']}, stubs={w['stub_symbols']}, "
                f"outgoing_calls={w['outgoing_calls']}, incoming_calls={w['incoming_calls']}"
            )

    lines.append("")
    lines.append(f"## 2. HOLLOW_STUBS ({len(stubs)})")
    if not stubs:
        lines.append("- *(None)*")
    else:
        for s in stubs:
            lines.append(
                f"- `{s['file']}:{s['lineno']}` (`{s['lineno']}-{s['end_lineno']}`) "
                f"`{s['symbol']}` [{s['kind']}]"
            )

    lines.append("")
    lines.append(f"## 3. SYNTAX_OR_PARSE_FAILURES ({len(failures)})")
    if not failures:
        lines.append("- *(None)*")
    else:
        for f in failures:
            lines.append(f"- `{f['file']}` -- {f['error']}")

    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Python 3 AST Code Dependency Graph & Forensic Reality Scanner"
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Target root directory to scan",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to write full code graph JSON",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print concise Markdown summary",
    )
    parser.add_argument(
        "--callers",
        default=None,
        metavar="SYMBOL_NAME",
        help="Print definition location(s) and all callers for SYMBOL_NAME",
    )
    parser.add_argument(
        "--forensic",
        action="store_true",
        help="Print Mode 3 Cold-Start Forensic Audit Report",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=DEFAULT_MAX_FILES,
        help=f"Maximum number of .py files to scan (default: {DEFAULT_MAX_FILES})",
    )

    args = parser.parse_args(argv)
    try:
        root_path = resolve_target_root(args.root)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    graph = build_code_graph(root_path, max_files=args.max_files)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")

    outputs: List[str] = []
    # Default to summary if neither --callers nor --forensic is specified, or if --summary is explicitly passed
    if args.summary or (not args.callers and not args.forensic):
        outputs.append(format_summary_markdown(graph))

    if args.callers:
        caller_res = query_callers(graph, args.callers)
        outputs.append(format_callers_report(caller_res))

    if args.forensic:
        outputs.append(format_forensic_report(graph))

    print("\n\n".join(outputs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
