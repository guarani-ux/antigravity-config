---
name: zero-trust-architect
description: Architectural patterns and procedural guidance for high-assurance software engineering tasks. Covers candidate isolation, deterministic evidence-bound verification, bounded repair iteration, and procedural separation of duties.
---

# ZERO-TRUST ARCHITECTURE PATTERNS (SOFTWARE 3.0)

This skill provides procedural patterns for high-assurance software development tasks requiring structured isolation, deterministic execution records, and bounded iteration. It is an optional high-assurance method, not a universal mandate for routine software edits.

---

## 1. Operating Alignment & Acceptance Contract

All candidate qualification, verification custody, and task acceptance are governed by the single operating contract in `IDEAS.md` (with 3-Tier Reversibility, Honesty, and 3-Strike Governor defined in `GEMINI.md` §§ 3–4). This skill provides architectural patterns supporting that contract; it does not introduce an alternative acceptance oracle or parallel ledger.

---

## 2. Architectural Patterns & Enforcement Realism

1. **Procedural Separation of Roles (Coordination Pattern, Not OS Security):**
   - Main conversation thread coordinates state and tracks invariants.
   - Code generation may be scoped to a candidate proposal step.
   - Verification may be assigned to a dedicated evaluation step.
   - *Epistemic note:* Delegating verification to a separate model subagent persona does **not** constitute independent validation. A subagent shares model biases and lacks verification authority unless bound to **external, deterministic contact** (e.g., test suite exit codes, linters, compiler checks, or human review).

2. **Isolated Candidate Staging:**
   - Candidate modifications should be isolated from protected branches or deployment targets (e.g., in a scratch directory, staging path, or ephemeral Git worktree).
   - Candidate changes are evaluated within their staging boundary before promotion.
   - Worktree isolation requires a functioning local Git repository and explicit branch management; it is a repository workspace pattern, not a virtualization container.

3. **Mechanical Guardrails Depend on Verified Host Infrastructure:**
   - Procedural guidelines cannot mechanically intercept tool calls on their own.
   - True mechanical prevention requires an installed, active, and verified host enforcement adapter (e.g., PreToolUse hook returning deny or `force_ask`, or operating system ACLs).
   - In the absence of a qualified mechanical guard, procedural rules rely on voluntary agent compliance, which must not be misrepresented as a tamper-resistant security boundary.

4. **Bounded Iteration:** Follow the 3-Strike Governor in `GEMINI.md` §3 — halt after 3 failed iterations on the same defect for a root-cause assessment.
