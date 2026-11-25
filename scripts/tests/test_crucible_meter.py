#!/usr/bin/env python3
"""Red-capable unit and adversarial tests for Crucible Turn Meter v2."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import crucible_meter  # noqa: E402
import operator_router  # noqa: E402
from sentinel import post, pre, stop  # noqa: E402


def _write_transcript(path: Path, steps: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(s) for s in steps) + "\n", encoding="utf-8")


class TestCrucibleMeterV2(unittest.TestCase):
    """Verify two-axis context physics, Anti-Goodhart Stop gate, RW-06 custody, and privacy."""

    def test_post_compaction_resets_window_pressure_unlike_v1_monotonic_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tp = Path(tmp) / "transcript.jsonl"
            # Large pre-compaction history (>700KB) that v1 would falsely mark DEPLETED
            filler = "x" * 150_000
            steps = [
                {"type": "USER_INPUT", "content": filler},
                {"type": "PLANNER_RESPONSE", "input_tokens": 5000, "cache_read_tokens": 650_000, "content": filler},
                {"type": "USER_INPUT", "content": filler},
                {"type": "USER_INPUT", "content": filler},
                {"type": "USER_INPUT", "content": filler},
                {"type": "CHECKPOINT", "content": "# Resuming from a compaction"},
                {"type": "USER_INPUT", "content": "fresh turn 1"},
                {"type": "PLANNER_RESPONSE", "input_tokens": 3000, "cache_read_tokens": 25_000, "content": "ok"},
                {"type": "USER_INPUT", "content": "fresh turn 2"},
                {"type": "PLANNER_RESPONSE", "input_tokens": 2500, "cache_read_tokens": 42_500, "content": "ok"},
            ]
            _write_transcript(tp, steps)
            m = crucible_meter.measure_transcript(tp)
            self.assertGreater(m["ctx_kb"], 600.0)
            self.assertEqual(m["token_source"], "exact_telemetry")
            self.assertEqual(m["active_tokens"], 45_000)
            self.assertEqual(m["compactions"], 1)
            self.assertEqual(m["turns_since_cp"], 2)
            self.assertEqual(m["ctx_status"], "GREEN")
            self.assertEqual(m["rot_reason"], "NONE")
            self.assertGreater(m["burn_rate"], 0)
            self.assertIsNotNone(m["est_turns_left"])

    def test_window_pressure_and_fidelity_decay_axes_trigger_independently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Axis A: Window pressure without compaction
            tp_win = Path(tmp) / "win.jsonl"
            _write_transcript(
                tp_win,
                [
                    {"type": "USER_INPUT", "content": "hi"},
                    {"type": "PLANNER_RESPONSE", "input_tokens": 4000, "cache_read_tokens": 560_000, "content": "ok"},
                ],
            )
            m_win = crucible_meter.measure_transcript(tp_win)
            self.assertEqual(m_win["ctx_status"], "DEPLETED")
            self.assertEqual(m_win["rot_reason"], "WINDOW_PRESSURE")

            # Axis B: Fidelity decay (2 compactions + 225k active tokens, matching observed 97-turn session)
            tp_fid = Path(tmp) / "fid.jsonl"
            _write_transcript(
                tp_fid,
                [
                    {"type": "CHECKPOINT", "content": "cp1"},
                    {"type": "CHECKPOINT", "content": "cp2"},
                    {"type": "USER_INPUT", "content": "t1"},
                    {"type": "PLANNER_RESPONSE", "input_tokens": 2000, "cache_read_tokens": 223_000, "content": "ok"},
                ],
            )
            m_fid = crucible_meter.measure_transcript(tp_fid)
            self.assertEqual(m_fid["ctx_status"], "DEPLETED")
            self.assertEqual(m_fid["rot_reason"], "FIDELITY_DECAY")

    def test_portable_fallback_when_token_telemetry_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tp = Path(tmp) / "claude_code.jsonl"
            _write_transcript(
                tp,
                [
                    {"type": "USER_INPUT", "content": "build parser"},
                    {"type": "PLANNER_RESPONSE", "content": "a" * 4000},
                ],
            )
            m = crucible_meter.measure_transcript(tp)
            self.assertEqual(m["token_source"], "estimated_bytes")
            self.assertGreater(m["active_tokens"], 900)
            self.assertEqual(m["ctx_status"], "GREEN")

    def test_latency_on_large_synthetic_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tp = Path(tmp) / "large.jsonl"
            chunk = json.dumps({"type": "GENERIC", "content": "z" * 4000})
            lines = [chunk] * 600  # ~2.4 MB
            lines.append(json.dumps({"type": "CHECKPOINT", "content": "cp"}))
            lines.append(json.dumps({"type": "USER_INPUT", "content": "go"}))
            lines.append(
                json.dumps(
                    {"type": "PLANNER_RESPONSE", "input_tokens": 2000, "cache_read_tokens": 98_000, "content": "done"}
                )
            )
            tp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            m = crucible_meter.measure_transcript(tp)
            self.assertEqual(m["active_tokens"], 100_000)
            self.assertLess(m["measure_ms"], 50.0, f"Expected <50ms on 2.4MB transcript, got {m['measure_ms']}ms")

    def test_anti_goodhart_stop_gate_blocks_fake_l10_and_unverified_p(self) -> None:
        # 1. Fake L10 inside a single automated turn -> BLOCKED
        st_verified = crucible_meter.TurnMeterState(turn=2, target_rank="L10", verify_passed=1)
        fake_l10 = (
            '{"stage":"T2","target":"L10","vec":{"L":10,"P":10,"C":10,"R":10},"rank":"L10"}\n'
            "[LEVEL 10 NOTICE] Paradigm shift!"
        )
        res_l10 = crucible_meter.audit_turn_claims(st_verified, fake_l10)
        self.assertFalse(res_l10["ok"])
        self.assertTrue(any("L10" in v for v in res_l10["violations"]))

        # 2. Claiming P=8 after code edits with 0 passing verification -> BLOCKED
        st_unverified = crucible_meter.TurnMeterState(turn=3, target_rank="L9", code_edits=2, verify_passed=0)
        fake_p = '{"stage":"T2","target":"L9","vec":{"L":9,"P":8,"C":9,"R":9},"rank":"L8"}'
        res_p = crucible_meter.audit_turn_claims(st_unverified, fake_p)
        self.assertFalse(res_p["ok"])
        self.assertEqual(res_p["verified_p_cap"], 3)

        # 3. Claiming [LEVEL 9 NOTICE] with zero tools/reads/verifies -> BLOCKED
        st_empty = crucible_meter.TurnMeterState(turn=4, target_rank="L9")
        fake_l9 = "[LEVEL 9 NOTICE] Pure theory without inspection."
        res_l9 = crucible_meter.audit_turn_claims(st_empty, fake_l9)
        self.assertFalse(res_l9["ok"])
        self.assertEqual(res_l9["verified_p_cap"], 3)

        # 4. Honest L9 with passing verification -> ALLOWED
        st_honest = crucible_meter.TurnMeterState(turn=5, target_rank="L9", code_edits=1, verify_passed=1)
        honest_l9 = (
            '{"stage":"T2","target":"L9","vec":{"L":9,"P":9,"C":9,"R":9},"rank":"L9"}\n'
            "[LEVEL 9 NOTICE] Verified with unit + replay tests."
        )
        res_ok = crucible_meter.audit_turn_claims(st_honest, honest_l9)
        self.assertTrue(res_ok["ok"])
        self.assertEqual(res_ok["verified_p_cap"], 9)

    def test_rw06_protects_turn_meter_state_and_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for fname in ("turn-meter-state.json", "meter_receipts.jsonl"):
                res = pre(
                    {
                        "workspacePaths": [tmp],
                        "toolCall": {"name": "write_file", "args": {"Path": str(Path(tmp) / fname), "Content": "{}"}},
                    }
                )
                self.assertEqual(res["decision"], "deny", f"Expected RW-06 deny for {fname}")

    def test_end_to_end_hook_chain_and_privacy_safe_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            ws.mkdir()
            (ws / "app.py").write_text("x = 1\n", encoding="utf-8")
            art = Path(tmp) / "art"
            art.mkdir()
            receipts = Path(tmp) / "receipts.jsonl"
            secret_prose = "TOP_SECRET_PROSE_TOKEN_994411"

            # PreInvocation with L9 target + depleted transcript -> writes HANDOFF_DRAFT.md
            tp = art / ".system_generated" / "logs" / "transcript.jsonl"
            _write_transcript(
                tp,
                [
                    {"type": "USER_INPUT", "content": secret_prose},
                    {"type": "PLANNER_RESPONSE", "input_tokens": 5000, "cache_read_tokens": 560_000, "content": "ok"},
                ],
            )
            pre_out = operator_router.handle_pre_invocation(
                {
                    "conversationId": "conv-e2e",
                    "artifactDirectoryPath": str(art),
                    "lastUserInput": f"Give me a Level 9 fix for {secret_prose}",
                }
            )
            joined = json.dumps(pre_out)
            self.assertIn("TARGET-SEEKING MODE (L9)", joined)
            self.assertIn("CONTEXT WINDOW DEPLETED", joined)
            self.assertTrue((art / "HANDOFF_DRAFT.md").is_file())

            # PostToolUse: code edit + passing pytest
            post(
                {
                    "artifactDirectoryPath": str(art),
                    "workspacePaths": [str(ws)],
                    "toolCall": {"name": "edit_file", "args": {"Path": str(ws / "app.py")}},
                }
            )
            post(
                {
                    "artifactDirectoryPath": str(art),
                    "workspacePaths": [str(ws)],
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "python -m pytest"}},
                }
            )

            # Stop with fake L10 -> blocked & receipt logged
            stop_bad = stop(
                {
                    "artifactDirectoryPath": str(art),
                    "workspacePaths": [str(ws)],
                    "lastAssistantResponse": '{"stage":"T2","target":"L10","vec":{"L":10,"P":10,"C":10,"R":10},"rank":"L10"}',
                    "receiptsPath": str(receipts),
                }
            )
            self.assertEqual(stop_bad["decision"], "continue")

            # Stop with honest L9 -> allowed & receipt logged
            stop_ok = stop(
                {
                    "artifactDirectoryPath": str(art),
                    "workspacePaths": [str(ws)],
                    "lastAssistantResponse": '{"stage":"T2","target":"L9","vec":{"L":9,"P":9,"C":9,"R":9},"rank":"L9"}',
                    "receiptsPath": str(receipts),
                }
            )
            self.assertEqual(stop_ok["decision"], "allow")

            # Privacy invariant: zero raw prompt prose leaked into receipts
            raw_receipts = receipts.read_text(encoding="utf-8")
            self.assertNotIn(secret_prose, raw_receipts)
            rows = [json.loads(ln) for ln in raw_receipts.splitlines() if ln.strip()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["decision"], "continue")
            self.assertEqual(rows[1]["decision"], "allow")
            self.assertEqual(rows[1]["verify_passed"], 1)
            self.assertEqual(rows[1]["code_edits"], 1)

    def test_pre_tool_intent_lease_blocks_unplanned_mutation_and_scores_wave_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            ws.mkdir()
            (ws / "app.py").write_text("x = 1\n", encoding="utf-8")
            (ws / "other.py").write_text("y = 2\n", encoding="utf-8")
            art = Path(tmp) / "art"
            art.mkdir()
            receipts = Path(tmp) / "receipts.jsonl"

            # PreInvocation enables intent_required=True for the live turn
            operator_router.handle_pre_invocation(
                {
                    "conversationId": "conv-intent",
                    "artifactDirectoryPath": str(art),
                    "lastUserInput": "update app.py to add helper",
                }
            )
            # Read-only stays fast (never gated)
            read_res = pre({"workspacePaths": [str(ws)], "artifactDirectoryPath": str(art), "toolCall": {"name": "read_file", "args": {"Path": str(ws / "app.py")}}})
            self.assertEqual(read_res["decision"], "allow")
            post({"workspacePaths": [str(ws)], "artifactDirectoryPath": str(art), "toolCall": {"name": "read_file", "args": {"Path": str(ws / "app.py")}}})

            # Unplanned write_file -> DENIED by INTENT GATE
            blocked = pre(
                {
                    "workspacePaths": [str(ws)],
                    "artifactDirectoryPath": str(art),
                    "toolCall": {"name": "edit_file", "args": {"Path": str(ws / "app.py"), "Target": "x = 1", "Replacement": "x = 2"}},
                }
            )
            self.assertEqual(blocked["decision"], "deny")
            self.assertIn("INTENT GATE", blocked["reason"])

            # Submit visible commit_intent MCP call -> PostToolUse mints wave lease for app.py
            commit_call = {
                "name": "mcp_crucible-meter_commit_intent",
                "args": {
                    "intent": "Add helper constant to app.py for cleaner config",
                    "middle": "Replace x = 1 with x = 2 while preserving module API",
                    "expected_outcome": "app.py parses cleanly and pytest passes",
                    "targets": ["app.py"],
                    "wave_size": 1,
                },
            }
            self.assertEqual(pre({"workspacePaths": [str(ws)], "artifactDirectoryPath": str(art), "toolCall": commit_call})["decision"], "allow")
            post({"workspacePaths": [str(ws)], "artifactDirectoryPath": str(art), "toolCall": commit_call})

            # Editing out-of-scope file other.py -> DENIED
            out_of_scope = pre(
                {
                    "workspacePaths": [str(ws)],
                    "artifactDirectoryPath": str(art),
                    "toolCall": {"name": "edit_file", "args": {"Path": str(ws / "other.py"), "Target": "y = 2", "Replacement": "y = 3"}},
                }
            )
            self.assertEqual(out_of_scope["decision"], "deny")
            self.assertIn("outside active intent lease", out_of_scope["reason"])

            # Editing planned file app.py -> ALLOWED, then PostToolUse completes wave (waves_succeeded=1)
            allowed = pre(
                {
                    "workspacePaths": [str(ws)],
                    "artifactDirectoryPath": str(art),
                    "toolCall": {"name": "edit_file", "args": {"Path": str(ws / "app.py"), "Target": "x = 1", "Replacement": "x = 2"}},
                }
            )
            self.assertEqual(allowed["decision"], "allow")
            post(
                {
                    "workspacePaths": [str(ws)],
                    "artifactDirectoryPath": str(art),
                    "toolCall": {"name": "edit_file", "args": {"Path": str(ws / "app.py")}},
                }
            )
            # Verification command passes -> Stop logs intent_outcome_score = 1.0
            post(
                {
                    "workspacePaths": [str(ws)],
                    "artifactDirectoryPath": str(art),
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "python -m pytest"}},
                }
            )
            stop_res = stop(
                {
                    "workspacePaths": [str(ws)],
                    "artifactDirectoryPath": str(art),
                    "lastAssistantResponse": "Updated app.py cleanly.",
                    "receiptsPath": str(receipts),
                }
            )
            self.assertEqual(stop_res["decision"], "allow")
            row = json.loads(receipts.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(row["intents_committed"], 1)
            self.assertEqual(row["intent_blocks"], 2)
            self.assertEqual(row["waves_succeeded"], 1)
            self.assertEqual(row["waves_failed"], 0)
            self.assertEqual(row["intent_outcome_score"], 1.0)

    def test_failed_mutation_invalidates_lease_and_mcp_server_validates_fields(self) -> None:
        import io
        import contextlib
        import crucible_meter_mcp  # noqa: E402

        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp) / "art"
            art.mkdir()
            payload = {"artifactDirectoryPath": str(art), "workspacePaths": [tmp]}
            crucible_meter.begin_turn(payload, "edit via cli commit", {"turn": 1, "target_rank": "AUTO"})

            # CLI commit mints a 3-use wave lease via PostToolUse
            cli_cmd = (
                'python scripts/crucible_meter.py commit '
                '--intent "Refactor parser module" '
                '--middle "Update token loop with bounds check" '
                '--outcome "All unit tests pass" '
                '--wave-size 3'
            )
            post({**payload, "toolCall": {"name": "run_command", "args": {"CommandLine": cli_cmd}}})
            st = crucible_meter.load_turn_state(payload)
            self.assertIsNotNone(st.active_lease)
            self.assertEqual(st.active_lease["remaining_uses"], 3)

            # A failed edit invalidates the entire remaining lease & increments waves_failed
            post({**payload, "error": "Target not found", "toolCall": {"name": "edit_file", "args": {"Path": str(Path(tmp) / "a.py")}}})
            st2 = crucible_meter.load_turn_state(payload)
            self.assertIsNone(st2.active_lease)
            self.assertEqual(st2.waves_failed, 1)

            # MCP server rejects trivial short intent and accepts substantive intent
            buf_bad = io.StringIO()
            with contextlib.redirect_stdout(buf_bad):
                crucible_meter_mcp.handle_request(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": "commit_intent", "arguments": {"intent": "fix", "middle": "edit", "expected_outcome": "ok"}},
                    }
                )
            bad_resp = json.loads(buf_bad.getvalue())
            self.assertTrue(bad_resp["result"]["isError"])

            buf_ok = io.StringIO()
            with contextlib.redirect_stdout(buf_ok):
                crucible_meter_mcp.handle_request(
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "commit_intent",
                            "arguments": {
                                "intent": "Prevent unverified mutations in sentinel",
                                "middle": "Require commit_intent lease in PreToolUse before writes",
                                "expected_outcome": "All 22 pytest tests pass cleanly",
                                "targets": ["lifecycle.py"],
                            },
                        },
                    }
                )
            ok_resp = json.loads(buf_ok.getvalue())
            self.assertFalse(ok_resp["result"]["isError"])
            self.assertIn("INTENT_COMMITTED", ok_resp["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
