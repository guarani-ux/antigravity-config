# Phase Boundaries in AV Story Skills

A **phase** is one stage of the writing flow: `/av-quarry` (exploration), `/av-spine` (spine design), `/av-beats` or `/av-paper-edit` (scripting), and `/av-review` (two-axis critique).

Because every skill persists its output to disk (`quarry.md`, `spine.md`, `script.md`), you have a clean decision point at every phase boundary.

## Table of Contents

- [The Decision Tree](#the-decision-tree)

---

## The Decision Tree

Work top to bottom at the boundary between two skills:

1. **Stay in the same session (Continue)** when the context window has plenty of room left. Keeping `/av-quarry` -> `/av-spine` -> `/av-beats` in one session preserves the tonal nuances of your answers alongside `quarry.md`.
2. **Clear context (`/clear`)** between `/av-spine` and `/av-beats` if the exploration phase was long and noisy. Because `quarry.md` and `spine.md` are on disk, `/av-beats` can start with a fresh, unpolluted context window.
3. **Sub-agents** are spawned automatically inside `/av-spine` (3 parallel spine designers) and `/av-review` (2 parallel review axes) so competing angles and reviews never pollute your main thread.