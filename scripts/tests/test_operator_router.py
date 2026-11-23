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


if __name__ == "__main__":
    unittest.main()
