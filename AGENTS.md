# AGENTS.md — Antigravity Config 2.0

Global constitution lives in `GEMINI.global.md` (installed to `~/.gemini/GEMINI.md` by `bootstrap.sh` / `bootstrap.ps1`). Budgeted, human-owned Cognitive Core lives in `core/` (`IDENTITY.md`, `PRINCIPLES.md`, `EPISODES.md`, hard cap <= 200 lines total).

## Active Operating Posture (Cloud + Local)
- **Probing Method first:** Treat exploratory ideas, metaphors, and proposed fixes as probes into an underlying condition, NOT literal build specs. Stay in zero-mutation Sense-Making mode until the root condition and cleanest domain architecture are clear; never patch symptoms reflexively.
- **Read `core/` before structural work:** Ground framing in `core/IDENTITY.md` (core CS mission vs. applied domains), `core/PRINCIPLES.md`, and `core/EPISODES.md`. Consolidate and prune instead of accumulating bloat.
- **Load-bearing verification:** Passing tests != proof of outcome. Verify what passing tests actually exercised against the original intention and real runtime integration; use 1 unified blind verification pass on structural changes.
- **Mechanical floor (local desktop):** Runs via `hooks.json` (`scripts/sentinel.py` + `scripts/operator_router.py`), configured by `policy.json` and `hooks.json.portable`.

## Verification
- `python3 -m unittest discover -s scripts/tests -v`
- `python3 scripts/doctor.py --strict` (or `--check-installed --strict` after local bootstrap)
- `python3 scripts/eval_harness.py`
