---
name: potential-unleashed
description: Unified engineering, probing, debugging, and load-bearing verification discipline. Deconstructs exploratory probes before coding, checks domain invariants, verifies real runtime integration, and runs one unified blind verification pass on structural changes.
---
# Potential Unleashed (2.0)

Own the real outcome, not the literal surface ask. Skip for pure Q&A or quick copy edits.

1. **Deconstruct the probe & domain invariants before code:**
   - When the user proposes a fix, rule, or mechanism while exploring a problem, treat it as a **probe**, not an immediate build ticket. Stay in zero-mutation Sense-Making mode until the root condition is clear and tested against real CS/domain knowledge.
   - Before touching existing code, inspect the live system, list the 3–5 non-negotiable **domain invariants**, and separate distinct states at the seam (missing vs. empty vs. corrupt vs. conflicting). Compare patching against reshaping, combining, or deleting existing machinery — recommend subtraction when it beats addition.
2. **Thin real slice first:** Never build speculative scaffolding, mocks, or layers for unverified needs. Build the smallest real end-to-end path on actual inputs, then thicken only what earns its place. Strip bloat losslessly and explicitly name anything cut.
3. **Red before green & causal reconsideration:**
   - *Bugs & regressions:* Redact secrets first. Reproduce the exact symptom with one fast failing command, isolate variables one at a time, and lock the fix at the real call-site seam.
   - *Builds & refactors:* Confirm a check through the actual user doorway (CLI, hook stdin/stdout, runtime interface) fails before the change — or break your own change once to prove the test bites.
   - *Causal reconsideration:* When an expected effect fails or a defect survives verification, reconsider the representation, causal model, or verification method — never repeat local patching.
4. **Load-bearing runtime verification (passing tests != proof):**
   - Exercise **real messy input**, **real integration seams** (never mock away the thing being proven), **absent/corrupt cases** (refuse loudly as `UNKNOWN`/`BLOCKED`, never `PASS` or silent reset), and **full relevant neighbor suites** *after the final edit*.
   - **After tests pass, audit what they actually proved:** Explicitly check (a) which changed code paths and runtime integrations actually executed, (b) whether the passing tests are genuinely load-bearing for the original intention (not just old assertions staying green), and (c) whether actions converged toward the goal. For prompts/skills/workflows, run a fresh isolated trial or label `Live trial: Not executed`. Label any skipped layer `Not executed: [reason]`.
5. **One unified blind verification pass on structural work:** Isolated single-file fixes (no schema, interface, skill, or cross-file contract impact) skip Step 5. On structural changes, run **1 fresh read-only reviewer** (zero author history/excuses; never spawn fragmented multi-agent swarms) auditing CS flaws, intent alignment, runtime integration, edge-case falsification, and test sensitivity (`file:line` + `High`/`Medium`/`Low` + `Cut or Fix`). Fix valid `High` issues (max 2 fix-and-retest retries, then escalate) and re-run checks. If subagents are unavailable, re-read from disk yourself and label `Single-agent fallback`.
6. **Consolidate, subtract & terminate honestly:** Delete displaced code, rules, or dead files once coverage is proven. If a durable cross-domain lesson emerged, fold it into the budgeted Cognitive Core (`core/`) and prune stale entries. Report only post-final-edit receipts and close with an explicit status (`DELIVERED`, `EXPLORATORY`, `PARTIAL`, or `BLOCKED`).
