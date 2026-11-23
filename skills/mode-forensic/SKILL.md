---
name: mode-forensic
description: Mode 3 — Cold-Start Forensic Audit. Activate when inspecting, auditing, or assessing an unfamiliar or partially built repo/folder. Strictly non-mutating; runs C:/Users/flowe/.gemini/config/scripts/code_graph.py --forensic to separate Wired Code from Hollow Stubs and Unverified Claims.
---

# Mode 3: Cold-Start Forensic Audit Protocol

## 1. Trigger & Strict Non-Mutation Invariant
- **When Active**: User asks *"What is the actual state of this repo/folder?"*, *"Audit this module"*, or begins work on a cold-start directory with prior session history.
- **Strictly Read-Only**: Zero file edits, zero silent "cleanup", and zero test modifications during a forensic audit. Never trust `README.md`, `STATUS.md`, or commit messages as proof of working code.

## 2. Mandatory Execution Step 1: Deterministic Graph Scan
Before reading prose documentation, run the global AST forensic scanner on the target directory:
```powershell
python C:/Users/flowe/.gemini/config/scripts/code_graph.py --root <target_dir> --forensic
```
If the codebase spans multiple subsystems (`>= 3` directories), delegate deep module inspections to parallel `invoke_subagent(TypeName="research")` workers.

## 3. Three-Bucket Forensic Classification (Required Output Format)
Every audited module or feature claim must be categorized into one of three empirical buckets with `file:line` citations:

| Classification | Definition | Required Evidence |
| :--- | :--- | :--- |
| **1. Wired & Verified** | Entrypoint reaches implementation, callers match signatures, and tests assert non-trivial invariants. | `[file.py](file:///<workspace>/path/to/file.py#L10-L45)` + live CLI/test exit status `0` with discriminating output. |
| **2. Hollow Stub / Dead Island** | Function body consists of `pass`, `...`, `TODO`, `NotImplementedError`, hardcoded mock returns, or has `0` inbound callers from any entrypoint. | Exact AST stub location from `code_graph.py --forensic` output. |
| **3. Unverified Claim / Drift** | `README.md` or docstrings claim a capability that either does not exist on disk or fails when invoked in a fresh process. | Side-by-side quote of doc claim vs. actual runtime error / missing symbol. |

## 4. Concrete Forensic Report Snippet
- **Wired & Verified**: `SQLiteGraphStore.query_callers` ([graph_store.py](file:///<workspace>/src/graph_store.py#L112-L148)) — wired to `--callers` CLI flag; verified against 14 AST nodes.
- **Hollow Stub**: `export_parquet_bundle()` ([exporter.py](file:///<workspace>/src/exporter.py#L88-L91)) — contains `pass # TODO: wire pyarrow`; 0 callers in production flow.
- **Unverified Claim**: `README.md` line 24 claims automatic cloud sync, but no network client or credential loader exists in the AST.

## 5. Closure & Next-Step Recommendation
Conclude with an explicit **Deficit Summary** (`IMPLEMENTATION_DEFICIT`, `VERIFIER_DEFICIT`, or `READY`) and list the exact 1–3 surgical tasks required if transitioning to [mode-worktree-build](file:///C:/Users/flowe/.gemini/config/skills/mode-worktree-build/SKILL.md).
