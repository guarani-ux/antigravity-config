# Antigravity Global Config (`guarani-ux/antigravity-config`)

Portable local AI agent chassis: 5 mechanical lifecycle hooks, deterministic AST/secret/test gates, privacy-safe hook telemetry, self-diagnostic Machine Doctor (with script reachability verification), fixed 16-case adversarial benchmark, cross-OS CI, and 2 lean core skills.

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

## Machine Architecture

| Subsystem | Component | What It Enforces / Provides |
| :--- | :--- | :--- |
| **Hook 1: `SessionStart`** | `scripts/operator_router.py session-start` | Minimal startup orientation + staleness-checked `NEXT_SESSION_HANDOFF.md` detection. |
| **Hook 2: `PreInvocation`** | `scripts/operator_router.py pre-invocation` | Deterministic skill routing (once per prompt) + post-compaction context-window pressure warnings (`WARN` / `DEPLETED`). |
| **Hook 3: `PreToolUse`** | `scripts/sentinel.py pre` (`policy.py`, `ast_gate.py`, `test_quality_gate.py`) | **RW-18** secret leak blocking across all file types, shell/MCP blast-radius gates, tamper locks (`RW-04`/`RW-06`), **RW-19** Git sprawl governor, **RW-20** deliverable hygiene, `Orient-Before-Edit`, `3-Strike Governor`, AST anti-cheat, and `TQ-01..TQ-05` test rigor. |
| **Hook 4: `PostToolUse`** | `scripts/sentinel.py post` (`lifecycle.py`) | Deterministic edit/verify/thrash state ledger (`sentinel-state.json`); rewards red discovery tests and rejects vacuous 0-test runs. |
| **Hook 5: `Stop`** | `scripts/sentinel.py stop` (`lifecycle.py`) | `Verify-Before-Stop`, edited Python AST check, multi-root `acceptance.lock.json`, and 3-error stuck check. |
| **Flight Recorder** | `scripts/sentinel/telemetry.py` | Privacy-safe local JSONL telemetry (`~/.gemini/telemetry/hook-events.jsonl`: decision, rule tag, latency ms; never file contents, secrets, or prompts). |
| **Machine Doctor** | `scripts/doctor.py` | Checks `GEMINI.md` parity, hook/MCP manifests, Python syntax, script reachability (no dead scripts), skill frontmatter & broken local links, and telemetry summary. |
| **Harness Benchmark** | `scripts/eval_harness.py` | 16 fixed end-to-end adversarial subprocess cases measuring Catch Rate, False-Positive Rate, and p50/p95 latency. |
| **Cross-OS CI** | `.github/workflows/ci.yml` | Runs bootstrap, unit tests, `TQ-01..TQ-05`, `doctor.py --strict`, and `eval_harness.py` on Ubuntu, macOS, and Windows PowerShell. |
| **Core Skills** | `skills/{potential-unleashed,meeting-brief}/SKILL.md` | 2 lean global skills (outcome-first partnership lives in `GEMINI.global.md`; domain workflows live in dedicated plugin repos like `calgary-library-production`). |

## Local Verification Commands
```bash
python3 -m unittest discover -s scripts/tests -v
python3 scripts/doctor.py --check-installed --strict
python3 scripts/eval_harness.py
```
