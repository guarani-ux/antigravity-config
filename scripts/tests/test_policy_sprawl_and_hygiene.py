#!/usr/bin/env python3
"""Unit tests for policy.json, RW-19 Git-based Sprawl Governor, and RW-20 Deliverable Hygiene."""

from __future__ import annotations

import json
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


class TestPolicySprawlAndHygiene(unittest.TestCase):
    """Verify RW-19 stateless Git sprawl limits and RW-20 policy.json deliverable hygiene."""

    def test_rw19_git_sprawl_governor_flags_fourth_new_prod_file_but_allows_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = Path(tmp) / "art"
            root.mkdir()
            art.mkdir()
            subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
            (root / "README.md").write_text("# Init\n", encoding="utf-8")

            base = {"workspacePaths": [str(root)], "artifactDirectoryPath": str(art)}
            sentinel.post({**base, "toolCall": {"name": "view_file", "args": {"AbsolutePath": str(root / "README.md")}}})

            # Create 3 untracked production Python files (at limit=3)
            for i in range(3):
                (root / f"mod_{i}.py").write_text(f"x = {i}\n", encoding="utf-8")

            # 4th new production file triggers RW-19 (force_ask for main, deny for subagent)
            fourth = {
                **base,
                "toolCall": {"name": "write_to_file", "args": {"TargetFile": str(root / "mod_3.py"), "CodeContent": "x = 3\n"}},
            }
            res_main = sentinel.pre(fourth)
            self.assertEqual(res_main["decision"], "force_ask")
            self.assertIn("RW-19", res_main["reason"])

            res_sub = sentinel.pre({**fourth, "parentConversationId": "coord-1"})
            self.assertEqual(res_sub["decision"], "deny")
            self.assertIn("RW-19", res_sub["reason"])

            # Writing a new test file MUST still be allowed (never punish tests)
            test_write = {
                **base,
                "toolCall": {
                    "name": "write_to_file",
                    "args": {
                        "TargetFile": str(root / "tests" / "test_mod.py"),
                        "CodeContent": "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertEqual(1 + 1, 2)\n    def test_neg(self):\n        self.assertNotEqual(1 + 1, 3)\n",
                    },
                },
            }
            self.assertEqual(sentinel.pre(test_write)["decision"], "allow")

    def test_rw20_deliverable_hygiene_catches_cpl_tiktok_emdash_and_allows_clean_pitch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pitch_path = str(root / "Open_the_Page_Series_Pitch.md")

            for bad_text, expected in (
                ("Calgary Public Library pitch for CPL fans.\n", "CPL"),
                ("Calgary Public Library launching on TikTok.\n", "TikTok"),
                ("Calgary Public Library \u2014 a great series.\n", "em-dash"),
            ):
                res = sentinel.pre(
                    {
                        "workspacePaths": [tmp],
                        "toolCall": {"name": "write_to_file", "args": {"TargetFile": pitch_path, "CodeContent": bad_text}},
                    }
                )
                self.assertEqual(res["decision"], "ask", expected)
                self.assertIn("RW-20", res["reason"])

            clean_res = sentinel.pre(
                {
                    "workspacePaths": [tmp],
                    "toolCall": {
                        "name": "write_to_file",
                        "args": {
                            "TargetFile": pitch_path,
                            "CodeContent": "Calgary Public Library launches on YouTube Shorts and Instagram Reels.\n",
                        },
                    },
                }
            )
            self.assertEqual(clean_res["decision"], "allow")


if __name__ == "__main__":
    unittest.main()
