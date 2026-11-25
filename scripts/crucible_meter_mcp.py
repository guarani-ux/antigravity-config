#!/usr/bin/env python3
"""Minimal zero-dependency stdio MCP server exposing Crucible Turn Meter's `commit_intent` tool.

Because `commit_intent` is a real MCP tool call, Antigravity renders its `intent`, `middle`,
`expected_outcome`, and `targets` arguments visibly right before gated mutating tool calls.
`sentinel.py` PostToolUse intercepts the completed call and mints the wave lease in
`turn-meter-state.json` under RW-06 custody.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import crucible_meter  # noqa: E402

SERVER_INFO = {"name": "crucible-meter", "version": "2.1.0"}
PROTOCOL_VERSION = "2024-11-05"

COMMIT_INTENT_TOOL: dict[str, Any] = {
    "name": "commit_intent",
    "description": (
        "Submit a visible pre-tool planning event before a mutating tool wave (write_file, edit_file, "
        "mutating run_command, or mutating MCP). Declares intent (why), middle (mechanism/invariant), "
        "and expected_outcome (falsifiable result) to mint a wave Intent Lease."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "description": "Why this mutation wave is needed (goal or bottleneck being attacked).",
            },
            "middle": {
                "type": "string",
                "description": "Mechanism/bridge: how the edit or command changes state and what invariant it preserves.",
            },
            "expected_outcome": {
                "type": "string",
                "description": "Falsifiable observable outcome proving the wave succeeded.",
            },
            "targets": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Target file basenames/paths or tool names covered by this wave lease.",
            },
            "wave_size": {
                "type": "integer",
                "minimum": 1,
                "maximum": 12,
                "description": "Optional number of mutating tool calls covered by this wave (default: len(targets) or 5).",
            },
        },
        "required": ["intent", "middle", "expected_outcome"],
    },
}


def _reply(req_id: Any, result: dict[str, Any]) -> None:
    msg = {"jsonrpc": "2.0", "id": req_id, "result": result}
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _error(req_id: Any, code: int, message: str) -> None:
    msg = {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle_request(req: dict[str, Any]) -> None:
    req_id = req.get("id")
    method = str(req.get("method") or "")
    params = req.get("params") if isinstance(req.get("params"), dict) else {}

    if method == "initialize":
        _reply(
            req_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        )
        return
    if method == "notifications/initialized":
        return
    if method == "ping":
        _reply(req_id, {})
        return
    if method == "tools/list":
        _reply(req_id, {"tools": [COMMIT_INTENT_TOOL]})
        return
    if method == "tools/call":
        name = str(params.get("name") or "")
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if name != "commit_intent":
            _error(req_id, -32601, f"Unknown tool: {name}")
            return
        intent = str(args.get("intent") or "")
        middle = str(args.get("middle") or "")
        outcome = str(args.get("expected_outcome") or "")
        targets = args.get("targets") if isinstance(args.get("targets"), list) else []
        wave_size = args.get("wave_size")

        ok, msg = crucible_meter.validate_intent_submission(intent, middle, outcome, targets)
        if not ok:
            _reply(
                req_id,
                {
                    "isError": True,
                    "content": [{"type": "text", "text": msg}],
                },
            )
            return

        payload = {
            "status": "INTENT_COMMITTED",
            "intent": intent.strip(),
            "middle": middle.strip(),
            "expected_outcome": outcome.strip(),
            "targets": [str(t).strip() for t in targets if str(t).strip()],
            "wave_size": int(wave_size) if isinstance(wave_size, int) else (len(targets) or crucible_meter.DEFAULT_WAVE_LEASE_USES),
        }
        _reply(
            req_id,
            {
                "isError": False,
                "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            },
        )
        return

    if req_id is not None:
        _error(req_id, -32601, f"Method not found: {method}")


def main() -> int:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(req, dict):
            handle_request(req)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
