---
name: meeting-simulator
description: Carry one live decision through a room of roles sequentially, enforcing order, current-state handoff, and explicit blockers with Python verification.
---

# Meeting Simulator

Carry one live decision through the room. Each role receives the latest accepted proposal, open objections, and evidence. The model reasons from that role's supplied responsibilities and priorities, then may revise, retain, or hold the proposal. Python enforces order, current-state handoff, and explicit blockers; it does not decide the merits.

1. Turn the request and authorized evidence into a plan. Preserve the issue, role order, priorities, authority, and any conditions being varied. Mark assumptions. For multiple runs, define one base plan plus variants and use the `prepare` command. See [plan and batch format](references/decision-plan.md).
2. Default to **one launch for the requested batch**. In one model pass per manageable chunk, produce a complete trace per meeting, with each role taking the immediately preceding proposal and open issues as its starting point. Do not stop for Python or user input between roles. For large batches, split into independent chunks where host context or time requires it; run chunks concurrently when available. Never silently replace fresh reasoning with copies of the same trace.
3. Run [the Python checker](scripts/decision_rehearsal.py) on the combined traces: `python3 <script> batch <traces.json> --prepared <plans.json>` (omit the flag for an ad hoc single plan). Read accepted results and rejected-run errors; fix only invalid runs. Do not treat a rejected trace as a meeting outcome or an unresolved accepted trace as a software failure. No terminal-only LLM inference is bundled: this skill supplies the model pass and Python verifies its decision record.
4. Report what changed, which constraint mattered, what stayed open, and the next step. Do not produce dialogue or actual approvals. When comparing orders, hold evidence, issue, starting proposal and participants fixed unless the user asks to vary them. Do not call a difference proof that order alone caused it.

Use the slower `init / next / apply / report` path only for requested audit/debugging or when independent contexts per role are essential. It requires no pauses for user decisions unless the user reserved one.
Use the original score-and-schedule simulator only when the user specifically asks for a rule-based comparison. This skill's normal path is sequential LLM reasoning, with no model API or keys required by the Python runner.
