# Antigravity Global Config (`guarani-ux/antigravity-config`)

Portable global constitution, 5 mechanical lifecycle hooks, deterministic AST/test gates, and lean skills for Antigravity workspaces.

## Bootstrap on a New Machine

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

> **Note:** Generated local configs (`hooks.json`, `mcp_config.json`), Marketplace plugins (`plugins/`), and machine-local state (`config.json`, `telemetry/`, `projects/`) are `.gitignore`d. Run `bootstrap.sh` or `bootstrap.ps1` after cloning to generate `hooks.json` and `mcp_config.json` with resolved absolute paths, and re-install Marketplace plugins once from the Antigravity UI.

## Architecture: 5 Mechanical Hooks + 3 Core Skills

| Layer | Component | What It Enforces |
| :--- | :--- | :--- |
| **Hook 1: `SessionStart`** | `scripts/operator_router.py session-start` | Minimal startup orientation + pending `NEXT_SESSION_HANDOFF.md` detection. |
| **Hook 2: `PreInvocation`** | `scripts/operator_router.py pre-invocation` | Deterministic skill-routing signals (once per prompt) + post-compaction context-window pressure warnings (`WARN` / `DEPLETED`). |
| **Hook 3: `PreToolUse`** | `scripts/sentinel.py pre` (`sentinel/policy.py`, `ast_gate.py`, `test_quality_gate.py`) | Shell/MCP blast-radius gates, tamper protection (`RW-04`/`RW-06`), `Orient-Before-Edit`, `3-Strike Governor`, AST anti-cheat, and `TQ-01..TQ-05` test rigor. |
| **Hook 4: `PostToolUse`** | `scripts/sentinel.py post` (`sentinel/lifecycle.py`) | Deterministic state ledger (`oriented`, `edited_code_files`, `unverified_code_edits`, `repair_strikes`, `consecutive_tool_errors`). |
| **Hook 5: `Stop`** | `scripts/sentinel.py stop` (`sentinel/lifecycle.py`) | `Verify-Before-Stop`, edited Python AST check, `acceptance.lock.json`, and 3-error stuck check. |
| **Always-On Constitution** | `GEMINI.global.md` -> `~/.gemini/GEMINI.md` | Lean 22-line baseline boundaries and tone rules. |
| **Core Skills** | `skills/{plainspoken-partner,waterwall,meeting-brief}/SKILL.md` | Synced lean collaboration, lossless build/review, and meeting-brief primitives alongside domain craft skills. |
| **Utilities** | `scripts/code_graph.py`, `scripts/eval_router.py`, `scripts/test_quality_gate.py` | Zero-dependency Python AST call graph, router transcript replay evaluator, and CLI test quality gate. |

## Verification
```bash
python3 -m unittest discover -s scripts/tests -v
```
