#!/usr/bin/env python3
"""Unit tests for operator_router signal detection, abstention, and prompt deduplication."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import operator_router  # noqa: E402


class TestOperatorRouter(unittest.TestCase):
    """Verify precision, abstention on neutral prompts, and single-emit deduplication."""

    def test_all_signal_rules_trigger(self) -> None:
        cases = [
            ("wait what does that mean", "plain-english"),
            ("check my power level please", "recursive-meta-calibration"),
            ("draft an av script for this video", "av-craft"),
            ("help write a cover letter for this role", "cl-craft"),
            ("run a forensic audit on this module", "mode-forensic"),
            ("what if we build a new system for notes", "idea-crucible"),
            ("please debug this failing test regression", "diagnosing-bugs"),
            ("polish the frontend dashboard css layout", "visual-reflex"),
        ]
        for prompt, expected_tag in cases:
            signals = operator_router.detect_prompt_signals(prompt)
            self.assertTrue(
                any(expected_tag in s for s in signals),
                f"Expected '{expected_tag}' for prompt '{prompt}', got: {signals}",
            )

    def test_neutral_prompts_abstain(self) -> None:
        neutral = [
            "refactor helper function in store.py",
            "check git status",
            "summarize the meeting notes from yesterday",
            "rename variable total_count to item_count",
        ]
        for prompt in neutral:
            signals = operator_router.detect_prompt_signals(prompt)
            self.assertEqual(signals, [], f"False positive on neutral prompt '{prompt}': {signals}")

    def test_traceback_triggers_diagnosing_bugs_without_acceleration(self) -> None:
        signals = operator_router.detect_prompt_signals("what if we check this traceback from pytest")
        self.assertTrue(any("diagnosing-bugs" in s for s in signals))
        self.assertFalse(any("idea-crucible" in s for s in signals))

    def test_pre_invocation_emits_once_per_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "conversationId": "test-conv",
                "artifactDirectoryPath": tmp,
                "lastUserInput": "please debug this traceback",
            }
            first = operator_router.handle_pre_invocation(payload)
            self.assertEqual(len(first["injectSteps"]), 1)
            second = operator_router.handle_pre_invocation(payload)
            self.assertEqual(second["injectSteps"], [])

            # Ensure clean JSON serialization
            encoded = json.dumps(first)
            self.assertIn("diagnosing-bugs", encoded)

    def test_diagnosing_bugs_rejects_false_positives_and_spec_docs(self) -> None:
        false_positives = [
            "You keep throwing off one version of the setup",
            "WORKFLOW 1 — PRE-BUILD PLAN HARDENING\nEnsure no regression test fails and diagnose scope.",
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
