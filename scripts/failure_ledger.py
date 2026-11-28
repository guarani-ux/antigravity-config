"""Cross-session Failure Ledger for antigravity-config.

Records root-cause lessons (e.g. 3-Strike Governor locks, OS-specific traps,
or recurring test/contract failures) into ~/.gemini/memory/failure-ledger.jsonl
so the machine surfaces relevant past lessons at SessionStart instead of
repeating the same mistake across repos.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_FILENAME = "failure-ledger.jsonl"
MAX_LEDGER_BYTES = 512 * 1024  # Cap at 512 KB


def default_ledger_path() -> Path:
    override = os.environ.get("ANTIGRAVITY_FAILURE_LEDGER_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".gemini" / "memory" / LEDGER_FILENAME


def record_failure_lesson(
    pattern: str,
    root_cause: str,
    fix: str,
    *,
    scope: str = "global",
    source: str = "manual",
    path_override: Path | None = None,
) -> bool:
    """Append a concise, deduplicated failure lesson to the ledger."""
    pat_clean = " ".join(pattern.split())[:160]
    cause_clean = " ".join(root_cause.split())[:240]
    fix_clean = " ".join(fix.split())[:240]
    if not pat_clean or not cause_clean:
        return False

    try:
        target = path_override if path_override is not None else default_ledger_path()
        # Avoid duplicate consecutive/identical pattern entries
        if target.is_file():
            for ln in target.read_text(encoding="utf-8", errors="replace").splitlines()[-50:]:
                try:
                    obj = json.loads(ln)
                    if isinstance(obj, dict) and obj.get("pattern") == pat_clean and obj.get("scope") == scope:
                        return False
                except ValueError:
                    continue
            if target.stat().st_size >= MAX_LEDGER_BYTES:
                lines = target.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
                target.write_text("\n".join(lines) + "\n", encoding="utf-8")

        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scope": scope[:64],
            "source": source[:32],
            "pattern": pat_clean,
            "root_cause": cause_clean,
            "fix": fix_clean,
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(entry, separators=(",", ":"), ensure_ascii=True) + "\n")
        return True
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"failure_ledger write error: {type(exc).__name__}", file=sys.stderr)
        return False


def load_recent_lessons(
    *,
    scope: str | None = None,
    limit: int = 5,
    path_override: Path | None = None,
) -> list[dict[str, Any]]:
    """Return up to `limit` most recent lessons matching `scope` (or global)."""
    try:
        target = path_override if path_override is not None else default_ledger_path()
    except (OSError, RuntimeError, ValueError):
        return []
    if not target.is_file():
        return []

    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
    except OSError:
        return []

    matches: list[dict[str, Any]] = []
    for ln in reversed(lines):
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(obj, dict) or not obj.get("pattern"):
            continue
        entry_scope = str(obj.get("scope") or "global")
        if scope and entry_scope not in ("global", scope):
            continue
        matches.append(obj)
        if len(matches) >= limit:
            break
    matches.reverse()
    return matches


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cross-Session Failure Ledger CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Record a new failure lesson")
    p_add.add_argument("--pattern", required=True)
    p_add.add_argument("--cause", required=True)
    p_add.add_argument("--fix", default="")
    p_add.add_argument("--scope", default="global")

    p_list = sub.add_parser("list", help="List recent failure lessons")
    p_list.add_argument("--scope", default=None)
    p_list.add_argument("--limit", type=int, default=5)
    p_list.add_argument("--json", action="store_true", dest="as_json")

    args = p.parse_args(argv)
    if args.cmd == "add":
        ok = record_failure_lesson(args.pattern, args.cause, args.fix, scope=args.scope, source="cli")
        print(json.dumps({"recorded": ok}))
        return 0
    lessons = load_recent_lessons(scope=args.scope, limit=args.limit)
    if args.as_json:
        print(json.dumps(lessons, indent=2))
    else:
        for item in lessons:
            print(f"[{item.get('scope', 'global')}] {item.get('pattern')} -> {item.get('fix') or item.get('root_cause')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
