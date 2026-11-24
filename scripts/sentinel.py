#!/usr/bin/env python3
"""CLI entrypoint for Sentinel lifecycle hooks (PreToolUse, PostToolUse, Stop)."""

from __future__ import annotations

import json
import sys

from sentinel import post, pre, stop


def _emit(data: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1 or args[0] not in ("pre", "post", "stop"):
        _emit({"decision": "force_ask", "reason": "Invalid sentinel hook invocation."})
        return 0
    mode = args[0]
    try:
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")
        handler = {"pre": pre, "post": post, "stop": stop}[mode]
        _emit(handler(payload))
    except Exception as exc:
        if mode == "pre":
            _emit({"decision": "force_ask", "reason": "Sentinel could not inspect operation."})
        elif mode == "stop":
            _emit({"decision": "allow"})
        else:
            _emit({})
        print(f"sentinel error: {type(exc).__name__}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
