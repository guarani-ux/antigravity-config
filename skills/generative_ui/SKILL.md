---
name: generative_ui
description: Comprehensive design system and interactive component library for rendering rich, responsive Generative UI widgets and standalone artifacts. Features 4 distinct style archetypes, adaptive auto-tile grid topologies, executable API cards, live telemetry terminals, and anti-slop craft standards.
---

# Generative UI — Advanced Component & Style Engine

This skill governs the creation of custom, interactive HTML user interfaces rendered inline in chat (`<agent-embed>`) or as standalone side-pane artifacts (`.html`). 

It elevates AI interfaces from generic corporate cards into **tactile, executable operational cockpits**.

---

## 1. Technical Constraints & Invariants

*   **Tailwind CDN**: Only use the allowlisted gstatic Tailwind library in `<head>`:
    ```html
    <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
    ```
*   **Semantic Theme Variables**: Never hardcode pure white or pure dark colors. Always bind to host design tokens:
    *   Surfaces: `bg-[var(--background)]`, `bg-[var(--card)]`, `bg-[var(--content)]`
    *   Borders: `border-[var(--border)]`
    *   Typography: `text-[var(--foreground)]`, `text-[var(--muted-foreground)]`
    *   Accents: `text-[var(--accent)]`, `bg-[var(--accent)]`
*   **Typography Floor**: Never use sub-12px micro-text (`text-[10px]`, `text-[11px]`). Maintain `text-xs` (12px) as the structural floor.
*   **Inline Embed Height Budget**: When inlining with `<agent-embed>`, content must comfortably fit within the **500px** height budget. Never use `h-screen`, `min-h-screen`, or `100vh` on the root container of an inline widget.

---

## 2. The 4 Style Archetypes

### Archetype 1: The Developer Command Matrix (Vercel / Linear / Raycast)
*Best for: API tooling, code inspectors, git repositories, outposts, and technical telemetry.*
*   **Aesthetic:** Deep obsidian, high-contrast crisp 1px borders (`border-slate-800`), monospace accents (`font-mono`), subtle cyan/emerald glowing indicators.
*   **Card Container:**
    ```html
    <div class="bg-[var(--card)] border border-[var(--border)] hover:border-sky-500/50 rounded-xl p-5 transition-all shadow-sm">
      <div class="flex items-start justify-between">
        <span class="text-xs font-mono text-sky-400 font-semibold uppercase tracking-wider">DOMAIN 01</span>
        <span class="px-2 py-0.5 rounded text-xs font-mono bg-emerald-950/70 text-emerald-400 border border-emerald-800">ACTIVE</span>
      </div>
      <h3 class="text-base font-semibold text-white mt-1">Runtime Coordinator</h3>
      <p class="text-xs text-[var(--muted-foreground)] mt-2">Core execution state and privileged authority gates.</p>
    </div>
    ```

### Archetype 2: The Analog Hardware Console (SSL 4000 / Studio Rack)
*Best for: Audio engineering, multi-track mixing, bus routing, priority scheduling, and gain staging.*
*   **Aesthetic:** Dark industrial slate, mechanical rack ear screws, vertical channel strips, multi-segment VU meters, warm gold/amber LEDs, tactile mute/solo toggles.
*   **Rack Strip:**
    ```html
    <div class="w-44 bg-slate-900 border border-slate-800 rounded-lg p-3.5 flex flex-col justify-between">
      <div class="text-xs font-mono text-slate-400 text-center pb-1 border-b border-slate-800 font-bold">CH 05 • VOCAL BUS</div>
      <div class="my-4 flex justify-center gap-1.5">
        <!-- Multi-segment VU Meter -->
        <div class="w-3 h-24 bg-slate-950 rounded-full p-0.5 flex flex-col justify-end gap-0.5">
          <div class="w-full h-2 bg-rose-500 rounded-sm"></div>
          <div class="w-full h-3 bg-amber-400 rounded-sm"></div>
          <div class="w-full h-12 bg-emerald-400 rounded-sm"></div>
        </div>
      </div>
      <div class="text-center font-mono text-xs text-white">-6.2 dBFS</div>
      <button class="w-full py-1 text-xs bg-amber-600 hover:bg-amber-500 text-slate-950 font-mono font-bold rounded mt-2">SOLO</button>
    </div>
    ```

### Archetype 3: The Spatial Citadel / Tactical HUD (Playable World / RPG)
*Best for: Map exploration, world building, provinces, fortress passes, quest systems, and spatial nodes.*
*   **Aesthetic:** Midnight navy/obsidian, coordinate grids, sigil badges, province borders, territory status chips, gold/purple faction colors.
*   **Territory Card:**
    ```html
    <div class="border border-slate-800 hover:border-purple-500/60 bg-slate-950/80 p-5 rounded-xl transition-all cursor-pointer">
      <div class="flex items-center justify-between">
        <span class="text-xs font-mono text-purple-400 font-bold">PROVINCE 04</span>
        <span class="text-xs font-mono px-2 py-0.5 bg-purple-950 text-purple-300 rounded border border-purple-800">TIER-1 GATE</span>
      </div>
      <div class="text-base font-bold text-white mt-2">The Iron Sluice Pass</div>
      <div class="text-xs text-slate-400 mt-1">Mountain Chokepoint • 14 Fortress Gates</div>
      <div class="mt-4 pt-3 border-t border-slate-900 text-xs font-mono text-purple-400">Endpoint: /provinces/iron-sluice</div>
    </div>
    ```

### Archetype 4: The Epistemic Data Table / Live Cockpit
*Best for: Job hunting dossiers, telemetry feeds, financial tables, test receipt ledgers.*
*   **Aesthetic:** Clean high-density rows, zebra striping, monospace metrics, status pills, and right-aligned action buttons.

---

## 3. Auto-Tile & Adaptive Grid Topologies

### 1. Responsive Auto-Fit Grid (Zero Hardcoded Columns)
Automatically wraps cards cleanly from phone screens to wide monitors without media query clutter:
```html
<div class="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-5">
  <!-- Dynamic cards populate here -->
</div>
```

### 2. The Master-Detail Cockpit (Grid + Live Inspection Drawer)
Left side holds the card grid (65% width); right side holds a live interactive inspection drawer (35% width) that updates whenever a card is clicked.

### 3. The Horizontal Scroll Rack
For audio faders, timeline events, or pipeline steps:
```html
<div class="flex gap-4 overflow-x-auto pb-4 custom-scroll">
  <!-- Horizontal channel strips -->
</div>
```

---

## 4. Interactive & Executable Element Library

### 1. Action Trigger Button with Live Feedback State
Never leave the user wondering if a button clicked. Always implement visual state transitions:
```javascript
function executeTrigger(btn, actionName, command, resultText) {
  const originalText = btn.innerHTML;
  btn.innerHTML = `<span class="animate-spin inline-block mr-1">⟳</span> Running...`;
  btn.disabled = true;

  setTimeout(() => {
    btn.innerHTML = `✔ Executed`;
    btn.classList.remove('bg-sky-600', 'hover:bg-sky-500');
    btn.classList.add('bg-emerald-600', 'text-white');
    
    // Log to terminal
    logTerminal(actionName, command, resultText);

    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.disabled = false;
      btn.classList.remove('bg-emerald-600', 'text-white');
      btn.classList.add('bg-sky-600');
    }, 2000);
  }, 600);
}
```

### 2. Live Telemetry & Execution Terminal
Embed a terminal drawer at the bottom of the interface so actions emit real receipts:
```html
<div class="border border-slate-800 bg-black/80 rounded-xl p-4 font-mono">
  <div class="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
    <div class="flex items-center gap-2 text-xs text-slate-400">
      <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
      <span class="font-semibold tracking-wider text-slate-300">EXECUTION TELEMETRY TERMINAL</span>
    </div>
    <button onclick="clearTerminal()" class="text-xs text-slate-400 hover:text-white uppercase font-bold tracking-wider">Clear</button>
  </div>
  <div id="terminal-logs" class="text-xs text-slate-300 space-y-1.5 max-h-48 overflow-y-auto custom-scroll">
    <div class="text-slate-500">// System ready. Click any action card above.</div>
  </div>
</div>
```

### 3. Copy-to-Clipboard Chip with Toast Animation
```javascript
function copyEndpoint(text, el) {
  navigator.clipboard.writeText(text);
  const orig = el.innerText;
  el.innerText = "COPIED!";
  el.classList.add("text-emerald-400");
  setTimeout(() => {
    el.innerText = orig;
    el.classList.remove("text-emerald-400");
  }, 1200);
}
```

### 4. Client-Side Instant Filter & Search Bar
```javascript
function filterCards(query) {
  const cards = document.querySelectorAll('.card-item');
  const q = query.toLowerCase();
  cards.forEach(card => {
    const text = card.innerText.toLowerCase();
    card.style.display = text.includes(q) ? 'block' : 'none';
  });
}
```

---

## 5. Anti-Slop UI Craft Standards (Impeccable Craft Floor)

Every UI artifact or embed built under this skill must pass Paul Bakaus's `impeccable detect` deterministic craft gate with **zero anti-patterns**.

1.  **Ban Zero-Offset Chromatic Glows (`[dark-glow]`)**:
    *   Never use zero-offset chromatic halos (`box-shadow: 0 0 15px rgba(56, 189, 248, 0.5)`). They are the universal dead giveaway of amateur AI mockups.
    *   Use directional elevation with true y-offset and soft spread: `box-shadow: 0 4px 12px -2px rgba(0, 0, 0, 0.4)`.
2.  **Ban Nested Cards (`[nested-cards]`)**:
    *   Never place a card container inside an existing card container. Cards inside cards create visual sludge and excessive boxed depth.
    *   Flatten the hierarchy: structure inner content using whitespace (`gap-3`), typography scale, hairline dividers (`border-t border-slate-800`), and tabular alignment.
3.  **Ban Fake Pulsing Status Dots (`[pulsing-dot]`)**:
    *   Never put `animate-pulse` on a decorative status dot in navigation or headers unless tied to a live streaming websocket or actively fluctuating payload. A steady, solid dot (`bg-emerald-500`) with precise text is honest and calm.
4.  **Strict Contrast Floor (`[low-contrast]`)**:
    *   Body and placeholder text must have ≥4.5:1 contrast against surface ground.
    *   Large text (≥18px bold or ≥24px regular) must have ≥3:1 contrast.
    *   Secondary text must be tinted from surface hue or ink, never flat uncalibrated gray or washed-out pastels.
5.  **Obvious Typography Scale (`[flat-type-hierarchy]`)**:
    *   Adjacent heading and body roles must differ by at least 1.25× in size.
    *   Never collapse H1, H2, and body around 14px–16px. Establish clear contrast: Title (24px–32px), Subsection (18px–20px), Body (14px–16px), Metadata/Code (12px).
6.  **Semantic Heading Hierarchy (`[skipped-heading]`)**:
    *   Never skip heading levels (e.g. `<h1>` immediately followed by `<h3>`). Screen readers and document outlines require unbroken sequential levels (`<h1>` -> `<h2>` -> `<h3>`).
7.  **Ban Eyebrows on Every Section (`[eyebrows]`)**:
    *   Do not reflexively place a micro-all-caps eyebrow/kicker above every single heading. The heading carries its own weight; let it speak directly.
8.  **Browser Surface Theming (`[browser-surfaces]`)**:
    *   Theme what you didn't draw: style custom scrollbars (`::-webkit-scrollbar`), selection highlights (`::selection`), input carets (`caret-color`), and set `font-variant-numeric: tabular-nums` on all tabular and metric data.
9.  **Verification Gate**:
    *   Run `impeccable detect <file>` or verify that the DOM has 0 findings before presenting to the user.
