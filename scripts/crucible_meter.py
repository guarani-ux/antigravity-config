#!/usr/bin/env python3
"""Crucible Turn Meter v2 — Standalone Context-Window Physics & Mechanical Proof Engine.

Pure Python stdlib (<15ms on 2.5MB+ transcripts). Usable inside Antigravity hooks
(PreInvocation, PostToolUse, Stop) and as a portable CLI for Claude Code, Codex CLI,
or any terminal agent runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Target-rank detector (explicit L9/L10 invocation)
TARGET_RANK_RE = re.compile(
    r"\b(?:level\s*(9|10)|l(9|10)|rank\s*(9|10))\b",
    re.IGNORECASE,
)

# Notice & meter-JSON extractors for Stop-hook Anti-Goodhart auditing
L9_NOTICE_RE = re.compile(r"\[LEVEL\s+9\s+NOTICE\]", re.IGNORECASE)
L10_NOTICE_RE = re.compile(r"\[LEVEL\s+10\s+NOTICE\]", re.IGNORECASE)
METER_JSON_RE = re.compile(r'\{[^{}]*"stage"\s*:\s*"T[012]"[^{}]*"vec"\s*:\s*\{[^{}]*\}[^{}]*\}')

# Two-Axis Context Physics thresholds (calibrated against observed 665k compaction cliff)
TOKENS_WARN = 350_000
TOKENS_DEPLETED = 550_000
COMPACT_WARN_COUNT = 1
COMPACT_WARN_TOKENS = 200_000
COMPACT_WARN_TURNS = 15
COMPACT_DEPLETED_COUNT = 2
COMPACT_DEPLETED_TOKENS = 200_000
COMPACT_DEPLETED_TURNS = 12
COMPACT_HARD_DEPLETED_COUNT = 3

TURN_STATE_FILENAME = "turn-meter-state.json"
HANDOFF_DRAFT_FILENAME = "HANDOFF_DRAFT.md"
DEFAULT_RECEIPTS_PATH = Path.home() / ".gemini" / "config" / "telemetry" / "meter_receipts.jsonl"
MIN_INTENT_FIELD_LEN = 8
MAX_WAVE_LEASE_USES = 12
DEFAULT_WAVE_LEASE_USES = 5


@dataclass
class TurnMeterState:
    conversation_id: str = ""
    turn: int = 0
    target_rank: str = "AUTO"
    prompt_hash: str = ""
    started_at: str = ""
    tool_calls: int = 0
    read_calls: int = 0
    code_edits: int = 0
    verify_passed: int = 0
    verify_failed: int = 0
    consecutive_errors: int = 0
    last_error_sig: str = ""
    repeated_error_count: int = 0
    ctx_status: str = "GREEN"
    active_tokens: int = 0
    compaction_count: int = 0
    rot_reason: str = "NONE"
    intent_required: bool = False
    active_lease: dict[str, Any] | None = None
    intents_committed: int = 0
    intent_blocks: int = 0
    waves_succeeded: int = 0
    waves_failed: int = 0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _short_hash(text: str) -> str:
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:12]


def detect_target_rank(user_text: str) -> str:
    m = TARGET_RANK_RE.search(user_text or "")
    if not m:
        return "AUTO"
    return f"L{m.group(1) or m.group(2) or m.group(3)}"


def _safe_json_loads(raw: bytes | str) -> dict[str, Any] | None:
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except (ValueError, TypeError, UnicodeDecodeError):
        return None


def _prompt_tokens_from_step(obj: dict[str, Any]) -> int | None:
    in_tok = obj.get("input_tokens")
    cache_tok = obj.get("cache_read_tokens")
    if in_tok is None and cache_tok is None:
        return None
    try:
        return max(0, int(in_tok or 0) + int(cache_tok or 0))
    except (ValueError, TypeError):
        return None


def measure_transcript(
    transcript_path: Path | None,
    user_text: str = "",
    *,
    tokens_warn: int = TOKENS_WARN,
    tokens_depleted: int = TOKENS_DEPLETED,
) -> dict[str, Any]:
    """Measure two-axis context-window physics (active tokens + compaction fidelity decay).

    Uses fast byte-level scanning + selective JSON parsing (<15ms on 2.6MB transcripts).
    Falls back to post-checkpoint byte/4 token estimation for non-Antigravity transcripts.
    """
    t0 = time.perf_counter()
    target_rank = detect_target_rank(user_text)

    ctx_kb = 0.0
    user_turns = 1
    compaction_count = 0
    turns_since_checkpoint = 1
    active_tokens = 0
    token_source = "none"
    burn_rate = 0
    est_turns_left: int | None = None

    if transcript_path is not None and transcript_path.is_file():
        try:
            raw_bytes = transcript_path.read_bytes()
        except OSError:
            raw_bytes = b""

        if raw_bytes:
            ctx_kb = round(len(raw_bytes) / 1024.0, 1)
            lines = raw_bytes.splitlines()

            total_user_inputs = 0
            last_cp_idx = -1
            for idx, ln in enumerate(lines):
                if b'"USER_INPUT"' in ln:
                    total_user_inputs += 1
                if b'"CHECKPOINT"' in ln:
                    obj = _safe_json_loads(ln)
                    if obj is not None and obj.get("type") == "CHECKPOINT":
                        compaction_count += 1
                        last_cp_idx = idx

            user_turns = max(1, total_user_inputs)
            post_lines = lines[last_cp_idx + 1 :] if last_cp_idx >= 0 else lines

            turns_since_cp_raw = sum(1 for ln in post_lines if b'"USER_INPUT"' in ln)
            turns_since_checkpoint = max(1, turns_since_cp_raw)

            # Collect candidate PLANNER_RESPONSE lines after last checkpoint
            pr_indices = [i for i, ln in enumerate(post_lines) if b'"PLANNER_RESPONSE"' in ln]

            latest_tokens: int | None = None
            first_tokens: int | None = None

            # Find latest exact token count (scan from end, at most last 12 PRs)
            for idx in reversed(pr_indices[-12:]):
                obj = _safe_json_loads(post_lines[idx])
                if obj is not None and obj.get("type") == "PLANNER_RESPONSE":
                    tok = _prompt_tokens_from_step(obj)
                    if tok is not None and tok > 0:
                        latest_tokens = tok
                        break

            # Find earliest exact token count post-checkpoint (scan from start, at most first 6 PRs)
            if latest_tokens is not None:
                for idx in pr_indices[:6]:
                    obj = _safe_json_loads(post_lines[idx])
                    if obj is not None and obj.get("type") == "PLANNER_RESPONSE":
                        tok = _prompt_tokens_from_step(obj)
                        if tok is not None and tok > 0:
                            first_tokens = tok
                            break

            if latest_tokens is not None:
                active_tokens = latest_tokens
                token_source = "exact_telemetry"
                if first_tokens is not None and turns_since_checkpoint > 1 and latest_tokens > first_tokens:
                    burn_rate = int((latest_tokens - first_tokens) / max(1, turns_since_checkpoint - 1))
            else:
                # Portable fallback for Claude Code / Codex / generic JSONL logs without token fields
                post_bytes = sum(len(ln) + 1 for ln in post_lines)
                active_tokens = max(0, int(post_bytes // 4))
                token_source = "estimated_bytes"
                if turns_since_checkpoint > 1 and active_tokens > 0:
                    burn_rate = int(active_tokens / turns_since_checkpoint)

    if burn_rate > 0 and active_tokens < tokens_depleted:
        est_turns_left = max(0, int((tokens_depleted - active_tokens) / burn_rate))
    elif active_tokens >= tokens_depleted:
        est_turns_left = 0

    # Axis A: Active Window Pressure
    win_depleted = active_tokens >= tokens_depleted
    win_warn = active_tokens >= tokens_warn

    # Axis B: Compaction Fidelity Decay
    fid_depleted = compaction_count >= COMPACT_HARD_DEPLETED_COUNT or (
        compaction_count >= COMPACT_DEPLETED_COUNT
        and (active_tokens >= COMPACT_DEPLETED_TOKENS or turns_since_checkpoint >= COMPACT_DEPLETED_TURNS)
    )
    fid_warn = compaction_count >= COMPACT_WARN_COUNT and (
        active_tokens >= COMPACT_WARN_TOKENS or turns_since_checkpoint >= COMPACT_WARN_TURNS
    )

    if win_depleted or fid_depleted:
        ctx_status = "DEPLETED"
        action = "START_NEW_CONVERSATION"
        if win_depleted and fid_depleted:
            rot_reason = "BOTH"
        elif win_depleted:
            rot_reason = "WINDOW_PRESSURE"
        else:
            rot_reason = "FIDELITY_DECAY"
    elif win_warn or fid_warn:
        ctx_status = "WARN"
        action = "COMPACT_SOON"
        if win_warn and fid_warn:
            rot_reason = "BOTH"
        elif win_warn:
            rot_reason = "WINDOW_PRESSURE"
        else:
            rot_reason = "FIDELITY_DECAY"
    else:
        ctx_status = "GREEN"
        action = "PROCEED"
        rot_reason = "NONE"

    win_pct = (active_tokens / tokens_depleted) * 100.0 if tokens_depleted > 0 else 0.0
    fid_pct = (compaction_count / float(COMPACT_HARD_DEPLETED_COUNT)) * 100.0
    ctx_est_pct = min(100, int(round(max(win_pct, fid_pct))))
    measure_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    return {
        "turn": user_turns,
        "turns_since_cp": turns_since_checkpoint,
        "active_tokens": active_tokens,
        "token_source": token_source,
        "compactions": compaction_count,
        "burn_rate": burn_rate,
        "est_turns_left": est_turns_left,
        "ctx_kb": ctx_kb,
        "ctx_est_pct": ctx_est_pct,
        "ctx_status": ctx_status,
        "rot_reason": rot_reason,
        "target_rank": target_rank,
        "action": action,
        "measure_ms": measure_ms,
    }


def resolve_transcript_path(payload: dict[str, Any]) -> Path | None:
    tpath = payload.get("transcriptPath")
    if isinstance(tpath, str) and tpath.strip():
        p = Path(tpath.strip())
        if p.is_file():
            return p
    art_dir = payload.get("artifactDirectoryPath")
    if isinstance(art_dir, str) and art_dir.strip():
        p = Path(art_dir.strip()) / ".system_generated" / "logs" / "transcript.jsonl"
        if p.is_file():
            return p
    return None


def turn_state_path(payload: dict[str, Any]) -> Path | None:
    art_dir = payload.get("artifactDirectoryPath")
    if isinstance(art_dir, str) and art_dir.strip():
        return Path(art_dir.strip()) / TURN_STATE_FILENAME
    tpath = payload.get("transcriptPath")
    if isinstance(tpath, str) and tpath.strip():
        return Path(tpath.strip()).resolve().parent / TURN_STATE_FILENAME
    return None


def load_turn_state(payload: dict[str, Any]) -> TurnMeterState:
    sp = turn_state_path(payload)
    if sp is None or not sp.is_file():
        return TurnMeterState()
    raw = _safe_json_loads(sp.read_text(encoding="utf-8", errors="replace"))
    if raw is None:
        return TurnMeterState()
    return TurnMeterState(
        conversation_id=str(raw.get("conversation_id") or ""),
        turn=int(raw.get("turn") or 0),
        target_rank=str(raw.get("target_rank") or "AUTO"),
        prompt_hash=str(raw.get("prompt_hash") or ""),
        started_at=str(raw.get("started_at") or ""),
        tool_calls=int(raw.get("tool_calls") or 0),
        read_calls=int(raw.get("read_calls") or 0),
        code_edits=int(raw.get("code_edits") or 0),
        verify_passed=int(raw.get("verify_passed") or 0),
        verify_failed=int(raw.get("verify_failed") or 0),
        consecutive_errors=int(raw.get("consecutive_errors") or 0),
        last_error_sig=str(raw.get("last_error_sig") or ""),
        repeated_error_count=int(raw.get("repeated_error_count") or 0),
        ctx_status=str(raw.get("ctx_status") or "GREEN"),
        active_tokens=int(raw.get("active_tokens") or 0),
        compaction_count=int(raw.get("compaction_count") or 0),
        rot_reason=str(raw.get("rot_reason") or "NONE"),
        intent_required=bool(raw.get("intent_required", False)),
        active_lease=raw.get("active_lease") if isinstance(raw.get("active_lease"), dict) else None,
        intents_committed=int(raw.get("intents_committed") or 0),
        intent_blocks=int(raw.get("intent_blocks") or 0),
        waves_succeeded=int(raw.get("waves_succeeded") or 0),
        waves_failed=int(raw.get("waves_failed") or 0),
    )


def save_turn_state(payload: dict[str, Any], state: TurnMeterState) -> None:
    sp = turn_state_path(payload)
    if sp is None:
        return
    try:
        sp.parent.mkdir(parents=True, exist_ok=True)
        tmp = sp.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(state), ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, sp)
    except OSError:
        pass


def begin_turn(payload: dict[str, Any], user_text: str, meter: dict[str, Any]) -> TurnMeterState:
    state = TurnMeterState(
        conversation_id=str(payload.get("conversationId") or ""),
        turn=int(meter.get("turn") or 1),
        target_rank=str(meter.get("target_rank") or "AUTO"),
        prompt_hash=_short_hash(user_text),
        started_at=_utc_now_iso(),
        ctx_status=str(meter.get("ctx_status") or "GREEN"),
        active_tokens=int(meter.get("active_tokens") or 0),
        compaction_count=int(meter.get("compactions") or 0),
        rot_reason=str(meter.get("rot_reason") or "NONE"),
        intent_required=os.environ.get("CRUCIBLE_INTENT_GATE", "1") != "0",
    )
    save_turn_state(payload, state)
    return state


def validate_intent_submission(
    intent: str,
    middle: str,
    expected_outcome: str,
    targets: list[str] | None = None,
) -> tuple[bool, str]:
    """Validate that an intent submission provides substantive intent, middle, and expected outcome."""
    fields = {
        "intent": (intent or "").strip(),
        "middle": (middle or "").strip(),
        "expected_outcome": (expected_outcome or "").strip(),
    }
    for name, val in fields.items():
        if len(val) < MIN_INTENT_FIELD_LEN:
            return (
                False,
                f"Invalid commit_intent: '{name}' must be at least {MIN_INTENT_FIELD_LEN} characters.",
            )
    if targets is not None and not isinstance(targets, list):
        return False, "Invalid commit_intent: 'targets' must be a list of tool/path strings."
    return True, "ok"


def mint_intent_lease(
    payload: dict[str, Any],
    *,
    intent: str,
    middle: str,
    expected_outcome: str,
    targets: list[str] | None = None,
    wave_size: int | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    """Validate and persist a wave Intent Lease into turn-meter-state.json."""
    ok, msg = validate_intent_submission(intent, middle, expected_outcome, targets)
    if not ok:
        return False, msg, None

    clean_targets = [str(t).strip() for t in (targets or []) if str(t).strip()]
    if wave_size is not None:
        uses = max(1, min(MAX_WAVE_LEASE_USES, int(wave_size)))
    elif clean_targets:
        uses = max(1, min(MAX_WAVE_LEASE_USES, len(clean_targets)))
    else:
        uses = DEFAULT_WAVE_LEASE_USES

    lease = {
        "lease_id": _short_hash(f"{_utc_now_iso()}:{intent}:{middle}:{expected_outcome}"),
        "intent_hash": _short_hash(intent),
        "middle_hash": _short_hash(middle),
        "outcome_hash": _short_hash(expected_outcome),
        "targets": clean_targets[:MAX_WAVE_LEASE_USES],
        "remaining_uses": uses,
        "created_at": _utc_now_iso(),
    }
    st = load_turn_state(payload)
    st.active_lease = lease
    st.intents_committed += 1
    save_turn_state(payload, st)

    return True, "ok", lease


def check_intent_lease(payload: dict[str, Any], tool_name: str, target_hint: str = "") -> tuple[bool, str]:
    """Verify an active wave Intent Lease exists before allowing a gated mutating tool."""
    if os.environ.get("CRUCIBLE_INTENT_GATE", "1") == "0":
        return True, "Intent gate disabled via CRUCIBLE_INTENT_GATE=0."
    st = load_turn_state(payload)
    if not st.intent_required:
        return True, "Intent lease not required for this context."

    lease = st.active_lease
    if not isinstance(lease, dict) or int(lease.get("remaining_uses") or 0) <= 0:
        st.intent_blocks += 1
        save_turn_state(payload, st)

        return (
            False,
            f"INTENT GATE: Before invoking mutating tool '{tool_name}', call commit_intent "
            "(or `python C:/Users/flowe/.gemini/config/scripts/crucible_meter.py commit --intent ... --middle ... --outcome ...`) "
            "declaring (1) intent, (2) middle/mechanism, and (3) expected_outcome.",
        )

    targets = lease.get("targets") or []
    if targets and target_hint:
        norm_hint = target_hint.replace("\\", "/").lower()
        base_hint = os.path.basename(norm_hint)
        matched = any(
            (t.replace("\\", "/").lower() in norm_hint)
            or (os.path.basename(t.replace("\\", "/").lower()) == base_hint)
            or (t.strip().lower() == tool_name.lower())
            for t in targets
            if isinstance(t, str) and t.strip()
        )
        if not matched:
            st.intent_blocks += 1
            save_turn_state(payload, st)

            return (
                False,
                f"INTENT GATE: Target '{base_hint or target_hint}' is outside active intent lease targets {targets}. "
                "Call commit_intent for this wave before mutating.",
            )

    return True, f"Intent lease {lease.get('lease_id', '')} verified."


def consume_intent_lease(payload: dict[str, Any], *, failed: bool) -> None:
    """Decrement active wave lease after a gated mutation; score wave outcome & invalidate on failure."""
    st = load_turn_state(payload)
    lease = st.active_lease
    if not isinstance(lease, dict):
        return
    if failed:
        st.waves_failed += 1
        st.active_lease = None
    else:
        rem = int(lease.get("remaining_uses") or 0) - 1
        if rem <= 0:
            st.waves_succeeded += 1
            st.active_lease = None
        else:
            lease["remaining_uses"] = rem
            lease["ops_succeeded"] = int(lease.get("ops_succeeded") or 0) + 1
            st.active_lease = lease
    save_turn_state(payload, st)



def parse_cli_commit_command(cmd: str) -> dict[str, Any] | None:
    """Parse `crucible_meter.py commit --intent ... --middle ... --outcome ...` from a shell command."""
    if not isinstance(cmd, str) or "crucible_meter.py" not in cmd.lower() or "commit" not in cmd.lower():
        return None
    try:
        tokens = shlex.split(cmd, posix=(os.name != "nt"))
    except ValueError:
        return None
    # Strip surrounding quotes left by Windows shlex mode
    cleaned = [t.strip('"').strip("'") for t in tokens]
    try:
        commit_idx = next(i for i, tok in enumerate(cleaned) if tok.lower() == "commit")
    except StopIteration:
        return None
    if not any("crucible_meter.py" in tok.lower() for tok in cleaned[:commit_idx]):
        return None

    sub = cleaned[commit_idx + 1 :]
    parsed: dict[str, Any] = {"intent": "", "middle": "", "expected_outcome": "", "targets": [], "wave_size": None}
    i = 0
    while i < len(sub):
        flag = sub[i]
        val = sub[i + 1] if i + 1 < len(sub) else ""
        if flag == "--intent":
            parsed["intent"] = val
            i += 2
        elif flag == "--middle":
            parsed["middle"] = val
            i += 2
        elif flag == "--outcome":
            parsed["expected_outcome"] = val
            i += 2
        elif flag == "--targets":
            parsed["targets"] = [t.strip() for t in val.split(",") if t.strip()]
            i += 2
        elif flag == "--wave-size":
            try:
                parsed["wave_size"] = int(val)
            except ValueError:
                pass
            i += 2
        else:
            i += 1
    return parsed

def record_tool_event(
    payload: dict[str, Any],
    *,
    tool_name: str,
    failed: bool,
    is_code_edit: bool = False,
    is_verify_cmd: bool = False,
    error_sig: str = "",
) -> TurnMeterState:
    st = load_turn_state(payload)
    st.tool_calls += 1
    if tool_name == "read_file" and not failed:
        st.read_calls += 1
    if is_code_edit and not failed:
        st.code_edits += 1
    if is_verify_cmd:
        if failed:
            st.verify_failed += 1
        else:
            st.verify_passed += 1

    if failed:
        st.consecutive_errors += 1
        sig = _short_hash(f"{tool_name}:{error_sig}") if error_sig else tool_name
        if sig == st.last_error_sig:
            st.repeated_error_count += 1
        else:
            st.last_error_sig = sig
            st.repeated_error_count = 1
    else:
        st.consecutive_errors = 0
        st.last_error_sig = ""
        st.repeated_error_count = 0

    save_turn_state(payload, st)

    return st


def extract_latest_planner_response(transcript_path: Path | None) -> str:
    """Return text content of the latest PLANNER_RESPONSE in transcript.jsonl."""
    if transcript_path is None or not transcript_path.is_file():
        return ""
    try:
        raw_bytes = transcript_path.read_bytes()
    except OSError:
        return ""
    for ln in reversed(raw_bytes.splitlines()[-40:]):
        if b'"PLANNER_RESPONSE"' not in ln:
            continue
        obj = _safe_json_loads(ln)
        if obj is not None and obj.get("type") == "PLANNER_RESPONSE":
            content = obj.get("content")
            if isinstance(content, str) and content.strip():
                return content
    return ""


def extract_claimed_meter(response_text: str) -> dict[str, Any]:
    """Parse Crucible JSON meter and [LEVEL 9/10 NOTICE] claims from assistant output."""
    text = response_text or ""
    has_l9_notice = bool(L9_NOTICE_RE.search(text))
    has_l10_notice = bool(L10_NOTICE_RE.search(text))

    claimed_vec: dict[str, int] | None = None
    claimed_rank: str | None = None
    claimed_stage: str | None = None

    matches = METER_JSON_RE.findall(text)
    if matches:
        obj = _safe_json_loads(matches[-1])
        if obj is not None:
            vec = obj.get("vec")
            if isinstance(vec, dict):
                parsed_vec: dict[str, int] = {}
                for k in ("L", "P", "C", "R"):
                    if k in vec:
                        try:
                            parsed_vec[k] = int(vec[k])
                        except (ValueError, TypeError):
                            pass
                if parsed_vec:
                    claimed_vec = parsed_vec
            if isinstance(obj.get("rank"), str):
                claimed_rank = obj["rank"].upper()
            if isinstance(obj.get("stage"), str):
                claimed_stage = obj["stage"].upper()

    return {
        "has_meter_json": claimed_vec is not None,
        "claimed_stage": claimed_stage,
        "claimed_vec": claimed_vec,
        "claimed_rank": claimed_rank,
        "has_l9_notice": has_l9_notice,
        "has_l10_notice": has_l10_notice,
    }


def audit_turn_claims(turn_state: TurnMeterState, response_text: str) -> dict[str, Any]:
    """Mechanically audit claimed P/L9/L10 proof against observed turn evidence."""
    claims = extract_claimed_meter(response_text)

    if turn_state.code_edits > 0 and turn_state.verify_passed == 0:
        verified_p_cap = 3
    elif turn_state.verify_passed > 0:
        verified_p_cap = 9
    elif turn_state.read_calls > 0 or turn_state.tool_calls > 0:
        verified_p_cap = 9
    else:
        verified_p_cap = 3

    violations: list[str] = []
    claimed_vec = claims["claimed_vec"] or {}
    claimed_p = claimed_vec.get("P")

    if claims["has_l10_notice"] or (claimed_p is not None and claimed_p >= 10) or claims["claimed_rank"] == "L10":
        violations.append(
            "Anti-Goodhart Gate: Never fake L10 or P=10 inside a single automated turn without Rung-4 field proof. "
            "Report honest ceiling (e.g. L9) and exact gap."
        )

    if claimed_p is not None and claimed_p >= 5 and turn_state.code_edits > 0 and turn_state.verify_passed == 0:
        violations.append(
            f"Anti-Goodhart Gate: Claimed P={claimed_p} after {turn_state.code_edits} code edit(s) with "
            "0 passing verification commands. Run verification or lower P <= 3."
        )

    if claims["has_l9_notice"] and verified_p_cap < 9:
        violations.append(
            f"Anti-Goodhart Gate: [LEVEL 9 NOTICE] requires verified P >= 9, "
            f"but mechanical turn evidence caps P <= {verified_p_cap}."
        )

    return {
        "ok": len(violations) == 0,
        "verified_p_cap": verified_p_cap,
        "claims": claims,
        "violations": violations,
    }


def write_handoff_draft(artifact_dir: Path, meter: dict[str, Any], turn_state: TurnMeterState) -> Path | None:
    """Write a safe, ready-to-review handoff draft inside artifact_dir when DEPLETED."""
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        out = artifact_dir / HANDOFF_DRAFT_FILENAME
        content = (
            "# Context-Window Handoff Draft (Auto-Generated by Crucible Turn Meter v2)\n\n"
            f"- **Generated:** {_utc_now_iso()}\n"
            f"- **Status:** `{meter.get('ctx_status')}` (`rot_reason={meter.get('rot_reason')}`)\n"
            f"- **Active Tokens:** `{meter.get('active_tokens')}` (`source={meter.get('token_source')}`)\n"
            f"- **Compactions:** `{meter.get('compactions')}` | **Turns:** `{meter.get('turn')}` "
            f"(since checkpoint: `{meter.get('turns_since_cp')}`)\n"
            f"- **Last Turn Telemetry:** `tool_calls={turn_state.tool_calls}`, "
            f"`code_edits={turn_state.code_edits}`, `verify_passed={turn_state.verify_passed}`\n\n"
            "## Next Session Action\n"
            "1. Review and copy this file to `~/.gemini/NEXT_SESSION_HANDOFF.md` if you want auto-pickup.\n"
            "2. Fill in the exact next slice, target files, and `verify_cmd` before starting a fresh conversation.\n"
        )
        out.write_text(content, encoding="utf-8")
        return out
    except OSError:
        return None


def append_receipt(
    turn_state: TurnMeterState,
    audit: dict[str, Any],
    *,
    decision: str,
    receipts_path: Path = DEFAULT_RECEIPTS_PATH,
) -> None:
    """Append a privacy-safe structured telemetry receipt (zero raw prompt/file prose)."""
    claims = audit.get("claims") or {}
    claimed_vec = claims.get("claimed_vec") or {}
    total_waves = turn_state.waves_succeeded + turn_state.waves_failed
    active_ops = int((turn_state.active_lease or {}).get("ops_succeeded") or 0)
    if total_waves > 0:
        intent_outcome_score: float | None = round(turn_state.waves_succeeded / float(total_waves), 2)
    elif active_ops > 0 and turn_state.waves_failed == 0:
        intent_outcome_score = 1.0
    else:
        intent_outcome_score = None

    record = {
        "ts": _utc_now_iso(),
        "conv_hash": _short_hash(turn_state.conversation_id),
        "prompt_hash": turn_state.prompt_hash,
        "turn": turn_state.turn,
        "target_rank": turn_state.target_rank,
        "active_tokens": turn_state.active_tokens,
        "compactions": turn_state.compaction_count,
        "rot_reason": turn_state.rot_reason,
        "ctx_status": turn_state.ctx_status,
        "tool_calls": turn_state.tool_calls,
        "read_calls": turn_state.read_calls,
        "code_edits": turn_state.code_edits,
        "verify_passed": turn_state.verify_passed,
        "verify_failed": turn_state.verify_failed,
        "intents_committed": turn_state.intents_committed,
        "intent_blocks": turn_state.intent_blocks,
        "waves_succeeded": turn_state.waves_succeeded,
        "waves_failed": turn_state.waves_failed,
        "intent_outcome_score": intent_outcome_score,
        "claimed_rank": claims.get("claimed_rank"),
        "claimed_p": claimed_vec.get("P"),
        "verified_p_cap": audit.get("verified_p_cap"),
        "violations_count": len(audit.get("violations") or []),
        "decision": decision,
    }
    try:
        receipts_path.parent.mkdir(parents=True, exist_ok=True)
        with receipts_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError:
        pass


def replay_brain(brain_dir: Path) -> dict[str, Any]:
    """Replay meter across all transcript.jsonl files under brain_dir for empirical calibration."""
    if not brain_dir.is_dir():
        return {"sessions": 0, "error": f"Directory not found: {brain_dir}"}

    transcripts = sorted(brain_dir.glob("*/.system_generated/logs/transcript.jsonl"))
    latencies: list[float] = []
    exact_count = 0
    compacted = 0
    v1_false_depleted_fixed = 0
    status_counts = {"GREEN": 0, "WARN": 0, "DEPLETED": 0}
    rot_counts = {"NONE": 0, "WINDOW_PRESSURE": 0, "FIDELITY_DECAY": 0, "BOTH": 0}
    samples: list[dict[str, Any]] = []

    for tp in transcripts:
        m = measure_transcript(tp)
        latencies.append(float(m["measure_ms"]))
        if m["token_source"] == "exact_telemetry":
            exact_count += 1
        if m["compactions"] > 0:
            compacted += 1
        status_counts[m["ctx_status"]] = status_counts.get(m["ctx_status"], 0) + 1
        rot_counts[m["rot_reason"]] = rot_counts.get(m["rot_reason"], 0) + 1

        v1_would_deplete = m["ctx_kb"] >= 600.0 or m["turn"] >= 40
        if v1_would_deplete and m["ctx_status"] != "DEPLETED":
            v1_false_depleted_fixed += 1

        if m["ctx_status"] != "GREEN" or m["compactions"] > 0:
            samples.append(
                {
                    "session": tp.parent.parent.parent.name[:8],
                    "turn": m["turn"],
                    "ctx_kb": m["ctx_kb"],
                    "active_tokens": m["active_tokens"],
                    "compactions": m["compactions"],
                    "status": m["ctx_status"],
                    "rot_reason": m["rot_reason"],
                    "ms": m["measure_ms"],
                }
            )

    latencies.sort()
    n = len(latencies)
    p50 = latencies[n // 2] if n else 0.0
    p99 = latencies[min(n - 1, int(n * 0.99))] if n else 0.0
    max_ms = latencies[-1] if n else 0.0

    return {
        "sessions": n,
        "exact_telemetry_sessions": exact_count,
        "compacted_sessions": compacted,
        "v1_false_depleted_fixed": v1_false_depleted_fixed,
        "status_counts": status_counts,
        "rot_counts": rot_counts,
        "p50_ms": round(p50, 2),
        "p99_ms": round(p99, 2),
        "max_ms": round(max_ms, 2),
        "notable_sessions": samples[:10],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crucible Turn Meter v2 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_meas = sub.add_parser("measure", help="Measure context physics of a transcript.jsonl")
    p_meas.add_argument("transcript", type=Path)
    p_meas.add_argument("--prompt", default="", help="Optional user prompt text for target_rank detection")

    p_aud = sub.add_parser("audit", help="Audit latest assistant response against turn state")
    p_aud.add_argument("transcript", type=Path)
    p_aud.add_argument("--state", type=Path, default=None, help="Optional turn-meter-state.json path")

    p_rep = sub.add_parser("replay", help="Empirically replay meter across a brain/ directory")
    p_rep.add_argument("brain_dir", type=Path)

    p_ho = sub.add_parser("handoff", help="Generate a safe HANDOFF_DRAFT.md from a transcript")
    p_ho.add_argument("transcript", type=Path)
    p_ho.add_argument("--out-dir", type=Path, required=True)

    p_com = sub.add_parser("commit", help="Validate and emit a visible pre-tool Intent Lease payload")
    p_com.add_argument("--intent", required=True, help="Why this mutation is needed (goal/bottleneck)")
    p_com.add_argument("--middle", required=True, help="Mechanism/bridge: how the change works and what invariant it preserves")
    p_com.add_argument("--outcome", required=True, help="Falsifiable expected outcome proving success")
    p_com.add_argument("--targets", default="", help="Optional comma-separated target files/tools for this wave")
    p_com.add_argument("--wave-size", type=int, default=None, help="Optional max mutations in this wave (1..12)")

    args = parser.parse_args(argv)
    if args.cmd == "measure":
        out = measure_transcript(args.transcript, args.prompt)
    elif args.cmd == "audit":
        payload = {"transcriptPath": str(args.transcript)}
        if args.state is not None:
            payload = {"artifactDirectoryPath": str(args.state.parent)}
        st = load_turn_state(payload)
        resp = extract_latest_planner_response(args.transcript)
        out = audit_turn_claims(st, resp)
    elif args.cmd == "replay":
        out = replay_brain(args.brain_dir)
    elif args.cmd == "handoff":
        m = measure_transcript(args.transcript)
        st = TurnMeterState(turn=m["turn"], active_tokens=m["active_tokens"], compaction_count=m["compactions"])
        draft = write_handoff_draft(args.out_dir, m, st)
        out = {"draft": str(draft) if draft else None, "meter": m}
    elif args.cmd == "commit":
        targets = [t.strip() for t in (args.targets or "").split(",") if t.strip()]
        ok, msg = validate_intent_submission(args.intent, args.middle, args.outcome, targets)
        if not ok:
            sys.stderr.write(msg + "\n")
            return 2
        out = {
            "status": "INTENT_COMMITTED",
            "intent": args.intent.strip(),
            "middle": args.middle.strip(),
            "expected_outcome": args.outcome.strip(),
            "targets": targets,
            "wave_size": args.wave_size or (len(targets) if targets else DEFAULT_WAVE_LEASE_USES),
        }
    else:
        out = {}

    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
