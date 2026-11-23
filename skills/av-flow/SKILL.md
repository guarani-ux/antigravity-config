---
name: av-flow
description: Ask which A/V scriptwriting skill or flow fits your situation. Router over the skills in av-story-skills.
disable-model-invocation: true
---

# AV Flow Router

You do not need to memorize every skill in this package. Ask which route fits your current project state.

Before recommending a step be skipped, read that skill's `SKILL.md`: the summaries below are for orientation only.

A **flow** is a path through the skills. Most projects travel along one **main flow**, with two **on-ramps** merging onto it and a shared **vocabulary layer** running underneath.

## Table of Contents

- [The main flow: brief -> quarry -> spine -> beats -> review](#the-main-flow-brief---quarry---spine---beats---review)
- [On-ramps](#on-ramps)
- [Vocabulary underneath](#vocabulary-underneath)
- [Phase boundaries](#phase-boundaries)

---

## The main flow: brief -> quarry -> spine -> beats -> review

Use this route when you have a video assignment, stakeholder brief, or documentary concept and need to produce a shoot-ready A/V script.

1. **`/av-quarry`** *(Explore)* sharpens the idea and builds `quarry.md`. It runs two tracks at once:
   - Spawns a background research agent to find authentic audience language, misconceptions, and friction in the wild.
   - Interviews you in **frontier rounds** on the stakeholder ask, on-camera talent/access, and real constraints.
   - Appends heterogeneous fragments (visual handles, room sounds, anecdotes, stakeholder non-negotiables) into `quarry.md` and pushes to coin the **Leading Word**.
   - **Hard boundary**: No script table or outline is allowed in `/av-quarry`.
2. **`/av-spine`** *(Design It 3 Ways)* reads `quarry.md` and spawns **3 parallel sub-agents**, each forced to build a radically different **Story Spine** (`Because -> But -> Therefore`) and Opening 10s Hook under a distinct narrative lens:
   - *Agent 1*: Revealed Design / Secret Access
   - *Agent 2*: Human Friction -> Relief Micro-Portrait
   - *Agent 3*: Contrarian Myth-Buster / Extreme Contrast
   It compares all three, gives an opinionated recommendation, and writes the chosen or hybridized spine to `spine.md`.
3. **`/av-beats`** *(Exploit: Pre-Shoot Script)* takes `spine.md` and `quarry.md` (treated as read-only) and builds `script.md`:
   - Settles **Audience Prerequisites** (what the viewer already knows walking in at second zero).
   - If filming real subject-matter experts (SMEs) or community members, generates the **Director's Field Interview Guide** (open anecdote-elicitation questions, never brochure prompts).
   - Builds the clean 3-column script (`SECTION / BEAT` | `AUDIO` | `VIDEO`, zero timecodes, zero WPM telemetry) beat by beat, enforcing **Dual-Channel Grounding (`Requires -> Grounds`)**, **Visual-First Subtraction**, **Physical Bridges**, **Voice-Off Completers**, and **Mouth-Shape Syntax**.
   - Can export to print-ready Landscape HTML (`Arial 14/12/10pt`) via `scripts/export_av_script.py`.
4. **`/av-review`** *(2-Axis Parallel Audit)* spawns **2 parallel sub-agents** to grade `script.md`:
   - **Smells Sub-Agent**: Hunts the 10 A/V Script Smells (*Left-Branching Essay Clause, Generic Plural Lecture, See-Say Mirroring, Verbal Pivot Seam, Wall-to-Wall Talking, Literary Triad, Surveillance Camera Angle, Ungrounded Payoff, Fake Verbatim Testimony, Timecode/WPM Clutter*).
   - **Brief & Custody Sub-Agent**: Verifies every stakeholder pillar from `quarry.md` is fulfilled, facts match source custody, and unfilmed interviewees have elicitation prompts rather than fake speeches.
5. **`/av-retro`** *(Close the Loop)* runs after you finish or hand-edit a script. It diffs your manual edits against the agent's draft and updates the smell baseline or `av-craft` so your taste becomes permanent.

## On-ramps

Starting situations that enter the flow at a different point:

- **You already shot the interviews and have `.srt` or `.txt` transcripts** -> **`/av-paper-edit`**.
  Treats your recorded transcripts as a **read-only quarry** of verbatim quotes. It sequences real spoken soundbites by causal value shifts, trims verbal filler without falsifying meaning, and writes minimal voiceover bridges only where a structural gap exists. Then run **`/av-review`** to verify custody and flow.
- **You already have a rich `quarry.md` of notes and audience research** -> start directly at **`/av-spine`**.

## Vocabulary underneath

One model-invoked reference skill runs beneath all the others as the single source of truth for craft and terminology:

- **`av-craft`**: Defines the shared vocabulary (**Leading Word**, **Dual-Channel Grounding**, **Visual-First Subtraction**, **Voice-Off Completer**, **Physical Bridge**, **Mouth-Shape Syntax**, **5-Shot Coverage**, **Optical Axis**) and holds the deep references on storytelling frameworks (`STORYTELLING-FRAMEWORKS.md`) and the six converging domains (`DOMAINS-AND-JUDGMENTS.md`).

## Phase boundaries

Between `/av-quarry`, `/av-spine`, `/av-beats`, and `/av-review`, decide how to manage your session context. Read [`PHASE-BOUNDARIES.md`](PHASE-BOUNDARIES.md) for the decision tree. Because each phase writes its state to disk (`quarry.md` -> `spine.md` -> `script.md`), you can either continue in one session or `/clear` at any boundary without losing your work.