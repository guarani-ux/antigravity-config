---
name: cl-flow
description: Router over the cover-letter-builder skill cartridge (cl-vault, cl-decode, cl-angles, cl-draft, cl-craft, cl-review, cl-retro) and its handoffs to Cognitive OS core.
disable-model-invocation: true
---

# Cover Letter Flow Router (`/cl-flow`)

Ask `/cl-flow` which skill fits your current application step. Never jump straight from a raw job description to a finished cover letter in one shot: doing so causes resume regurgitation, generic flattery, and subtle credential fabrication.

## Table of Contents

- [1. The Main Application Flow](#1-the-main-application-flow)
- [2. On-Ramps by Situation](#2-on-ramps-by-situation)
- [3. Shared Craft Layer Underneath](#3-shared-craft-layer-underneath)
- [4. Handoff to Cognitive OS Core](#4-handoff-to-cognitive-os-core)

---

## 1. The Main Application Flow

1. **[`/cl-vault`](../cl-vault/SKILL.md)** *(Persistent Career Quarry — Build Once, Grow Incrementally)*:
   Extracts your real career stories into `vault/career-quarry.md` using the **CFJOV Schema** (*Context, Friction, Judgment, Outcome, Verification*) and locks your natural cadence in `vault/voice-profile.md`.
2. **[`/cl-decode`](../cl-decode/SKILL.md)** *(3-Layer JD X-Ray)*:
   Strips a target Job Description into `Layer 1 (Table-Stakes Boilerplate)`, `Layer 2 (Hidden 90-Day Mandate)`, and `Layer 3 (Screener Anxieties)`. Detects the **Selection Regime** (`Private Mandate Mode` vs. `Institutional Rubric Mode`), checks `vault/career-quarry.md` for missing gaps, and writes `jd-xray.md`.
3. **[`/cl-angles`](../cl-angles/SKILL.md)** *(Design Positioning 3 Ways)*:
   Spawns **3 parallel sub-agents** to pitch three distinct positioning hooks, argument topologies, and story pairings from `vault/career-quarry.md`. Compares them and writes your chosen strategy to `angle.md`.
4. **[`/cl-draft`](../cl-draft/SKILL.md)** *(4-Beat Exploit with Proof Custody)*:
   Drafts `cover-letter.md` using the **4-Sentence Transduction Formula**, enforcing `vault/voice-profile.md` and attaching `<!-- ref: STORY-ID -->` custody tags to every claim.
5. **[`/cl-review`](../cl-review/SKILL.md)** *(2-Axis Parallel Sub-Agent Audit)*:
   Spawns **2 parallel sub-agents**:
   - **Hiring Manager 20-Second Scan & Slop Detector** (checks the 12 LLM Cover Letter Smells).
   - **Mandate & Proof Custody Verifier** (verifies every claim and metric against `vault/career-quarry.md` and `jd-xray.md`).
   Then runs `domains/professional/scripts/export_cover_letter.py` to output clean, print-ready HTML.
6. **[`/cl-retro`](../cl-retro/SKILL.md)** *(Close the Loop)*:
   Diffs your manual edits against the draft and updates `vault/voice-profile.md` so you never have to repeat the same stylistic correction twice.

---

## 2. On-Ramps by Situation

- **You already have `vault/career-quarry.md` populated and just found a new job posting** $\rightarrow$ Start directly at **`/cl-decode`**.
- **You already drafted or edited a letter and want a ruthless critique** $\rightarrow$ Run **`/cl-review`**.
- **You finished editing a letter and want the system to learn your edits** $\rightarrow$ Run **`/cl-retro`**.

---

## 3. Shared Craft Layer Underneath

- **[`cl-craft`](../cl-craft/SKILL.md)**: Model-invoked discipline layer enforcing the 12 Cover Letter Anti-Smells, Selection Regime rules, and the 4 Structural Topologies.

---

## 4. Handoff to Cognitive OS Core

Once a letter passes `/cl-review` and exports cleanly, enqueue the application in `vault/approvals.md` (`TIER-A`) via [`/cos-approve`](../../../skills/cos-approve/SKILL.md) and log any strategic targeting shifts in `vault/decisions.md` via [`/cos-decide`](../../../skills/cos-decide/SKILL.md).
