---
name: meeting-brief
description: Turn a meeting transcript into a scannable executive Meeting Brief with settled decisions, owned next steps, waiting-on owners, risks/tension, optional follow-up draft, and typed handoffs for Calgary Public Library production skills and Working_Context.md.
---
# Meeting Brief

Turn noisy meeting transcripts into a scannable executive brief (~1 page / <=400 words for the core brief) and optional downstream handoffs below a divider. Never write passive chronological notes.

1. **Clean honestly:** Fix obvious ASR name/term glitches without altering meaning. Keep quote anchors verbatim and put obvious ASR fixes in `[brackets]`. Mark unclear speakers `[confirm speaker]` and unverified details `unknown` or `hypothesis` (never fabricate dates, owners, quotes, or policy rules).
2. **Extract 4 sharp cuts (omit empty buckets instead of inventing filler):**
   - **Settled vs. Hype:** List only genuinely decided items, each with a short verbatim quote anchor. Never promote brainstorm enthusiasm to settled.
   - **Actions & Waiting-On:** Split into the owner's immediate leverage-ordered next steps, a `Waiting On Others` table (`Owner | Owed | Date`), and hard deadlines (asterisk tentative dates).
   - **Risks, Gaps & Tension:** Surface unanswered blocking questions, scope/workload traps, and (when relevant to media production) one-off stunt vs. repeatable series leverage plus active `policy.json` deliverable rules.
   - **Meta Check:** End the core brief with 1-2 falsifiable assumptions for the owner to confirm.
3. **Single-pass by default:** Process transcripts in one direct pass. Only split into read-only chunk extractors on multi-hour transcripts (>15,000 words), and always reconcile chunks end-to-end so later reversals override earlier decisions.
4. **Optional section below a horizontal divider (include only when applicable):**
   - **Follow-Up Draft:** A 3-5 line ready-to-send Teams/email nudge only when follow-up is actually needed.
   - **Production Handoff (`calgary-library-production`):** If `calgary-library-production` is mounted, conform to its schema; otherwise emit clean blocks using these keys:
     - *Kickoff/Brainstorm:* `sources[]` (`id`: `"S1"`, `origin`, `role`: `request|fact|permission|context|style_example`, `text`, `quote`, `status`: `verified|hypothesis|unknown`, optional `owner`, `resolve_by`), `decision_records[]` (`id`: `"DR1"`, `question`, `answer`, `decided_by`, `date`), and concept seeds.
     - *Review:* `review_log[]` (`comment_id`, `author`, `category`: `factual_mandatory|scope_tradeoff|creative_taste|premature_execution`, `decision`: `accepted|rejected|deferred|escalated`, `rationale`, `applied_in_version`).
     - *Debrief:* `wrap_actuals` (`actual_shoot_hours`, `actual_edit_hours`, `dropped_shots_or_beats`, `retention_notes`, `policy_or_desk_friction`).
   - **`Working_Context.md` Delta:** Propose 1-2 lines (settled decisions and links) in chat only if durable context changed; never edit Drive without explicit user confirmation.
