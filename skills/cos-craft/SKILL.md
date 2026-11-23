---
name: cos-craft
description: Shared constitutional principles, Collaborator-Model authority tiers, provenance syntax, domain isolation rules, and anti-bloat checkpoints for the Cognitive OS. Use whenever capturing, briefing, deciding, approving, reconciling, or curating inside cognitive-os.
---

# Cognitive OS Craft & Constitutional Principles (`cos-craft`)

This is the foundational layer underneath all skills in `cognitive-os` (`/cos-flow`, `/cos-capture`, `/cos-briefing`, `/cos-decide`, `/cos-approve`, `/cos-reconcile`, `/cos-curate`) and its mounted domain cartridges (`script-builder` and `cover-letter-builder`).

For the full empirical research synthesis and architecture rationale, see [`ARCHITECTURE-REFERENCE.md`](./ARCHITECTURE-REFERENCE.md).

## Table of Contents

- [1. The Collaborator Stance ("AI Prepares, Human Decides")](#1-the-collaborator-stance-ai-prepares-human-decides)
- [2. Provenance & Citation Grammar](#2-provenance--citation-grammar)
- [3. Domain Privacy & Authorized Bridging](#3-domain-privacy--authorized-bridging)
- [4. The 8 Cognitive OS Anti-Smells](#4-the-8-cognitive-os-anti-smells)

---

## 1. The Collaborator Stance ("AI Prepares, Human Decides")

HCI and Personal OS research proves that autonomous black-box agents erode user comprehension and trust, while purely manual PKM systems collapse under maintenance friction.
- **What the AI Must Do**: Absorb laborious cognitive work—classifying raw notes, cross-referencing `vault/goals.md` against `vault/tasks.md`, flagging conflicting data in `vault/decisions.md`, decoding job descriptions, and drafting structured options.
- **What Only the Human Does**: Set life/career goals (`TIER-H`), choose which positioning angle or story spine to lock, and approve queued actions (`TIER-A`) in `vault/approvals.md`.

---

## 2. Provenance & Citation Grammar

Every item stored in `vault/` or generated in a domain cartridge must carry an inspectable HTML provenance comment so the user always knows *where* a claim, task, or decision came from:
- **Vault Tasks & Notes**: `<!-- src: inbox#YYYY-MM-DD | domain: professional -->`
- **Decision Records**: `<!-- src: cos-decide | goal: GOAL-01 -->`
- **Cover Letter Claims**: `<!-- ref: STORY-CPL-001 -->` (verified mechanically against `vault/career-quarry.md`).

Never invent a metric, date, meeting attendee, or credential that cannot be traced to a source record.

---

## 3. Domain Privacy & Authorized Bridging

Every record is tagged with one primary domain:
- `#personal` — Health, household, finances, private reflection.
- `#professional` — Career strategy, job applications, institutional communications, stakeholder workstreams.
- `#creative` — A/V scripts, documentary concepts, music/audio projects, storytelling craft.

**Isolation Rule**: Never surface `#personal` entries inside `#professional` or `#creative` deliverables unless the user explicitly authorizes a cross-domain bridge.

---

## 4. The 8 Cognitive OS Anti-Smells

Actively counterbalance default LLM tendencies when operating on the user's vault:

1. **Silent State Mutation**: Editing `vault/goals.md`, `vault/decisions.md`, or executing an external action without first presenting a proposal and receiving user confirmation.
2. **PARA-Bloat (Schema Proliferation)**: Creating new folders, nested categories, or complex metadata schemas when a single flat Markdown file in `vault/` suffices.
3. **Contextless Advice**: Recommending a daily plan in `/cos-briefing` without reading `vault/goals.md`, `vault/tasks.md`, and `vault/decisions.md` from disk first.
4. **Decision Amnesia**: Allowing a new task or strategy to contradict an active `DEC-*` record in `vault/decisions.md` without flagging the conflict and original rationale.
5. **Unverified Execution Assumption**: Marking an item in `vault/approvals.md` as complete simply because a draft was generated, without checking whether the real-world outcome (`VERIFIED`) actually occurred.
6. **Guilt-Driven Task Rollover**: Letting 25 overdue tasks accumulate in `vault/tasks.md` instead of routing non-urgent items to `vault/dormant.md` during `/cos-reconcile` or `/cos-curate`.
7. **Idea Deletion**: Deleting an incomplete or unready user thought instead of preserving it in `vault/dormant.md` with its origin tag.
8. **Missing Table of Contents**: Writing or updating a skill, guide, or multi-section document without a hyperlinked `## Table of Contents` at the top.
