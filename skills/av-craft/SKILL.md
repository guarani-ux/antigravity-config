---
name: av-craft
description: Shared vocabulary, storytelling principles, cinematography rules, and anti-inclination checkpoints for Audio-Video (A/V) scriptwriting. Use whenever planning, writing, editing, or reviewing an A/V script, documentary treatment, YouTube script, interview guide, or paper edit.
---

# AV Craft (Shared Vocabulary & Anti-Inclination Discipline)

Single source of truth for the concepts, mechanics, and anti-inclination checkpoints shared across the `av-story-skills` suite (`/av-quarry`, `/av-spine`, `/av-beats`, `/av-paper-edit`, `/av-review`, `/av-retro`).

For deep theoretical and cross-domain reference, read:
- [`STORYTELLING-FRAMEWORKS.md`](STORYTELLING-FRAMEWORKS.md): Narrative mechanics (Bernard, Glass, McKee, Coyne, Eisenstein, Green & Brock).
- [`DOMAINS-AND-JUDGMENTS.md`](DOMAINS-AND-JUDGMENTS.md): How Communications, Marketing, Directing, Cinematography, Sound Design, and Documentary Custody converge.

## Table of Contents

- [Core Vocabulary & Mechanics](#core-vocabulary-mechanics)
- [Routing Default Requests](#routing-default-requests)

---

## Core Vocabulary & Mechanics

1. **Quarry (`quarry.md`)**: Heterogeneous raw material (visual handles, acoustic room sounds, lived audience language, human anecdotes, stakeholder non-negotiables) mined before structure is locked.
2. **Leading Word**: One load-bearing phrase or concrete physical image that names the emotional center of the whole piece (for example, *"the look back"*, *"first living room"*).
3. **Story Spine (`Because -> But -> Therefore`)**: A single causal chain connecting every beat from opening state to final realization. Replaces static **Topic Buckets** (*"And also..."*).
4. **Dual-Channel Grounding (`Requires -> Grounds`)**: Every beat logs what spatial geography or emotional fact it **Requires** (already shown to the viewer) and what new state it **Grounds** for the next beat, plus its polarity **Shift (`[State A] -> [State B]`)**.
5. **Visual-First Subtraction**: Draft the `VIDEO` action and `NAT SOUND` first. Ask what the viewer's eye already understands silently, then subtract that literal information from the `AUDIO` column so the voice only carries unseen meaning ($1 + 1 = 3$).
6. **Voice-Off Completer**: A 1.5–3 second `[NAT SOUND POCKET]` where the speaker sets up an expectation and stops talking while a physical action and spot sound finish the sentence on screen.
7. **Physical Bridge**: A transition between Beat $N$ and Beat $N+1$ triggered by a concrete physical action, sound, or eye-line inside the frame (never a verbal brochure pivot).
8. **Mouth-Shape Syntax**: Four mechanical edits applied to every spoken line before it enters the `AUDIO` column:
   - **Right-branching clauses**: Start directly with the person, action, or screen pointer (cut dependent openers like *"Long before..."*, *"When we opened..."*).
   - **Singular screen pointers**: Point at the specific person or object in the frame (*"Look at her hands here. She's two."*) rather than lecturing in generic plurals (*"Toddlers learn..."*).
   - **Single concrete images**: Break three-item literary lists into one observable detail.
   - **Jagged breath cadence**: Alternate a 10–14 word sentence with a 2–4 word fragment (*"It doesn't fit. She tries again. Click."*).
9. **5-Shot Coverage & Optical Axis**: Specify camera height (`28" toddler eye-level`, `seated bench axis`, `90-degree tabletop`), focal proximity (`35mm close presence` vs. `85mm candid compression`), and 5-shot coverage *(Hands, Eyes, Wide, OTS, Creative angle)* in the `VIDEO` column.
10. **Clean Page Contract**: `SECTION / BEAT` | `AUDIO` | `VIDEO` (or 2-column `VIDEO` | `AUDIO`). Zero timestamps/timecodes (`00:00`) and zero WPM telemetry numbers in pre-shoot script tables.

## Routing Default Requests

When a user asks to write or plan an A/V script without naming a specific skill:
1. If the brief is new and unshaped, run the `/av-quarry` -> `/av-spine` -> `/av-beats` progression (stopping after pitching spines unless the user asked for an immediate full table).
2. If the user provides recorded `.srt`/`.txt` transcripts, use `/av-paper-edit`.