---
name: crucible-loop
description: Thin-orchestrator, fresh-context execution loop (up to N rounds, default 12) for multi-step systems, spoke/media, and research campaigns. Orchestrates isolated workers via run_workflow, Campaign IR DAG compilation and CAS/FSM/ratchet state (campaign_ir.py), in-RAM Copy-on-Write file transactions (tx_patch.py), and single-command verification (scripts/verify_all.ps1). Use when the user asks to "run a crucible loop", "loop for N rounds", or "self-prompt until <target outcome>".
---

# Crucible Loop v4 — Thin-Orchestrator + Fresh-Context Workers

Execute multi-round campaigns using an `O(1)` parent orchestrator (`run_workflow` + `campaign_ir.py` + `tx_patch.py`) that dispatches fresh-context workers in isolated `workspace="share"` copies and merges only structured typed receipts back into parent state.

## 1. Loop Contract & Thin-Orchestrator Architecture
- **Branch Isolation:** Create/checkout `loop/<slug>` in every touched repository (`main` remains untouched until operator-approved merge).
- **Campaign IR (`campaign_ir.py`):** Load and validate `CampaignSpec` + `SliceNode` (`id`, `target_paths`, `depends_on`, `verify_cmd`, `input_sha256`) via `load_campaign_spec()` and `compile_campaign()` before Round 1 (path containment within `CRUCIBLE_ALLOWED_ROOTS` / `repo_root`, unique IDs, valid dependencies, acyclic DAG).
- **Wave Levelization:** Run `optimize_campaign(spec, receipt_cache)` to mark unchanged slices `SKIP_CACHED` (0 tokens) and schedule `CompiledCampaign.execution_waves` across parallel DAG levels.
- **O(1) Parent Context:** The parent orchestrator uses `run_workflow` (`parallel` / `pipeline` + `agent(..., schema=WORKER_RESULT_SCHEMA, workspace="share")`) with `build_slice_worker_prompt()` so raw child logs, file reads, and stack traces never enter parent context.
- **Round Budget:** Default `max_rounds = 12`; halt immediately once all exit criteria verify `passed=True`.

## 2. CS Domain Augmentation Pass
Map each slice bottleneck to a deterministic Computer Science primitive before dispatching workers:

| Bottleneck / Failure Mode | CS Domain Primitive | Crucible Mechanism |
| :--- | :--- | :--- |
| Repeated work on unchanged inputs | **Compilers & Build Systems** (DAG + Content-Addressable Memoization) | `campaign_ir.py` (`optimize_campaign` -> `SKIP_CACHED` at 0 tokens; AST local-import hashing) |
| Concurrent cache overwrite races | **Distributed Storage** (Optimistic Compare-And-Swap) | `W5` Optimistic CAS (`save_receipt_cache_cas` / `merge_receipt_cache` with `CacheConflictError` retry) |
| Out-of-order or stale verification | **Automata / Formal Verification** (Deterministic Finite State Machine) | `LoopStateMachine` (`PLAN -> STAGE -> VERIFY -> COMMIT -> CACHE` / `FAILED`, strict SHA match) |
| Half-written / broken multi-file edits | **Databases / Storage** (Copy-on-Write ACID Transactions) | `tx_patch.py` (`TransactionBuffer` + pre-commit syntax/JSON/`TQ-01..05` validation + `os.replace()`) |
| Context bloat across rounds | **Systems Architecture** (Process Isolation + Typed IPC) | `run_workflow` thin orchestrator (`agent(..., schema=WORKER_RESULT_SCHEMA, workspace="share")`) |
| Lost audit trail or silent regressions | **Database Logging** (Append-Only Write-Ahead Ratchet Ledger) | Append-only `results.tsv` Ratchet Ledger (`KEEP` / `REVERT` / `SKIP_CACHED` / `TRIPPED`) |
| Quota burn or stuck retry loops | **Operating Systems** (Resource Budgets & Fault Isolation) | Per-slice `max_rounds`, model tiering, `ErrorCircuitBreaker` (`error_sha256` deduplication) |
| Cross-domain leaks / unsafe paths | **Security** (Least-Privilege Object Capabilities) | `CRUCIBLE_ALLOWED_ROOTS` containment enforced at compile, `TransactionBuffer`, and spoke boundary |

## 3. Four Coding Guardrails (Worker Contract)
Every slice worker must enforce these four constraints before calling `finish`:
1. **State Assumptions First:** Declare target files, dependencies, and invariants before editing; halt on unresolved ambiguity.
2. **Zero Bloat:** Emit minimal, cohesive changes; never add unrequested abstractions, wrapper classes, or speculative helpers.
3. **Surgical Target-Path Edits Only:** Modify strictly the slice's declared `target_paths`; touch zero unrelated files or directories.
4. **Verifiable Success Criteria:** Validate every change with an executable check (`verify_cmd` / `scripts/verify_all.ps1`) and return `WORKER_RESULT_SCHEMA` (`slice_id`, `commit_sha`, `after_sha256`, `passed`, `error_output`).

## 4. Execution Engine & Deterministic Cycle
1. **In-RAM Staging (`python -` + `TransactionBuffer`):** Pipe a single Python script into `python -` importing `TransactionBuffer` from `crucible.tx_patch`. Never chain raw `edit_file`/`write_file` loops or leave temporary `.py` files on disk.
2. **FSM Progression (`LoopStateMachine`):** Advance each active slice strictly through `PLAN -> STAGE -> VERIFY -> COMMIT -> CACHE`. `verify(exit_code, staged_sha256, error_output)` rejects stale SHAs (`StateTransitionError`) and transitions to `FAILED` on non-zero exit.
3. **Worker Fan-Out (`run_workflow`):** Dispatch each wave with `parallel(wave, lambda ps: agent(build_slice_worker_prompt(ps, repo_root), schema=WORKER_RESULT_SCHEMA, workspace="share"))`.
4. **Ratchet & CAS Persistence:** Append a `RatchetEntry` row (`KEEP`, `REVERT`, `SKIP_CACHED`, or `TRIPPED`) to `results.tsv` via `append_ratchet_ledger()`, and persist cache updates atomically via `merge_receipt_cache()`.
5. **Error-Hash Circuit Breaker:** Feed failures into `ErrorCircuitBreaker`; trip immediately on **2 consecutive identical `error_sha256`** digests or **3 consecutive failed rounds**.

## 5. Three Domain Presets
| Preset | Per-Round Verification Gate |
| :--- | :--- |
| **Systems / Code** | `pwsh -NoProfile -File scripts/verify_all.ps1` (or `crucible_gate.py check --strict` + `doctor` `0 WARN | 0 FAIL` + targeted `pytest`) |
| **Spoke / Media** | Spoke `recognize -> prepare -> deliver` + `ig-evidence-review` (stage-matched per `K-MCP-01`) |
| **Research / Architecture** | Source-cited artifact updated + local link/drift check (`crucible_gate.py doctor`) |

## 6. Tier 1/2 Gates, Rewind & High-Signal Output Contract
- **Tier 1 / Tier 2 Gates:** Never execute destructive file deletions, `git reset --hard`, environment-wide installs (Tier 1), or remote `git push` / PR merges (Tier 2) without explicit operator approval.
- **Rewind:** Inspect checkpoints with `git log --oneline main..loop/<slug>` and revert cleanly per round commit.
- **High-Signal Output Contract:**
  - Lead with the verified outcome or next action; zero preamble or filler.
  - Use literal CS/CE/SE terminology only (zero metaphors).
  - Cap lists at `<= 5` items and report failures matter-of-factly (error + fix).
  - End with **1 concrete next action** (plus a ready-to-paste fresh-thread prompt anchored to branch and commit SHA on campaign completion).
