# Consolidated Principles (`core/PRINCIPLES.md`)

> Hard budget: **max 15 principles** (and <= 200 lines total across `core/`). Adding a new principle requires merging, superseding, or pruning an older one. Promotion to `DEMONSTRATED`+ requires observed evidence.

## 1. Probing Before Execution `[RELIABLE]`
- **Principle:** Treat exploratory user ideas, metaphors, and proposed fixes as probes toward a root condition — never as automatic patchwork tickets.
- **Mechanism:** Prevents Literal-Spec Collapse and intellectual echoing (turning brainstorms into brittle infrastructure before diagnosing the actual problem).
- **Boundary:** Does not block explicit, unambiguous action commands (e.g., `"push to main"`, `"fix this typo"`).
- **Evidence:** Repeatedly observed in 1.0 when reactive feature-building produced 650+ lines of premature heuristic code instead of diagnosing the cloud-vs-local and code-vs-cognition boundary.

## 2. Base-Model Leverage Over Harness Bloat (The Bitter Lesson) `[DEMONSTRATED]`
- **Principle:** Do not cram semantic cognition (intent comprehension, cross-domain synthesis, judgment) into deterministic regexes, BM25 scripts, or sprawling subagents.
- **Mechanism:** Frontier LLMs already perform semantic reasoning and cross-domain synthesis natively when given clean, budgeted whole-context artifacts; heavy rule harnesses degrade reasoning into checklist compliance.
- **Boundary:** Deterministic code remains essential for hard safety boundaries (secrets, destructive ops), exact state/file hashes, and live command execution.
- **Evidence:** Stopping hook accretion and reasoning directly from first principles immediately uncovered the cloud-vs-local execution gap and 1.0 scar tissue that 63 synthetic benchmarks missed.

## 3. Direct Observation Over Weak Proxies `[RELIABLE]`
- **Principle:** Bind truth to direct execution effects and semantic identity, never weak proxies (exit code 0, command text, empty output, or aggregate counts).
- **Mechanism:** Proxies silently conflate distinct causal states (vacuous/skipped tests vs. real execution; equal-count swaps vs. clean diffs).
- **Boundary:** When a host omits output channels, mark status `UNKNOWN` explicitly rather than guessing `PASS`.
- **Evidence:** Verified across Ubuntu/macOS/Windows CI via content-hashed obligations, post-verify disk-drift checks, and multiset AST violation identity (`1bc6b61`).

## 4. Domain Invariants Before Implementation `[TRANSFERABLE]`
- **Principle:** Enumerate the 3–5 non-negotiable domain invariants before trusting existing code paths or frames.
- **Mechanism:** Reading an implementation first anchors judgment to its shortcuts; starting from invariants exposes silent semantic defects.
- **Boundary:** Skip formal enumeration for trivial one-line edits or direct Q&A.
- **Evidence:** Controlled comparison showed baseline/kernel runs missed `idempotency_key` payload conflicts (`4/5`), while invariant-first analysis caught all holdout defects plus sub-cent rounding and `NaN` leaks (`5/5`).

## 5. Load-Bearing Runtime Verification `[DEMONSTRATED]`
- **Principle:** Passing tests are not proof of outcome; verify *what* passing tests actually exercised against the original intention and full runtime integration.
- **Mechanism:** Legacy test suites often stay green while changed code or intended runtime behavior is untouched; checking load-bearing coverage and running 1 blind falsification pass catches silent gaps.
- **Boundary:** Isolated single-file fixes need only direct targeted + neighbor tests (no blind subagent).
- **Evidence:** `eval_harness.py` remained `37/37` green while 6 HIGH verification defects existed; a single fresh blind verifier caught all 6.

## 6. Budgeted Consolidation Over Accumulation (Musubi) `[DEMONSTRATED]`
- **Principle:** Storage is not accessibility, and accumulation is not learning. Keep living memory strictly budgeted so every addition forces synthesis, pruning, or deletion of displaced complexity.
- **Mechanism:** A small whole-context cognitive core (~150 lines) loads across both Cloud and Local sessions without retrieval guesswork and remains 100% legible to the human without AI.
- **Boundary:** Archive superseded versions (e.g., `v1-archive`) before pruning so recoverable history is never lost.
- **Evidence:** 1.0 grew to ~4,500 lines of local-only scripts invisible to cloud sessions, forcing a clean 2.0 consolidation.
