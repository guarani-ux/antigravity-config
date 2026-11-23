---
name: mode-quarry
description: Mode 2 — Quarry & Mechanism Research. Activate when reverse-engineering external repos, videos, games/RPGs, papers, or narrative/technical domains. Spawns 1 parallel research subagent per source and extracts structured Mechanism Cards (including Narrative & Consequence Mechanics).
---

# Mode 2: Quarry & Mechanism Research Protocol

## 1. Trigger & Automatic Subagent Fan-Out
- **When Active**: User asks to study, quarry, or reverse-engineer external codebases, RPG systems (e.g., *Pendragon*, *Disco Elysium*), narrative worlds, videos, or domain mechanics.
- **1 Source = 1 Parallel Subagent**: Never serialize multi-source research (`>= 2` sources) in the main window. Immediately spawn one `invoke_subagent(TypeName="research")` per target source so each subagent operates with unpolluted context.
- **Anti-Plot-Recap Rule**: Reject surface Wikipedia plot recaps or marketing blurbs. For code/systems, extract runnable data structures and state transitions; for narrative/RPG/story systems, extract **Narrative & Consequence Mechanics** (how lore, factions, passions, or dialogue choices structurally gate and mutate state).

## 2. Mechanism Card Template (Required Output Per Extracted Pattern)
Each subagent (and the Lead Agent's synthesis) must format findings strictly as **Mechanism Cards**:

```markdown
### Mechanism Card: [Name of Mechanic / Narrative Rule / Algorithm]
- **Source**: [Repo file:line, RPG rulebook section, or video timestamp]
- **State Variables**: Exact typed fields, faction clocks, or counters mutated (e.g., `passions: dict[str, int]`, `winter_phase_tick: int`).
- **Causal Rule (`If X -> Y`)**: Deterministic trigger, threshold calculation, narrative consequence, and state transition equation.
- **Failure Mode / Edge Case**: How this mechanism breaks under degenerate inputs, runaway feedback loops, or canon contradiction.
- **Stealable Primitive**: 5–15 line pseudocode, schema, or narrative rule table showing how to transplant this into our workspace.
```

## 3. Concrete Example (*Pendragon* Winter Phase Quarry)
```markdown
### Mechanism Card: Pendragon Winter Phase Solo-Tick & Dynasty Consequence
- **Source**: Book of the Estate / Great Pendragon Campaign Yearly Loop
- **State Variables**: `manor_fortune: int`, `stewardship_skill: int`, `passion_loyalty: int`, `heir_survival_roll: d20`
- **Causal Rule (`If X -> Y`)**: If `season == "Winter"`, freeze tactical movement; execute batch resolution (`d20 + weather_mod <= stewardship_skill` -> increment `manor_fortune`, else apply `shortfall_debt` and trigger family survival/passion checks).
- **Failure Mode / Edge Case**: Unbounded wealth compounding if misfortune tables lack progressive maintenance sinks.
- **Stealable Primitive**: Separate high-frequency interactive scenes from a mandatory end-of-epoch batch consolidation pass (`run_epoch_tick(state)`).
```

## 4. Synthesis & Quarry Handoff
After all parallel `research` subagents return their Mechanism Cards, deduplicate overlapping primitives, rank by **Implementation Cost** vs. **Leverage**, and link to [mode-worktree-build](file:///C:/Users/flowe/.gemini/config/skills/mode-worktree-build/SKILL.md) for implementation.
