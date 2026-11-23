#!/usr/bin/env python3
"""Portable boundary & enforcement tests for hook_v4.py (PreToolUse and Stop)."""

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

import hook_v4  # noqa: E402


class TestHookV4Enforcement(unittest.TestCase):
    """Verify hook_v4 blocks tampering, swallowed exceptions, syntax errors, and missing acceptance files."""

    def test_denies_write_to_protected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {
                        "Path": str(Path(tmp) / ".agents" / "hooks.json"),
                        "Content": "{}\n",
                    },
                },
            }
            res = hook_v4.pre(payload)
            self.assertEqual(res["decision"], "deny")

    def test_denies_swallowed_exception_and_syntax_error_on_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "module.py"
            bad_syntax = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {"Path": str(target), "Content": "def broken(:\n    pass\n"},
                },
            }
            res_syn = hook_v4.pre(bad_syntax)
            self.assertEqual(res_syn["decision"], "deny")

            swallowed = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {
                        "Path": str(target),
                        "Content": "def quiet():\n    try:\n        return 1\n    except Exception:\n        pass\n",
                    },
                },
            }
            res_sw = hook_v4.pre(swallowed)
            self.assertEqual(res_sw["decision"], "ask")
            self.assertIn("RW-08", res_sw["reason"])

            test_tamper = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {
                        "Path": str(Path(tmp) / "test_fake.py"),
                        "Content": "def test_fake():\n    assert True\n",
                    },
                },
            }
            self.assertEqual(hook_v4.pre(test_tamper)["decision"], "deny")

    def test_allows_clean_python_write_and_gates_destructive_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clean_target = Path(tmp) / "app.py"
            clean_write = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {"Path": str(clean_target), "Content": "def add(a: int, b: int) -> int:\n    return a + b\n"},
                },
            }
            res_ok = hook_v4.pre(clean_write)
            self.assertEqual(res_ok["decision"], "allow")

            subagent_rm = {
                "workspacePaths": [tmp],
                "parentConversationId": "parent-123",
                "toolCall": {
                    "name": "run_command",
                    "args": {"CommandLine": "git reset --hard HEAD"},
                },
            }
            res_rm = hook_v4.pre(subagent_rm)
            self.assertEqual(res_rm["decision"], "deny")

            if os.name == "nt":
                grep_cmd = {
                    "workspacePaths": [tmp],
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "grep foo bar.txt"}},
                }
                self.assertEqual(hook_v4.pre(grep_cmd)["decision"], "deny")

    def test_stop_gate_enforces_acceptance_lock_required_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agents").mkdir()
            (root / "README.md").write_text("# OK\n", encoding="utf-8")
            (root / ".agents" / "acceptance.lock.json").write_text(
                json.dumps({"required_files": ["README.md", "MISSING.md"], "python_syntax": []}),
                encoding="utf-8",
            )
            payload = {
                "workspacePaths": [tmp],
                "terminationReason": "NO_TOOL_CALL",
                "executionNum": 0,
            }
            res_block = hook_v4.stop(payload)
            self.assertEqual(res_block["decision"], "continue")
            self.assertIn("MISSING.md", res_block["reason"])

            (root / "MISSING.md").write_text("# Present\n", encoding="utf-8")
            res_pass = hook_v4.stop(payload)
            self.assertEqual(res_pass["decision"], "allow")


if __name__ == "__main__":
    unittest.main()
