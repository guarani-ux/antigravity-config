---
name: idea-crucible
description: >-
  Compresses and hardens Elijah's rapid ideas before any code or new directory is created.
  Use whenever a new system, tool, folder, or feature spark is proposed so ideation becomes
  a structured card in IDEAS.md, passes 3 hardening checks, and converts into one bounded
  vertical slice.
---

# Idea Crucible (Capture -> Compress -> Harden -> Ship)

Rapid ideation is high-gain creative input, not a directive to immediately scaffold files or spin up new folders.
Use this 4-stage envelope to turn acceleration into durable, finished work.

## Target Ledger
- Workspace Local Ledger: `<workspace>/IDEAS.md` (e.g., `c:/Users/flowe/OneDrive/Desktop/Crucible Domain/IDEAS.md`).

## Workflow

### Step 1: Capture Without Friction (`Stage 1: RAW SPARKS`)
- Distill the idea into 3 crisp lines without killing momentum:
  - **Spark Name & Date**
  - **Core Problem / Intuition** (1 sentence)
  - **Raw Inspiration / Analogy**
- Log it under `## Stage 1: RAW SPARKS` so nothing is lost if focus shifts.

### Step 2: Run the 3 Hardening Checks (`Stage 2: CHALLENGED`)
Present 3 concise checks (prefer Default-Yes or numbered choices):
1. **Existing-Home Check (Anti-Sprint-&-Rename):** Check existing project roots (`C:/Kageyoni`, `Crucible Domain/Project`, `Crucible Domain/CPL`). Never create a new top-level folder unless existing homes fail for a concrete technical reason.
2. **Red -> Green Vertical Slice:** Define the smallest **Green v0.1** slice (1 data unit + 1 core behavior + 1 verifiable proof) runnable today. Park everything else as **Later**.
3. **Negative Scope (What Is Banned):** Name 2 things this slice is explicitly forbidden to become (e.g., no new SQLite daemon, no 10-agent swarm, no UI polish before logic passes).

### Step 3: Lock the Contract (`Stage 3: HARDENED SPEC` -> `Stage 4: ACTIVE SLICE`)
- Only after explicit lock, promote to **HARDENED SPEC** with target files, done check, and negative scope.
- Enforce **`WIP = 1`** in **ACTIVE SLICE**—do not pull a second build until the active slice passes its check or is explicitly paused.

### Step 4: Graduate (`SHIPPED & VERIFIED`)
- Move the card to **SHIPPED & VERIFIED** only after observing raw passing verification output after your final edit.
