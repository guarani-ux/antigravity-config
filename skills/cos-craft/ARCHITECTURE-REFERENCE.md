# Cognitive OS Architecture Reference & Research Foundation

This document codifies the empirical research foundation behind `cognitive-os`, synthesizing findings from Personal Information Management (PIM), Personal Knowledge Management (PKM), Extended Mind theory, Cybernetics, and real-world AI Personal OS implementations.

## Table of Contents

- [1. Domain Map & Converging Disciplines](#1-domain-map--converging-disciplines)
- [2. Why File-Centric (Markdown + Git) Beats Complex Databases](#2-why-file-centric-markdown--git-beats-complex-databases)
- [3. Solving the 3 Industry-Wide Gaps](#3-solving-the-3-industry-wide-gaps)
- [4. Evaluation & Health Metrics](#4-evaluation--health-metrics)
- [5. Key Bibliography](#5-key-bibliography)

---

## 1. Domain Map & Converging Disciplines

A practical Cognitive OS sits at the convergence of six distinct disciplines:

| Discipline | Core Contribution | Limitation When Isolated | How `cognitive-os` Integrates It |
| :--- | :--- | :--- | :--- |
| **Task Management (GTD / Asana)** | Concrete commitments, deadlines, action lists | Siloed from broad knowledge context and rationale | `vault/tasks.md` bound via provenance to `vault/goals.md` and `vault/decisions.md` |
| **PIM & PKM (Second Brain / Obsidian)** | Flexible capture, networked notes, retrieval | Passive storage; prone to `PARA-bloat` and separated from action | `/cos-capture` 3-way ontological triage (`[OBSERVATION]`, `[IDEA]`, `[COMMITMENT]`) |
| **Extended Mind (Clark & Chalmers)** | Outsourcing memory to trusted external substrates | Philosophical framing without operational workflow | Plain-text `vault/*.md` files that extend memory without lock-in |
| **Cognitive Augmentation (Centaur HCI)** | AI handles laborious synthesis; human steers judgment | Risk of skill erosion or unverified hallucination if unchecked | 4 Authority Tiers + mandatory `<!-- ref: ... -->` custody checks |
| **Cybernetics & Control Theory** | Goal setting, telemetry comparison, feedback loops | Rarely tracks *why* decisions were made or when to reconsider | `vault/decisions.md` with explicit `reconsider_on` and `reconsider_if` triggers |
| **Domain Craft Systems** | Deep execution rules for specialized work | Generic OS tools produce shallow "AI slop" in real work | Mounted **Domain Cartridges** (`script-builder` & `cover-letter-builder`) |

---

## 2. Why File-Centric (Markdown + Git) Beats Complex Databases

Comparative analyses of real-world Personal OS builds demonstrate that at personal scale (hundreds to tens of thousands of records), **human-readable Markdown files with YAML frontmatter and Git versioning** decisively outperform relational or vector-only databases:
1. **Zero Lock-In & Total Transparency**: You can inspect, edit, or grep every memory record in any text editor offline.
2. **Model Agnostic**: When LLM architectures change, your canonical `vault/` files remain untouched.
3. **Native Git Provenance**: Every modification to goals, decisions, and career stories has an immutable diff history.

---

## 3. Solving the 3 Industry-Wide Gaps

1. **Gap 1 — Reconsideration (`vault/decisions.md` + `/cos-decide`)**:
   Existing tools record tasks but forget the conditions under which a decision was made. `cognitive-os` stores every major commitment with its **Assumptions** and **Reconsideration Triggers** (`reconsider_on` date or `reconsider_if` conflicting evidence), surfacing it automatically in `/cos-briefing`.
2. **Gap 2 — Active Forgetting & Curation (`vault/dormant.md` + `/cos-curate`)**:
   Instead of letting unready ideas clutter daily task lists or deleting them, `/cos-curate` moves non-urgent sparks to `vault/dormant.md` and periodically resurfaces 1–2 dormant possibilities when goals shift.
3. **Gap 3 — Post-Action Verification (`vault/approvals.md` + `/cos-approve`)**:
   Distinguishes *intended outcome* (`APPROVED` / `EXECUTED_UNVERIFIED`) from *actual verified outcome* (`VERIFIED` vs. `FAILED`).

---

## 4. Evaluation & Health Metrics

Measured via `scripts/cos_cli.py` and weekly `/cos-curate` reviews:
- **Active Load Discipline**: Keeping active tasks in `vault/tasks.md` $\le 10$ items.
- **Provenance Coverage**: 100% of active commitments and cover letter claims carry valid `<!-- src: ... -->` or `<!-- ref: ... -->` tags.
- **Reconsideration Hygiene**: 0 overdue `reconsider_on` dates left unreviewed in `vault/decisions.md`.
- **Approval & Verification Closure**: 0 stale `EXECUTED_UNVERIFIED` actions in `vault/approvals.md`.

---

## 5. Key Bibliography

- Clark, A., & Chalmers, D. (1998). *The Extended Mind*. Analysis, 58(1).
- Forte, T. (2023). *Building a Second Brain*.
- Jones, W. (2007). *Keeping Found Things Found: The Study and Practice of Personal Information Management*.
- Marks, C. (2023). *Personal Operating Systems: A Comparative Analysis*.
- Pocock, M. (2025). *Composable Agent Skills Architecture (`mattpocock/skills`)*.
