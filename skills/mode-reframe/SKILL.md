---
name: mode-reframe
description: Mode 1 — Reframe, Paradigm & Mobilization Modulator. Activate when the user is exploring a problem, instinct, process, or architecture before committing to execution. Zero file creation; dynamically identifies the governing discipline(s), flags missing information, compares 3 genuinely distinct paradigms with pitfalls, and issues an explicit Downstream Mobilization Directive (Engage / Suppress / Gate) with Default-Yes Frontier Grilling.
---

# Mode 1: Reframe, Paradigm & Mobilization Modulator

## 1. Trigger & Hard Invariants
- **Role**: Top-of-the-totem-pole judgment modulator sitting *above* downstream scripts, hooks, skills, and domain workflows. Never settle for the first plausible idea or jump straight into scope-sizing a single script before evaluating the problem class and paradigm space.
- **When Active**: User asks open-ended architecture or process questions, explores how to approach a problem, weighs options/trade-offs, or shares an instinct without requesting immediate code/file edits.
- **Zero File Creation**: Do NOT create or mutate workspace files, scaffolding directories, or `implementation_plan.md` artifacts during Mode 1. Read-only inspection and RAM routing queries are encouraged.

## 2. Stage 1 — Altitude & Governing Discipline (Open-Domain)
Never hardcode a closed list of domains. Dynamically infer what actually governs the outcome:
1. **Surface Ask vs. Governing Problem Class**: In 2–3 lines, separate the user's stated intent from the underlying problem class across whichever discipline(s) apply — e.g., Computer Science (static analysis, typed capability graph, map-reduce, state machine, retrieval), Executive/Document Craft (20-second reader triage, selection regime, proof custody, narrative spine), Physical/Mechanical Systems (fault isolation, tolerances, sequence of operations), Culinary/Process Craft, or a **Hybrid** where two disciplines collide.
2. **Altitude Check**: Call out explicitly if the current framing is optimizing too far downstream (e.g., micro-rules, regexes, or "spell-checking `l-o-v-e`" when the true leverage point is paradigm selection, audience triage, or system composition).

## 3. Stage 2 — Missing-Information & Epistemic Gate
Before proposing solutions, state what information is **missing, uninspected, or unavailable locally** that could materially alter the outcome:
- **Blocking Unknowns**: Facts, constraints, environmental conditions, or unseen sources that must be verified or asked before committing to an approach.
- **Non-Blocking Assumptions**: Safe, reversible defaults that allow exploration to proceed without stalling.

## 4. Stage 3 — The 3-Paradigm Matrix (Distinct Approaches, Not Just 3 Sizes)
Compare **three genuinely distinct paradigms** from the governing discipline(s) (or a hybrid synthesis) — never just Small/Medium/Large versions of the first idea:

| Paradigm / Approach | Core Mechanism & Governing Principle | Strength / What It Solves | Failure Mode, Token/Resource Trap & Mechanical Cap |
| :--- | :--- | :--- | :--- |
| **1. Paradigm A** *(e.g. Deterministic / Subtractive / Static)* | Exact mechanism in the governing discipline. | Where it wins with minimal moving parts. | Where it hits a ceiling under current tools/constraints + how to cap it. |
| **2. Paradigm B** *(e.g. Structural / Graph / Schema / Rubric)* | Exact mechanism in the governing discipline. | What higher-order relationship or guarantee it unlocks. | Where it risks rigidity or premature taxonomy + how to cap it. |
| **3. Paradigm C or Integrated Hybrid** *(Recommended Synthesis)* | How the winning primitives combine while cutting out the traps. | End-to-end leverage across both intent and discipline. | Exact boundaries (`WIP = 1` sequential vertical slices) required to keep it safe. |

*(Once the paradigm is selected, size the immediate execution entry point as **Zero-Build / Subtraction**, **Lightweight Mechanism**, or **Full System**.)*

## 5. Stage 4 — Downstream Mobilization Directive
Because `mode-reframe` modulates what runs downstream, end the architectural synthesis with an explicit 3-line mobilization contract:
- **Engage**: Which existing downstream scripts, skills, repositories, or read-only checks to mobilize (and in what order) — or state plainly if no local capability exists yet.
- **Suppress**: Which files, giant repos, noisy keyword searches, or low-altitude detours to explicitly *not* read, clone, or run (preventing token burn and drift).
- **Gate**: Which deterministic checks, test suites (`TQ-01..TQ-05`), or human receiving checks must pass before the first vertical slice is considered done.

## 6. "Default-Yes" Frontier Grilling & Handoff Gate
Resolve open architectural forks as a zero-friction decision frontier so the user can reply `"yes"` or `"go"`:
```markdown
❓ **Q1** - **<title>**: <body/options> ➡️ **Recommended: <choice>**
❓ **Q2** - **<title>**: <body/options> ➡️ **Recommended: <choice>**
```
End with the handoff prompt into execution ([mode-worktree-build](file:///C:/Users/flowe/.gemini/config/skills/mode-worktree-build/SKILL.md) or the mobilized domain skill).
