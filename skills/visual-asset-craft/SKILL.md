---
name: visual-asset-craft
description: "Use when the user needs to create, design, extract, or render graphics, visual overlays, title cards, diagrams, or scene assets for a video, screen recording, presentation, or campaign from a photo, video clip, screen capture, or brief. Manages deterministic programmatic rendering (transparent PNG/SVG overlays), generative diffusion scenes, and video frame extraction."
---

# Visual Asset Craft (Production Graphic & Video Asset Engine)

This skill governs the production of production-ready visual assets for video creators, editors, and filmmakers.

When the user says:
> *"I'm making a video and I need a graphic. Here is a screen recording / photo / video / description..."*

This skill replaces vague AI text prompting with **director-level visual asset crafting**: precise canvas dimensions, transparent alpha channels, color-palette matching, and clean asset delivery ready to drag into DaVinci Resolve, Premiere Pro, Final Cut, or CapCut.

---

## 1. The 3 Production Regimes

Every requested graphic routes into one of three execution regimes:

### Regime 1: Deterministic Motion / Title / UI Overlays (Vector & Code)
*Best for:* Lower thirds, title cards, stat callouts, comparison tables, code syntax cards, timeline graphics, split-screen frames, and YouTube end-screens.
*   **Engine:** Authored HTML/Tailwind/CSS captured at 2x/4K scale via headless browser (`chrome-devtools-mcp`), or SVG/PIL.
*   **Contract:** 
    *   Transparent background (`rgba(0, 0, 0, 0)`).
    *   High-DPI rasterization (1080p: `1920x1080`, 4K: `3840x2160`, or Shorts: `1080x1920`).
    *   Zero AI blur or warped typography; text is rendered with true system fonts.
    *   Strict adherence to the Impeccable Craft Floor (high contrast, distinct typography hierarchy, no fake zero-offset glow).

### Regime 2: Generative Scene / Concept / Illustration (Diffusion)
*Best for:* Character art, cinematic scene backgrounds, 3D prop concepts, storyboards, and texture plates.
*   **Engine:** `image-generator` subagent conditioned on visual reference DNA + ArtCraft spatial parameters.
*   **Contract:**
    *   Camera orbit framing: specify rotation (`0°`, `45°`, `90°`), tilt (`-30°`, `0°`, `30°`), and focal length (`35mm close` vs `85mm compression`).
    *   Style conditioning: reference lighting, grain, and color temperature extracted from the user's reference media.

### Regime 3: Mixed Asset Compositing & Frame Extraction
*Best for:* Isolating a software UI or object from a screen recording, cutting out a subject, or combining a photo with animated graphics.
*   **Engine:** Native Windows `ffmpeg.exe` + Python `PIL`.
*   **Contract:**
    *   Exact timestamp frame extraction: `ffmpeg -ss <HH:MM:SS> -i <input.mp4> -vframes 1 <out.png>`.
    *   Clean crop, alpha masking, and drop-shadow backing.

---

## 2. Ingestion & Visual DNA Extraction

When the user provides a reference file:

1.  **Inspect the Media**:
    *   If image/photo: call `read_file` to visually analyze the framing, color palette, lighting direction, and font styles.
    *   If video/screen recording:
        *   If a timestamp is mentioned (e.g. "at 1:14"): extract the exact frame using FFmpeg:
            ```powershell
            ffmpeg -ss 00:01:14 -i "input.mp4" -vframes 1 -q:v 2 "extracted_frame.png"
            ```
        *   If no timestamp is given: use `read_file` on the video file to inspect key scenes.
2.  **Extract the Visual DNA Card**:
    *   **Canvas Target**: 16:9 (`1920x1080` / `3840x2160`), 9:16 (`1080x1920`), or 1:1 (`1080x1080`).
    *   **Primary Palette**: Extract 3 dominant hex colors (Ground, Accent, Text).
    *   **Typography Archetype**: Clean Sans (Inter/Helvetica), Editorial Serif, or Technical Monospace.
    *   **Placement In Frame**: Lower-third, center takeover, top-right badge, or sidebar drawer.

---

## 3. High-DPI Deterministic Rendering Pipeline

To render a pixel-perfect transparent graphic overlay for video editors:

1.  **Create the HTML/CSS Template**:
    Write an isolated HTML template with transparent body and fixed canvas dimensions:
    ```html
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
      <style>
        body { background: transparent !important; margin: 0; padding: 0; }
        .canvas-container {
          width: 1920px;
          height: 1080px;
          position: relative;
          overflow: hidden;
          background: transparent;
        }
      </style>
    </head>
    <body>
      <div class="canvas-container flex items-end p-20">
        <!-- Lower Third / Callout / Graphic -->
        <div class="bg-slate-900/90 border border-slate-700/80 rounded-2xl p-6 shadow-2xl backdrop-blur-md">
          <span class="text-xs font-mono text-sky-400 font-bold uppercase tracking-widest">CHAPTER 02</span>
          <h2 class="text-3xl font-bold text-white mt-1">Causal Clash Adjudication</h2>
        </div>
      </div>
    </body>
    </html>
    ```

2.  **Capture at Native Resolution**:
    Use `chrome-devtools-mcp` or a headless browser script to take a transparent viewport screenshot (`captureScreenshot(omitBackground: true)`), saving directly as a 32-bit PNG (`RGBA`).

---

## 4. Asset Delivery Contract

Every generated visual asset must provide:
1.  **Direct File Link**: `[view graphic](file:///path/to/graphic.png)` with exact dimensions (`1920x1080 PNG (Transparent Alpha)`).
2.  **Editor Instructions**: One sentence explaining placement (e.g. *"Drag onto Video Track 2 over your footage; background is transparent"*).
3.  **Source Custody**: Keep the generator script or HTML template next to the asset in `assets/graphics/` so the user can easily request adjustments (e.g. *"make the title gold"* or *"change the chapter number"*) without starting from scratch.
