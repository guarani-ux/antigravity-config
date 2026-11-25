#!/usr/bin/env python3
"""Windows-safe signal-chain router for Elijah's Antigravity 2.0 environment.

Routes SessionStart and PreInvocation lifecycle events to skills without making
blocking cross-OS UNC calls into WSL and without ever locking out the IDE.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import crucible_meter

SIGNAL_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "cpl_media",
        re.compile(
            r"\b(calgary public library|cpl|youtube|pilot|writers[- ]?room|story[- ]?lane|av script|a/v script|cutdown|call sheet)\b",
            re.IGNORECASE,
        ),
        "SIGNAL [outcome-media]: Pin Calgary Public Library/GROUND_TRUTH.md (Asana read-only). "
        "Use writers-room / story-lane MCP spokes (K-MCP-01) and run cold-receiver-review (G05) + ig-evidence-review before handoff.",
    ),
    (
        "meeting_sim",
        re.compile(
            r"\b(stakeholder|handoff|approval|sign-?off|release package|should we ship|trade-?off|decision)\b",
            re.IGNORECASE,
        ),
        "SIGNAL [meeting-simulator]: Before responding on this consequential decision, run a sequential role-order pass "
        "(each role receives prior proposal, open objections, and blockers -> revise|retain|hold) and report what changed, "
        "which constraint mattered, and what stayed open.",
    ),
    (
        "crucible_code",
        re.compile(
            r"\b(crucible_gate|campaign\.json|tx_patch|doctor\.py|router\.py|hook_v4|operator_router)\b",
            re.IGNORECASE,
        ),
        "SIGNAL [outcome-code]: Follow Orient -> Freeze -> Execute -> Verify. "
        "Use slice-worker (Workspace='share') for multi-slice work and verify with scripts/verify_all.ps1.",
    ),
    (
        "av_craft",
        re.compile(
            r"\b(av script|a/v script|paper edit|story spine|two-column script)\b",
            re.IGNORECASE,
        ),
        "SIGNAL [av-craft]: Load av-craft. Separate Explore (quarry -> spine) "
        "from Exploit (beats / paper-edit). Never jump straight into a final script table.",
    ),
    (
        "cl_craft",
        re.compile(
            r"\b(cover letter|job description|jd decode)\b",
            re.IGNORECASE,
        ),
        "SIGNAL [cl-craft]: Load cl-craft. Run JD X-Ray + proof custody against "
        "career-quarry.md before drafting prose.",
    ),
    (
        "forensic",
        re.compile(
            r"\b(forensic audit|dead code|what'?s actually wired)\b",
            re.IGNORECASE,
        ),
        "SIGNAL [mode-forensic]: Strictly read-only inspection first. Verify callers, "
        "tests, and entrypoints before proposing edits.",
    ),
    (
        "diagnosing_bugs",
        re.compile(
            r"\b(?:debug(?:ging)?|diagnos(?:e|ing)|failing tests?|flaky|stack trace|traceback|"
            r"throwing\s+(?:an?\s+)?(?:error|exception|typeerror|valueerror|keyerror|runtimeerror|traceback)|"
            r"(?:fix|investigate|caused|introduced|hit|track\s+down|debug)\s+(?:a\s+|this\s+|the\s+)?regression)\b",
            re.IGNORECASE,
        ),
        "SIGNAL [diagnosing-bugs]: Reproduce with a red-capable command and state 3 falsifiable hypotheses BEFORE editing code.",
    ),
    (
        "visual_reflex",
        re.compile(
            r"\b(frontend|tailwind|css|dashboard|landing page|ui redesign|ui polish|visual design)\b",
            re.IGNORECASE,
        ),
        "SIGNAL [visual-reflex]: Load visual-reflex (no #000/#fff clipping, 2-stage contact shadows, hairline partitions) and verify visually.",
    ),
    (
        "mode_reframe",
        re.compile(
            r"\b(?:think about our options|what are our options|weigh(?:ing)? our options|"
            r"how should we approach|how can we go about|repeatable,\s*deterministic way|"
            r"before we commit to code|compare paradigms)\b",
            re.IGNORECASE,
        ),
        "SIGNAL [mode-reframe]: Load mode-reframe (Top-of-Totem-Pole Modulator). Zero file edits. "
        "Identify governing discipline(s) & altitude, flag missing information, compare 3 distinct "
        "paradigms + pitfalls, and issue an Engage/Suppress/Gate Mobilization Directive.",
    ),
    (
        "acceleration",
        re.compile(
            r"\b(what if we|new system|new folder|new repo|new project|new idea|spark:|idea:|another idea|let'?s build a brand new)\b",
            re.IGNORECASE,
        ),
        "SIGNAL [idea-crucible]: Rapid ideation / new-build impulse detected. Activate idea-crucible "
        "(and mode-reframe if design is open). Compress the spark, check existing canonical homes first, "
        "and run the 3 Hardening Checks BEFORE creating code or directories.",
    ),
)

SPEC_DOC_RE = re.compile(
    r"(?im)^\s*(?:WORKFLOW\s+\d+|#\s*PHASE\s+\d+|##\s*Final Execution Prompt|TARGET REPOSITORY:)"
)
TRACE_RE = re.compile(r"\b(?:traceback|stack trace)\b", re.IGNORECASE)
TARGET_RANK_RE = re.compile(
    r"\b(?:level\s*(9|10)|l(9|10)|rank\s*(9|10))\b",
    re.IGNORECASE,
)

# Mechanical context-window pressure thresholds on compact transcript.jsonl
CTX_WARN_KB = 350.0
CTX_DEPLETED_KB = 600.0
CTX_WARN_TURNS = 25
CTX_DEPLETED_TURNS = 40

SECTION_MAP = (
    ("stage 4:", "active"),
    ("stage 3:", "hardened"),
    ("stage 2:", "challenged"),
    ("stage 1:", "raw"),
    ("shipped", "shipped"),
)


def parse_ledger_summary(ledger_path: Path) -> dict[str, Any]:
    """Parse stage counts from an IDEAS.md ledger if locally accessible."""
    summary: dict[str, Any] = {
        "exists": False,
        "active": 0,
        "hardened": 0,
        "challenged": 0,
        "raw": 0,
        "shipped": 0,
    }
    if not ledger_path.exists():
        return summary

    summary["exists"] = True
    current_bucket: str | None = None
    for raw_line in ledger_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            lower_heading = stripped[3:].strip().lower()
            current_bucket = None
            for prefix, bucket in SECTION_MAP:
                if lower_heading.startswith(prefix):
                    current_bucket = bucket
                    break
            continue
        if current_bucket is None or not raw_line.startswith("- "):
            continue
        item_body = raw_line[2:].strip()
        if not item_body or item_body.startswith("*("):
            continue
        summary[current_bucket] += 1

    return summary


def find_local_ledger(payload: dict[str, Any]) -> Path | None:
    """Return local workspace IDEAS.md if present without touching UNC network paths."""
    for ws in payload.get("workspacePaths") or []:
        ws_str = str(ws)
        if ws_str.startswith("\\\\") or ws_str.startswith("//"):
            continue
        candidate = Path(ws_str) / "IDEAS.md"
        if candidate.exists():
            return candidate
    fallback = Path.home() / ".gemini" / "IDEAS.md"
    return fallback if fallback.exists() else None


def detect_prompt_signals(user_text: str) -> list[str]:
    """Return targeted skill-routing nudges matching user_text."""
    if not user_text:
        return []
    messages: list[str] = []
    lower_text = user_text.lower()
    skip_acceleration = (
        "traceback" in lower_text
        or "active slice" in lower_text
        or "hardened spec" in lower_text
    )
    skip_diagnosing = (
        len(user_text) > 1500 or bool(SPEC_DOC_RE.search(user_text))
    ) and not bool(TRACE_RE.search(user_text))
    for signal_id, pattern, instruction in SIGNAL_RULES:
        if signal_id == "acceleration" and skip_acceleration:
            continue
        if signal_id == "diagnosing_bugs" and skip_diagnosing:
            continue
        if pattern.search(user_text):
            messages.append(instruction)
    return messages


def handle_session_start(payload: dict[str, Any]) -> dict[str, Any]:
    """Emit minimal startup orientation and surface any pending NEXT_SESSION_HANDOFF.md."""
    steps: list[dict[str, Any]] = [
        {"systemMessage": {"systemMessage": "Global constitution active (Orient -> Freeze -> Execute -> Verify; Tier 0/1/2)."}}
    ]
    handoff = Path.home() / ".gemini" / "NEXT_SESSION_HANDOFF.md"
    if handoff.is_file():
        steps.append(
            {
                "systemMessage": {
                    "systemMessage": (
                        f"PENDING HANDOFF READY at {handoff.as_posix()} — "
                        "If the user says 'go' (or starts without specifying another task), "
                        "read that file immediately and execute its mandate."
                    )
                }
            }
        )
    return {"injectSteps": steps}


def _already_emitted_for_prompt(payload: dict[str, Any], user_text: str) -> bool:
    """Emit PreInvocation nudges at most once per unique user prompt in a conversation."""
    import hashlib
    art_dir = payload.get("artifactDirectoryPath")
    if not isinstance(art_dir, str) or not art_dir.strip():
        return False
    state_file = Path(art_dir) / "operator-router-seen.json"
    digest = hashlib.sha256(user_text.encode("utf-8", errors="replace")).hexdigest()
    conv_id = str(payload.get("conversationId") or "")
    key = f"{conv_id}:{digest}"
    try:
        if state_file.is_file():
            prev = json.loads(state_file.read_text(encoding="utf-8"))
            if isinstance(prev, dict) and prev.get("last_key") == key:
                return True
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"last_key": key}) + "\n", encoding="utf-8")
    except OSError:
        return False
    return False


def measure_turn_and_context_meter(payload: dict[str, Any], user_text: str) -> dict[str, Any]:
    """Mechanically measure two-axis context physics (active tokens + compactions) and L9/L10 target rank."""
    transcript = crucible_meter.resolve_transcript_path(payload)
    return crucible_meter.measure_transcript(transcript, user_text)


def handle_pre_invocation(payload: dict[str, Any]) -> dict[str, Any]:
    """Route incoming user intent + Turn-Start Crucible Meter once per user turn without per-tool-step flooding."""
    user_text = str(payload.get("lastUserInput") or "")
    if _already_emitted_for_prompt(payload, user_text):
        return {"injectSteps": []}

    nudges = detect_prompt_signals(user_text)
    meter = measure_turn_and_context_meter(payload, user_text)
    turn_state = crucible_meter.begin_turn(payload, user_text, meter)

    if meter["target_rank"] in ("L9", "L10"):
        nudges.append(
            f"CRUCIBLE_TURN_METER {json.dumps(meter, separators=(',', ':'))} — "
            f"TARGET-SEEKING MODE ({meter['target_rank']}): Run T0->T1->T2 gradient meter on (L,P,C,R), "
            f"refuse symptom patches, attack argmin(L,P,C,R) first, emit JSON meter, and NEVER fake L10."
        )

    if meter["ctx_status"] == "DEPLETED":
        draft_note = ""
        art_dir = payload.get("artifactDirectoryPath")
        if isinstance(art_dir, str) and art_dir.strip():
            draft = crucible_meter.write_handoff_draft(Path(art_dir.strip()), meter, turn_state)
            if draft is not None:
                draft_note = f" Handoff draft written to {draft.as_posix()}."
        nudges.append(
            f"CRUCIBLE_TURN_METER {json.dumps(meter, separators=(',', ':'))} — "
            f"CONTEXT WINDOW DEPLETED ({meter['rot_reason']}): Inform the user clearly at the end of your reply "
            f"and recommend starting a fresh conversation (or /compact).{draft_note}"
        )
    elif meter["ctx_status"] == "WARN" and meter["target_rank"] not in ("L9", "L10"):
        nudges.append(
            f"CRUCIBLE_TURN_METER {json.dumps(meter, separators=(',', ':'))} — "
            f"CONTEXT PRESSURE WARNING ({meter['rot_reason']}): Keep outputs compact and mention /compact or a fresh thread."
        )

    if not nudges:
        return {"injectSteps": []}
    return {
        "injectSteps": [
            {"systemMessage": {"systemMessage": nudge}} for nudge in nudges
        ]
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    mode = args[0] if args else ""
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
    except Exception:
        out = {}

    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
