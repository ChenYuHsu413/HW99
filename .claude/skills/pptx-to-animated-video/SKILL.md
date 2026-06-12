---
name: pptx-to-animated-video
description: Convert an image-only slide deck (NotebookLM-style PPTX/PDF where every slide is one flat image) into an animated MP4 with TTS narration and subtitles. Segments each slide into element layers (cards, arrows, charts, highlight groups), schedules layer entrances from the narration timeline, previews in the browser, and renders via ffmpeg. Use when the user wants slide images turned into a narrated/animated video.
---

# PPTX → Animated Narrated Video

Treat every slide as a flat image — never assume editable PowerPoint elements.
All scripts run **from the project root** (they read/write `output/`, `audio/`,
`narration/`, `hyperframes/`, `final/` under the cwd).

## Prerequisites

```
pip install opencv-python pymupdf pillow edge-tts
```
ffmpeg: system install, or `npm i ffmpeg-static ffprobe-static` in the project,
or set `FFMPEG_PATH`. Scripts auto-discover it.

## Workflow

`SKILL_DIR` = this skill's folder; run scripts as `python "<SKILL_DIR>/scripts/<name>.py"`.

1. **Slides → PNG**: need a PDF (export PPTX to PDF if necessary), then
   `render_slides.py deck.pdf` → `output/slide_##/original.png` (1920x1080).
2. **Write the narration** `narration/narration_script.md` yourself (the model)
   after looking at every slide image. Format — one section per slide:
   ```
   ## Slide 01 - <title>

   <口語化、教學型旁白，2-4 句>
   ```
   Match the deck's language (zh-TW deck → 繁體中文旁白). Pace ≈ 130–160
   chars/min; each slide's text should speak in roughly 10–16 s.
3. **TTS**: `tts_edge.py` (defaults: `zh-TW-HsiaoChenNeural`, rate -8%; pass a
   different voice for other languages). Audio durations drive all timing, so
   do this BEFORE segmenting.
4. **Segment**: `segment_elements.py [slide numbers]`. Prints per-slide layer
   count and a reconstruction diff — **any nonzero diff is a bug, stop and fix**.
   Outputs per slide: transparent layers + `background.png` + `metadata.json`,
   plus review artifacts:
   - `work_preview/element_debug/slide_##_debug.jpg` — original / detected
     boxes / background-after-cut / reconstruction
   - `work_preview/slide_##_layer_gallery.jpg` — each layer on a checkerboard
     with name/type/position/start time
5. **Review loop (do not skip)**: read several galleries yourself, then show
   the user the galleries for the most complex slides and ask if the cuts
   match their expectation. Iterate on `segment_elements.py` thresholds until
   approved. Re-run is cheap; renders are not.
6. **Timeline**: `build_timeline.py` → `narration_timing.json`, SRT/VTT,
   `hyperframes/` browser preview. Preview: `python -m http.server 8080` →
   `http://localhost:8080/hyperframes/index.html`.
7. **Render — only after the user approves the cuts** (it's the expensive
   step): `render_final_video.py` → `final/final_video_with_voiceover.mp4` +
   burned-subtitles version. Run it in the background; it prints one line per
   slide.

## Quality bar for segmentation (learned from human review)

- **Human reading logic rules everything.** Title first, then rows top-to-
  bottom, left-to-right inside a row (row clustering by vertical centre — not
  fixed bands, they misorder at boundaries).
- **A sentence is ONE layer.** Never let words of one sentence appear as
  separate animated pieces. Word-gap merging must scale with font size
  (large display fonts have 35px+ word spacing).
- **Cards/flow boxes/tables** are detected via enclosed interiors (holes in
  the ink mask, `cv2.RETR_CCOMP` children) because hand-drawn arrows touch
  box borders and defeat plain connected components. Adjacent table cells
  merge into one table.
- **Arrows/icons/loose text** come from the ink that remains after erasing
  card rects — that's what keeps card-border slivers out of arrow crops.
  Dashed arrows need the dash-chain rule (small fragments, gap < ~42px).
- **Red circle/doodle/note over a card** → one `highlight_group` with that
  card. It must not be torn apart, and must not swallow neighbouring cards
  (zero the alpha over other cards' rects, keeping only red ink there).
- **Red annotations drawn on charts** (note text + vector arrow/star/circle)
  become separate `annotation` layers with stroke-mask alpha (include the
  faint anti-aliased skirt or you get pink ghosts + broken glyphs), whitened
  out of the chart crop, fading in ~0.85s after the chart. Distinguish from
  same-coloured data curves by stroke thickness (≥6px half-width) and glyph
  size (≤70px); curves are thinner and wider.
- **Axis labels belong to the chart** (rotated y-label, x caption, ticks).
- **Tiny/thin fragments touching a card** (area <2000px² or min side <26px)
  are border residue — fold them back into the card. Real small elements
  (flow arrows ~55x39) sit clear of cards and stay separate.
- **Watermarks** (e.g. NotebookLM, bottom-right) stay in the background.
- **Verification is non-negotiable**: compositing background + all layers
  must reproduce the original with 0 px diff (>20 intensity) on every slide.

## Timing rules

- Narration first: each slide's duration = its voiceover length + 0.55s;
  layer starts spread across the narration window; 0.5s crossfade between
  slides. Animations: title fade-in-down, cards fade-in-up, arrows wipe-in,
  icons pop-in, charts draw-in, annotations fade-in (no movement — they sit
  over whitened pixels).
- If there is no TTS available, still produce script/subtitles/timing and a
  README explaining how to plug in ElevenLabs/Azure/OpenAI/Google TTS; do not
  block the pipeline.

## Token/cost discipline

- After threshold tweaks: re-run segment + timeline + galleries only.
  **Never re-render the MP4s unless the user asks** — say the videos are now
  stale and give the one-command re-render instead.
- Subtitle burn style that fits 1080p CJK:
  `FontSize=11,Outline=1.2,MarginL=30,MarginR=30,MarginV=22` (ASS sizes are
  relative to 288-line script resolution; 16+ overflows the frame).
