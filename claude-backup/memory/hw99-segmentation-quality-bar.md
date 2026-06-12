---
name: hw99-segmentation-quality-bar
description: "User's quality bar for slide element cutting — human reading logic, no split sentences, annotations as separate late layers"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 75e759e1-ae7d-4cb7-ac82-4509be712111
---

The user reviews layer galleries closely and judges cuts by human reading logic.

**Why:** Layers drive animation order; a sentence split into words appearing one by one looks broken, and an annotation baked into a chart can't sync with narration.

**How to apply:**
- A sentence/title must be ONE layer (word-gap merging must scale with font size; large fonts have ~35px+ word spacing).
- Red annotations drawn over charts (note text + vector arrow/star/circle) should be their own `annotation` layer with stroke-mask alpha, whitened out of the chart crop, fading in after the chart (separate same-coloured data curves by stroke thickness ≥6px half-width and glyph size ≤70px).
- Don't re-render the final MP4s after every tweak — it costs time/tokens; only re-run `segment_elements.py` + `rebuild_timeline.py` and show galleries (`work_preview/slide_##_layer_gallery.jpg`), render video only when asked. See [[hw99-element-segmentation-pipeline]].
