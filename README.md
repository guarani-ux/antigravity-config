# Antigravity Config 2.0 (`guarani-ux/antigravity-config`)

Two-layer portable AI operating system designed to run coherently across **both Cloud sessions and Local Desktop**:
1. **LLM-Native Cognitive Core (`core/`, `GEMINI.global.md`, `AGENTS.md`, synced skills):** Plain-English, human-owned, strictly budgeted (<= 200 lines) whole-context memory (`IDENTITY.md`, `PRINCIPLES.md`, `EPISODES.md`) plus the **Probing Method** (*sense-making before execution*), **Load-Bearing Runtime Verification**, and **one unified blind verification pass**.
2. **Thin Mechanical Safety & Verification Floor (`scripts/`):** Deterministic cross-OS hooks (`SessionStart`, `PreInvocation`, `PreToolUse`, `PostToolUse`, `Stop`) enforcing only what code does reliably — secret blocking (`RW-18`), destructive/external gating, content-hashed file obligations + post-verify disk-drift detection, positive verification evidence, context-window monitoring, and self-diagnostic Machine Doctor.

> **1.0 History Preserved:** Pre-2.0 state is tagged at `v1-archive` (`3a34c1f`).

## Bootstrap on a Local Machine

**Windows (PowerShell):**
```powershell
git clone https://github.com/guarani-ux/antigravity-config.git "$env:USERPROFILE\.gemini\config"
& "$env:USERPROFILE\.gemini\config\bootstrap.ps1" -Force
```

**macOS / Linux (Bash/Zsh):**
```bash
git clone https://github.com/guarani-ux/antigravity-config.git ~/.gemini/config
chmod +x ~/.gemini/config/bootstrap.sh
~/.gemini/config/bootstrap.sh --force
```

> **Cloud vs. Local Note:** Cloud Antigravity sessions do not execute local `~/.gemini/hooks.json`. They load your **cloud-synced skills** (`plainspoken-partner`, `potential-unleashed`, `meeting-brief`), repo **`AGENTS.md`**, and shared files (`core/` + `Working_Context.md` on Drive). Local desktop runs the exact same Cognitive Core plus the mechanical safety hooks after running `bootstrap`.

## Architecture Overview

| Layer | Component | What It Provides |
| :--- | :--- | :--- |
| **Cognitive Core** | `core/{IDENTITY,PRINCIPLES,EPISODES}.md` | Human-owned, whole-context living memory (hard-capped at <= 200 lines total by `doctor.py` to force consolidation over accumulation). |
| **Constitution** | `GEMINI.global.md` + `AGENTS.md` | Unified 2.0 operating rules active in both Local (`~/.gemini/GEMINI.md`) and Cloud (`<user_rules>`): Probing Method, core vs. applied domains, load-bearing verification. |
| **Core Skills** | `skills/{potential-unleashed,meeting-brief}/SKILL.md` + cloud `plainspoken-partner` | Unified probing, building, and load-bearing verification discipline synced across Cloud and Local. |
| **Session & Router Hooks** | `scripts/operator_router.py` (`SessionStart`, `PreInvocation`) | Loads `core/` brief at session start, surfaces pending `NEXT_SESSION_HANDOFF.md`, routes skills, and alerts on post-compaction context pressure (`WARN`/`DEPLETED`). |
| **Mechanical Safety & Ledger** | `scripts/sentinel.py` + `scripts/sentinel/*` (`PreToolUse`, `PostToolUse`, `Stop`) | Secret blocking (`RW-18`), blast-radius gates, transactional v2 content-hashed obligations, post-verify disk-drift checks, positive execution evidence, AST/TQ integrity. |
| **Diagnostics & CI** | `scripts/doctor.py`, `scripts/eval_harness.py`, `.github/workflows/ci.yml` | Validates manifests, `core/` line budget, script reachability, telemetry, 63-case adversarial benchmark, and cross-OS CI (Ubuntu, macOS, Windows). |

## Local Verification Commands
```bash
python3 -m unittest discover -s scripts/tests -v
python3 scripts/doctor.py --strict
python3 scripts/eval_harness.py
```
