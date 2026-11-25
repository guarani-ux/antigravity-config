# Crucible Scale (`L1`–`L10`) — Canonical Ranking & Upstream Routing Benchmark

> **Single Benchmark:** Whenever we rank, scale, or evaluate any turn, system, or artifact across **Software/ML, Creative/A/V Craft, Institutional Governance, or Meta-Process**, we use this compressed 4-attribute scale.

## 1. The 4 Orthogonal Scalable Attributes (`1–10` each)

| Attribute | Measures | `1` (Baseline) | `5` (Structural) | `9` (Phase-Shift) | `10` (Paradigm) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`L` Leverage** | Failure-class & constraint shift | Single typo / symptom patch | Reusable guardrail or invariant | Orthogonal IR/schema/state-machine shift eliminating a failure *class* | Control-plane grammar transforming all subsystems |
| **`P` Proof** | Epistemic grounding & surprise | Unverified claim / confirms prior | Deterministic unit test / local repro | Empirical/statistical/adversarial proof overturning a core assumption | Real-world human/field (Rung-4) closed-loop proof |
| **`C` Custody** | Reversibility, authority & anti-Goodhart | Fragile / untracked mutation | Reversible edit + explicit holds | Ungameable mechanical gates + read-only epistemic locks | Sovereign human-calibration breaker + immutable audit trail |
| **`R` Reach** | Scope, persistence & realm transfer | Ephemeral one-off reply | Single module, form, or workflow | Multi-subsystem + cross-session persistent capability | Portable across `>=2` realms and any AI runtime |

## 2. Three Coupling Laws (Non-Masking, Never Averaged)
1. **Proof Caps Leverage:** `P <= 3` hard-caps rank at `<= L7` regardless of `L` (unverified theory is never `L9`).
2. **Custody Governs Reach:** High `R` with low `C` is amplified blast radius, not high rank; never widen `R` ahead of `C`.
3. **Bottleneck-First Upstream Routing (Intelligence Upstream):** Before executing a non-trivial turn, estimate `(L, P, C, R)` prospectively:
   - Match effort to target rank (never burn `L9` machinery on an `L2` task).
   - On consequential work, attack `min(L, P, C, R)` first (shift representation when rules pile up; add proof before claiming gain; lock custody before scaling reach).

## 3. Canonical Rank Gates (`L1`–`L10`)
- **`L1–L3` (Local — Silent):** `L <= 3` (lookup, single-step edit, localized fix).
- **`L4–L6` (Structural — Silent):** `L, P, C in 4..6` (verified multi-file slice, guardrail, integrated subsystem).
- **`L7–L8` (High-Leverage — Silent):** `L, P, C in 7..8` (bottleneck optimization, multi-agent synthesis *within* current paradigm).
- **`L9` (Phase-Shift / Critical Catch — `[LEVEL 9 NOTICE]`):** **`L >= 9` AND `P >= 9` AND `C >= 8`**.
- **`L10` (Paradigm Breakthrough — `[LEVEL 10 NOTICE]`):** **`L=10, P=10, C=10, R=10`** across `>= 2` realms.

## 4. `L9+` Notice Contract (Triggered on `L9` / `L10` ONLY)
Stay completely silent on `L1–L8`. When a turn clears `L9` or `L10`, append a `[LEVEL 9 NOTICE]` (or `[LEVEL 10 NOTICE]`) callout reporting:
1. **`(L, P, C, R)` vector & realm(s)**
2. **What happened in the process** (exact observed mechanism)
3. **Broken assumption / eliminated failure class**
4. **Reusable leverage unlocked**

## 5. Active In-Turn Crucible Meter (`T0 -> T1 -> T2` Gradient Loop)
Each user prompt -> reasoning/tool execution -> final reply is one **Turn**. Inside every turn, run the Crucible Meter synchronously at 3 phase transitions (silently on routine `L1–L8` turns; visibly in machine-readable JSON when the user explicitly requests a target rank like *"Give me a Level 9/10 course of action"*):
- **`T0` (Intake / Orient):** Score baseline `(L, P, C, R)` and identify `bottleneck = argmin(L, P, C, R)` relative to `target`.
- **`T1` (Pre-Act / Freeze):** Compute gradient move — refuse symptom patches when `target >= L9`; force representation shift (`L`), adversarial/empirical verification (`P`), custody lock (`C`), and reusable scope (`R`) before acting.
- **`T2` (Pre-Output / Verify):** Score realized `(L, P, C, R)` against `target`. **Never fake `L10`**: if `P=10` requires real-world human/field proof unavailable inside the turn, report the honest ceiling (e.g., `L9`, `gap: P=9->10 requires Rung-4 field test`) and the exact action to close it.

Machine-readable meter format (emitted when target rank is requested or `L9+` triggers):
```json
{"stage":"T2","target":"L10","vec":{"L":10,"P":9,"C":10,"R":10},"rank":"L9","bottleneck":"P","gap":"Rung-4 field proof","next_move":"Run 1 live shoot test"}
```

