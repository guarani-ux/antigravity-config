---
name: cl-craft
description: Shared vocabulary, 20-second hiring manager triage mechanics, Selection Regime calibration (Mandate vs. Institutional Rubric), 4-Sentence Transduction rules, and the 12 LLM Cover Letter Anti-Smells. Use whenever decoding a JD, pitching angles, drafting, or reviewing a cover letter.
---

# Cover Letter Craft & Anti-Slop Discipline (`cl-craft`)

A cover letter fails the moment a hiring manager recognizes that an LLM wrote it, or when it merely repeats the resume in full sentences. This skill is the shared discipline layer underneath `/cl-vault`, `/cl-decode`, `/cl-angles`, `/cl-draft`, `/cl-review`, and `/cl-retro`.

For deep reference specs, read:
- [`SMELLS-AND-REGIMES.md`](./SMELLS-AND-REGIMES.md) — The 20-Second Eye-Tracking Reality, Selection Regime Switch (`Private Mandate` vs. `Institutional Rubric`), and the **12 LLM Cover Letter Smells** with mechanical counter-rules.
- [`TOPOLOGIES-AND-TRANSDUCTION.md`](./TOPOLOGIES-AND-TRANSDUCTION.md) — Resume-vs-Letter Orthogonality, the **4-Sentence Transduction Formula**, and the **4 Structural Topologies**.

## Table of Contents

- [1. The Orthogonality Law (Resume vs. Cover Letter)](#1-the-orthogonality-law-resume-vs-cover-letter)
- [2. The 20-Second F-Pattern Triage Rules](#2-the-20-second-f-pattern-triage-rules)
- [3. Selection Regime Calibration](#3-selection-regime-calibration)
- [4. The 12 Cover Letter Smells (Quick Reference)](#4-the-12-cover-letter-smells-quick-reference)
- [5. Zero-Fabrication Proof Custody](#5-zero-fabrication-proof-custody)

---

## 1. The Orthogonality Law (Resume vs. Cover Letter)

- **The Resume** is the *Backward-Looking Accounting Ledger* (`Action Verb + System + Metric`).
- **The Cover Letter** is the *Forward-Looking Causal Decision Log* (`Friction/Constraint` $\rightarrow$ `Judgment & Trade-off` $\rightarrow$ `Verified Result` $\rightarrow$ `Target Role Transfer`).
- **Hard Rule**: Never write *"As you can see on my resume..."* or turn a resume bullet into a standalone sentence without adding the unwritten constraint and judgment call behind it.

---

## 2. The 20-Second F-Pattern Triage Rules

Eye-tracking studies show that hiring managers give a cover letter a **3-to-5 second initial bounce test** followed by a **15-to-20 second F-pattern scan**:
1. **First Fixation (Lines 1–2)**: Must state your operational identity and a sharp observation about *their* mandate within 35 words. If Paragraph 1 could be sent to a competitor by swapping `[Company Name]`, rewrite it.
2. **Left-Margin Vertical Sweep**: Keep paragraphs under 4–5 lines (max 65–75 words in Mandate Mode) with concrete numerals and proper nouns that catch the eye.
3. **Sign-Off**: Close with peer-level professional parity, never obsequious begging.

---

## 3. Selection Regime Calibration

Always verify which regime applies in `jd-xray.md`:
- **`Private Mandate Mode`** *(Tech, Corporate, Agencies)*: 250–320 words. Focus 100% on the **2-Pillar Bridge** (solving their hidden 90-day bottleneck). Skip table-stakes HR boilerplate.
- **`Institutional Rubric Mode`** *(Universities, Municipalities, Public Libraries, Civil Service)*: 400–550 words. Search committees score applications on an auditable KSA rubric; explicitly evidence every Minimum and Desirable Qualification inside the narrative while preserving human cadence.

---

## 4. The 12 Cover Letter Smells (Quick Reference)

Full definitions and syntactic replacements are in [`SMELLS-AND-REGIMES.md`](./SMELLS-AND-REGIMES.md):
1. `RULE_NO_FLATTERY_OPENER` — Ban *"I was thrilled to apply..."* and unearned company praise.
2. `RULE_ASYMMETRIC_SYNTAX` — Ban 3-item symmetric triads (`X, Y, and Z` gerunds or adjectives).
3. `RULE_ZERO_EMPTY_INTENSIFIERS` — Ban *passionate, seamlessly, spearheaded, transformative, pivotal, synergy, testament*.
4. `RULE_NON_CHRONOLOGICAL_PROOF` — Ban chronological life-story recaps (*"My career began..."*, *"Throughout my career..."*).
5. `RULE_NO_SELF_EVALUATION` — Never call yourself *"the ideal candidate"* or *"uniquely qualified"*; prove it with facts.
6. `RULE_GROUNDED_CAUSAL_METRICS` — Every metric must state its baseline and causal mechanism.
7. `RULE_ACTIVE_DECLARATIVE_SYNTAX` — Ban dangling participial openers (*"Having managed..."*, *"Leveraging..."*).
8. `RULE_LITERAL_ENTERPRISE_GROUNDING` — Ban essay metaphors (*tapestry, beacon, journey, symphony*).
9. `RULE_DYNAMIC_TYPOGRAPHY` — Vary paragraph lengths (2–3 line hook, 4–5 line proof blocks, 2-line close).
10. `RULE_EMPLOYER_MANDATE_CENTRIC` — Frame 85% of sentences around solving the employer's problem, not fulfilling personal career dreams.
11. `RULE_CONCRETE_NOUN_ANCHOR` — Every sentence must name at least one tangible domain object, tool, metric, or deliverable.
12. `RULE_CONFIDENT_DIRECT_CLOSE` — Ban timid, over-hedged closings (*"Humbly grateful for the opportunity..."*).

---

## 5. Zero-Fabrication Proof Custody

Every paragraph in `cover-letter.md` must end with `<!-- ref: STORY-ID -->` or `<!-- ref: PHIL-ID -->` matching an entry in `vault/career-quarry.md`. `scripts/export_cover_letter.py` mechanically blocks export if any claim is unreferenced or if any number drifts from the quarry.
