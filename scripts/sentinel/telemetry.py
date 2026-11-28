"""Privacy-safe local JSONL flight recorder for Antigravity hooks.

Records only hook name, tool/rule metadata, decision, rule tag, and latency_ms.
Never records file contents, shell command arguments, secrets, or user prompt text.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TELEMETRY_FILENAME = "hook-events.jsonl"
MAX_LOG_BYTES = 2 * 1024 * 1024  # Rotate at 2 MB
TAIL_READ_BYTES = 256 * 1024  # Read at most last 256 KB when summarizing

_TAG_PATTERNS: tuple[tuple[re.Pattern[str], str | None], ...] = (
    (re.compile(r"\b((?:RW|TQ)-\d{2}|FM-H\d{2})\b"), None),
    (re.compile(r"\b(Orient-Before-Edit|Verify-Before-Stop|3-Strike Governor|Unresolved Obligations|State Integrity)\b"), None),
    (re.compile(r"Sentinel could not inspect", re.IGNORECASE), "Sentinel-Error"),
    (re.compile(r"Invalid sentinel hook", re.IGNORECASE), "Invalid-Invocation"),
    (re.compile(r"Catastrophic destructive", re.IGNORECASE), "Catastrophic-Shell"),
    (re.compile(r"Tier-1/Tier-2", re.IGNORECASE), "Tier-1-2-Shell"),
    (re.compile(r"Tier 2 MCP", re.IGNORECASE), "Tier-2-MCP"),
    (re.compile(r"External acceptance", re.IGNORECASE), "Acceptance-Lock"),
    (re.compile(r"Outcome custody", re.IGNORECASE), "Custody-Check"),
    (re.compile(r"Lazy placeholder", re.IGNORECASE), "Lazy-Placeholder"),
    (re.compile(r"Exact no-op", re.IGNORECASE), "No-Op-Edit"),
    (re.compile(r"Broad deletion", re.IGNORECASE), "Broad-Deletion"),
    (re.compile(r"Could not inspect write|Could not inspect edit|Cannot inspect tool arguments", re.IGNORECASE), "Uninspectable-Args"),
    (re.compile(r"outside (?:the |mounted )?workspace", re.IGNORECASE), "Outside-Workspace"),
    (re.compile(r"Cannot verify command text", re.IGNORECASE), "Uninspectable-Command"),
    (re.compile(r"Empty file write blocked", re.IGNORECASE), "Empty-Write"),
    (re.compile(r"Last three tools failed", re.IGNORECASE), "Consecutive-Errors"),
)


def is_telemetry_disabled() -> bool:
    return os.environ.get("ANTIGRAVITY_TELEMETRY_DISABLED", "").strip().lower() in ("1", "true", "yes")


def default_telemetry_path() -> Path:
    override = os.environ.get("ANTIGRAVITY_TELEMETRY_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".gemini" / "telemetry" / TELEMETRY_FILENAME


def extract_rule_tag(reason: str) -> str:
    if not reason:
        return ""
    for pat, fixed in _TAG_PATTERNS:
        m = pat.search(reason)
        if m:
            return fixed if fixed is not None else m.group(1)
    return ""


def _rotate_if_oversized(target: Path) -> None:
    try:
        if target.is_file() and target.stat().st_size >= MAX_LOG_BYTES:
            backup = target.with_suffix(".jsonl.1")
            os.replace(target, backup)
    except OSError:
        pass


def record_hook_event(
    hook: str,
    tool: str,
    decision: str,
    tag: str,
    latency_ms: float,
    *,
    path_override: Path | None = None,
) -> None:
    if is_telemetry_disabled():
        return
    try:
        target = path_override if path_override is not None else default_telemetry_path()
        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "hook": hook[:32],
            "tool": tool[:64],
            "decision": decision[:32],
            "tag": tag[:64],
            "latency_ms": round(max(0.0, latency_ms), 2),
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_oversized(target)
        with target.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(entry, separators=(",", ":"), ensure_ascii=True) + "\n")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"sentinel telemetry write error: {type(exc).__name__}", file=sys.stderr)


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = max(0, min(len(sorted_vals) - 1, math.ceil(pct * len(sorted_vals)) - 1))
    return round(sorted_vals[idx], 2)


def _read_tail_lines(target: Path, limit_lines: int) -> list[str]:
    try:
        size = target.stat().st_size
        with target.open("rb") as fh:
            if size > TAIL_READ_BYTES:
                fh.seek(size - TAIL_READ_BYTES)
                raw = fh.read()
                # Drop potentially partial first line after mid-file seek
                nl = raw.find(b"\n")
                if nl >= 0:
                    raw = raw[nl + 1 :]
            else:
                raw = fh.read()
        return raw.decode("utf-8", errors="replace").splitlines()[-limit_lines:]
    except OSError:
        return []


def summarize_telemetry(path: Path | None = None, *, limit_lines: int = 2000) -> dict[str, Any]:
    try:
        target = path if path is not None else default_telemetry_path()
    except (OSError, RuntimeError, ValueError):
        return {
            "path": "",
            "exists": False,
            "events": 0,
            "decisions": {},
            "top_blocks": [],
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "by_hook": {},
        }
    if not target.is_file():
        return {
            "path": str(target),
            "exists": False,
            "events": 0,
            "decisions": {},
            "top_blocks": [],
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "by_hook": {},
        }

    lines = _read_tail_lines(target, limit_lines)
    decisions: Counter[str] = Counter()
    block_tags: Counter[str] = Counter()
    latencies: list[float] = []
    hook_latencies: dict[str, list[float]] = defaultdict(list)
    valid = 0
    corrupt = 0

    for ln in lines:
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except ValueError:
            corrupt += 1
            continue
        if not isinstance(obj, dict):
            corrupt += 1
            continue
        valid += 1
        dec = str(obj.get("decision") or "unknown")
        decisions[dec] += 1
        tag = str(obj.get("tag") or "")
        if dec in ("deny", "ask", "force_ask", "continue"):
            block_tags[tag or "Untagged"] += 1
        lat = obj.get("latency_ms")
        if isinstance(lat, (int, float)) and not isinstance(lat, bool):
            f_lat = float(lat)
            latencies.append(f_lat)
            hk = str(obj.get("hook") or "unknown")
            hook_latencies[hk].append(f_lat)

    latencies.sort()
    by_hook: dict[str, dict[str, Any]] = {}
    for hk, vals in sorted(hook_latencies.items()):
        vals.sort()
        by_hook[hk] = {
            "events": len(vals),
            "p50_ms": _percentile(vals, 0.50),
            "p95_ms": _percentile(vals, 0.95),
        }

    return {
        "path": str(target),
        "exists": True,
        "events": valid,
        "corrupt_lines": corrupt,
        "decisions": dict(decisions),
        "top_blocks": [{"tag": k, "count": v} for k, v in block_tags.most_common(5)],
        "p50_ms": _percentile(latencies, 0.50),
        "p95_ms": _percentile(latencies, 0.95),
        "by_hook": by_hook,
    }
