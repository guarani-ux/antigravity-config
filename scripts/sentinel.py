#!/usr/bin/env python3
"""CLI entrypoint for Sentinel lifecycle hooks (PreToolUse, PostToolUse, Stop)."""

from __future__ import annotations

import json
import sys
import time

from sentinel import extract_rule_tag, is_subagent, post, pre, record_hook_event, stop


def _emit(data: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=True) + "\n")


def _safe_record(hook: str, tool: str, decision: str, tag: str, latency_ms: float) -> None:
    try:
        record_hook_event(hook, tool, decision, tag, latency_ms)
    except Exception as exc:
        print(f"sentinel telemetry error: {type(exc).__name__}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    t0 = time.perf_counter()
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1 or args[0] not in ("pre", "post", "stop"):
        out: dict[str, object] = {"decision": "force_ask", "reason": "Invalid sentinel hook invocation."}
        _emit(out)
        _safe_record("invalid", "sentinel", "force_ask", "Invalid-Invocation", (time.perf_counter() - t0) * 1000.0)
        return 0
    mode = args[0]
    payload: dict[str, object] = {}
    tool_name = ""
    out = {}
    errored = False
    try:
        raw = sys.stdin.read().strip()
        loaded = json.loads(raw) if raw else {}
        if not isinstance(loaded, dict):
            raise ValueError("Payload must be a JSON object")
        payload = loaded
        tc = payload.get("toolCall")
        if isinstance(tc, dict):
            tool_name = str(tc.get("name") or "")
        handler = {"pre": pre, "post": post, "stop": stop}[mode]
        out = handler(payload)
        _emit(out)
    except Exception as exc:
        errored = True
        if mode == "pre":
            decision = "deny" if is_subagent(payload) else "force_ask"
            out = {"decision": decision, "reason": "Sentinel could not inspect operation."}
        elif mode == "stop":
            out = {"decision": "allow"}
        else:
            out = {}
        _emit(out)
        print(f"sentinel error: {type(exc).__name__}", file=sys.stderr)

    latency_ms = (time.perf_counter() - t0) * 1000.0
    if errored:
        dec = "error"
        tag = "Sentinel-Error"
    else:
        dec = str(out.get("decision") or ("ok" if mode == "post" else "allow"))
        tag = extract_rule_tag(str(out.get("reason") or ""))
    _safe_record(mode, tool_name or mode, dec, tag, latency_ms)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
