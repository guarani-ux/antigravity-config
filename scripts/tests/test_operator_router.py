#!/usr/bin/env python3
"""Unit and CLI tests for operator_router signal detection, abstention, dedup, and context pressure."""

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

import operator_router  # noqa: E402


class TestOperatorRouter(unittest.TestCase):
    """Verify precision, abstention on neutral prompts, corrupt-state recovery, and context pressure."""

    def test_all_signal_rules_trigger(self) -> None:
        cases = [
            ("draft a calgary public library av script", "calgary-library-production"),
            ("turn this kickoff transcript into a brief", "meeting-brief"),
            ("build a python validator for our workflow", "waterwall"),
            ("help frame this stakeholder pitch email and trade-off", "plainspoken-partner"),
            ("please debug this failing test regression", "diagnosing-bugs"),
        ]
        for prompt, expected_tag in cases:
            signals = operator_router.detect_prompt_signals(prompt)
            self.assertTrue(
                any(expected_tag in s for s in signals),
                f"Expected '{expected_tag}' for prompt '{prompt}', got: {signals}",
            )

    def test_neutral_and_collision_prompts_abstain(self) -> None:
        neutral = [
            "refactor helper function in store.py",
            "check git status",
            "summarize the meeting notes from yesterday",
            "rename variable total_count to item_count",
            "watch a youtube tutorial on guitar",
            "log this error to stderr",
            "adjust the audio pitch by 2 semitones",
        ]
        for prompt in neutral:
            signals = operator_router.detect_prompt_signals(prompt)
            self.assertEqual(signals, [], f"False positive on prompt '{prompt}': {signals}")

    def test_session_start_emits_lean_constitution_banner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = operator_router.handle_session_start({"workspacePaths": [tmp]})
            msg = out["injectSteps"][0]["systemMessage"]["systemMessage"]
            self.assertIn("Global constitution active", msg)
            self.assertIn("waterwall", msg)
            self.assertNotIn("L9", msg)

    def test_pre_invocation_dedup_corrupt_state_recovery_and_ctx_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / ".system_generated" / "logs"
            log_dir.mkdir(parents=True)
            tp = log_dir / "transcript.jsonl"
            tp.write_text(json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "hi"}) + "\n", encoding="utf-8")

            # Corrupt state file must self-heal instead of killing PreInvocation
            seen = Path(tmp) / "operator-router-seen.json"
            seen.write_text("{corrupt json", encoding="utf-8")

            payload = {
                "conversationId": "test-conv",
                "artifactDirectoryPath": tmp,
                "lastUserInput": "please debug this traceback",
            }
            first = operator_router.handle_pre_invocation(payload)
            self.assertEqual(len(first["injectSteps"]), 1)
            self.assertIn("diagnosing-bugs", json.dumps(first))

            # Same prompt while context is still OK suppresses duplicate nudge
            second = operator_router.handle_pre_invocation(payload)
            self.assertEqual(second["injectSteps"], [])

            # Same prompt after context crosses DEPLETED MUST still emit DEPLETED alert
            big_chunk = json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "a" * 10000}) + "\n"
            tp.write_text(big_chunk * 65, encoding="utf-8")
            third = operator_router.handle_pre_invocation(payload)
            self.assertTrue(any("CONTEXT WINDOW DEPLETED" in s["systemMessage"]["systemMessage"] for s in third["injectSteps"]))

    def test_context_pressure_ignores_system_rows_and_resets_after_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tp = Path(tmp) / "transcript.jsonl"

            # 45 SYSTEM rows mentioning "USER_INPUT" must NOT inflate turn count
            sys_rows = [
                json.dumps({"type": "SYSTEM", "content": 'reading code with "USER_INPUT" literal'})
                for _ in range(45)
            ]
            tp.write_text("\n".join(sys_rows) + "\n", encoding="utf-8")
            ctx_sys = operator_router.measure_context_pressure(tp)
            self.assertEqual(ctx_sys["turns_since_checkpoint"], 0)
            self.assertEqual(ctx_sys["ctx_status"], "OK")

            # Compaction thresholds: 2 compactions -> WARN, 4 compactions -> DEPLETED
            tp.write_text((json.dumps({"type": "CHECKPOINT"}) + "\n") * 2, encoding="utf-8")
            self.assertEqual(operator_router.measure_context_pressure(tp)["ctx_status"], "WARN")
            tp.write_text((json.dumps({"type": "CHECKPOINT"}) + "\n") * 4, encoding="utf-8")
            self.assertEqual(operator_router.measure_context_pressure(tp)["ctx_status"], "DEPLETED")

            # Post-compaction byte reset works after 1 checkpoint
            big_chunk = json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "a" * 10000}) + "\n"
            tp.write_text(
                (big_chunk * 65)
                + json.dumps({"type": "CHECKPOINT"}) + "\n"
                + json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "fresh"}) + "\n",
                encoding="utf-8",
            )
            reset_ctx = operator_router.measure_context_pressure(tp)
            self.assertEqual(reset_ctx["ctx_status"], "OK")
            self.assertEqual(reset_ctx["compactions"], 1)
            self.assertEqual(reset_ctx["turns_since_checkpoint"], 1)

    def test_cli_subprocess_roundtrip_and_invalid_json_resilience(self) -> None:
        script = str(SCRIPTS_DIR / "operator_router.py")
        proc = subprocess.run(
            [sys.executable, script, "pre-invocation"],
            input=json.dumps({"lastUserInput": "build a skill with waterwall"}),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        parsed = json.loads(proc.stdout)
        self.assertTrue(any("waterwall" in s["systemMessage"]["systemMessage"] for s in parsed["injectSteps"]))

        bad = subprocess.run(
            [sys.executable, script, "pre-invocation"],
            input="{broken json",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(bad.returncode, 0)
        self.assertEqual(json.loads(bad.stdout), {})

    def test_diagnosing_bugs_rejects_false_positives_and_spec_docs(self) -> None:
        false_positives = [
            "You keep throwing off one version of the setup",
            "WORKFLOW 1 - PRE-BUILD PLAN HARDENING\nEnsure no regression test fails and diagnose scope.",
            ("x" * 1600) + " debug this later",
        ]
        for prompt in false_positives:
            signals = operator_router.detect_prompt_signals(prompt)
            self.assertFalse(
                any("diagnosing-bugs" in s for s in signals),
                f"Unexpected diagnosing-bugs hit on: {prompt[:80]}",
            )

        true_positives = [
            ("x" * 1600) + " Traceback (most recent call last): ValueError",
            "service is throwing a ValueError on startup",
            "investigate this regression in parser.py",
        ]
        for prompt in true_positives:
            signals = operator_router.detect_prompt_signals(prompt)
            self.assertTrue(
                any("diagnosing-bugs" in s for s in signals),
                f"Expected diagnosing-bugs hit on: {prompt[:80]}",
            )

    def test_eval_router_replays_synthetic_transcripts_and_flags_noisy_rules(self) -> None:
        import eval_router  # noqa: E402

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            s1 = root / "s1" / ".system_generated" / "logs"
            s2 = root / "s2" / ".system_generated" / "logs"
            s1.mkdir(parents=True)
            s2.mkdir(parents=True)

            (s1 / "transcript.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "refactor store.py"}),
                        json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "<USER_REQUEST>debug traceback</USER_REQUEST>"}),
                        json.dumps({"type": "USER_INPUT", "source": "SYSTEM", "content": "debug ignored system row"}),
                        "{corrupted json line",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (s2 / "transcript.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "check git status"}),
                        json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "summarize notes"}),
                        json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "service is throwing an exception"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            report = eval_router.evaluate_router(root, noisy_threshold=0.25)
            self.assertEqual(report["total_prompts"], 5)
            self.assertEqual(report["fired_prompts"], 2)
            self.assertEqual(report["abstained_prompts"], 3)
            self.assertEqual(report["skipped_lines"], 1)
            self.assertEqual(report["per_rule_hits"]["diagnosing_bugs"], 2)
            self.assertIn("diagnosing_bugs", report["noisy_rules"])

            missing = eval_router.evaluate_router(root / "does_not_exist")
            self.assertEqual(missing["total_prompts"], 0)
            self.assertEqual(missing["fire_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
