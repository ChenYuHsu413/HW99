---
name: hw99-element-segmentation-pipeline
description: hw99 slide-video project — element segmentation approach the user approved and the pipeline entry points
metadata: 
  node_type: memory
  type: project
  originSessionId: 75e759e1-ae7d-4cb7-ac82-4509be712111
---

hw99 converts a NotebookLM image-only PPTX (20 slides, Excalidraw style) into an animated MP4 with zh-TW female narration (edge-tts `zh-TW-HsiaoChenNeural`).

**User-approved segmentation style (2026-06-12):** cut each flow box/card as its own layer, each arrow as its own layer; a red circle/doodle/note overlapping a card becomes ONE `highlight_group` layer together with that card (do not tear the highlight apart, do not let it swallow neighbouring cards). Arrow crops must not include slivers of neighbouring box borders.

**Key technical insight:** arrows are drawn touching the boxes, so connected components merge the whole row. Cards must be detected via *holes* (enclosed interiors) in the ink mask (`cv2.RETR_CCOMP`, child contours), then arrows/icons found from the remaining ink after erasing card rects.

Pipeline: `scripts/segment_elements.py` → `scripts/rebuild_timeline.py` → `scripts/render_final_video.py` (numpy compositing piped to `node_modules/ffmpeg-static/ffmpeg.exe`; bake finished layers into a settled canvas and reuse cached static frames for speed). Reconstruction must stay 0-px-diff vs originals. Narration timing drives animation starts, not the other way around.
