#!/usr/bin/env python3
"""Cross-platform signal-chain router for Antigravity SessionStart and PreInvocation hooks.

Routes incoming user intent to lean skills and warns on mechanical context-window
pressure (post-compaction bytes/turns) with zero LLM calls and zero scoring rubrics.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

SIGNAL_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "cpl_media",
        re.compile(
            r"\b(?:calgary public library|av script|a/v script|shot list|call sheet|concept outline|"
            r"media production brief|video reverse[- ]?engineer|story[- ]?lane|instagram reels|youtube shorts|"
            r"(?:library|cpl)\s+(?:youtube|video|pilot|campaign|brief|cutdown))\b",
            re.IGNORECASE,
        ),
        "SIGNAL [calgary-library-production]: Apply Calgary Public Library production skills and house rules "
        "(write 'Calgary Public Library' or 'the Library', never 'CPL'; Instagram Reels or YouTube Shorts only, "
        "never TikTok; no em-dashes in deliverables).",
    ),
    (
        "meeting_brief",
        re.compile(
            r"(?:\b(?:meeting|teams|zoom|kickoff|debrief|call)\s+(?:transcript|recording)\b|"
            r"\bmeeting brief\b|\btranscript\b.{0,40}\b(?:brief|decisions|action items)\b)",
            re.IGNORECASE,
        ),
        "SIGNAL [meeting-brief]: Load meeting-brief. Extract Settled vs. Hype (verbatim quote anchors), "
        "Actions & Waiting-On, Risks/Tension, 1-2 falsifiable assumptions, and typed handoffs below a divider.",
    ),
    (
        "potential_unleashed",
        re.compile(
            r"\b(?:potential[- ]?unleashed|crucible_gate|sentinel\.py|operator_router|hooks\.json|test_quality_gate|"
            r"cross-file contract|schema change|"
            r"(?:build|refactor|ship|update|create|harden|audit|redesign|transform)\s+(?:a\s+|an\s+|the\s+|my\s+)?"
            r"(?:[\w./-]+\s+){0,2}(?:[\w./-]+-)?(?:skill|validator|harness|pipeline|engine|module|cli|hook|workflow|system|script|config))\b",
            re.IGNORECASE,
        ),
        "SIGNAL [potential-unleashed]: Load potential-unleashed. Own the outcome, reshape/cut before patching, "
        "prove red-to-green through the real doorway (including the absent case), and blind-break structural changes.",
    ),
)

BUG_SIGNAL_RE = re.compile(
    r"\b(?:debug(?:ging)?|diagnos(?:e|ing)|failing tests?|flaky|stack trace|traceback|"
    r"throwing\s+(?:an?\s+)?(?:error|exception|typeerror|valueerror|keyerror|runtimeerror|traceback)|"
    r"(?:fix|investigate|caused|introduced|hit|track\s+down|debug)\s+(?:a\s+|this\s+|the\s+)?regression)\b",
    re.IGNORECASE,
)

SPEC_DOC_RE = re.compile(
    r"(?im)^\s*(?:WORKFLOW\s+\d+|#\s*PHASE\s+\d+|##\s*Final Execution Prompt|TARGET REPOSITORY:)"
)
TRACE_RE = re.compile(r"\b(?:traceback|stack trace)\b", re.IGNORECASE)

# Mechanical context-window pressure thresholds on transcript.jsonl (post-compaction aware)
CTX_WARN_KB = 350.0
CTX_DEPLETED_KB = 600.0
CTX_WARN_TURNS = 25
CTX_DEPLETED_TURNS = 40
COMPACTION_WARN = 2
COMPACTION_DEPLETED = 4
HANDOFF_STALE_HOURS = 48.0


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


def measure_context_pressure(transcript_path: Path | None) -> dict[str, Any]:
    """Measure mechanical context-window pressure (active bytes/turns since last compaction + compaction count)."""
    if transcript_path is None or not transcript_path.is_file():
        return {"ctx_status": "OK", "active_kb": 0.0, "turns_since_checkpoint": 0, "compactions": 0, "reason": ""}

    try:
        raw = transcript_path.read_bytes()
    except OSError:
        return {"ctx_status": "OK", "active_kb": 0.0, "turns_since_checkpoint": 0, "compactions": 0, "reason": ""}

    if not raw:
        return {"ctx_status": "OK", "active_kb": 0.0, "turns_since_checkpoint": 0, "compactions": 0, "reason": ""}

    lines = raw.splitlines()
    compactions = 0
    last_cp_idx = -1
    for idx, ln in enumerate(lines):
        if b'"CHECKPOINT"' in ln:
            try:
                obj = json.loads(ln)
            except (ValueError, UnicodeDecodeError):
                obj = None
            if isinstance(obj, dict) and obj.get("type") == "CHECKPOINT":
                compactions += 1
                last_cp_idx = idx

    active_lines = lines[last_cp_idx + 1 :] if last_cp_idx >= 0 else lines
    active_bytes = sum(len(ln) + 1 for ln in active_lines)
    active_kb = round(active_bytes / 1024.0, 1)

    turns = 0
    for ln in active_lines:
        if b'"USER_INPUT"' not in ln:
            continue
        try:
            obj = json.loads(ln)
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(obj, dict) and obj.get("type") == "USER_INPUT":
            src = obj.get("source")
            if src is None or src == "USER_EXPLICIT":
                turns += 1

    reasons: list[str] = []
    status = "OK"
    if active_kb >= CTX_DEPLETED_KB or turns >= CTX_DEPLETED_TURNS or compactions >= COMPACTION_DEPLETED:
        status = "DEPLETED"
        if active_kb >= CTX_DEPLETED_KB:
            reasons.append(f"active_kb={active_kb}>={CTX_DEPLETED_KB}")
        if turns >= CTX_DEPLETED_TURNS:
            reasons.append(f"turns={turns}>={CTX_DEPLETED_TURNS}")
        if compactions >= COMPACTION_DEPLETED:
            reasons.append(f"compactions={compactions}>={COMPACTION_DEPLETED}")
    elif active_kb >= CTX_WARN_KB or turns >= CTX_WARN_TURNS or compactions >= COMPACTION_WARN:
        status = "WARN"
        if active_kb >= CTX_WARN_KB:
            reasons.append(f"active_kb={active_kb}>={CTX_WARN_KB}")
        if turns >= CTX_WARN_TURNS:
            reasons.append(f"turns={turns}>={CTX_WARN_TURNS}")
        if compactions >= COMPACTION_WARN:
            reasons.append(f"compactions={compactions}>={COMPACTION_WARN}")

    return {
        "ctx_status": status,
        "active_kb": active_kb,
        "turns_since_checkpoint": turns,
        "compactions": compactions,
        "reason": ", ".join(reasons),
    }


def detect_prompt_signals(user_text: str) -> list[str]:
    """Return targeted skill-routing nudges matching user_text."""
    if not user_text:
        return []
    messages: list[str] = []
    matched_pu = False
    pu_instruction = ""
    for signal_id, pattern, instruction in SIGNAL_RULES:
        if signal_id == "potential_unleashed":
            pu_instruction = instruction
        if pattern.search(user_text):
            messages.append(instruction)
            if signal_id == "potential_unleashed":
                matched_pu = True

    skip_bug_signal = (
        len(user_text) > 1500 or bool(SPEC_DOC_RE.search(user_text))
    ) and not bool(TRACE_RE.search(user_text))
    if not matched_pu and not skip_bug_signal and BUG_SIGNAL_RE.search(user_text):
        messages.append(pu_instruction)
    return messages


def handle_session_start(payload: dict[str, Any]) -> dict[str, Any]:
    """Emit minimal startup orientation and surface any fresh pending NEXT_SESSION_HANDOFF.md."""
    steps: list[dict[str, Any]] = [
        {
            "systemMessage": {
                "systemMessage": (
                    "Global constitution active (5 Sentinel/Router hooks live; "
                    "potential-unleashed for engineering/debugging, meeting-brief for transcripts)."
                )
            }
        }
    ]
    handoff = Path.home() / ".gemini" / "NEXT_SESSION_HANDOFF.md"
    if handoff.is_file():
        try:
            age_hours = max(0.0, (time.time() - handoff.stat().st_mtime) / 3600.0)
        except OSError:
            age_hours = 0.0
        if age_hours > HANDOFF_STALE_HOURS:
            msg = (
                f"STALE HANDOFF FOUND ({age_hours:.0f}h old) at {handoff.as_posix()}: "
                "Ask the user before executing it, and archive or delete it once consumed."
            )
        else:
            msg = (
                f"PENDING HANDOFF READY ({age_hours:.1f}h old) at {handoff.as_posix()}: "
                "If the user says 'go' (or starts without specifying another task), "
                "read that file, execute its mandate, and archive or delete it once consumed."
            )
        steps.append({"systemMessage": {"systemMessage": msg}})

    return {"injectSteps": steps}


def _load_router_state(state_file: Path) -> dict[str, Any]:
    if not state_file.is_file():
        return {}
    try:
        prev = json.loads(state_file.read_text(encoding="utf-8"))
        return prev if isinstance(prev, dict) else {}
    except (OSError, ValueError) as exc:
        print(f"operator_router state load error: {type(exc).__name__}", file=sys.stderr)
        return {}


def _save_router_state(state_file: Path, data: dict[str, Any]) -> None:
    tmp = state_file.with_name(f".{state_file.name}.{os.getpid()}.tmp")
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(data) + "\n", encoding="utf-8")
        os.replace(tmp, state_file)
    except OSError as exc:
        print(f"operator_router state save error: {type(exc).__name__}", file=sys.stderr)
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def handle_pre_invocation(payload: dict[str, Any]) -> dict[str, Any]:
    """Route incoming user intent once per prompt and surface context-window pressure transitions."""
    user_text = str(payload.get("lastUserInput") or "")
    art_dir = payload.get("artifactDirectoryPath")
    state_file = Path(art_dir.strip()) / "operator-router-seen.json" if isinstance(art_dir, str) and art_dir.strip() else None

    prev_state = _load_router_state(state_file) if state_file is not None else {}
    digest = hashlib.sha256(user_text.encode("utf-8", errors="replace")).hexdigest()
    conv_id = str(payload.get("conversationId") or "")
    key = f"{conv_id}:{digest}"
    same_prompt = bool(state_file is not None and prev_state.get("last_key") == key)

    nudges: list[str] = [] if same_prompt else detect_prompt_signals(user_text)

    ctx = measure_context_pressure(resolve_transcript_path(payload))
    ctx_status = ctx["ctx_status"]
    prev_ctx_status = str(prev_state.get("last_ctx_status") or "OK")
    should_emit_ctx = (not same_prompt) or (ctx_status != prev_ctx_status)

    if should_emit_ctx and ctx_status == "DEPLETED":
        nudges.append(
            f"CONTEXT WINDOW DEPLETED ({ctx['reason']}): Keep this reply concise and recommend starting a fresh conversation (or /compact)."
        )
    elif should_emit_ctx and ctx_status == "WARN":
        nudges.append(
            f"CONTEXT PRESSURE WARNING ({ctx['reason']}): Keep outputs compact and mention /compact or a fresh thread if needed."
        )

    if state_file is not None and (not same_prompt or ctx_status != prev_ctx_status):
        _save_router_state(state_file, {"last_key": key, "last_ctx_status": ctx_status})

    if not nudges:
        return {"injectSteps": []}
    return {
        "injectSteps": [
            {"systemMessage": {"systemMessage": nudge}} for nudge in nudges
        ]
    }


def main(argv: list[str] | None = None) -> int:
    t0 = time.perf_counter()
    args = argv if argv is not None else sys.argv[1:]
    mode = args[0] if args else ""
    out: dict[str, Any] = {}
    try:
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
        if not isinstance(payload, dict):
            payload = {}
        if mode == "session-start":
            out = handle_session_start(payload)
        elif mode == "pre-invocation":
            out = handle_pre_invocation(payload)
        else:
            out = {}
    except Exception as exc:
        print(f"operator_router error: {type(exc).__name__}", file=sys.stderr)
        out = {}

    sys.stdout.write(json.dumps(out))
    try:
        from sentinel.telemetry import record_hook_event

        steps = out.get("injectSteps") if isinstance(out, dict) else []
        n = len(steps) if isinstance(steps, list) else 0
        record_hook_event(
            mode or "router",
            "operator_router",
            "emit" if n > 0 else "abstain",
            f"nudges={n}" if n > 0 else "",
            (time.perf_counter() - t0) * 1000.0,
        )
    except Exception as exc:
        print(f"operator_router telemetry error: {type(exc).__name__}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
