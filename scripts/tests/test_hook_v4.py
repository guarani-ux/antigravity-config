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

    def test_live_tq_gate_denies_bad_tests_and_allows_solid_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "test_sample.py")
            dynamic_user_path = "/".join(["", "home", "demo", "repo"])
            bad_cases = [
                ("def test_empty():\n    x = 1\n", "TQ-01"),
                ("def test_eq():\n    x = 1\n    assert x == x\n", "TQ-01"),
                (
                    f'p = "{dynamic_user_path}"\ndef test_path():\n    assert len(p) > 0\n',
                    "TQ-03",
                ),
                (
                    "import unittest\n\nclass PosOnly(unittest.TestCase):\n"
                    "    def test_a(self):\n        self.assertEqual(1 + 1, 2)\n"
                    "    def test_b(self):\n        self.assertEqual(2 + 2, 4)\n",
                    "TQ-05",
                ),
            ]
            for content, expected_rule in bad_cases:
                payload = {
                    "workspacePaths": [tmp],
                    "toolCall": {"name": "write_file", "args": {"Path": target, "Content": content}},
                }
                res = hook_v4.pre(payload)
                self.assertEqual(res["decision"], "deny", f"Expected deny for {expected_rule}, got {res}")
                self.assertIn(expected_rule, res["reason"])

            good_content = (
                "import unittest\n\nclass Solid(unittest.TestCase):\n"
                "    def test_positive(self):\n        self.assertEqual(1 + 1, 2)\n"
                "    def test_negative(self):\n        self.assertNotEqual(1 + 1, 3)\n"
            )
            good_payload = {
                "workspacePaths": [tmp],
                "toolCall": {"name": "write_file", "args": {"Path": target, "Content": good_content}},
            }
            self.assertEqual(hook_v4.pre(good_payload)["decision"], "allow")

    def test_rw01_blocks_test_skip_and_assertion_weakening(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            test_file = Path(tmp) / "test_existing.py"
            test_file.write_text(
                "import unittest\n\nclass Existing(unittest.TestCase):\n"
                "    def test_one(self):\n        self.assertEqual(2 + 2, 4)\n"
                "    def test_two(self):\n        self.assertNotEqual(2 + 2, 5)\n",
                encoding="utf-8",
            )
            weaken_payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "edit_file",
                    "args": {
                        "Path": str(test_file),
                        "Target": "        self.assertNotEqual(2 + 2, 5)",
                        "Replacement": "        x = 5",
                    },
                },
            }
            res_weaken = hook_v4.pre(weaken_payload)
            self.assertEqual(res_weaken["decision"], "ask")
            self.assertIn("RW-01", res_weaken["reason"])

            skip_payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "edit_file",
                    "args": {
                        "Path": str(test_file),
                        "Target": "    def test_two(self):",
                        "Replacement": '    @unittest.skip("later")\n    def test_two(self):',
                    },
                },
            }
            res_skip = hook_v4.pre(skip_payload)
            self.assertEqual(res_skip["decision"], "ask")
            self.assertIn("RW-01", res_skip["reason"])

            skip_subagent = dict(skip_payload, parentConversationId="parent-1")
            res_sub = hook_v4.pre(skip_subagent)
            self.assertEqual(res_sub["decision"], "deny")
            self.assertIn("RW-01", res_sub["reason"])

    def test_rw02_denies_always_true_eq_reward_hack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {
                        "Path": str(Path(tmp) / "model.py"),
                        "Content": "class Fake:\n    def __eq__(self, other):\n        return True\n",
                    },
                },
            }
            res = hook_v4.pre(payload)
            self.assertEqual(res["decision"], "deny")
            self.assertIn("RW-02", res["reason"])

    def test_rw04_gates_env_and_gov_mutations_while_allowing_readonly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_read = {
                "workspacePaths": [tmp],
                "toolCall": {"name": "run_command", "args": {"CommandLine": "type .env"}},
            }
            res_env = hook_v4.pre(env_read)
            self.assertEqual(res_env["decision"], "force_ask")
            self.assertIn("RW-04", res_env["reason"])

            env_sub = dict(env_read, parentConversationId="parent-1")
            self.assertEqual(hook_v4.pre(env_sub)["decision"], "deny")

            gov_mut = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "run_command",
                    "args": {"CommandLine": "Set-Content .agents/hooks.json '{}'"},
                },
            }
            res_gov = hook_v4.pre(gov_mut)
            self.assertEqual(res_gov["decision"], "force_ask")
            self.assertIn("RW-04", res_gov["reason"])

            readonly_cmd = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "run_command",
                    "args": {"CommandLine": "python .agents/scripts/crucible_gate.py check"},
                },
            }
            self.assertEqual(hook_v4.pre(readonly_cmd)["decision"], "allow")

    def test_rw08_catches_contextlib_suppress_and_except_return_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            suppress_payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {
                        "Path": str(Path(tmp) / "svc.py"),
                        "Content": "import contextlib\nwith contextlib.suppress(Exception):\n    x = 1\n",
                    },
                },
            }
            res_sup = hook_v4.pre(suppress_payload)
            self.assertEqual(res_sup["decision"], "ask")
            self.assertIn("RW-08", res_sup["reason"])

            ret_none_payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {
                        "Path": str(Path(tmp) / "svc2.py"),
                        "Content": "def f():\n    try:\n        return 1\n    except Exception:\n        return None\n",
                    },
                },
            }
            res_none = hook_v4.pre(ret_none_payload)
            self.assertEqual(res_none["decision"], "ask")
            self.assertIn("RW-08", res_none["reason"])

    def test_rw11_and_rw17_guard_production_mocks_and_harness_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mock_payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {
                        "Path": str(Path(tmp) / "prod.py"),
                        "Content": "from unittest.mock import MagicMock\n",
                    },
                },
            }
            res_mock = hook_v4.pre(mock_payload)
            self.assertEqual(res_mock["decision"], "ask")
            self.assertIn("RW-11", res_mock["reason"])

            mock_sub = dict(mock_payload, parentConversationId="parent-1")
            self.assertEqual(hook_v4.pre(mock_sub)["decision"], "deny")

            harness_payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {
                        "Path": str(Path(tmp) / "prod2.py"),
                        "Content": 'import os\nflag = os.environ.get("PYTEST_CURRENT_TEST")\n',
                    },
                },
            }
            res_har = hook_v4.pre(harness_payload)
            self.assertEqual(res_har["decision"], "deny")
            self.assertIn("RW-17", res_har["reason"])

    def test_rw13_is_meaningful_verification_command(self) -> None:
        for non_verif in ("", "python --version", "git status", "echo hi", "pytest --version"):
            self.assertFalse(hook_v4.is_meaningful_verification_command(non_verif), non_verif)
        for real_verif in ("pytest tests/ -q", "python -m unittest discover", "npm test"):
            self.assertTrue(hook_v4.is_meaningful_verification_command(real_verif), real_verif)

    def test_fm_h02_h03_h08_write_integrity_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctrl_payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {"Path": str(Path(tmp) / "ctrl.py"), "Content": "x = 1" + chr(7) + "\n"},
                },
            }
            res_ctrl = hook_v4.pre(ctrl_payload)
            self.assertEqual(res_ctrl["decision"], "deny")
            self.assertIn("FM-H02", res_ctrl["reason"])

            lazy_comment = "# " + "... " + "existing code\n"
            lazy_payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {"Path": str(Path(tmp) / "lazy.py"), "Content": lazy_comment},
                },
            }
            self.assertEqual(hook_v4.pre(lazy_payload)["decision"], "force_ask")

            target_py = Path(tmp) / "target.py"
            target_py.write_text("def ok():\n    return 1\n", encoding="utf-8")

            noop_payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "edit_file",
                    "args": {
                        "Path": str(target_py),
                        "Target": "def ok():\n    return 1",
                        "Replacement": "def ok():\n    return 1",
                    },
                },
            }
            self.assertEqual(hook_v4.pre(noop_payload)["decision"], "deny")

            missing_target_payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "edit_file",
                    "args": {
                        "Path": str(target_py),
                        "Target": "def missing():\n    return 2",
                        "Replacement": "def missing():\n    return 3",
                    },
                },
            }
            res_missing = hook_v4.pre(missing_target_payload)
            self.assertEqual(res_missing["decision"], "deny")
            self.assertIn("FM-H03", res_missing["reason"])

            meta_payload = {
                "workspacePaths": [tmp],
                "toolCall": {
                    "name": "write_file",
                    "args": {
                        "Path": str(Path(tmp) / "note.md"),
                        "Content": "# Note\n",
                        "ArtifactMetadata": {"Summary": "s", "UserFacing": True, "RequestFeedback": False},
                    },
                },
            }
            res_meta = hook_v4.pre(meta_payload)
            self.assertEqual(res_meta["decision"], "deny")
            self.assertIn("FM-H08", res_meta["reason"])

    def test_mcp_mutating_tool_gated_and_readonly_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mut_payload = {
                "workspacePaths": [tmp],
                "toolCall": {"name": "call_mcp_tool", "args": {"ToolName": "delete_instance"}},
            }
            self.assertEqual(hook_v4.pre(mut_payload)["decision"], "force_ask")

            mut_sub = dict(mut_payload, parentConversationId="parent-1")
            self.assertEqual(hook_v4.pre(mut_sub)["decision"], "deny")

            ro_payload = {
                "workspacePaths": [tmp],
                "toolCall": {"name": "call_mcp_tool", "args": {"ToolName": "list_instances"}},
            }
            self.assertEqual(hook_v4.pre(ro_payload)["decision"], "allow")

    def test_stop_gate_respects_execution_cap_and_three_consecutive_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agents").mkdir()
            (root / ".agents" / "acceptance.lock.json").write_text(
                json.dumps({"required_files": ["MISSING.md"], "python_syntax": []}),
                encoding="utf-8",
            )
            cap_payload = {
                "workspacePaths": [tmp],
                "terminationReason": "NO_TOOL_CALL",
                "executionNum": 3,
            }
            self.assertEqual(hook_v4.stop(cap_payload)["decision"], "allow")

            cancel_payload = {
                "workspacePaths": [tmp],
                "terminationReason": "USER_CANCELED",
                "executionNum": 0,
            }
            self.assertEqual(hook_v4.stop(cancel_payload)["decision"], "allow")

            art_root = root / "no_contract"
            art_dir = art_root / "art"
            art_dir.mkdir(parents=True)
            (art_dir / "reliability-events.jsonl").write_text(
                '{"tool": "run_command", "failed": true}\n' * 3,
                encoding="utf-8",
            )
            err_payload = {
                "workspacePaths": [str(art_root)],
                "artifactDirectoryPath": str(art_dir),
                "terminationReason": "NO_TOOL_CALL",
                "executionNum": 0,
            }
            res_err = hook_v4.stop(err_payload)
            self.assertEqual(res_err["decision"], "continue")
            self.assertIn("Last three tools failed", res_err["reason"])


if __name__ == "__main__":
    unittest.main()
