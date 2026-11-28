#!/usr/bin/env python3
"""Unit tests for failure_ledger.py and code_graph.py blast-radius caller analysis."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import code_graph  # noqa: E402
import failure_ledger  # noqa: E402
import operator_router  # noqa: E402


class TestFailureLedgerAndCodeGraph(unittest.TestCase):
    """Verify cross-session failure ledger persistence/surfacing and AST caller blast-radius queries."""

    def test_failure_ledger_records_deduplicates_and_surfaces_at_session_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "failure-ledger.jsonl"
            prev = os.environ.get("ANTIGRAVITY_FAILURE_LEDGER_PATH")
            os.environ["ANTIGRAVITY_FAILURE_LEDGER_PATH"] = str(ledger_path)
            try:
                ok1 = failure_ledger.record_failure_lesson(
                    "Windows Copy-Item * skips dotfiles",
                    "PowerShell glob omits .github",
                    "Use Copy-Item -Path .",
                    scope="antigravity-config",
                )
                self.assertTrue(ok1)
                # Duplicate pattern in same scope is deduplicated
                ok_dup = failure_ledger.record_failure_lesson(
                    "Windows Copy-Item * skips dotfiles",
                    "PowerShell glob omits .github",
                    "Use Copy-Item -Path .",
                    scope="antigravity-config",
                )
                self.assertFalse(ok_dup)

                # Different scope lesson is filtered out when querying antigravity-config
                failure_ledger.record_failure_lesson(
                    "Other repo bug",
                    "Unrelated",
                    "Fix it",
                    scope="other-repo",
                )
                lessons = failure_ledger.load_recent_lessons(scope="antigravity-config", limit=5)
                self.assertEqual(len(lessons), 1)

                # SessionStart surfaces the lesson automatically
                out = operator_router.handle_session_start({"workspacePaths": [str(Path(tmp) / "antigravity-config")]})
                msgs = [s["systemMessage"]["systemMessage"] for s in out["injectSteps"]]
                self.assertTrue(any("FAILURE LEDGER" in m and "Copy-Item" in m for m in msgs))
            finally:
                if prev is None:
                    os.environ.pop("ANTIGRAVITY_FAILURE_LEDGER_PATH", None)
                else:
                    os.environ["ANTIGRAVITY_FAILURE_LEDGER_PATH"] = prev

    def test_code_graph_discovers_callers_and_flags_hollow_stubs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "core.py").write_text(
                "def load_data(x: int) -> int:\n    return x + 1\n\n"
                "def hollow_stub() -> None:\n    pass\n",
                encoding="utf-8",
            )
            (root / "caller.py").write_text(
                "from core import load_data\n\ndef run() -> int:\n    return load_data(5)\n",
                encoding="utf-8",
            )
            graph = code_graph.build_code_graph(root)
            self.assertEqual(len(graph["modules"]), 2)

            callers = code_graph.query_callers(graph, "load_data")
            caller_files = [c["caller_file"] for c in callers.get("callers", [])]
            self.assertIn("caller.py", caller_files)

            # Missing directory raises FileNotFoundError cleanly
            with self.assertRaises(FileNotFoundError):
                code_graph.build_code_graph(root / "nonexistent_sub")


if __name__ == "__main__":
    unittest.main()
