#!/usr/bin/env python3
"""Allow/deny unit tests for Sentinel safety boundaries and GEMINI.md lifecycle FSM."""

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

import sentinel  # noqa: E402


class TestSentinelEnforcement(unittest.TestCase):
    """Verify Sentinel enforces Tier 1/2 boundaries, single-pass AST rules, and GEMINI.md lifecycle."""

    def test_protected_files_and_hook_state_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for rel_target in (".agents/hooks.json", "sentinel-state.json", "AGENTS.md"):
                payload = {
                    "workspacePaths": [tmp],
                    "toolCall": {
                        "name": "write_file",
                        "args": {"Path": str(Path(tmp) / rel_target), "Content": "{}\n"},
                    },
                }
                res = sentinel.pre(payload)
                self.assertEqual(res["decision"], "deny", rel_target)

            ok_payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {"Path": str(Path(tmp) / "app.py"), "Content": "def f() -> int:\n    return 1\n"},
                },
            }
            self.assertEqual(sentinel.pre(ok_payload)["decision"], "allow")
            self.assertNotEqual(sentinel.pre(ok_payload)["decision"], "deny")

    def test_orient_before_edit_blocks_blind_mutation_then_unlocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            (root / ".git").mkdir(parents=True)
            art.mkdir(parents=True)

            write_call = {
                "workspacePaths": [str(root)],
                "artifactDirectoryPath": str(art),
                "toolCall": {
                    "name": "write_file",
                    "args": {"Path": str(root / "mod.py"), "Content": "x = 1\n"},
                },
            }
            blocked = sentinel.pre(write_call)
            self.assertEqual(blocked["decision"], "deny")
            self.assertIn("Orient-Before-Edit", blocked["reason"])

            # Delegated subagent with parentConversationId is not blocked by coordinator orient gate
            sub_call = dict(write_call, parentConversationId="coord-1")
            self.assertEqual(sentinel.pre(sub_call)["decision"], "allow")

            # After a read_file step completes, main agent is oriented and unlocked
            sentinel.post(
                {
                    "workspacePaths": [str(root)],
                    "artifactDirectoryPath": str(art),
                    "toolCall": {"name": "read_file", "args": {"Path": str(root / "README.md")}},
                }
            )
            self.assertEqual(sentinel.pre(write_call)["decision"], "allow")

    def test_three_strike_governor_locks_on_third_failed_verify_and_resets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            (root / ".git").mkdir(parents=True)
            art.mkdir(parents=True)
            target = root / "calc.py"

            base = {"workspacePaths": [str(root)], "artifactDirectoryPath": str(art)}
            sentinel.post({**base, "toolCall": {"name": "read_file", "args": {"Path": str(target)}}})

            edit_payload = {
                **base,
                "toolCall": {"name": "write_file", "args": {"Path": str(target), "Content": "val = 1\n"}},
            }
            self.assertEqual(sentinel.pre(edit_payload)["decision"], "allow")
            sentinel.post(edit_payload)

            fail_verify = {
                **base,
                "error": "exit status 1",
                "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest -q"}},
            }
            # Strikes 1 and 2 still allow repair edits (normal TDD / bounded repair)
            sentinel.post(fail_verify)
            self.assertEqual(sentinel.pre(edit_payload)["decision"], "allow")
            sentinel.post(fail_verify)
            self.assertEqual(sentinel.pre(edit_payload)["decision"], "allow")

            # Strike 3 locks further edits
            sentinel.post(fail_verify)
            locked = sentinel.pre(edit_payload)
            self.assertEqual(locked["decision"], "deny")
            self.assertIn("3-Strike Governor", locked["reason"])

            # Diagnostic read_file steps down 3 -> 2 for one informed hypothesis attempt
            sentinel.post({**base, "toolCall": {"name": "read_file", "args": {"Path": str(target)}}})
            self.assertEqual(sentinel.pre(edit_payload)["decision"], "allow")

            # Passing verification resets strikes completely
            sentinel.post({**base, "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest -q"}}})
            self.assertEqual(sentinel.pre(edit_payload)["decision"], "allow")

    def test_verify_before_stop_respects_fully_idle_and_continuation_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            root.mkdir(parents=True)
            art.mkdir(parents=True)
            target = root / "engine.py"
            target.write_text("a = 1\n", encoding="utf-8")

            base = {"workspacePaths": [str(root)], "artifactDirectoryPath": str(art)}
            sentinel.post(
                {
                    **base,
                    "toolCall": {"name": "write_file", "args": {"Path": str(target), "Content": "a = 2\n"}},
                }
            )

            # Yielding while a background task is running (fullyIdle=False) must be allowed
            bg_stop = {**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": False, "executionNum": 0}
            self.assertEqual(sentinel.stop(bg_stop)["decision"], "allow")

            # Stopping completely idle without verification requires continuation
            idle_stop = {**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": True, "executionNum": 0}
            blocked = sentinel.stop(idle_stop)
            self.assertEqual(blocked["decision"], "continue")
            self.assertIn("Verify-Before-Stop", blocked["reason"])

            # Anti-loop guard: continuationActive=True allows stop
            cont_stop = dict(idle_stop, continuationActive=True)
            self.assertEqual(sentinel.stop(cont_stop)["decision"], "allow")

            # Passing verification clears unverified_code_edits
            sentinel.post({**base, "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest -q"}}})
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "allow")

    def test_single_pass_ast_and_test_quality_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mod = str(Path(tmp) / "svc.py")
            tst = str(Path(tmp) / "test_svc.py")
            dyn_user_path = "/".join(["", "home", "demo", "repo"])

            cases = [
                (mod, "def broken(:\n", "deny", "FM-H02"),
                (mod, "class X:\n    def __eq__(self, other):\n        return True\n", "deny", "RW-02"),
                (mod, "def f():\n    try:\n        return 1\n    except Exception:\n        pass\n", "ask", "RW-08"),
                (mod, "from unittest.mock import MagicMock\n", "ask", "RW-11"),
                (mod, 'import os\nx = os.environ.get("PYTEST_CURRENT_TEST")\n', "deny", "RW-17"),
                (tst, "def test_cheat():\n    assert True\n", "deny", "RW-01"),
                (tst, f'p = "{dyn_user_path}"\ndef test_p():\n    assert len(p) > 0\n', "deny", "TQ-03"),
            ]
            for path, content, expected_dec, expected_tag in cases:
                res = sentinel.pre(
                    {
                        "workspacePaths": [tmp],
                        "toolCall": {"name": "write_file", "args": {"Path": path, "Content": content}},
                    }
                )
                self.assertEqual(res["decision"], expected_dec, f"{expected_tag}: {res}")
                self.assertIn(expected_tag, res["reason"])

            # Subagent upgrades 'ask' (e.g., RW-08) to hard 'deny'
            sub_res = sentinel.pre(
                {
                    "workspacePaths": [tmp],
                    "parentConversationId": "p-1",
                    "toolCall": {
                        "name": "write_file",
                        "args": {"Path": mod, "Content": "import contextlib\nwith contextlib.suppress(Exception):\n    x = 1\n"},
                    },
                }
            )
            self.assertEqual(sub_res["decision"], "deny")

            solid_test = (
                "import unittest\n\nclass Solid(unittest.TestCase):\n"
                "    def test_ok(self):\n        self.assertEqual(2 + 2, 4)\n"
                "    def test_neg(self):\n        self.assertNotEqual(2 + 2, 5)\n"
            )
            ok_res = sentinel.pre(
                {
                    "workspacePaths": [tmp],
                    "toolCall": {"name": "write_file", "args": {"Path": tst, "Content": solid_test}},
                }
            )
            self.assertEqual(ok_res["decision"], "allow")

    def test_shell_mcp_and_acceptance_lock_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agents").mkdir()
            (root / ".agents" / "acceptance.lock.json").write_text(
                json.dumps({"required_files": ["README.md"], "python_syntax": []}),
                encoding="utf-8",
            )
            stop_missing = sentinel.stop({"workspacePaths": [tmp], "terminationReason": "NO_TOOL_CALL", "executionNum": 0})
            self.assertEqual(stop_missing["decision"], "continue")
            self.assertIn("README.md", stop_missing["reason"])

            (root / "README.md").write_text("# Ready\n", encoding="utf-8")
            self.assertEqual(
                sentinel.stop({"workspacePaths": [tmp], "terminationReason": "NO_TOOL_CALL", "executionNum": 0})["decision"],
                "allow",
            )

            push_main = sentinel.pre({"workspacePaths": [tmp], "toolCall": {"name": "run_command", "args": {"CommandLine": "git push origin main"}}})
            self.assertEqual(push_main["decision"], "force_ask")
            push_sub = sentinel.pre({"workspacePaths": [tmp], "parentConversationId": "p-1", "toolCall": {"name": "run_command", "args": {"CommandLine": "git push origin main"}}})
            self.assertEqual(push_sub["decision"], "deny")

            if os.name == "nt":
                grep_res = sentinel.pre({"workspacePaths": [tmp], "toolCall": {"name": "run_command", "args": {"CommandLine": "grep foo README.md"}}})
                self.assertEqual(grep_res["decision"], "deny")

            mcp_mut = sentinel.pre({"workspacePaths": [tmp], "toolCall": {"name": "call_mcp_tool", "args": {"ToolName": "delete_instance"}}})
            self.assertEqual(mcp_mut["decision"], "force_ask")
            mcp_ro = sentinel.pre({"workspacePaths": [tmp], "toolCall": {"name": "call_mcp_tool", "args": {"ToolName": "writersroom_recognize"}}})
            self.assertEqual(mcp_ro["decision"], "allow")

            self.assertFalse(sentinel.is_meaningful_verification_command("git status"))
            self.assertTrue(sentinel.is_meaningful_verification_command("pwsh -File scripts/verify_all.ps1"))


if __name__ == "__main__":
    unittest.main()
