---
name: av-scriptwriting
description: Audio-Video (A/V) scriptwriting, documentary pre-shoot scripting, YouTube script development, and paper-edit system. Actively counterbalances LLM print-prose biases through Visual-First Subtraction, the Print-to-Speech Mouth-Shape Pass, Dual-Channel Grounding (Requires -> Grounds), Physical Bridge Transitions, and clean no-timecode tables.
---

# Audio-Video (A/V) Scriptwriting System

Use this skill whenever planning, researching, outlining, writing, or revising an Audio-Video (A/V) script, documentary pre-shoot package, YouTube script, institutional/community film, or post-shoot paper edit.

## Why This Skill Exists: Counterbalancing Default AI Inclinations

Left to its default training, a language model writes A/V scripts like written essays with B-roll pasted beside them:
1. It writes **print syntax** (left-branching clauses, literary rules-of-three, generic plurals) instead of spoken human mouth-shapes.
2. It drafts the `AUDIO` column first as a complete radio essay, then fills `VIDEO` with redundant illustrations (**See-Say**).
3. It maps prompt requirements into separate **topic buckets** glued together with verbal pivots (*"And it's not just for..."*).
4. It talks wall-to-wall because it fears empty cells.
5. It rushes to output a full script table in one turn before the human director has chosen the story spine.

This skill replaces those defaults with **mechanical checkpoints and process reversals**.

For deep domain references and export tools, consult:
- [`references/storytelling-frameworks.md`](references/storytelling-frameworks.md) — Core narrative engines (Bernard, Glass, McKee, Coyne, Eisenstein, Green & Brock).
- [`references/domains-and-judgments.md`](references/domains-and-judgments.md) — How Communications, Marketing, Directing, Cinematography, Sound Design, and Documentary Custody negotiate trade-offs.
- [`scripts/export_av_script.py`](scripts/export_av_script.py) — Clean print-ready Landscape HTML/Markdown exporter (Arial 14/12/10pt, zero timecode/WPM clutter).

---

## Stage 1: Diagnosis, Grounding & Spine Candidates (Stop Here First)

Unless the user explicitly asks for a full script immediately, **stop at the end of Stage 1** so the user can choose the spine before you build the table.

### Step 1.1: Classify the Input & Custody Mode
Identify which material you are working from:
- **Mode A — Scripted VO / Presenter:** Word-for-word spoken script.
- **Mode B — Pre-Shoot Documentary / SME Hybrid:** Real subject-matter experts (SMEs) or community members will be filmed. Deliver (1) a **Director's Field Interview Guide** (open prompts that elicit stories/feelings, not lectures) and (2) the **A/V Script** separating scripted `[V.O. / ON-CAMERA]` bridges from `[SOUNDBITE TARGET]` moments.
- **Mode C — Post-Shoot Paper Edit (Transcript Quarry):** The user provides recorded transcripts (`.srt` / `.txt`). Treat the transcript as a read-only quarry: build the script out of **exact verbatim quotes** (preserving speaker and attribution), trimming filler without altering meaning, and writing minimal VO bridges only where a structural gap exists.

### Step 1.2: Establish Audience Prerequisites (`Walk-In State`)
State clearly:
1. **Who is watching & their Awareness Level (New / Casual / Core):** What misconception or friction do they walk in with at second zero?
2. **Stakeholder Translation:** What are the institutional non-negotiables, and how do we subordinate them under **one human story spine**?
3. **The Leading Word:** Coin or identify a single compact phrase or image that anchors the emotional truth of the whole piece (e.g., *"the look back"*, *"first living room"*).

### Step 1.3: Pitch 2–3 Distinct Opening + Story Spine Candidates
Present **2–3 genuinely different Story Spines** (each with its opening 10-second visual/audio hook and its causal `Because / But / Therefore` chain). Show what each angle unlocks, and ask the user to pick or hybridize one before drafting the script table.

---

## Stage 2: The 5 Anti-Inclination Checkpoints (During Drafting)

Once the spine is chosen (or if the user asked for the script directly), build the script beat-by-beat using these **five mandatory process reversals**:

### Checkpoint 1: The Dual-Channel Grounding Ledger (`Requires → Grounds`)
Every beat has two jobs: it leans on what the viewer has *already seen or felt* (**Requires**), and it plants the spatial or emotional setup that the *next* beat needs (**Grounds**).
- **Spatial Grounding:** Before cutting to a tight interaction across a room (e.g., an eye-line match between a child on the floor and a parent on a bench), an earlier shot must visually ground the geography of the space.
- **Value Shift (`[State A] → [State B]`):** Every beat must turn the emotional or epistemic polarity. If a beat begins and ends in the same state, cut or merge it.

### Checkpoint 2: Visual-First Subtraction (Counteracting "Radio Essay + B-Roll")
Reverse your internal drafting order for every row:
1. **Design the `VIDEO` action + `NAT SOUND` first:** Specify the concrete physical behavior, camera height/axis, focal proximity, and 5-Shot Sequence coverage *(Hands, Eyes, Wide, OTS, Creative angle)*.
2. **Ask:** *"What does the viewer's eye already understand just by watching this shot and hearing the room?"*
3. **Subtract that from `AUDIO`:** Never let the voice describe what the picture is already showing. Choose one of three timing choreographies for the beat:
   - **Picture Lead (Visual Puzzle $\rightarrow$ Voice):** Show the physical action + nat sound for 2 seconds *before* the voice enters to reveal what it means.
   - **Voice Setup $\rightarrow$ Visual Punchline (Voice-Off Completer):** Have the speaker set up the thought (*"And watch who she looks for the second it fits—"*), then **stop talking** while the visual cut and spot sound finish the sentence.
   - **Contrapuntal Contrast:** Pair kinetic visual energy with quiet, intimate reflection (or a still portrait against bustling room sound).

### Checkpoint 3: The Physical Bridge Lock (Counteracting Topic Buckets)
Never transition between beats using verbal brochure pivots (*"And the design isn't only for..."*, *"Another benefit is..."*, *"Beyond that..."*).
- Every transition from Beat $N$ to Beat $N+1$ must be caused by a **physical action, sound, or eye-line inside the frame** (e.g., the child turns to look at the bench $\rightarrow$ we cut to the bench; a toddler carries a book through the glass doors $\rightarrow$ we follow them into the wider library).

### Checkpoint 4: The Print-to-Speech Mouth-Shape Pass (Counteracting Written Prose)
Language models naturally write essay syntax. Before any spoken line enters the `AUDIO` column, run all four mechanical rewrites:
1. **Cut Left-Branching Openers:** Rewrite sentences that start with dependent clauses (*"Long before a child reads a word, their brain..."*, *"When we opened in 2016, we..."*). Start directly with the person, the action, or a demonstrative pointer:
   - *Print:* `"Long before a child ever sounds out a word on a page, their brain has to learn how patterns fit together."`
   - *Spoken:* `"She's two. She's not reading words on a page yet. Right now, she's just trying to figure out why this wooden gear won't turn."`
2. **Point at the Screen (Singular over Generic Plurals):** Replace abstract plural nouns (*"toddlers," "caregivers," "children"*) with singular, screen-anchored demonstratives (*"Look at her hands here," "Watch this kid," "That bench right behind him"*). Speak as someone looking at the frame alongside the viewer.
3. **Break Literary Triads:** When you catch yourself writing three parallel nouns, verbs, or adjectives (*"movement, rhythm, and touch"*), cut it to one concrete action or split it across breaths.
4. **Jagged Breath Cadence:** Alternate sentence lengths. Follow a 10–14 word sentence with a 2–4 word fragment (*"It doesn't fit. She tries again. There."*).

### Checkpoint 5: Particular Before Universal (Ira Glass Rule)
In every beat, ground the **concrete physical observation (the anecdote)** before offering the **reflection (why it matters)**. Never let a speaker state a thesis until the viewer has seen the human moment that proves it.

---

## Stage 3: Table Format & Clean Output Contract

1. **Columns:**
   - **3-Column (Default):** `SECTION / BEAT` | `AUDIO (VOICE / NAT SOUND / SFX)` | `VIDEO (FRAMING / ACTION / COVERAGE)`
   - **2-Column (On Request):** `VIDEO` | `AUDIO`
2. **Clean Page Rule:**
   - **Zero Timecodes / Timestamps:** Do not put `00:00 – 00:20` in the script table (unless logging an existing locked cut).
   - **Zero WPM / Telemetry Math:** Regulate duration silently through line economy and beat count. Never print WPM numbers or system jargon on the user-facing script.
3. **Clear Audio Tagging:**
   - `[NAT SOUND OPEN / POCKET]:` Specific room acoustics or physical action sounds where voice is silent.
   - `SPEAKER (V.O.):` Spoken over B-roll.
   - `SPEAKER (ON-CAMERA):` Spoken directly on screen (keep short: 1–2 natural sentences at a time).
   - `[SOUNDBITE TARGET — SPEAKER]:` In pre-shoot documentary scripts, state the emotional/narrative beat the interviewee covers in their own words, plus a natural spoken example in italics.
   - `[J-CUT / L-CUT]:` Mark where audio leads or trails the visual cut by 1–2 seconds.

---

## Stage 4: Pre-Output Verification Pass

Before outputting the script, scan every row in the `AUDIO` and `VIDEO` columns against these 5 red flags. If any row triggers a flag, rewrite that row before showing the user:

- [ ] **Flag 1 (Left-Branching Print Clause):** Does any spoken sentence begin with *"Long before..."*, *"When you consider..."*, *"By providing..."*, or *"In order to..."*? $\rightarrow$ *Rewrite to start with subject/action.*
- [ ] **Flag 2 (Generic Plural Lecture):** Is the speaker lecturing about *"children"* and *"parents"* in the abstract instead of pointing to the specific human moment on screen? $\rightarrow$ *Anchor to the singular person in the shot.*
- [ ] **Flag 3 (See-Say Mirroring):** Does the voice say the same noun the camera is currently showing? $\rightarrow$ *Subtract from audio or shift timing so picture leads voice.*
- [ ] **Flag 4 (Verbal Pivot Seam):** Does any beat open with a topic-change phrase (*"And it's not just for..."*, *"Another important part..."*)? $\rightarrow$ *Replace with a physical visual bridge.*
- [ ] **Flag 5 (Continuous Talking):** Does any beat lack a moment where the voice stops so nat sound and a human reaction can land? $\rightarrow$ *Insert a 2-second Voice-Off Pocket.*
