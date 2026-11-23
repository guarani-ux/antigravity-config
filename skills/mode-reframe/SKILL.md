---
name: mode-reframe
description: Mode 1 — Reframe & Discovery. Activate when the user is exploring a problem, instinct, or architecture before committing to code. Zero file creation; presents 3 distinct representations (Zero-Build/Subtraction, Lightweight Mechanism, Full System) with concrete trade-offs, and uses Default-Yes Frontier Grilling to eliminate user typing friction.
---

# Mode 1: Reframe & Discovery Protocol

## 1. Trigger & Hard Invariants
- **When Active**: User asks open-ended architecture questions, shares an instinct, or explores how to solve a bottleneck without requesting immediate code edits.
- **Zero File Creation**: Do NOT create workspace files, scaffolding directories, or `implementation_plan.md` artifacts during Mode 1.
- **Symptom vs. Cause Check**: In 2 lines, separate the *downstream symptom* reported by the user from the *structural root cause*.

## 2. The 3-Representation Matrix (Mandatory Output Template)
Always present three genuinely distinct structural options so the user chooses the right leverage point before a single line of code is written:

| Representation | Core Mechanism | What Gets Deleted / Avoided | Failure Mode & Cost |
| :--- | :--- | :--- | :--- |
| **1. Zero-Build / Subtraction** | Solve by deleting dead abstractions, tightening a prompt rule, or reusing an existing CLI flag. | Zero new code; removes existing complexity. | May hit ceiling if runtime state enforcement is strictly required. |
| **2. Lightweight Mechanism** | Single-file hook, AST query, or SQLite/JSON table (~50–150 LOC) wired into existing entrypoints. | Avoids daemon servers, new dependencies, or multi-package frameworks. | Limited to single-host synchronous execution. |
| **3. Full System** | Multi-component architecture, isolated worker pool, or persistent state engine. | Avoids ad-hoc patches; provides full isolation and auditability. | Highest maintenance surface and integration latency. |

## 3. "Default-Yes" Frontier Grilling (Zero-Friction Decision Trees)
When architectural or requirement forks need resolution, do NOT ask open-ended questions. Treat the decision space as a DAG, compute the active **Frontier** (decisions whose prerequisites are settled), and batch all unblocked questions with your recommended choice:
```markdown
❓ **Q1** - **<title>**: <body/options> ➡️ **Recommended: <choice>**
❓ **Q2** - **<title>**: <body/options> ➡️ **Recommended: <choice>**
```
Word every recommendation so the user can literally reply `"yes"` or `"yes to all"` to accept. Look up background facts autonomously via subagents; never interrogate the user for facts.

## 4. Handoff Gate
End the response with the decision prompt:
> *"Which representation fits your appetite right now (1: Subtraction, 2: Lightweight Mechanism, or 3: Full System)? Once selected, I will transition to Mode 4 ([mode-worktree-build](file:///C:/Users/flowe/.gemini/config/skills/mode-worktree-build/SKILL.md))."*
