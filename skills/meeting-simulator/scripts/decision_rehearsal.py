#!/usr/bin/env python3
"""Deterministic checker for Meeting Simulator decision traces.

Enforces role order, current-state handoff, and explicit blockers without deciding merits.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

VALID_ACTIONS = {"revise", "retain", "hold"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_prepare(plan_path: Path, out_path: Path) -> int:
    base = _load_json(plan_path)
    roles = base.get("roles") or []
    role_map = {r["name"]: r for r in roles if isinstance(r, dict) and "name" in r}
    plans: dict[str, Any] = {
        "base": {
            "id": "base",
            "issue": base.get("issue", ""),
            "starting_proposal": base.get("starting_proposal", ""),
            "evidence": base.get("evidence", []),
            "roles": roles,
        }
    }
    for var in base.get("variants") or []:
        vid = str(var.get("id") or "")
        if not vid:
            continue
        order = var.get("role_order") or [r["name"] for r in roles]
        plans[vid] = {
            "id": vid,
            "issue": var.get("issue", base.get("issue", "")),
            "starting_proposal": var.get("starting_proposal", base.get("starting_proposal", "")),
            "evidence": var.get("evidence", base.get("evidence", [])),
            "roles": [role_map[name] for name in order if name in role_map],
        }
    out_path.write_text(json.dumps({"plans": plans}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"prepared": len(plans), "output": str(out_path)}))
    return 0


def validate_run(run: dict[str, Any], plan: dict[str, Any] | None) -> tuple[bool, list[str]]:
    errors: list[str] = []
    steps = run.get("steps")
    if not isinstance(steps, list) or not steps:
        return False, ["run.steps must be a non-empty list"]

    expected_roles = [r["name"] for r in (plan.get("roles") or [])] if plan else None
    if expected_roles is not None and len(steps) != len(expected_roles):
        errors.append(f"expected {len(expected_roles)} steps matching roles {expected_roles}, got {len(steps)}")

    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"step[{idx}] must be an object")
            continue
        role = step.get("role")
        if expected_roles is not None and idx < len(expected_roles) and role != expected_roles[idx]:
            errors.append(f"step[{idx}] role '{role}' != expected '{expected_roles[idx]}'")
        action = step.get("action")
        if action not in VALID_ACTIONS:
            errors.append(f"step[{idx}] invalid action '{action}' (expected revise|retain|hold)")
        proposal = step.get("proposal")
        if not isinstance(proposal, str) or not proposal.strip():
            errors.append(f"step[{idx}] missing non-empty proposal")
        blockers = step.get("blockers")
        if action == "hold" and (not isinstance(blockers, list) or not any(str(b).strip() for b in blockers)):
            errors.append(f"step[{idx}] action 'hold' requires at least one explicit blocker")

    return len(errors) == 0, errors


def cmd_batch(traces_path: Path, prepared_path: Path | None) -> int:
    traces_data = _load_json(traces_path)
    runs = traces_data.get("runs") if isinstance(traces_data, dict) else traces_data
    if not isinstance(runs, list):
        print(json.dumps({"error": "traces.json must contain a 'runs' list"}))
        return 1

    plans: dict[str, Any] = {}
    if prepared_path is not None:
        prep = _load_json(prepared_path)
        plans = prep.get("plans") or {}

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for idx, run in enumerate(runs):
        plan_id = str(run.get("plan_id") or "base") if isinstance(run, dict) else "base"
        plan = plans.get(plan_id) if plans else None
        if plans and plan is None:
            rejected.append({"run_index": idx, "plan_id": plan_id, "errors": [f"unknown plan_id '{plan_id}'"]})
            continue
        ok, errs = validate_run(run, plan)
        if ok:
            last = run["steps"][-1]
            accepted.append({
                "run_index": idx,
                "plan_id": plan_id,
                "final_action": last["action"],
                "final_proposal": last["proposal"],
                "open_objections": last.get("open_objections", []),
                "blockers": last.get("blockers", []),
            })
        else:
            rejected.append({"run_index": idx, "plan_id": plan_id, "errors": errs})

    print(json.dumps({"accepted": accepted, "rejected": rejected}, indent=2))
    return 0 if not rejected else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Meeting Simulator decision trace checker")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prep = sub.add_parser("prepare", help="Expand base plan + variants into plans.json")
    p_prep.add_argument("plan", type=Path)
    p_prep.add_argument("-o", "--output", type=Path, default=Path("plans.json"))

    p_batch = sub.add_parser("batch", help="Validate meeting traces against prepared or ad hoc plans")
    p_batch.add_argument("traces", type=Path)
    p_batch.add_argument("--prepared", type=Path, default=None)

    args = parser.parse_args(argv)
    if args.cmd == "prepare":
        return cmd_prepare(args.plan, args.output)
    return cmd_batch(args.traces, args.prepared)


if __name__ == "__main__":
    raise SystemExit(main())
