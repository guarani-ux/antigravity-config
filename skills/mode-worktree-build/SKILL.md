---
name: mode-worktree-build
description: Mode 4 — Graph & Worktree Build. Activate when writing, fixing, or refactoring code, UI, or creative/canon artifacts. Enforces the 5-Line Pre-Flight Contract, Red-Capable command gates on bugs, the 'Push Right' law, Workspace="share" worktree subagents, the 4-Point Visual Screenshot Gate, Commit-Cited Memory, and 2 Parallel Critic Subagents.
---

# Mode 4: Graph & Worktree Build Protocol

## 1. Step 1: The 5-Line Pre-Flight Contract & "Push Right" Law
Before mutating any workspace file, state this exact 5-line block at the top of the turn:
1. **Goal**: Single-sentence functional or creative outcome.
2. **Files Touched**: Exact list of files permitted to change (if `>= 3` non-test files, MUST delegate via `invoke_subagent`).
3. **Files Untouched**: Critical adjacent files, canon docs, or locked tests protected against modification.
4. **Real-World Acceptance Check**: Exact command, 4-Point Visual Screenshot check, or canon verification proving success.
5. **Execution Route**: Direct surgical edit (`< 3` files) OR isolated worktree subagent (`Workspace="share"`).

**The "Push Right" Law (Split)**: Confirm **intent and contract at the start** (via the 5-Line Pre-Flight Contract or `IDEAS.md` contract); defer **execution checkpoints** (research, coding, automated testing, and 2-axis review) to the end, presenting a single decision-ready **Brief** (what was built, why, and a pointer to the diff/artifact) at the finish line.

## 2. Step 2: Caller Blast-Radius, Bug Reproducers & Canon Custody Check
- **Python Code**: Run `python C:/Users/flowe/.gemini/config/scripts/code_graph.py --root <dir> --callers <symbol>` before editing shared functions/classes.
- **Bug Fixes (Hard Red-Loop Gate)**: Forbid editing source code until Phase 1 produces a fast, automated command that goes **RED** on the exact symptom. Prefix temporary debug logs with a unique session tag (e.g. `[DEBUG-4a9f]`) and run an automated regex sweep to delete all tags before completion.
- **Non-Python Code (`.ts/.tsx/.js/.css`)**: Trace all imports, props, and usages across the workspace via targeted `grep_search` / `rg`.
- **Creative / World-Building / A-V Script Work**: Skip `code_graph.py`; read canonical world/source/quarry files before drafting (zero silent retcons or invented source quotes).

## 3. Step 3: Isolated Worktree Execution (`Workspace="share"`)
- **Multi-File / Component Builds (`>= 3` files)**: Spawn `invoke_subagent(TypeName="self", Workspace="share", ...)` per orthogonal slice so subagents edit in isolated Git worktrees without colliding.
- **Hard / Ambiguous Bugs (Best-of-2 Worktrees)**: Spawn 2 parallel `Workspace="share"` subagents with competing hypotheses; promote only the worktree that passes all invariant checks cleanly.

## 4. Step 4: Locked Tests, Fresh-Process Reopening & 4-Point Visual Screenshot Gate
Never trust `exit code 0` or mocked unit tests alone:
- **UI / Web / Visual Work (4-Point Visual Screenshot Gate)**: Capture the rendered viewport via `chrome-devtools-mcp` or `read_file` on image/video outputs and explicitly inspect: `1. Hierarchy & Contrast`, `2. Overflow/Clipping/Alignment`, `3. Interactive State Affordance`, and `4. Anti-Slop Craft — zero generic AI gradients/cards`.
- **Data / Persistence & Invariants**: Reopen SQLite/JSON/package artifacts from a **fresh separate process** and test both valid and malformed/adversarial inputs.
- **Commit-Cited Memory**: Record durable architectural decisions in `.agents/wiki/` (or project decision log) citing exact dates and commit SHAs (`As of commit abc1234 on 2026-10-25...`). Never write "currently" or "is" without an anchored commit SHA.

## 5. Step 5: Mandatory 2-Axis Parallel Critic Gate (Non-Trivial Builds)
Before reporting Done, spawn **2 Parallel `research` Critic Subagents**:
- **For Software / UI Builds**: **Axis 1 (Anti-Hack & Logic Critic)** audits `git diff` for stubs, swallowed errors, or weakened tests; **Axis 2 (Goal & Caller Custody Critic)** verifies every caller and Pre-Flight Contract item.
- **For Creative / World-Building / A-V Builds**: **Axis 1 (Voice, Spoken-Ear & Anti-Slop Craft)** audits prose/dialogue rhythm and bans AI tropes; **Axis 2 (Canon & Source Custody)** verifies 100% fidelity to world rules and source quotes.
