---
name: waterwall
description: Lean, integrated discipline for building, refactoring, or shipping code, prompts, and technical workflows. Skip for pure Q&A, brainstorming, or quick drafts.
---
# Waterwall

Verification is built into how work is made, not bolted on afterward. Skip for pure Q&A, brainstorming, or quick drafts.

1. **Protect boundaries:** Always ask before external state-mutating, externally visible, or destructive actions (read-only lookups need no approval). No speculative files, bloat, or silent refactors.
2. **Lossless compression:** When compressing code, skills, or prompts, strip bloat and ceremony without silently dropping invariants, edge cases, or contracts. Explicitly name anything intentionally cut.
3. **Shape non-trivial builds:** Skip upfront ceremony on isolated single-file fixes. Before non-trivial builds, identify in 3-5 concise bullets (internally, or in chat if ambiguous/high-rework): real outcome, load-bearing parts, 1-2 messy test cases, and what gets replaced/cut (add deterministic-code vs. LLM-judgment split only for AI workflows).
4. **Prove against reality (fresh, no theater):**
   - Test every touched layer as you work: unit edge cases, system seams/contracts, and messy end-to-end inputs (use staging/dry-run if live runs mutate external state).
   - Run the existing relevant test suite (not just new checks) **after the final edit** and cite actual command + observed pass/fail/skip counts.
   - For prompts/workflows, run the artifact in a fresh isolated session/subagent on a real sample and report observed failures, or label `Live trial: Not executed` (self-simulation is not proof).
   - Label any skipped or unsafe layer `Not executed: [reason]`. Distinguish real artifacts from constructed adversarial tests.
5. **Reset context only on structural changes:**
   - *Isolated single-file fixes:* Steps 1-4 are enough. No subagents.
   - *Changes to schemas, public interfaces, cross-file contracts, prompts/skills, or >1 module:* Run **1 fresh read-only review pass** (subagent must not edit files, invoke Waterwall, or spawn subagents). Pass the user goal, diff/artifact, and git-diff/relevant test & caller paths, with zero author rationalizations. Audit CS flaws, runtime traps, test gaps, and outcome friction using `file:line` (or `section/quote`) + `High`/`Medium`/`Low` (`High` = breaks correctness, runtime safety, or core outcome) + `Cut or Fix`. Fix valid `High` issues (max **2 local fix-and-retest retries after Pass 1**, then escalate); reject false-positive `High` only with direct contradicting evidence in the final handoff; log unresolved `Medium`/`Low` as tradeoffs/skips.
   - *Second pass (only if user explicitly asks or on irreversible bets):* Run sequentially after Pass 1 fixes, passing the updated artifact, disputed Pass 1 claims, and direct contradicting evidence only.
   - *No-subagent fallback:* Re-read saved files from disk, run the 4-area check yourself, and label `Single-agent fallback (no fresh context reset)`.
6. **Final handoff (Meta Gate):** Return plainly: (a) the artifact/change, (b) fresh executed evidence (or `Not executed` labels), and (c) open tradeoffs, direction choices, unresolved findings, rejected `High` claims, or fallback flags (omit if none).
