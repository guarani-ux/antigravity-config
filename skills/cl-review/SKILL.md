---
name: cl-review
description: "Cover letter 2-axis parallel review: spawn 2 sub-agents to audit cover-letter.md along Hiring Manager 20-Second Scan & Slop (Axis 1) and JD Mandate & Proof Custody (Axis 2), then run export_cover_letter.py."
---

# Cover Letter 2-Axis Parallel Review (`/cl-review`)

A single self-grading LLM pass suffers from confirmation bias: a letter can sound smooth while subtly inflating a metric, or satisfy every JD keyword while reading like unmistakable ChatGPT slop. `/cl-review` spawns **2 independent sub-agents in parallel** along orthogonal axes, followed by mechanical custody verification via `export_cover_letter.py`.

## Table of Contents

- [1. Spawn 2 Parallel Review Sub-Agents](#1-spawn-2-parallel-review-sub-agents)
- [2. Run Mechanical Custody Verifier (`export_cover_letter.py`)](#2-run-mechanical-custody-verifier-export_cover_letterpy)
- [3. Report Side-by-Side Verdict & Enqueue Approval](#3-report-side-by-side-verdict--enqueue-approval)

---

## 1. Spawn 2 Parallel Review Sub-Agents

Pass both sub-agents `cover-letter.md`, `jd-xray.md`, `vault/career-quarry.md`, and `vault/voice-profile.md`:

- **Sub-Agent 1 — Axis 1: Hiring Manager 20-Second Scan & Slop Detector**:
  1. **3-Second Bounce Test**: Could Sentence 1 be sent to a competitor by swapping the company name? Does it open with flattery or throat-clearing?
  2. **12 LLM Smells Audit**: Scan every line against the 12 smells in [`SMELLS-AND-REGIMES.md`](../cl-craft/SMELLS-AND-REGIMES.md) (triads, participial openers, empty intensifiers, resume-bullet echoing, passive voice).
  3. **Cadence & Word Budget Check**: Verify word count against the active Selection Regime (`250–320w` for Mandate Mode; `400–550w` for Institutional Rubric Mode) and check alignment with `vault/voice-profile.md`.
  - *Return*: `Axis 1 Verdict: PASS | NEEDS_REVISION` + exact line-level rewrites for any smell found.

- **Sub-Agent 2 — Axis 2: JD Mandate & Zero-Fabrication Custody Auditor**:
  1. **Citation Coverage**: Does every paragraph carry a valid `<!-- ref: STORY-... -->` or `<!-- ref: PHIL-... -->` tag?
  2. **Metric & Scope Fidelity**: Does every number, tool, and responsibility in `cover-letter.md` match `vault/career-quarry.md` without rounding, inflation, or violating `SCOPE-NEG-*` boundaries?
  3. **Mandate & Anxiety Resolution**: Does the letter directly answer the `Layer 2 Hidden 90-Day Mandate` and disarm the `Layer 3 Screener Anxiety` from `jd-xray.md`?
  - *Return*: `Axis 2 Verdict: PASS | CUSTODY_FAIL` + exact discrepancy citations.

---

## 2. Run Mechanical Custody Verifier (`export_cover_letter.py`)

Execute the standard-library custody verifier and print exporter:

```bash
python domains/professional/scripts/export_cover_letter.py --draft <path/to/cover-letter.md> --quarry vault/career-quarry.md --name "<Candidate Name>" --company "<Company Name>" --role "<Role Title>"
```

---

## 3. Report Side-by-Side Verdict & Enqueue Approval

Present both sub-agent verdicts and the mechanical verifier receipt side by side. Neither axis can mask a failure in the other.

Once both axes and `export_cover_letter.py` pass:
- Offer to enqueue the verified application package in `vault/approvals.md` (`TIER-A`) via [`/cos-approve`](../../../skills/cos-approve/SKILL.md).
