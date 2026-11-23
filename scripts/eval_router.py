#!/usr/bin/env python3
"""In-RAM replay evaluator for operator_router.py across local brain transcripts."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

USER_REQ_TAG_RE = re.compile(r"</?USER_REQUEST>", re.IGNORECASE)
ADDITIONAL_META_RE = re.compile(r"<ADDITIONAL_METADATA>.*$", re.DOTALL)


def _clean_prompt(raw: str) -> str:
    cleaned = USER_REQ_TAG_RE.sub("", raw)
    cleaned = ADDITIONAL_META_RE.sub("", cleaned)
    return cleaned.strip()


def collect_prompts(brain_dir: Path) -> tuple[list[str], int, int]:
    """Read USER_EXPLICIT prompts from transcript.jsonl files under brain_dir."""
    if not brain_dir.is_dir():
        return [], 0, 0

    prompts: list[str] = []
    transcripts_scanned = 0
    skipped_lines = 0

    for tf in sorted(brain_dir.rglob("transcript.jsonl")):
        transcripts_scanned += 1
        try:
            text = tf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            skipped_lines += 1
            continue
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                skipped_lines += 1
                continue
            if not isinstance(obj, dict):
                continue
            if obj.get("type") == "USER_INPUT" and obj.get("source") == "USER_EXPLICIT":
                content = obj.get("content")
                if isinstance(content, str):
                    cleaned = _clean_prompt(content)
                    if cleaned:
                        prompts.append(cleaned)
    return prompts, transcripts_scanned, skipped_lines


def evaluate_router(brain_dir: Path, *, noisy_threshold: float = 0.05) -> dict[str, Any]:
    """Replay operator_router across transcripts and return aggregate metrics without printing prompt text."""
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import operator_router

    prompts, transcripts_scanned, skipped_lines = collect_prompts(brain_dir)
    instruction_to_id = {instruction: signal_id for signal_id, _, instruction in operator_router.SIGNAL_RULES}
    per_rule_hits: dict[str, int] = {signal_id: 0 for signal_id, _, _ in operator_router.SIGNAL_RULES}

    fired_prompts = 0
    t0 = time.perf_counter()
    for prompt in prompts:
        nudges = operator_router.detect_prompt_signals(prompt)
        if nudges:
            fired_prompts += 1
            for nudge in nudges:
                sig_id = instruction_to_id.get(nudge)
                if sig_id is not None:
                    per_rule_hits[sig_id] += 1
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    total = len(prompts)
    abstained = total - fired_prompts
    fire_rate = round(fired_prompts / total, 4) if total > 0 else 0.0
    abstention_rate = round(abstained / total, 4) if total > 0 else 0.0

    noisy_rules = (
        [sid for sid, hits in per_rule_hits.items() if hits / total > noisy_threshold]
        if total > 0
        else []
    )
    zero_hit_rules = [sid for sid, hits in per_rule_hits.items() if hits == 0]

    return {
        "brain_dir": str(brain_dir),
        "transcripts_scanned": transcripts_scanned,
        "total_prompts": total,
        "skipped_lines": skipped_lines,
        "fired_prompts": fired_prompts,
        "abstained_prompts": abstained,
        "fire_rate": fire_rate,
        "abstention_rate": abstention_rate,
        "elapsed_ms": round(elapsed_ms, 2),
        "per_rule_hits": per_rule_hits,
        "noisy_rules": noisy_rules,
        "zero_hit_rules": zero_hit_rules,
    }


def _format_text(report: dict[str, Any]) -> str:
    lines = [
        f"Router Replay: {report['total_prompts']} prompts across {report['transcripts_scanned']} transcript(s) in {report['elapsed_ms']}ms",
        (
            f"Fired: {report['fired_prompts']} ({report['fire_rate'] * 100:.2f}%) | "
            f"Abstained: {report['abstained_prompts']} ({report['abstention_rate'] * 100:.2f}%) | "
            f"Skipped lines: {report['skipped_lines']}"
        ),
        "Per-rule hits:",
    ]
    for sid, hits in report["per_rule_hits"].items():
        lines.append(f"  - {sid:22s}: {hits}")
    lines.append(f"Noisy rules: {report['noisy_rules']}")
    lines.append(f"Zero-hit rules: {report['zero_hit_rules']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate operator_router signal precision/abstention in RAM.")
    parser.add_argument(
        "--brain-dir",
        type=Path,
        default=Path.home() / ".gemini" / "antigravity" / "brain",
        help="Root directory holding session transcript.jsonl files.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON metrics.")
    parser.add_argument(
        "--noisy-threshold",
        type=float,
        default=0.05,
        help="Flag rules exceeding this fraction of total prompts as noisy.",
    )
    args = parser.parse_args(argv)
    report = evaluate_router(args.brain_dir.resolve(), noisy_threshold=args.noisy_threshold)
    print(json.dumps(report, indent=2) if args.json else _format_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
