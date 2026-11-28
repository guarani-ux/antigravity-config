---
name: potential-unleashed
description: Unified engineering, debugging, and verification loop. Transforms systems at the real seam instead of patching, proves changes through the real user doorway, and blind-tests non-trivial work before handoff.
---
# Potential Unleashed

Own the outcome, not just the literal words. Skip for pure Q&A or quick copy edits.

1. **Outcome & seam before code:** Restate the real outcome you are making possible. Inspect the live system and probe real environment inputs/payloads before assuming how they work. Before adding files or layers, compare the quick patch against reshaping, combining, or deleting what already exists; recommend the stronger move plainly when it beats a band-aid.
2. **Thin real slice first:** Never write specs, docs, or mocks for machinery that does not exist yet. Build the smallest real end-to-end path on actual inputs, then thicken only what earns its place. Strip bloat losslessly without dropping invariants or contracts.
3. **Red before green (through the real doorway):**
   - *Bugs & regressions:* Redact secrets from logs first. Build one fast failing command that reproduces the exact symptom, minimize it, test ranked falsifiable hypotheses one variable at a time, and lock the fix at the real call-site seam.
   - *Builds & refactors:* Write or run a check through the actual entrypoint the user touches (CLI, hook stdin/stdout, generated file, UI) and confirm it fails before the change — or break your own change once to prove the test bites.
4. **Test what actually breaks (never easy happy-path only):**
   - Exercise **real messy input** (realistic domain data, whitespace, unicode, edge values), **real boundaries/seams** (no mocking away the integration boundary), **the absent case** (empty/missing input or 0 items must refuse loudly as `UNKNOWN`/`BLOCKED`, never `PASS` or guess filler), and **existing neighbors** (run the full relevant suite *after the final edit*).
   - For prompts/skills/workflows, run a fresh isolated trial on a real sample or label `Live trial: Not executed`. Label any skipped layer `Not executed: [reason]`.
5. **Blind breaker on structural work:** Isolated single-file fixes (with no schema, interface, skill, or cross-file contract impact) skip Step 5 and proceed to Step 6. On schemas, interfaces, cross-file contracts, skills, or >1 module, send the user goal and the files on disk (with **zero** author history or excuses) to **1 fresh read-only subagent** whose job is to run and break the work (`file:line` + `High`/`Medium`/`Low` + `Cut or Fix`). Fix valid `High` issues (max 2 fix-and-retest retries, then escalate) and re-run checks. If subagents are unavailable, re-read from disk yourself and label `Single-agent fallback`.
6. **Consolidate & rank honestly:** Delete displaced code, rules, or dead files once coverage is proven (confirm every remaining module is reachable from a real entrypoint). Report only observed post-edit commands, pass/fail/skip counts, and what remains unverified; never claim a capability works above what was actually executed.
