---
name: av-review
description: "Review an A/V script or Paper Edit along two independent axes using parallel sub-agents: Craft Smells (does it pass spoken-ear, counterpoint, grounding, and camera standards?) and Brief & Custody (does it fulfill the quarry/spine requirements and preserve source/interview integrity?). Use when reviewing script.md or paper-edit.md."
---

# AV Review (Two-Axis Parallel Critique)

Two-axis review of an A/V script (`script.md` or `paper-edit.md`):

- **Craft Smells**: Does the script pass spoken-ear, audiovisual counterpoint, grounding, and cinematography standards?
- **Brief & Custody**: Does the script faithfully deliver the originating `quarry.md` / `spine.md` obligations and honor documentary/transcript custody?

Both axes run as **parallel sub-agents** so one axis never masks the other, then this skill aggregates their findings side by side.

## Table of Contents

- [Process](#process)
  - [1. Locate the Script & Originating Sources](#1-locate-the-script-originating-sources)
  - [2. The 10 A/V Script Smells Baseline](#2-the-10-av-script-smells-baseline)
  - [3. Spawn Both Sub-Agents in Parallel](#3-spawn-both-sub-agents-in-parallel)
  - [4. Aggregate Without Merging](#4-aggregate-without-merging)

---

## Process

### 1. Locate the Script & Originating Sources
1. Identify the script file to review (`script.md`, `paper-edit.md`, or a path passed by the user).
2. Locate the originating brief/sources (`quarry.md`, `spine.md`, and any `.srt`/`.txt` transcript files if reviewing a Paper Edit).

### 2. The 10 A/V Script Smells Baseline
The **Craft Smells** sub-agent evaluates every row against these 10 baseline smells (*What it is* -> *How to fix*):

- **Left-Branching Essay Clause**: A spoken line starting with a dependent print clause (*"Long before a child reads a word..."*, *"When you consider..."*, *"While many people..."*). -> Rewrite to start with the person, action, or screen pointer.
- **Generic Plural Lecture**: Speaking about *"children," "parents,"* or *"customers"* in the abstract rather than pointing to the specific human on screen. -> Replace with a singular screen-anchored demonstrative (*"Look at her hands here. She's two."*).
- **See-Say Mirroring**: The `AUDIO` column names the exact same literal action or noun the `VIDEO` column is showing ($1 + 1 = 1$). -> Apply **Visual-First Subtraction**: delete the literal description from `AUDIO` so the voice carries only unseen meaning.
- **Verbal Pivot Seam**: Moving between beats via a brochure transition (*"And the design isn't only for..."*, *"Another important aspect is..."*). -> Replace with a **Physical Bridge** (an eye-line, gesture, or sound inside the frame).
- **Wall-to-Wall Talking**: A beat with continuous narration and no **Voice-Off Completer** (`[NAT SOUND POCKET]`). -> Stop the voice mid-setup and let a physical action + room sound finish the thought.
- **Literary Triad**: Three parallel nouns, verbs, or adjectives in a row (*"movement, rhythm, and touch"*). -> Cut to one concrete observable action.
- **Ungrounded Payoff**: A beat leaning on spatial geography or an emotional realization that no earlier beat grounded (`Requires -> Grounds` gap). -> Plant the visual or emotional prerequisite in an earlier beat.
- **Surveillance Camera Axis**: Vague *"B-roll of..."* placeholders or default standing adult eye-level tilting down. -> Specify camera height (`28" toddler axis`, `seated axis`), focal proximity (`35mm` vs `85mm`), and 5-Shot Sequence coverage.
- **Fake Verbatim Testimony**: Putting scripted brochure paragraphs in quotation marks for an unfilmed interviewee in a pre-shoot script. -> Convert to `[SOUNDBITE TARGET]` + an open anecdote prompt in the Interview Guide.
- **Timecode / Telemetry Clutter**: Timestamps (`00:00 - 00:20`) or WPM math printed inside a pre-shoot table. -> Strip them out.

### 3. Spawn Both Sub-Agents in Parallel
Issue both sub-agent calls in parallel and aggregate their reports:

- **Craft Smells Sub-Agent Prompt**:
  Pass the full text of the script and the 10 A/V Script Smells above.
  Brief: *"Inspect every beat and line of the script. Quote each hunk that exhibits one of the 10 A/V Script Smells, name the smell, and provide the exact rewritten line or shot fix. Under 450 words."*

- **Brief & Custody Sub-Agent Prompt**:
  Pass the full text of the script plus `quarry.md`, `spine.md`, and any source transcripts.
  Brief: *"Report: (a) any stakeholder requirement or non-negotiable from the quarry/brief that is missing or weak; (b) any factual claim, count, or date that drifts from the supplied source material; (c) for a Paper Edit, any quote that does not match the verbatim transcript; for a Pre-Shoot script, any missing interview elicitation prompt. Quote the exact lines. Under 400 words."*

### 4. Aggregate Without Merging
Present the two reports under `## Craft Smells` and `## Brief & Custody` headings. Do not merge or rerank findings across the two axes:
- A script that hits every stakeholder requirement but sounds like a brochure is **Craft Smells FAIL, Brief & Custody PASS**.
- A script that sounds cinematic and natural but drops a required pillar or alters a transcript quote is **Craft Smells PASS, Brief & Custody FAIL**.

End with a one-line summary of total findings per axis and offer to apply the fixes in place.