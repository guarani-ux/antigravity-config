# Recent Judgments & Consolidation Log (`core/EPISODES.md`)

> Rolling window: **max 10 entries**. When full, fold durable lessons into `PRINCIPLES.md` and prune settled episodes.

- **2026-11-28 | Cloud-vs-Local Execution Blind Spot `[worked]`:**
  - *Situation:* Upgraded local Python hooks for hours inside a cloud VM session without verifying whether those hooks actually ran in cloud sessions.
  - *Lesson:* Cloud VM sessions do NOT load `~/.gemini/hooks.json` or `~/.gemini/GEMINI.md`; they load synced cloud skills, repo `AGENTS.md`, and Drive/repo files. Put the cognitive core and probing posture in the portable synced layer so both Cloud and Local share one mind.
- **2026-11-28 | Literal-Spec Collapse & Patchwork Trap `[worked]`:**
  - *Situation:* User brainstormed memory, load-bearing checks, and hooks as exploratory probes; agent immediately wrote 650+ lines of BM25 and symbol-grep scripts instead of diagnosing the underlying code-vs-cognition mismatch.
  - *Lesson:* Embed the Probing Method into both `GEMINI.global.md`/`AGENTS.md` and live cloud skills; hold in zero-mutation Sense-Making mode until root conditions are aligned.
- **2026-11-28 | Blind Falsification Over Self-Review `[worked]`:**
  - *Situation:* After M3.0 edits passed `34/34` unit tests and `37/37` benchmark cases, one fresh read-only blind verifier audited the diff.
  - *Lesson:* One fresh blind verification pass caught 6 HIGH and 7 MEDIUM flaws invisible to self-review; keep verification unified in 1 pass instead of spawning fragmented agents.
