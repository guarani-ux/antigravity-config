#!/usr/bin/env python3
"""Allow/deny unit and CLI tests for Sentinel safety boundaries, AST gates, and lifecycle FSM."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sentinel  # noqa: E402


class TestSentinelEnforcement(unittest.TestCase):
    """Verify Sentinel enforces Tier 1/2 boundaries, AST/test rules, and lifecycle FSM."""

    def test_protected_files_and_hook_state_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for rel_target in (".agents/hooks.json", "sentinel-state.json", "operator-router-seen.json", "AGENTS.md", "scripts/operator_router.py", "scripts/test_quality_gate.py"):
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

    def test_orient_before_edit_supports_both_tool_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            (root / ".git").mkdir(parents=True)
            art.mkdir(parents=True)

            write_call = {
                "workspacePaths": [str(root)],
                "artifactDirectoryPath": str(art),
                "toolCall": {
                    "name": "write_to_file",
                    "args": {"TargetFile": str(root / "mod.py"), "CodeContent": "x = 1\n"},
                },
            }
            blocked = sentinel.pre(write_call)
            self.assertEqual(blocked["decision"], "deny")
            self.assertIn("Orient-Before-Edit", blocked["reason"])

            # Failed shell command must NOT orient the workspace
            sentinel.post(
                {
                    "workspacePaths": [str(root)],
                    "artifactDirectoryPath": str(art),
                    "exitCode": 1,
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "ls nonexistent"}},
                }
            )
            self.assertEqual(sentinel.pre(write_call)["decision"], "deny")

            # Delegated subagent is not blocked by coordinator orient gate
            sub_call = dict(write_call, parentConversationId="coord-1")
            self.assertEqual(sentinel.pre(sub_call)["decision"], "allow")

            # view_file unlocks orientation cleanly
            sentinel.post(
                {
                    "workspacePaths": [str(root)],
                    "artifactDirectoryPath": str(art),
                    "toolCall": {"name": "view_file", "args": {"AbsolutePath": str(root / "README.md")}},
                }
            )
            self.assertEqual(sentinel.pre(write_call)["decision"], "allow")

    def test_three_strike_governor_and_exit_code_failure_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            (root / ".git").mkdir(parents=True)
            art.mkdir(parents=True)
            target = root / "calc.py"

            base = {"workspacePaths": [str(root)], "artifactDirectoryPath": str(art)}
            sentinel.post({**base, "toolCall": {"name": "read_file", "args": {"Path": str(target)}}})

            fail_verify = {
                **base,
                "toolResult": {"exitCode": 1},
                "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest -v"}},
            }
            edit_payload = {
                **base,
                "toolCall": {"name": "write_file", "args": {"Path": str(target), "Content": "val = 1\n"}},
            }

            # Red discovery test BEFORE editing must NOT add a strike
            sentinel.post(fail_verify)
            sentinel.post(fail_verify)
            self.assertEqual(sentinel.pre(edit_payload)["decision"], "allow")

            # Writing a new red TDD test file and watching it fail must NOT add a strike
            tdd_test = root / "tests" / "test_calc.py"
            tdd_payload = {
                **base,
                "toolCall": {"name": "write_file", "args": {"Path": str(tdd_test), "Content": "def test_red():\n    assert False\n"}},
            }
            sentinel.post(tdd_payload)
            sentinel.post(fail_verify)
            self.assertEqual(sentinel.pre(edit_payload)["decision"], "allow")

            # Strike 1: prod edit -> fail; extra diagnostic fails without editing must NOT add strikes
            sentinel.post(edit_payload)
            sentinel.post(fail_verify)
            sentinel.post(fail_verify)
            sentinel.post(fail_verify)
            self.assertEqual(sentinel.pre(edit_payload)["decision"], "allow")

            # Strike 2: edit -> fail
            sentinel.post(edit_payload)
            sentinel.post(fail_verify)
            self.assertEqual(sentinel.pre(edit_payload)["decision"], "allow")

            # Strike 3: edit -> fail locks further edits
            sentinel.post(edit_payload)
            sentinel.post(fail_verify)
            locked = sentinel.pre(edit_payload)
            self.assertEqual(locked["decision"], "deny")
            self.assertIn("3-Strike Governor", locked["reason"])

            # Diagnostic read_file steps down 3 -> 2
            sentinel.post({**base, "toolCall": {"name": "read_file", "args": {"Path": str(target)}}})
            self.assertEqual(sentinel.pre(edit_payload)["decision"], "allow")

            # Passing verbose unittest -v clears strikes and unverified_code_edits
            sentinel.post({**base, "toolCall": {"name": "run_command", "args": {"CommandLine": "python3 -m unittest discover -s scripts/tests -v"}}})
            self.assertEqual(sentinel.pre(edit_payload)["decision"], "allow")
            stop_ok = sentinel.stop({**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": True, "executionNum": 0})
            self.assertEqual(stop_ok["decision"], "allow")

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

            bg_stop = {**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": False, "executionNum": 0}
            self.assertEqual(sentinel.stop(bg_stop)["decision"], "allow")

            idle_stop = {**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": True, "executionNum": 0}
            blocked = sentinel.stop(idle_stop)
            self.assertEqual(blocked["decision"], "continue")
            self.assertIn("Verify-Before-Stop", blocked["reason"])

            # git add app.py must NOT clear Verify-Before-Stop
            sentinel.post({**base, "toolCall": {"name": "run_command", "args": {"CommandLine": "git add engine.py"}}})
            still_blocked = sentinel.stop(idle_stop)
            self.assertEqual(still_blocked["decision"], "continue")

            # Vacuous 0-test and all-skipped runs must NOT clear Verify-Before-Stop
            for vacuous_out in (
                "Ran 0 tests in 0.000s\n\nOK\n",
                "collected 0 items\nno tests ran in 0.01s\n",
                "test result: ok. 0 passed; 0 failed\n",
                "3 skipped in 0.01s\n",
                "Ran 2 tests in 0.001s\n\nOK (skipped=2)\n",
            ):
                sentinel.post(
                    {
                        **base,
                        "toolResult": {"exitCode": 0, "stdout": vacuous_out},
                        "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest -v"}},
                    }
                )
                self.assertEqual(sentinel.stop(idle_stop)["decision"], "continue", vacuous_out)

            cont_stop = dict(idle_stop, continuationActive=True)
            self.assertEqual(sentinel.stop(cont_stop)["decision"], "allow")

            # Partial-skip run with real passes (unittest) MUST clear Verify-Before-Stop
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "Ran 5 tests in 0.02s\n\nOK (skipped=2)\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "python3 -m unittest discover -s tests -v"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "allow")

            # Re-dirty and confirm multi-suite cargo test with 12 passed + 0 doc-tests MUST clear Verify-Before-Stop
            sentinel.post({**base, "toolCall": {"name": "write_file", "args": {"Path": str(target), "Content": "a = 3\n"}}})
            cargo_out = (
                "running 12 tests\n"
                "test result: ok. 12 passed; 0 failed\n\n"
                "Doc-tests app\n"
                "running 0 tests\n"
                "test result: ok. 0 passed; 0 failed\n"
            )
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": cargo_out},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "cargo test"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "allow")

    def test_single_pass_ast_edit_file_conftest_and_jetski_brain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mod = Path(tmp) / "svc.py"
            tst = Path(tmp) / "tests" / "test_svc.py"
            conftest = Path(tmp) / "tests" / "conftest.py"
            tst.parent.mkdir(parents=True)
            dyn_user_path = "/".join(["", "home", "demo", "repo"])

            # tests/conftest.py without test_* functions MUST be allowed (not misclassified as test file)
            cf_res = sentinel.pre(
                {
                    "workspacePaths": [tmp],
                    "toolCall": {"name": "write_file", "args": {"Path": str(conftest), "Content": "FIXTURE_VAL = 42\n"}},
                }
            )
            self.assertEqual(cf_res["decision"], "allow", cf_res)

            # Artifact writes inside dynamic artifactDirectoryPath (e.g. jetski/brain) MUST be allowed
            art_dir = Path(tmp) / ".gemini" / "jetski" / "brain" / "conv-1"
            art_dir.mkdir(parents=True)
            art_res = sentinel.pre(
                {
                    "workspacePaths": [tmp],
                    "artifactDirectoryPath": str(art_dir),
                    "toolCall": {
                        "name": "write_to_file",
                        "args": {
                            "TargetFile": str(art_dir / "plan.md"),
                            "CodeContent": "# Plan\n",
                            "ArtifactMetadata": {"Summary": "Plan", "UserFacing": True, "RequestFeedback": False},
                        },
                    },
                }
            )
            self.assertEqual(art_res["decision"], "allow", art_res)

            cases = [
                (str(mod), "def broken(:\n", "deny", "FM-H02"),
                (str(mod), "class X:\n    def __eq__(self, other):\n        return True\n", "deny", "RW-02"),
                (str(mod), "def f():\n    try:\n        return 1\n    except Exception:\n        pass\n", "ask", "RW-08"),
                (str(mod), "from unittest.mock import MagicMock\n", "ask", "RW-11"),
                (str(mod), 'import os\nx = os.environ.get("PYTEST_CURRENT_TEST")\n', "deny", "RW-17"),
                (str(tst), "def test_cheat():\n    assert True\n", "deny", "RW-01"),
                (str(tst), f'p = "{dyn_user_path}"\ndef test_p():\n    assert len(p) > 0\n', "deny", "TQ-03"),
            ]
            for path, content, expected_dec, expected_tag in cases:
                res = sentinel.pre(
                    {
                        "workspacePaths": [tmp],
                        "toolCall": {"name": "write_to_file", "args": {"TargetFile": path, "CodeContent": content}},
                    }
                )
                self.assertEqual(res["decision"], expected_dec, f"{expected_tag}: {res}")
                self.assertIn(expected_tag, res["reason"])

            # edit_file / replace_file_content checks: empty target, target not found, syntax break, valid edit
            mod.write_text("x = 1\ny = 2\n", encoding="utf-8")
            empty_t = sentinel.pre(
                {"workspacePaths": [tmp], "toolCall": {"name": "edit_file", "args": {"Path": str(mod), "Target": "", "Replacement": "z = 3"}}}
            )
            self.assertEqual(empty_t["decision"], "deny")
            self.assertIn("FM-H03", empty_t["reason"])

            bad_edit = sentinel.pre(
                {
                    "workspacePaths": [tmp],
                    "toolCall": {
                        "name": "replace_file_content",
                        "args": {"TargetFile": str(mod), "TargetContent": "x = 1", "ReplacementContent": "def broken(:"},
                    },
                }
            )
            self.assertEqual(bad_edit["decision"], "deny")
            self.assertIn("FM-H02", bad_edit["reason"])

            ok_edit = sentinel.pre(
                {
                    "workspacePaths": [tmp],
                    "toolCall": {
                        "name": "replace_file_content",
                        "args": {"TargetFile": str(mod), "TargetContent": "x = 1", "ReplacementContent": "x = 10"},
                    },
                }
            )
            self.assertEqual(ok_edit["decision"], "allow")

            # Missing write content fails closed (ask / subagent deny) instead of bypassing AST
            missing_args = sentinel.pre({"workspacePaths": [tmp], "toolCall": {"name": "write_to_file", "args": {"TargetFile": str(mod)}}})
            self.assertEqual(missing_args["decision"], "ask")

            # Subagent upgrades 'ask' (e.g., RW-08) to hard 'deny'
            sub_res = sentinel.pre(
                {
                    "workspacePaths": [tmp],
                    "parentConversationId": "p-1",
                    "toolCall": {
                        "name": "write_file",
                        "args": {"Path": str(mod), "Content": "import contextlib\nwith contextlib.suppress(Exception):\n    x = 1\n"},
                    },
                }
            )
            self.assertEqual(sub_res["decision"], "deny")

    def test_shell_mcp_multiroot_and_verification_command_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root1 = Path(tmp) / "r1"
            root2 = Path(tmp) / "r2"
            (root1 / ".agents").mkdir(parents=True)
            root2.mkdir(parents=True)
            (root1 / ".agents" / "acceptance.lock.json").write_text(
                json.dumps({"required_files": ["README.md"], "python_syntax": []}),
                encoding="utf-8",
            )
            # Multi-root workspace must still enforce acceptance.lock.json
            stop_missing = sentinel.stop({"workspacePaths": [str(root1), str(root2)], "terminationReason": "NO_TOOL_CALL", "executionNum": 0})
            self.assertEqual(stop_missing["decision"], "continue")
            self.assertIn("README.md", stop_missing["reason"])

            (root1 / "README.md").write_text("# Ready\n", encoding="utf-8")
            self.assertEqual(
                sentinel.stop({"workspacePaths": [str(root1), str(root2)], "terminationReason": "NO_TOOL_CALL", "executionNum": 0})["decision"],
                "allow",
            )

            # Harmless 2>&1 on read-only test command must NOT trigger RW-04
            ro_2_1 = sentinel.pre({"workspacePaths": [str(root1)], "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest scripts/tests/test_sentinel.py 2>&1"}}})
            self.assertEqual(ro_2_1["decision"], "allow")

            # POSIX cp onto protected hook file MUST trigger RW-04
            cp_gov = sentinel.pre({"workspacePaths": [str(root1)], "toolCall": {"name": "run_command", "args": {"CommandLine": "cp /tmp/x scripts/sentinel.py"}}})
            self.assertEqual(cp_gov["decision"], "force_ask")

            # .env.example is allowed; .env is gated
            env_ex = sentinel.pre({"workspacePaths": [str(root1)], "toolCall": {"name": "run_command", "args": {"CommandLine": "cat .env.example"}}})
            self.assertEqual(env_ex["decision"], "allow")
            env_real = sentinel.pre({"workspacePaths": [str(root1)], "toolCall": {"name": "run_command", "args": {"CommandLine": "cat .env"}}})
            self.assertEqual(env_real["decision"], "force_ask")

            push_main = sentinel.pre({"workspacePaths": [str(root1)], "toolCall": {"name": "run_command", "args": {"CommandLine": "git push origin main"}}})
            self.assertEqual(push_main["decision"], "force_ask")
            push_sub = sentinel.pre({"workspacePaths": [str(root1)], "parentConversationId": "p-1", "toolCall": {"name": "run_command", "args": {"CommandLine": "git push origin main"}}})
            self.assertEqual(push_sub["decision"], "deny")

            # MCP token boundaries: desktop_list allowed, github_push_files / delete_instance gated
            self.assertEqual(sentinel.pre({"workspacePaths": [str(root1)], "toolCall": {"name": "call_mcp_tool", "args": {"ToolName": "desktop_list"}}})["decision"], "allow")
            self.assertEqual(sentinel.pre({"workspacePaths": [str(root1)], "toolCall": {"name": "call_mcp_tool", "args": {"ToolName": "github_push_files"}}})["decision"], "force_ask")
            self.assertEqual(sentinel.pre({"workspacePaths": [str(root1)], "toolCall": {"name": "call_mcp_tool", "args": {"ToolName": "delete_instance"}}})["decision"], "force_ask")

            # Verification command accuracy
            self.assertTrue(sentinel.is_meaningful_verification_command("python3 -m unittest discover -s scripts/tests -v"))
            self.assertTrue(sentinel.is_meaningful_verification_command("pytest -v"))
            self.assertTrue(sentinel.is_meaningful_verification_command("pwsh -File scripts/verify_all.ps1"))
            self.assertFalse(sentinel.is_meaningful_verification_command("python3 -V"))
            self.assertFalse(sentinel.is_meaningful_verification_command("git add app.py"))
            self.assertFalse(sentinel.is_meaningful_verification_command("git status"))

    def test_cli_subprocess_pre_post_stop_chain_and_bootstrap_contract(self) -> None:
        script = str(SCRIPTS_DIR / "sentinel.py")

        def run_hook(mode: str, payload: dict) -> dict:
            proc = subprocess.run(
                [sys.executable, script, mode],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            (root / ".git").mkdir(parents=True)
            art.mkdir(parents=True)
            mod = root / "app.py"
            base = {"workspacePaths": [str(root)], "artifactDirectoryPath": str(art)}

            blind = run_hook("pre", {**base, "toolCall": {"name": "write_file", "args": {"Path": str(mod), "Content": "x = 1\n"}}})
            self.assertEqual(blind["decision"], "deny")

            run_hook("post", {**base, "toolCall": {"name": "read_file", "args": {"Path": str(root / "README.md")}}})
            allowed = run_hook("pre", {**base, "toolCall": {"name": "write_file", "args": {"Path": str(mod), "Content": "x = 1\n"}}})
            self.assertEqual(allowed["decision"], "allow")

            mod.write_text("x = 1\n", encoding="utf-8")
            run_hook("post", {**base, "toolCall": {"name": "write_file", "args": {"Path": str(mod), "Content": "x = 1\n"}}})
            blocked_stop = run_hook("stop", {**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": True, "executionNum": 0})
            self.assertEqual(blocked_stop["decision"], "continue")
            self.assertIn("Verify-Before-Stop", blocked_stop["reason"])

            run_hook("post", {**base, "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest -v"}}})
            ok_stop = run_hook("stop", {**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": True, "executionNum": 0})
            self.assertEqual(ok_stop["decision"], "allow")

            # Verify hooks.json.portable is valid JSON with all 5 hook events and placeholders
            portable = json.loads((REPO_ROOT / "hooks.json.portable").read_text(encoding="utf-8"))
            self.assertIn("PreToolUse", portable["sentinel"])
            self.assertIn("PostToolUse", portable["sentinel"])
            self.assertIn("Stop", portable["sentinel"])
            self.assertIn("SessionStart", portable["operator-router"])
            self.assertIn("PreInvocation", portable["operator-router"])
            self.assertNotIn("matcher", portable["sentinel"]["Stop"][0])
            self.assertNotIn("matcher", portable["operator-router"]["SessionStart"][0])

            # Verify bootstrap.sh resolves absolute paths on POSIX
            if os.name != "nt" and shutil.which("bash"):
                boot_root = Path(tmp) / "boot_test"
                cfg = boot_root / "config"
                cfg.mkdir(parents=True)
                for fn in ("GEMINI.global.md", "hooks.json.portable", "mcp_config.portable.json", "bootstrap.sh"):
                    shutil.copy2(REPO_ROOT / fn, cfg / fn)
                # Copy only a minimal passing test so bootstrap completes quickly
                (cfg / "scripts" / "tests").mkdir(parents=True)
                (cfg / "scripts" / "tests" / "test_smoke.py").write_text(
                    "import unittest\nclass S(unittest.TestCase):\n    def test_ok(self):\n        self.assertEqual(1, 1)\n    def test_neg(self):\n        self.assertNotEqual(1, 2)\n",
                    encoding="utf-8",
                )
                proc = subprocess.run(["bash", str(cfg / "bootstrap.sh"), "--force"], capture_output=True, text=True, check=False)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                gen_hooks = (cfg / "hooks.json").read_text(encoding="utf-8")
                self.assertNotIn("__PYTHON__", gen_hooks)
                self.assertNotIn("__CONFIG_DIR__", gen_hooks)
                self.assertIn(str(cfg), gen_hooks)
                self.assertTrue((boot_root / "GEMINI.md").is_file())
                self.assertTrue((cfg / "mcp_config.json").is_file())


if __name__ == "__main__":
    unittest.main()
