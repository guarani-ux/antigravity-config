---
name: diagnosing-bugs
description: Systematic root-cause loop for hard bugs, regressions, and performance issues. Use when debugging failing tests, tracebacks, or broken behavior.
---
# Diagnosing Bugs

Never jump straight to guessing a fix. Build a tight failing repro first, minimize it, test ranked hypotheses, and lock the fix with a regression test.

1. **Redact secrets first:** Replace any tokens, keys, or auth headers with `<REDACTED>` before quoting commands or logs. Run loops against env vars, never hardcoded credentials.
2. **Build a tight red-capable repro command first:** Construct one fast, deterministic command (failing unit/integration test, CLI invocation, HTTP script, trace replay, or `git bisect`) that asserts the exact reported symptom. For flaky bugs, repeat/stress until reproduction is reliable. If no repro loop is possible, stop and ask the user for access, logs, or temporary instrumentation rather than guessing.
3. **Reproduce and minimize:** Run the command to confirm it fails with the user's exact symptom, then strip away unrelated inputs/steps until every remaining element is load-bearing.
4. **Rank 3-5 falsifiable hypotheses:** State each as a concrete prediction ("If X is the cause, changing Y will flip the result"). Share the ranked list quickly before probing if useful.
5. **Probe one variable at a time:** Prefer a debugger/REPL or targeted logs prefixed with `[DEBUG-<tag>]` (for performance bugs, profile/measure first instead of logging).
6. **Fix at the real seam and clean up:** Add a failing regression test at the real call-site seam (or note if architecture blocks a real seam), apply the fix, confirm both the regression test and original un-minimized repro pass, remove all `[DEBUG-...]` logs and throwaway files, and state the root cause in the commit message.
