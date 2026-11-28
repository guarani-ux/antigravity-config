#!/usr/bin/env python3
"""Tests for test_quality_gate.py verifying rejection of weak/tautological/coupled tests."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import test_quality_gate  # noqa: E402


class TestTestQualityGate(unittest.TestCase):
    """Verify TQ-01..TQ-05 catch bad tests and allow high-caliber portable tests."""

    def test_rejects_zero_assertion_and_tautology(self) -> None:
        bad_src = (
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_empty(self):\n"
            "        x = 1 + 1\n"
            "    def test_tautology(self):\n"
            "        assert True\n"
            "    def test_self_eq(self):\n"
            "        val = 5\n"
            "        self.assertEqual(val, val)\n"
        )
        findings = test_quality_gate.check_test_source(bad_src, "test_bad.py")
        rules = [f.rule_id for f in findings]
        self.assertEqual(rules.count("TQ-01"), 3, findings)
        self.assertIn("TQ-05", rules)

    def test_rejects_unconditional_skip_and_machine_coupled_paths(self) -> None:
        fake_user_path = "C:" + "/Users/" + "someone/secret"
        fake_uuid = "11111111-2222-3333-4444-555555555555"
        bad_src = (
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    @unittest.skip('later')\n"
            "    def test_skipped(self):\n"
            "        self.assertEqual(1, 2)\n"
            "    def test_local_machine(self):\n"
            f"        p = '{fake_user_path}'\n"
            f"        s = session_id='{fake_uuid}'\n"
            "        self.assertNotEqual(p, s)\n"
        )
        findings = test_quality_gate.check_test_source(bad_src, "test_coupled.py")
        rules = {f.rule_id for f in findings}
        self.assertIn("TQ-02", rules)
        self.assertIn("TQ-03", rules)

    def test_rejects_happy_path_only_and_skipped_exec_without_live_exec(self) -> None:
        bad_src = (
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_one(self):\n"
            "        ok = run_check(execute_hooks=False)\n"
            "        self.assertTrue(ok)\n"
            "    def test_two(self):\n"
            "        self.assertEqual(1 + 1, 2)\n"
        )
        findings = test_quality_gate.check_test_source(bad_src, "test_happy.py")
        rules = {f.rule_id for f in findings}
        self.assertIn("TQ-04", rules)
        self.assertIn("TQ-05", rules)

    def test_accepts_portable_positive_and_negative_suite(self) -> None:
        good_src = (
            "import tempfile, unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_allows_valid_input(self):\n"
            "        with tempfile.TemporaryDirectory() as tmp:\n"
            "            self.assertTrue(bool(tmp))\n"
            "    def test_denies_invalid_input(self):\n"
            "        with self.assertRaises(ValueError):\n"
            "            int('not-a-number')\n"
        )
        findings = test_quality_gate.check_test_source(good_src, "test_good.py")
        self.assertEqual(findings, [], findings)

    def test_cli_reports_exit_1_on_violation_and_0_on_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test_sample.py"
            p.write_text("def test_bad():\n    pass\n", encoding="utf-8")
            bad = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "test_quality_gate.py"), "--json", str(p)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bad.returncode, 1)
            self.assertGreaterEqual(json.loads(bad.stdout)["count"], 1)

            p.write_text(
                "def test_ok():\n    assert compute(2) == 4\n\n"
                "def test_rejects():\n    assert run_bad() == 'FAIL'\n",
                encoding="utf-8",
            )
            good = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "test_quality_gate.py"), "--json", str(p)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(good.returncode, 0, good.stdout)

    def test_tq05_rejects_happy_path_returncode_zero_only(self) -> None:
        """Fails if happy-path assertEqual(proc.returncode, 0) satisfies TQ-05 alone."""
        bad_src = (
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_happy_cli(self):\n"
            "        proc = run_ok()\n"
            "        self.assertEqual(proc.returncode, 0)\n"
            "    def test_math(self):\n"
            "        self.assertEqual(1 + 1, 2)\n"
        )
        findings = test_quality_gate.check_test_source(bad_src, "test_happy_rc0.py")
        rules = {f.rule_id for f in findings}
        self.assertIn("TQ-05", rules, findings)

    def test_tq04_rejects_live_named_test_skipping_hook_execution(self) -> None:
        """Fails if a test named 'live' skips hooks even when a sibling executes them."""
        bad_src = (
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_temp_hooks(self):\n"
            "        rep = run_doctor(repo, execute_hooks=True)\n"
            "        self.assertEqual(rep.fail_count, 0)\n"
            "    def test_live_workspace_hooks(self):\n"
            "        rep = run_doctor(repo, execute_hooks=False)\n"
            "        self.assertEqual(rep.fail_count, 0)\n"
            "    def test_rejects_bad(self):\n"
            "        self.assertNotEqual('FAIL', 'PASS')\n"
        )
        findings = test_quality_gate.check_test_source(bad_src, "test_fake_live.py")
        rules = {f.rule_id for f in findings}
        self.assertIn("TQ-04", rules, findings)


if __name__ == "__main__":
    unittest.main()
