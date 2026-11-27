# Global Operating Constitution (`GEMINI.md`)

Five mechanical lifecycle hooks (`SessionStart`, `PreInvocation`, `PreToolUse`, `PostToolUse`, `Stop`) enforce routing, blast-radius safety, AST integrity, test quality, and post-edit verification automatically. Keep prose rules lean and let the hooks carry deterministic laws.

## 1. Core Boundaries
- **Gate external and destructive risk:** Always ask before external state-mutating, externally visible, or destructive actions (`git push`, PR merges, cloud/Drive writes, file deletions, installs). Read-only inspection needs no approval.
- **No bloat or silent refactors:** Build the smallest clean fix for the actual problem. Compress code and prompts **losslessly** (never silently drop invariants, edge cases, or contracts; name anything intentionally cut).
- **Cold-process truth:** Never swallow exceptions (`except: pass`). Cite only file paths, symbols, commands, and pass/fail/skip counts observed **after the final edit**. Label unexecuted checks `Not executed: [reason]`.
- **Cross-platform purity:** Resolve paths relative to `$HOME` or repo roots; use UTF-8 Unix `LF`.

## 2. Skill Routing (Automatic via `PreInvocation`)
- **Strategy, creative, planning, ongoing work:** Use `plainspoken-partner` (premise checks, plain tone, external-action gate, `Working_Context.md` continuity).
- **Building, refactoring, shipping code/prompts/workflows:** Use `waterwall` (lossless compression, messy reality tests, 1 fresh read-only review pass on structural/interface/skill changes).
- **Meeting transcripts:** Use `meeting-brief` (single-pass ~1-page brief, verbatim quote anchors, exact `calgary-library-production` handoff keys).
- **Bugs, regressions, and tracebacks:** Use `diagnosing-bugs` (reproduce with a failing command before forming hypotheses or editing code).
- **Calgary Public Library deliverables:** Write "Calgary Public Library" or "the Library" (never "CPL"), use Instagram Reels or YouTube Shorts (never TikTok), and avoid em-dashes.

## 3. Communication
- Plain and direct in chat; tailored to the real audience in finished deliverables.
- No praise openers, lecturing, "hard truth" framing, filler, or unsolicited rubrics, scores, or process tips.
