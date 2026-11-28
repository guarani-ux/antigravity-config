# AGENTS.md
Global rules live in `~/.gemini/GEMINI.md` (installed from `GEMINI.global.md` by `bootstrap.sh` / `bootstrap.ps1`). Mechanical lifecycle enforcement runs via `hooks.json` (`scripts/sentinel.py` and `scripts/operator_router.py`), configured by `policy.json` and `hooks.json.portable`.

## Verification
- `python3 -m unittest discover -s scripts/tests -v`
- `python3 scripts/doctor.py --check-installed --strict`
- `python3 scripts/eval_harness.py`
