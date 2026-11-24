# Antigravity Global Config (`guarani-ux/antigravity-config`)

Portable global rules, lifecycle hooks, routing scripts, and skills for Antigravity workspaces (including [Crucible-Domain](https://github.com/guarani-ux/Crucible-Domain)).

## Bootstrap on a New Machine
```powershell
git clone https://github.com/guarani-ux/antigravity-config.git "$env:USERPROFILE\.gemini\config"
& "$env:USERPROFILE\.gemini\config\bootstrap.ps1" -Force
```

## What Lives Here vs. Machine-Local
| Component | Status in Repo | Honest Notes & Known Gaps |
|---|---|---|
| `GEMINI.global.md` | Tracked (`bootstrap.ps1` installs to `~/.gemini/GEMINI.md`) | Live `~/.gemini/GEMINI.md` sits outside `config/` unless synced via `bootstrap.ps1`. |
| `hooks.json.portable` / `hooks.json` | Tracked | `hooks.json.portable` uses `./scripts/...` relative paths; live `hooks.json` uses `C:/Users/flowe/...` until `bootstrap.ps1 -Force` overwrites it. |
| `scripts/sentinel.py` + `scripts/sentinel/` | Tracked (`~380` lines modular + `test_sentinel.py`) | Enforces `PreToolUse` / `PostToolUse` / `Stop` (`Tier 1/2`, single-pass AST, `Orient-Before-Edit`, `3-Strike Governor`, `Verify-Before-Stop`). |
| `scripts/operator_router.py` | Tracked + `test_operator_router.py` | Outcome-regime & `meeting-simulator` `SessionStart` / `PreInvocation` router. |
| `skills.json` | Tracked (`empty` — skills internalized under `skills/`) | Portable across machines. |
| `mcp_config.json` | Tracked (`2` active GCP MCP URLs) | Redundant/dead MCP entries removed. |
| `config.json`, `plugins/`, `projects/`, `backups/` | Excluded (`.gitignore`) | Machine hostname, OAuth tokens, permission grants, and large binaries (`impeccable.exe`) are never pushed; see `config.example.json`. |
