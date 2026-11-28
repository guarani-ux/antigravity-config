#!/usr/bin/env python3
"""METAMORPHOSIS v3.0 semantic-integrity tests: obligations, evidence identity, violation identity, and locking."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sentinel  # noqa: E402


class TestSemanticIntegrity(unittest.TestCase):
    """Prove obligation-evidence-identity invariants over indirect proxy heuristics."""

    def test_vacuous_dry_run_xfail_and_empty_captured_output_do_not_discharge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            (root / ".git").mkdir(parents=True)
            art.mkdir(parents=True)
            mod = root / "billing.py"
            mod.write_text("def charge():\n    return 1\n", encoding="utf-8")
            base = {"workspacePaths": [str(root)], "artifactDirectoryPath": str(art)}
            idle_stop = {**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": True, "executionNum": 0}

            sentinel.post({**base, "toolCall": {"name": "write_file", "args": {"Path": str(mod), "Content": "def charge():\n    return 2\n"}}})
            mod.write_text("def charge():\n    return 2\n", encoding="utf-8")

            non_discharging = [
                ("pytest", {"exitCode": 0, "stdout": ""}),
                ("pytest --collect-only", {"exitCode": 0, "stdout": "collected 5 items\n5 tests collected in 0.01s\n"}),
                ("pytest --co", {"exitCode": 0, "stdout": "collected 3 items\n"}),
                ("pytest", {"exitCode": 0, "stdout": "=== 2 xfailed in 0.04s ===\n"}),
                ("pytest -k none", {"exitCode": 0, "stdout": "collected 5 items / 5 deselected / 0 selected\n5 deselected in 0.01s\n"}),
                ("python3 -m unittest", {"exitCode": 0, "stdout": "Ran 1 test in 0.001s\n\nOK (expected failures=1)\n"}),
                ("python3 -m unittest", {"exitCode": 0, "stdout": "Ran 2 tests in 0.001s\n\nOK (skipped=1, expected failures=1)\n"}),
                ("cargo test -- --list", {"exitCode": 0, "stdout": "test_a: test\n1 test, 0 benchmarks\n"}),
                ("go test ./...", {"exitCode": 0, "stdout": "?   \texample/pkg\t[no test files]\n"}),
            ]
            for cmd, tool_res in non_discharging:
                sentinel.post({**base, "toolResult": tool_res, "toolCall": {"name": "run_command", "args": {"CommandLine": cmd}}})
                res = sentinel.stop(idle_stop)
                self.assertEqual(res["decision"], "continue", f"Should NOT discharge on {cmd!r} / {tool_res!r}")

            # Genuine passing execution discharges obligations cleanly
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "=== 3 passed in 0.05s ===\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest -v"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "allow")

    def test_post_verification_disk_drift_and_compound_mutation_reopen_obligations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            (root / ".git").mkdir(parents=True)
            art.mkdir(parents=True)
            mod = root / "engine.py"
            mod.write_text("VAL = 1\n", encoding="utf-8")
            base = {"workspacePaths": [str(root)], "artifactDirectoryPath": str(art)}
            idle_stop = {**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": True, "executionNum": 0}

            # Edit -> verify -> pass
            mod.write_text("VAL = 2\n", encoding="utf-8")
            sentinel.post({**base, "toolCall": {"name": "write_file", "args": {"Path": str(mod), "Content": "VAL = 2\n"}}})
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "2 passed in 0.02s\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "allow")

            # Out-of-band disk mutation after passing verification MUST be caught at Stop via SHA-256 drift
            mod.write_text("VAL = 999\n", encoding="utf-8")
            drifted_stop = sentinel.stop(idle_stop)
            self.assertEqual(drifted_stop["decision"], "continue")
            self.assertIn("Verify-Before-Stop", drifted_stop["reason"])

            # Compound `pytest && echo 'VAL = 3' >> engine.py` must NOT discharge obligations
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "2 passed in 0.02s\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest && echo 'VAL = 3' >> engine.py"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "continue")

    def test_semantic_violation_identity_catches_equal_count_swaps_and_bool_collapse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            (root / ".git").mkdir(parents=True)
            (root / "tests").mkdir(parents=True)
            art.mkdir(parents=True)
            base = {"workspacePaths": [str(root)], "artifactDirectoryPath": str(art)}
            sentinel.post({**base, "toolCall": {"name": "read_file", "args": {"Path": str(root / "README.md")}}})

            # 1. Boolean collapse: legacy assert True in test_old must NOT permit adding assert True in test_auth
            tfile = root / "tests" / "test_auth.py"
            tfile.write_text(
                "def test_old():\n    assert True\n\n"
                "def test_auth():\n    assert check_auth() != 'DENY'\n",
                encoding="utf-8",
            )
            add_second_cheat = sentinel.pre(
                {
                    **base,
                    "toolCall": {
                        "name": "edit_file",
                        "args": {
                            "Path": str(tfile),
                            "Target": "assert check_auth() != 'DENY'",
                            "Replacement": "assert True",
                        },
                    },
                }
            )
            self.assertEqual(add_second_cheat["decision"], "deny")

            # Positive control: editing an unrelated line (with line shift) in test_auth is still allowed
            legit_edit = sentinel.pre(
                {
                    **base,
                    "toolCall": {
                        "name": "edit_file",
                        "args": {
                            "Path": str(tfile),
                            "Target": "assert check_auth() != 'DENY'",
                            "Replacement": "res = check_auth()\n    assert res != 'DENY'",
                        },
                    },
                }
            )
            self.assertEqual(legit_edit["decision"], "allow")

            # 2. Equal-count RW-08 swap: removing suppress in fn_a while adding except Exception: pass in fn_b
            mfile = root / "svc.py"
            mfile.write_text(
                "import contextlib\n"
                "def fn_a():\n    with contextlib.suppress(FileNotFoundError):\n        cleanup()\n\n"
                "def fn_b():\n    return charge()\n",
                encoding="utf-8",
            )
            swapped_rw08 = (
                "def fn_a():\n    cleanup()\n\n"
                "def fn_b():\n    try:\n        return charge()\n    except Exception:\n        pass\n"
            )
            rw08_res = sentinel.pre({**base, "toolCall": {"name": "write_file", "args": {"Path": str(mfile), "Content": swapped_rw08}}})
            self.assertEqual(rw08_res["decision"], "ask")
            self.assertIn("RW-08", rw08_res["reason"])

            # 3. Equal-count TQ cross-rule swap: removing TQ-03 path while introducing TQ-02 unconditional skip
            dyn_path = "/".join(["", "home", "demo", "file.txt"])
            qfile = root / "tests" / "test_swap.py"
            qfile.write_text(
                "import unittest\n"
                f"def test_a():\n    p = '{dyn_path}'\n    assert run_a(p) == 1\n\n"
                "def test_b():\n    assert run_b() != 0\n",
                encoding="utf-8",
            )
            swapped_tq = (
                "import unittest\n"
                "def test_a():\n    assert run_a('ok') == 1\n\n"
                "@unittest.skip('later')\n"
                "def test_b():\n    assert run_b() != 0\n"
            )
            tq_res = sentinel.pre({**base, "toolCall": {"name": "write_file", "args": {"Path": str(qfile), "Content": swapped_tq}}})
            self.assertIn(tq_res["decision"], ("ask", "deny"))

            # 4. Equal-count RW-18 split-suffix secret token swap must still be denied (chunk alone isn't a secret!)
            tok1 = "ghp_" + ("A1b2C3d4" * 4) + "Aa11"
            tok2 = "ghp_" + ("Z9y8X7w6" * 4) + "Bb22"
            sfile = root / "cfg.py"
            sfile.write_text(f"TOKEN = '{tok1}'\n", encoding="utf-8")
            sec_swap = sentinel.pre(
                {
                    **base,
                    "toolCall": {
                        "name": "edit_file",
                        "args": {"Path": str(sfile), "Target": tok1[4:], "Replacement": tok2[4:]},
                    },
                }
            )
            self.assertEqual(sec_swap["decision"], "deny")
            self.assertIn("RW-18", sec_swap["reason"])

    def test_unrelated_passing_tests_and_partial_obligation_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            (root / ".git").mkdir(parents=True)
            (root / "tests").mkdir(parents=True)
            art.mkdir(parents=True)
            billing = root / "billing.py"
            auth = root / "auth.py"
            billing.write_text("def charge():\n    return 10\n", encoding="utf-8")
            auth.write_text("def check():\n    return True\n", encoding="utf-8")
            (root / "tests" / "test_unrelated.py").write_text("def test_math():\n    assert 1 + 1 == 2\n", encoding="utf-8")
            (root / "tests" / "test_billing.py").write_text("import billing\ndef test_b():\n    assert billing.charge() == 10\n", encoding="utf-8")
            (root / "tests" / "test_integration.py").write_text("import auth\ndef test_a():\n    assert auth.check() is True\n", encoding="utf-8")

            base = {"workspacePaths": [str(root)], "artifactDirectoryPath": str(art)}
            idle_stop = {**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": True, "executionNum": 0}

            sentinel.post({**base, "toolCall": {"name": "write_file", "args": {"Path": str(billing), "Content": billing.read_text(encoding="utf-8")}}})
            sentinel.post({**base, "toolCall": {"name": "write_file", "args": {"Path": str(auth), "Content": auth.read_text(encoding="utf-8")}}})

            # Unrelated passing test MUST NOT discharge either billing.py or auth.py
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "=== 1 passed in 0.01s ===\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest tests/test_unrelated.py"}},
                }
            )
            stop1 = sentinel.stop(idle_stop)
            self.assertEqual(stop1["decision"], "continue")
            from sentinel.state import load_state

            st1 = load_state(base)
            self.assertIsNotNone(st1.last_evidence)
            self.assertEqual(st1.last_evidence.detail, "unrelated_scope")
            self.assertEqual(len(st1.obligations), 2)

            # Targeted test_billing.py discharges billing.py only; auth.py remains open
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "=== 1 passed in 0.01s ===\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest tests/test_billing.py"}},
                }
            )
            stop2 = sentinel.stop(idle_stop)
            self.assertEqual(stop2["decision"], "continue")
            self.assertIn("auth.py", stop2["reason"])
            self.assertNotIn("billing.py", stop2["reason"])

            # Targeted test_integration.py imports auth -> directly discharges auth.py
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "=== 1 passed in 0.01s ===\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest tests/test_integration.py"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "allow")

            # Editing a test file and running a DIFFERENT test file keeps the edited test file open
            tb = root / "tests" / "test_billing.py"
            sentinel.post({**base, "toolCall": {"name": "write_file", "args": {"Path": str(tb), "Content": tb.read_text(encoding="utf-8")}}})
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "=== 1 passed in 0.01s ===\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest tests/test_unrelated.py"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "continue")
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "=== 1 passed in 0.01s ===\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest tests/test_billing.py"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "allow")

    def test_strict_output_evidence_stdout_strikes_v1_migration_and_lock_protection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            (root / ".git").mkdir(parents=True)
            art.mkdir(parents=True)
            mod = root / "worker.py"
            mod.write_text("X = 1\n", encoding="utf-8")
            base = {"workspacePaths": [str(root)], "artifactDirectoryPath": str(art)}
            idle_stop = {**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": True, "executionNum": 0}

            # 1. Strict require_output_evidence=True rejects absent output channel
            from sentinel.lifecycle import evaluate_verification_evidence
            from sentinel.policy import classify_verification_command
            from sentinel.state import compute_state_digest, file_digest, load_state

            vc = classify_verification_command("pytest -v")
            self.assertIsNotNone(vc)
            ev_strict = evaluate_verification_evidence(
                {**base, "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest -v"}}},
                vc,
                "sha256:abc",
                require_output_evidence=True,
            )
            self.assertEqual(ev_strict.outcome, "UNKNOWN")
            self.assertFalse(ev_strict.discharged)

            # 2. stdout-only failure (exitCode=0, stdout='1 failed') increments 3-Strike Governor
            sentinel.post({**base, "toolCall": {"name": "read_file", "args": {"Path": str(mod)}}})
            for i in range(3):
                mod.write_text(f"X = {i + 2}\n", encoding="utf-8")
                sentinel.post({**base, "toolCall": {"name": "write_file", "args": {"Path": str(mod), "Content": f"X = {i + 2}\n"}}})
                sentinel.post(
                    {
                        **base,
                        "toolResult": {"exitCode": 0, "stdout": "=== 1 failed in 0.02s ===\n"},
                        "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest"}},
                    }
                )
            st = load_state(base)
            self.assertEqual(st.repair_strikes, 3)
            blocked_edit = sentinel.pre({**base, "toolCall": {"name": "write_file", "args": {"Path": str(mod), "Content": "X = 99\n"}}})
            self.assertEqual(blocked_edit["decision"], "deny")
            self.assertIn("3-Strike", blocked_edit["reason"])

            # 3. Transparent v1 -> v2 state read-migration preserves open obligations
            import json

            (art / "sentinel-state.json").write_text(
                json.dumps({"oriented": True, "unverified_code_edits": True, "edited_code_files": [str(mod)]}),
                encoding="utf-8",
            )
            migrated = load_state(base)
            self.assertEqual(migrated.schema_version, 2)
            self.assertIn(str(mod), migrated.obligations)
            self.assertEqual(migrated.obligations[str(mod)], file_digest(str(mod)))
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "continue")

            # 4. sentinel-state.lock is mechanically protected from direct edit and shell removal
            lock_write = sentinel.pre({**base, "toolCall": {"name": "write_file", "args": {"Path": str(art / "sentinel-state.lock"), "Content": "x"}}})
            self.assertEqual(lock_write["decision"], "deny")
            self.assertIn("RW-06", lock_write["reason"])
            lock_redir = sentinel.pre({**base, "toolCall": {"name": "run_command", "args": {"CommandLine": "echo x > sentinel-state.lock"}}})
            self.assertEqual(lock_redir["decision"], "force_ask")
            self.assertIn("RW-04", lock_redir["reason"])
            lock_redir_sub = sentinel.pre({**base, "parentConversationId": "parent-1", "toolCall": {"name": "run_command", "args": {"CommandLine": "echo x > sentinel-state.lock"}}})
            self.assertEqual(lock_redir_sub["decision"], "deny")

            # 5. State digest sensitivity: single-byte change or flag toggle changes digest deterministically
            d1 = compute_state_digest(1, {str(mod): file_digest(str(mod))}, False)
            d1_repeat = compute_state_digest(1, {str(mod): file_digest(str(mod))}, False)
            self.assertEqual(d1, d1_repeat)
            mod.write_text("X = 999\n", encoding="utf-8")
            d2 = compute_state_digest(1, {str(mod): file_digest(str(mod))}, False)
            d3 = compute_state_digest(1, {str(mod): file_digest(str(mod))}, True)
            self.assertNotEqual(d1, d2)
            self.assertNotEqual(d2, d3)

    def test_concurrent_post_state_updates_preserve_all_obligations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            (root / ".git").mkdir(parents=True)
            art.mkdir(parents=True)
            base = {"workspacePaths": [str(root)], "artifactDirectoryPath": str(art)}

            files = []
            for i in range(8):
                fp = root / f"mod_{i}.py"
                fp.write_text(f"V = {i}\n", encoding="utf-8")
                files.append(fp)

            barrier = threading.Barrier(len(files))
            errors: list[Exception] = []

            def worker(fp: Path) -> None:
                try:
                    barrier.wait(timeout=5)
                    sentinel.post({**base, "toolCall": {"name": "write_file", "args": {"Path": str(fp), "Content": fp.read_text(encoding="utf-8")}}})
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(fp,)) for fp in files]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            self.assertEqual(errors, [])
            from sentinel.state import load_state

            st = load_state(base)
            tracked = set(getattr(st, "obligations", {}).keys()) | set(getattr(st, "edited_code_files", []))
            expected = {os.path.realpath(str(fp)) for fp in files}
            self.assertEqual(tracked, expected)

    def test_retry_exhaustion_preserves_unresolved_obligations_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            (root / ".git").mkdir(parents=True)
            art.mkdir(parents=True)
            mod = root / "app.py"
            mod.write_text("x = 1\n", encoding="utf-8")
            base = {"workspacePaths": [str(root)], "artifactDirectoryPath": str(art)}

            sentinel.post({**base, "toolCall": {"name": "write_file", "args": {"Path": str(mod), "Content": "x = 2\n"}}})
            exhausted = sentinel.stop({**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": True, "executionNum": 2})
            self.assertEqual(exhausted["decision"], "allow")
            self.assertIn("unresolved", str(exhausted.get("reason") or "").lower())

            # M5: explicit executionNum=None must NOT bypass stop()
            null_exec = sentinel.stop({**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": True, "executionNum": None})
            self.assertEqual(null_exec["decision"], "continue")

    def test_blind_audit_regression_controls(self) -> None:
        """Executable regression suite for all M3.0 blind-verifier falsification findings (H1-H6, M1-M5, M7, L1)."""
        import json

        from sentinel.policy import classify_verification_command
        from sentinel.state import load_state
        import test_quality_gate

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            (root / ".git").mkdir(parents=True)
            (root / "src").mkdir(parents=True)
            (root / "tests" / "unit").mkdir(parents=True)
            art.mkdir(parents=True)
            base = {"workspacePaths": [str(root)], "artifactDirectoryPath": str(art)}
            idle_stop = {**base, "terminationReason": "NO_TOOL_CALL", "fullyIdle": True, "executionNum": 0}

            # H1: Pre-verify shell mutation + dry-run or unrelated test MUST stay dirty
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "collected 2 items\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "echo 'x = 999' > new_app.py && pytest --collect-only"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "continue")
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "=== 1 passed in 0.01s ===\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "echo 'x = 999' > new_app.py && pytest tests/test_unrelated.py"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "continue")
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "=== 2 passed in 0.01s ===\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "echo 'x = 999' > new_app.py && pytest"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "allow")
            # M-R1: Pre-verify mutation + failing trailing pytest MUST stay dirty and block stop()
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 1, "stdout": "=== 1 failed in 0.01s ===\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "echo 'x = 1000' > new_app.py && pytest"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "continue")
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "=== 2 passed in 0.01s ===\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "allow")

            # H2: _collect_scoped_tests catches tests inside `if` blocks and avoids FP on platform-gated TestCase
            hidden_bad = (
                "def test_real():\n    assert run() == 1\n"
                "    assert run() != 2\n"
                "if True:\n    def test_empty():\n        pass\n"
            )
            bad_findings = test_quality_gate.check_test_source(hidden_bad, "test_hidden.py")
            self.assertTrue(any(f.rule_id == "TQ-01" and f.symbol == "test_empty" for f in bad_findings))
            gated_ok = (
                "import sys, unittest\n"
                "if sys.platform == 'linux':\n"
                "    class T(unittest.TestCase):\n"
                "        def test_a(self):\n            self.assertEqual(run(), 1)\n"
                "        def test_b(self):\n            self.assertNotEqual(run(), 2)\n"
            )
            self.assertEqual(test_quality_gate.check_test_source(gated_ok, "test_gated.py"), [])

            # H3: Generic filename src/utils.py IS dischargeable by pytest tests/test_utils.py
            utils = root / "src" / "utils.py"
            utils.write_text("def fmt(x):\n    return str(x)\n", encoding="utf-8")
            (root / "tests" / "test_utils.py").write_text("def test_u():\n    assert True is not False\n", encoding="utf-8")
            sentinel.post({**base, "toolCall": {"name": "write_file", "args": {"Path": str(utils), "Content": utils.read_text(encoding="utf-8")}}})
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "=== 1 passed in 0.01s ===\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest tests/test_utils.py"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "allow")

            # H4: Directory target pytest tests/unit discharges prod obligations
            billing = root / "billing.py"
            billing.write_text("def charge():\n    return 5\n", encoding="utf-8")
            sentinel.post({**base, "toolCall": {"name": "write_file", "args": {"Path": str(billing), "Content": billing.read_text(encoding="utf-8")}}})
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "=== 4 passed in 0.02s ===\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest tests/unit"}},
                }
            )
            self.assertEqual(sentinel.stop(idle_stop)["decision"], "allow")

            # H5: Space-separated value flags keep suite-wide classification
            for suite_cmd in ("cargo test -j 4", "cargo test --features serde", "go test -count 1 ./...", "pytest -r a"):
                vc = classify_verification_command(suite_cmd)
                self.assertIsNotNone(vc, suite_cmd)
                self.assertEqual((vc.targets, vc.filters), ((), ()), f"Should be suite-wide: {suite_cmd}")

            # H6 & M2 & M3 & M4: Targeted filters, go empty warning / -c, unittest skipped+log, crucible doctor do NOT discharge
            sentinel.post({**base, "toolCall": {"name": "write_file", "args": {"Path": str(billing), "Content": "def charge():\n    return 6\n"}}})
            non_discharging = [
                ("pytest -m smoke", {"exitCode": 0, "stdout": "=== 1 passed in 0.01s ===\n"}),
                ("pytest --ignore tests/test_billing.py", {"exitCode": 0, "stdout": "=== 2 passed in 0.01s ===\n"}),
                ("cargo test -- test_unrelated", {"exitCode": 0, "stdout": "test result: ok. 1 passed; 0 failed\n"}),
                ("npm test -- test_unrelated.spec.js", {"exitCode": 0, "stdout": "Tests: 1 passed, 1 total\n"}),
                ("go test ./...", {"exitCode": 0, "stdout": "testing: warning: no tests to run\nPASS\nok  \texample/pkg\t0.001s\n"}),
                ("go test -c", {"exitCode": 0}),
                ("python3 -m unittest", {"exitCode": 0, "stdout": "1 passed in log output\nRan 2 tests in 0.001s\n\nOK (skipped=2)\n"}),
                ("python3 .agents/scripts/crucible_gate.py doctor", {"exitCode": 0, "stdout": "HEALTHY\n"}),
            ]
            for cmd, res in non_discharging:
                sentinel.post({**base, "toolResult": res, "toolCall": {"name": "run_command", "args": {"CommandLine": cmd}}})
                self.assertEqual(sentinel.stop(idle_stop)["decision"], "continue", f"Should NOT discharge on {cmd!r}")

            # M1: Adding a second tautology inside an already-tautological test is denied
            sentinel.post({**base, "toolCall": {"name": "read_file", "args": {"Path": str(billing)}}})
            taut_file = root / "tests" / "test_taut.py"
            taut_file.write_text("def test_legacy():\n    assert x == x\n    assert run() == 1\n", encoding="utf-8")
            add_taut = sentinel.pre(
                {
                    **base,
                    "toolCall": {
                        "name": "edit_file",
                        "args": {"Path": str(taut_file), "Target": "assert run() == 1", "Replacement": "assert y == y"},
                    },
                }
            )
            self.assertEqual(add_taut["decision"], "deny")

            # M7: Partial discharge of billing.py must NOT reset repair_strikes while auth.py stays open
            auth = root / "auth.py"
            auth.write_text("def ok():\n    return True\n", encoding="utf-8")
            sentinel.post({**base, "toolCall": {"name": "write_file", "args": {"Path": str(auth), "Content": "def ok():\n    return False\n"}}})
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 1, "stdout": "1 failed in 0.01s\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest"}},
                }
            )
            self.assertEqual(load_state(base).repair_strikes, 1)
            (root / "tests" / "test_billing.py").write_text("import billing\ndef test_b():\n    assert billing.charge() == 6\n", encoding="utf-8")
            sentinel.post(
                {
                    **base,
                    "toolResult": {"exitCode": 0, "stdout": "=== 1 passed in 0.01s ===\n"},
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest tests/test_billing.py"}},
                }
            )
            self.assertEqual(load_state(base).repair_strikes, 1)

            # L1: Malformed v2 obligations fails closed with corrupt=True
            (art / "sentinel-state.json").write_text(
                json.dumps({"schema_version": 2, "obligations": "bad"}),
                encoding="utf-8",
            )
            self.assertTrue(load_state(base).corrupt)


if __name__ == "__main__":
    unittest.main()
