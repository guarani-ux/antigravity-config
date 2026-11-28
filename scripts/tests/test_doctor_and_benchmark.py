#!/usr/bin/env python3
"""Unit and integration tests for RW-18 secret scanner, telemetry privacy, doctor.py, and eval_harness.py."""

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

import doctor  # noqa: E402
import eval_harness  # noqa: E402
import sentinel  # noqa: E402


class TestMachineSubsystems(unittest.TestCase):
    """Verify RW-18 secret patterns/bypasses, real telemetry privacy, cross-OS doctor, and benchmark CLI."""

    def test_secret_leak_guard_covers_all_families_split_writes_and_example_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gh_tok = "ghp_" + ("Ab12Cd34" * 4) + "Ef56"
            gh_pat = "github_pat_" + ("Xy98Zw76" * 3)
            aws_key = "AKIA" + "0123456789ABCDEF"
            # Test hyphen-terminated Google API key and OpenAI project key (boundary regression)
            g_key = "AIza" + ("B1c2D3e4" * 4) + "Xy-"
            oai_key = "sk-proj-" + ("M1n2O3p4" * 3) + "-"
            stripe_key = "sk_live_" + ("9a8b7c6d" * 3)
            slack_tok = "xoxb-" + "1234567890-abcdef"
            db_uri = "postgres://" + "admin:Sup3rS3cretPw@db.internal:5432/app"
            pgp_hdr = "-----BEGIN " + "PGP PRIVATE KEY BLOCK-----"
            enc_hdr = "-----BEGIN " + "ENCRYPTED PRIVATE KEY-----"

            for idx, secret_val in enumerate((gh_tok, gh_pat, aws_key, g_key, oai_key, stripe_key, slack_tok, db_uri, pgp_hdr, enc_hdr)):
                res = sentinel.pre(
                    {
                        "workspacePaths": [tmp],
                        "toolCall": {
                            "name": "write_to_file",
                            "args": {"TargetFile": str(Path(tmp) / f"f{idx}.md"), "CodeContent": f"val=\"{secret_val}\"\n"},
                        },
                    }
                )
                self.assertEqual(res["decision"], "deny", f"Failed to block pattern #{idx}")
                self.assertIn("RW-18", res["reason"])
                self.assertNotIn(secret_val, res["reason"])

            # Split-write (Append=True) bypass MUST be caught on assembled candidate
            split_file = Path(tmp) / "split.txt"
            half1, half2 = gh_tok[:18], gh_tok[18:]
            split_file.write_text(f"TOKEN={half1}", encoding="utf-8")
            append_res = sentinel.pre(
                {
                    "workspacePaths": [tmp],
                    "toolCall": {
                        "name": "write_to_file",
                        "args": {"TargetFile": str(split_file), "CodeContent": half2 + "\n", "Append": True},
                    },
                }
            )
            self.assertEqual(append_res["decision"], "deny")
            self.assertIn("RW-18", append_res["reason"])

            # Split-edit bypass MUST be caught on assembled candidate
            edit_file = Path(tmp) / "split_edit.txt"
            edit_file.write_text(f"TOKEN={half1}PLACEHOLDER\n", encoding="utf-8")
            edit_res = sentinel.pre(
                {
                    "workspacePaths": [tmp],
                    "toolCall": {
                        "name": "replace_file_content",
                        "args": {
                            "TargetFile": str(edit_file),
                            "TargetContent": "PLACEHOLDER",
                            "ReplacementContent": half2,
                        },
                    },
                }
            )
            self.assertEqual(edit_res["decision"], "deny")
            self.assertIn("RW-18", edit_res["reason"])

            # Official AWS example key, UUIDs, and SHA-256 hashes MUST NOT false-positive
            benign = (
                "AWS_SAMPLE=AKIAIOSFODNN7EXAMPLE\n"
                "UUID=550e8400-e29b-41d4-a716-446655440000\n"
                "SHA=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\n"
            )
            clean_res = sentinel.pre(
                {
                    "workspacePaths": [tmp],
                    "toolCall": {"name": "write_to_file", "args": {"TargetFile": str(Path(tmp) / "docs.md"), "CodeContent": benign}},
                }
            )
            self.assertEqual(clean_res["decision"], "allow", clean_res)

    def test_end_to_end_telemetry_privacy_optout_and_corrupt_line_resilience(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tel = Path(tmp) / "hook-events.jsonl"
            env = dict(os.environ, ANTIGRAVITY_TELEMETRY_PATH=str(tel))
            env.pop("ANTIGRAVITY_TELEMETRY_DISABLED", None)

            secret_val = "ghp_" + ("Qz12Wx34" * 4) + "Ec56"
            prompt_secret = "CONFIDENTIAL_PROMPT_TEXT_9981"

            # Trigger sentinel.py pre with secret payload + operator_router.py with confidential prompt
            p1 = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "sentinel.py"), "pre"],
                input=json.dumps(
                    {
                        "workspacePaths": [tmp],
                        "toolCall": {"name": "write_to_file", "args": {"TargetFile": str(Path(tmp) / "x.md"), "CodeContent": secret_val}},
                    }
                ),
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(p1.returncode, 0)
            p2 = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "operator_router.py"), "pre-invocation"],
                input=json.dumps({"lastUserInput": f"build a validator for {prompt_secret}"}),
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(p2.returncode, 0)

            raw_tel = tel.read_text(encoding="utf-8")
            self.assertNotIn(secret_val, raw_tel)
            self.assertNotIn(prompt_secret, raw_tel)

            # Corrupt line mixed into JSONL must not break summarize_telemetry
            with tel.open("a", encoding="utf-8") as fh:
                fh.write("{corrupt json line\n")
            summary = sentinel.summarize_telemetry(tel)
            self.assertEqual(summary["events"], 2)
            self.assertEqual(summary["top_blocks"][0]["tag"], "RW-18")
            self.assertIn("pre", summary["by_hook"])

            # Opt-out via ANTIGRAVITY_TELEMETRY_DISABLED=true suppresses writes
            tel_off = Path(tmp) / "disabled.jsonl"
            env_off = dict(os.environ, ANTIGRAVITY_TELEMETRY_PATH=str(tel_off), ANTIGRAVITY_TELEMETRY_DISABLED="true")
            subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "sentinel.py"), "pre"],
                input=json.dumps({"workspacePaths": [tmp], "toolCall": {"name": "read_file", "args": {"Path": str(Path(tmp) / "a.py")}}}),
                capture_output=True,
                text=True,
                env=env_off,
                check=False,
            )
            self.assertFalse(tel_off.exists())

    def test_doctor_validates_cross_os_hooks_skills_drift_and_cli_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            isolated_tel = Path(tmp) / "empty-tel.jsonl"
            clean = doctor.run_doctor(REPO_ROOT, check_installed=False, telemetry_path=isolated_tel)
            self.assertTrue(clean["ok"], clean["errors"])
            self.assertEqual(clean["warnings"], [], clean["warnings"])
            self.assertEqual(clean["unreachable_scripts"], [])
            skill_names = {s["name"] for s in clean["skills"]}
            self.assertEqual(skill_names, {"potential-unleashed", "meeting-brief"})

            # Test Windows backslash hook script resolution, GEMINI.md drift, dead script, broken skill dir, and unresolved placeholders
            cfg = Path(tmp) / "config"
            cfg.mkdir(parents=True)
            for fn in ("GEMINI.global.md", "hooks.json.portable", "mcp_config.portable.json"):
                shutil.copy2(REPO_ROOT / fn, cfg / fn)
            shutil.copytree(REPO_ROOT / "scripts", cfg / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            (cfg / "scripts" / "dead_orphan.py").write_text("x = 1\n", encoding="utf-8")

            # Valid installed GEMINI.md (drifted), invalid Windows backslash script typo, missing SKILL.md dir
            (Path(tmp) / "GEMINI.md").write_text("# Old drifted version\n", encoding="utf-8")
            (cfg / "mcp_config.json").write_text(json.dumps({"mcpServers": None}), encoding="utf-8")
            bad_hooks = json.loads((REPO_ROOT / "hooks.json.portable").read_text(encoding="utf-8"))
            bad_hooks["sentinel"]["PreToolUse"][0]["hooks"][0]["command"] = f'{sys.executable} "{cfg}\\scripts\\missing_hook.py" pre'
            bad_hooks["operator-router"]["Stop_extra"] = []
            (cfg / "hooks.json").write_text(json.dumps(bad_hooks), encoding="utf-8")

            bad_skill = cfg / "skills" / "broken-skill"
            bad_skill.mkdir(parents=True)
            (bad_skill / "SKILL.md").write_text(
                "---\nname: wrong-name\ndescription: test\n---\nRun `scripts/does_not_exist.sh`.\n",
                encoding="utf-8",
            )
            (cfg / "skills" / "empty-dir").mkdir(parents=True)

            bad = doctor.run_doctor(cfg, check_installed=True, gemini_dir=Path(tmp), telemetry_path=isolated_tel)
            self.assertFalse(bad["ok"])
            joined_err = "\n".join(bad["errors"])
            self.assertIn("missing_hook.py", joined_err)
            self.assertIn("dead_orphan.py", joined_err)
            self.assertNotIn("eval_harness.py", joined_err)
            self.assertIn("does_not_exist.sh", joined_err)
            self.assertIn("wrong-name", joined_err)
            self.assertIn("directory missing SKILL.md", joined_err)
            self.assertIn("mcp_config.json", joined_err)
            self.assertTrue(any("drifted" in w for w in bad["warnings"]))

            # CLI exit codes: 0 on clean repo, 1 on broken dir
            self.assertEqual(doctor.main(["--config-dir", str(REPO_ROOT), "--strict", "--json"]), 0)
            self.assertEqual(doctor.main(["--config-dir", str(cfg), "--check-installed", "--gemini-dir", str(tmp)]), 1)

    def test_eval_harness_cli_json_output_and_exit_code(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "eval_harness.py"), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["catch_rate"], "27/27 (100.0%)")
        self.assertEqual(report["false_positive_rate"], "0/16 (0.0%)")
        self.assertTrue(report["telemetry_verified"])
        self.assertNotEqual(report["p95_subprocess_ms"], 0.0)


if __name__ == "__main__":
    unittest.main()
