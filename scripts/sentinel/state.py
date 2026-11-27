"""O(1) per-session Finite State Machine persistence for Sentinel lifecycle hooks."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STATE_FILENAME = "sentinel-state.json"


@dataclass
class SentinelState:
    oriented: bool = False
    repair_strikes: int = 0
    consecutive_tool_errors: int = 0
    unverified_code_edits: bool = False
    edited_code_files: list[str] = field(default_factory=list)
    edited_domain_dirs: list[str] = field(default_factory=list)


def state_path(payload: dict[str, Any]) -> Path | None:
    art_dir = payload.get("artifactDirectoryPath")
    if isinstance(art_dir, str) and art_dir.strip():
        return Path(art_dir.strip()) / STATE_FILENAME
    tpath = payload.get("transcriptPath")
    if isinstance(tpath, str) and tpath.strip():
        return Path(tpath.strip()).resolve().parent / STATE_FILENAME
    return None


def load_state(payload: dict[str, Any]) -> SentinelState:
    sp = state_path(payload)
    if sp is None or not sp.is_file():
        return SentinelState()
    try:
        raw = json.loads(sp.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return SentinelState()
        return SentinelState(
            oriented=bool(raw.get("oriented", False)),
            repair_strikes=int(raw.get("repair_strikes", 0)),
            consecutive_tool_errors=int(raw.get("consecutive_tool_errors", 0)),
            unverified_code_edits=bool(raw.get("unverified_code_edits", False)),
            edited_code_files=[str(x) for x in (raw.get("edited_code_files") or []) if isinstance(x, str)],
            edited_domain_dirs=[str(x) for x in (raw.get("edited_domain_dirs") or []) if isinstance(x, str)],
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"sentinel state load error: {type(exc).__name__}", file=sys.stderr)
        return SentinelState()


def save_state(payload: dict[str, Any], state: SentinelState) -> None:
    sp = state_path(payload)
    if sp is None:
        return
    tmp = sp.with_name(f".{sp.name}.{os.getpid()}.tmp")
    try:
        sp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(asdict(state), ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, sp)
    except OSError as exc:
        print(f"sentinel state save error: {type(exc).__name__}", file=sys.stderr)
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
