"""Element-level segmentation for image-based slides.

Cuts each slide into animatable element layers:
- individual cards / flow boxes (box border + inner text as one layer)
- individual arrows
- icons, charts, standalone text blocks
- highlight groups: red circle / annotation overlapping an element is merged
  with that element into a single layer instead of being torn apart

Replaces the coarse region segmentation in generate_hyperframes_video_project.py.
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_hyperframes_video_project import (  # noqa: E402
    SLIDE_PLANS,
    WIDTH,
    HEIGHT,
    AUDIO,
    OUT,
    audio_duration,
)

ROOT = Path(__file__).resolve().parents[1]
DEBUG = ROOT / "work_preview" / "element_debug"

MARGIN = 16
MAX_LAYERS = 16


def load_slide(slide_num):
    path = OUT / f"slide_{slide_num:02d}" / "original.png"
    return np.array(Image.open(path).convert("RGB"))


def ink_mask(img):
    """Raw foreground: dark ink or saturated color, margins cleared."""
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    mask = ((gray < 235) | (hsv[:, :, 1] > 40)).astype(np.uint8) * 255
    mask[:MARGIN, :] = 0
    mask[-MARGIN:, :] = 0
    mask[:, :MARGIN] = 0
    mask[:, -MARGIN:] = 0
    return mask


def red_mask(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    return (((h < 12) | (h > 168)) & (s > 90) & (v > 70)).astype(np.uint8) * 255


def red_mask_loose(img):
    """Looser variant that also catches dark brick-red strokes; only used to
    decide whether a split red annotation belongs to a card it straddles."""
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    return (((h < 12) | (h > 168)) & (s > 55) & (v > 55)).astype(np.uint8) * 255


def connect_mask(mask):
    """Connect strokes of the same glyph/word without bridging real gaps."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    out = cv2.dilate(mask, kernel, iterations=1)
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, close_kernel, iterations=1)
    return out


def rect_of(box):
    x, y, w, h = box
    return x, y, x + w, y + h


def union_box(a, b):
    ax1, ay1, ax2, ay2 = rect_of(a)
    bx1, by1, bx2, by2 = rect_of(b)
    x1, y1 = min(ax1, bx1), min(ay1, by1)
    x2, y2 = max(ax2, bx2), max(ay2, by2)
    return [x1, y1, x2 - x1, y2 - y1]


def intersection_area(a, b):
    ax1, ay1, ax2, ay2 = rect_of(a)
    bx1, by1, bx2, by2 = rect_of(b)
    iw = min(ax2, bx2) - max(ax1, bx1)
    ih = min(ay2, by2) - max(ay1, by1)
    return max(0, iw) * max(0, ih)


def axis_gap_overlap(a, b):
    """(gap_x, gap_y, overlap_x, overlap_y) between two boxes."""
    ax1, ay1, ax2, ay2 = rect_of(a)
    bx1, by1, bx2, by2 = rect_of(b)
    gap_x = max(0, max(ax1, bx1) - min(ax2, bx2))
    gap_y = max(0, max(ay1, by1) - min(ay2, by2))
    overlap_x = min(ax2, bx2) - max(ax1, bx1)
    overlap_y = min(ay2, by2) - max(ay1, by1)
    return gap_x, gap_y, overlap_x, overlap_y


def should_merge(a, b):
    area_a = a[2] * a[3]
    area_b = b[2] * b[3]
    inter = intersection_area(a, b)
    small = min(area_a, area_b)
    # Containment / heavy overlap: inner text inside a card border,
    # red circle over a box, crossing annotation strokes.
    if small > 0 and inter / small >= 0.45:
        return True
    gap_x, gap_y, overlap_x, overlap_y = axis_gap_overlap(a, b)
    max_h = max(a[3], b[3])
    min_h = min(a[3], b[3])
    min_w = min(a[2], b[2])
    # Words on the same text line. Cards are detected separately via their
    # enclosed interiors and never enter this merge, so a generous word gap
    # cannot chain arrows and boxes together any more. The 30px gap covers
    # inter-word spacing of the rendered font; max_h < 220 lets a word join a
    # paragraph that already merged into two lines.
    word_gap = max(30, 0.5 * min_h)  # spacing scales with the font size
    if max_h < 220 and min_h < 130 and gap_x < word_gap and overlap_y > 0.6 * min_h:
        return True
    # Stacked lines of the same paragraph.
    if max_h < 220 and min_h < 95 and gap_y < 20 and overlap_x > 0.6 * min_w:
        return True
    # Chains of dashes forming a hand-drawn dashed arrow: the segments are
    # small, disconnected, and offset diagonally, so the word/line rules
    # above never catch them. Merge small fragments separated by a small gap
    # in any direction; the size cap lets a partially merged arrow keep
    # absorbing its remaining dashes without ever reaching card size.
    if max(a[2], a[3]) < 170 and max(b[2], b[3]) < 170 and gap_x + gap_y < 42:
        return True
    return False


def merge_pass(boxes, predicate):
    changed = True
    while changed:
        changed = False
        result = []
        used = [False] * len(boxes)
        for i in range(len(boxes)):
            if used[i]:
                continue
            current = list(boxes[i])
            used[i] = True
            grew = True
            while grew:
                grew = False
                for j in range(len(boxes)):
                    if used[j]:
                        continue
                    if predicate(current, boxes[j]):
                        current = union_box(current, boxes[j])
                        used[j] = True
                        grew = True
                        changed = True
            result.append(current)
        boxes = result
    return boxes


def tight_refine(box, raw_mask, pad=5):
    x, y, w, h = box
    x, y = max(0, x), max(0, y)
    w, h = min(WIDTH - x, w), min(HEIGHT - y, h)
    region = raw_mask[y : y + h, x : x + w]
    ys, xs = np.where(region > 0)
    if len(xs) == 0:
        return None
    x1 = max(0, x + int(xs.min()) - pad)
    y1 = max(0, y + int(ys.min()) - pad)
    x2 = min(WIDTH, x + int(xs.max()) + 1 + pad)
    y2 = min(HEIGHT, y + int(ys.max()) + 1 + pad)
    return [x1, y1, x2 - x1, y2 - y1]


def detect_cards(connected):
    """Cards / flow boxes / table cells: their interiors are holes enclosed by
    drawn borders, which survive even when arrow tips touch the borders."""
    contours, hierarchy = cv2.findContours(connected, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    cards = []
    if hierarchy is None:
        return cards
    for idx, c in enumerate(contours):
        if hierarchy[0][idx][3] == -1:
            continue  # outer contour, not a hole
        x, y, w, h = cv2.boundingRect(c)
        if w * h < 7000 or w < 110 or h < 55:
            continue
        if cv2.contourArea(c) < 0.55 * w * h:
            continue  # crescent-shaped hole, not a box interior
        pad = 12  # cover the border stroke around the interior
        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2, y2 = min(WIDTH, x + w + pad), min(HEIGHT, y + h + pad)
        cards.append([x1, y1, x2 - x1, y2 - y1])

    def card_adjacent(a, b):
        if intersection_area(a, b) > 0:
            return True  # shared border (table cells)
        gap_x, gap_y, overlap_x, overlap_y = axis_gap_overlap(a, b)
        if gap_x < 8 and overlap_y > 0.5 * min(a[3], b[3]):
            return True
        if gap_y < 8 and overlap_x > 0.5 * min(a[2], b[2]):
            return True
        return False

    return merge_pass(cards, card_adjacent)


def red_ratio_of(img, box):
    x, y, w, h = box
    region = red_mask(img[y : y + h, x : x + w])
    ink = ink_mask(img)[y : y + h, x : x + w]
    ink_count = int((ink > 0).sum())
    if ink_count == 0:
        return 0.0
    return int((region > 0).sum()) / ink_count


def detect_elements(img):
    raw = ink_mask(img)
    connected = connect_mask(raw)
    cards = detect_cards(connected)

    # Everything outside cards: arrows, icons, standalone text, highlights.
    remaining = connected.copy()
    raw_remaining = raw.copy()
    for cx, cy, cw, ch in cards:
        cv2.rectangle(remaining, (cx, cy), (cx + cw, cy + ch), 0, -1)
        cv2.rectangle(raw_remaining, (cx, cy), (cx + cw, cy + ch), 0, -1)
    contours, _ = cv2.findContours(remaining, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    pieces = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w * h < 160:
            continue
        # NotebookLM watermark in the bottom-right corner stays in background.
        if y > HEIGHT - 110 and x > WIDTH - 360 and h < 70:
            continue
        pieces.append([x, y, w, h])
    pieces = merge_pass(pieces, should_merge)

    # Group red annotation strokes (circle, doodle arrow, note text) together.
    def red_pair(a, b):
        gap_x, gap_y, _, _ = axis_gap_overlap(a, b)
        if gap_x + gap_y > 60:
            return False
        return red_ratio_of(img, a) > 0.55 and red_ratio_of(img, b) > 0.55

    pieces = merge_pass(pieces, red_pair)

    refined = []
    for box in pieces:
        tight = tight_refine(box, raw_remaining, pad=4)
        if tight is None:
            continue
        ink = raw_remaining[tight[1] : tight[1] + tight[3], tight[0] : tight[0] + tight[2]]
        if tight[2] * tight[3] < 900 or int((ink > 0).sum()) < 140:
            continue
        refined.append(tight)

    # A red highlight overlapping a card becomes one highlight group with it.
    # The circle's bbox contains the card's black ink, so the red ratio of the
    # combined region is well below a pure-red piece; use a low threshold.
    # sort_box keeps the core element's position so a highlight group is
    # ordered where its wrapped card sits, not where its annotation floats.
    items = [
        {"box": list(c), "sort_box": list(c), "card": True, "highlight": False}
        for c in cards
    ]
    for piece in refined:
        if red_ratio_of(img, piece) > 0.22:
            target = None
            piece_area = piece[2] * piece[3]
            for item in items:
                if not item["card"]:
                    continue
                card_area = item["box"][2] * item["box"][3]
                inter = intersection_area(piece, item["box"])
                # Merge when the red mark wraps the card (circle around a box)
                # or sits mostly on top of it -- not when a red note merely
                # grazes a big chart's bbox.
                if inter / piece_area > 0.4 or inter / card_area > 0.8:
                    target = item
                    break
            if target is not None:
                target["box"] = union_box(target["box"], piece)
                target["highlight"] = True
                continue
        items.append({"box": piece, "sort_box": list(piece), "card": False, "highlight": False})

    # Red note text that points at a highlight (e.g. "HW6 v4") joins its group.
    changed = True
    while changed:
        changed = False
        for item in list(items):
            if item["card"] or item["highlight"]:
                continue
            if red_ratio_of(img, item["box"]) <= 0.5:
                continue
            for group in items:
                if not group["highlight"]:
                    continue
                gap_x, gap_y, _, _ = axis_gap_overlap(item["box"], group["box"])
                if gap_x + gap_y < 90:
                    group["box"] = union_box(group["box"], item["box"])
                    items.remove(item)
                    changed = True
                    break
            if changed:
                break

    def absorb(keep, other):
        keep["box"] = union_box(keep["box"], other["box"])
        keep["card"] = keep["card"] or other["card"]
        keep["highlight"] = keep["highlight"] or other["highlight"]

    # Rectangular bboxes may graze each other (highlight group over the next
    # card, arrow pad touching a card border); only merge substantial overlap.
    changed = True
    while changed:
        changed = False
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i]["box"], items[j]["box"]
                small = min(a[2] * a[3], b[2] * b[3])
                if small <= 0:
                    continue
                ratio = intersection_area(a, b) / small
                if items[i]["highlight"] or items[j]["highlight"]:
                    # A highlight group's bbox legitimately overlaps its
                    # neighbours; only swallow loose pieces buried inside it,
                    # never another card.
                    other = items[j] if items[i]["highlight"] else items[i]
                    if other["card"] or other["highlight"] or ratio <= 0.6:
                        continue
                elif ratio <= 0.4:
                    continue
                absorb(items[i], items[j])
                items.pop(j)
                changed = True
                break
            if changed:
                break

    # Trim small loose pieces (arrows) so they don't carry slivers of a
    # neighbouring card border inside their crop. But if the piece's strokes
    # run right up to the cut line (an annotation written across a chart
    # edge), trimming would slice the drawing in half -- merge it into the
    # card instead. We probe a thin strip just outside the card boundary.
    full_red = red_mask_loose(img)

    def red_strip(x1, y1, x2, y2):
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(WIDTH, x2), min(HEIGHT, y2)
        if x2 <= x1 or y2 <= y1:
            return 0
        return int((full_red[y1:y2, x1:x2] > 0).sum())

    for item in list(items):
        if item["card"]:
            continue
        box = item["box"]
        for card_item in items:
            if not card_item["card"] or card_item is item:
                continue
            card = card_item["box"]
            if intersection_area(box, card) == 0:
                continue
            x1, y1, x2, y2 = rect_of(box)
            cx1, cy1, cx2, cy2 = rect_of(card)
            # A red annotation whose strokes continue inside the card rect was
            # split by the card-erase step; reunite it with the card layer.
            # (Card borders and flow arrows are black, so red is decisive.)
            if red_ratio_of(img, box) > 0.35:
                inside = max(
                    red_strip(cx2 - 14, y1, cx2, y2),
                    red_strip(cx1, y1, cx1 + 14, y2),
                    red_strip(x1, cy2 - 14, x2, cy2),
                    red_strip(x1, cy1, x2, cy1 + 14),
                )
                if inside > 60:
                    absorb(card_item, item)
                    items.remove(item)
                    break
            cut_left = cx2 - x1 if cx2 > x1 and cx1 <= x1 else None
            cut_right = x2 - cx1 if cx1 < x2 and cx2 >= x2 else None
            cut_top = cy2 - y1 if cy2 > y1 and cy1 <= y1 else None
            cut_bottom = y2 - cy1 if cy1 < y2 and cy2 >= y2 else None
            options = []
            if cut_left is not None and cut_left < 0.3 * box[2]:
                options.append((cut_left, "left"))
            if cut_right is not None and cut_right < 0.3 * box[2]:
                options.append((cut_right, "right"))
            if cut_top is not None and cut_top < 0.3 * box[3]:
                options.append((cut_top, "top"))
            if cut_bottom is not None and cut_bottom < 0.3 * box[3]:
                options.append((cut_bottom, "bottom"))
            small = box[2] < 280 and box[3] < 120
            if not options:
                # Overlap too deep to trim away: the piece genuinely spans the
                # card, so they belong together.
                absorb(card_item, item)
                items.remove(item)
                break
            cut, side = min(options)
            # A small piece (arrow) never has ink inside the card rect -- its
            # overlap is only bbox padding, so trimming is always safe. A big
            # piece overlapping by more than a sliver is an annotation whose
            # strokes continue inside the card crop; keep them together.
            if not small and cut > 14:
                absorb(card_item, item)
                items.remove(item)
                break
            if side == "left":
                box[0] += cut
                box[2] -= cut
            elif side == "right":
                box[2] -= cut
            elif side == "top":
                box[1] += cut
                box[3] -= cut
            else:
                box[3] -= cut

    # Hand-drawn card borders wobble outside the detected card box, and the
    # trim step can leave thin slivers of that border ink hugging the card.
    # A sliver or tiny fragment touching a card is not a meaningful animation
    # element of its own -- fold it back into the card. Real small elements
    # (flow arrows ~55x39, dashed arrows) stay above these thresholds or sit
    # clear of any card.
    for item in list(items):
        if item["card"] or item["highlight"]:
            continue
        x, y, w, h = item["box"]
        if min(w, h) >= 26 and w * h >= 2000:
            continue
        for card_item in items:
            if not card_item["card"]:
                continue
            gap_x, gap_y, _, _ = axis_gap_overlap(item["box"], card_item["box"])
            if gap_x + gap_y < 8:
                absorb(card_item, item)
                items.remove(item)
                break

    # Axis tick labels, rotated axis names and captions belong to the big
    # chart next to them ("R-squared" is ~61x186, "Number of Features" is
    # ~333x57, tick labels are smaller still).
    def axis_label_shaped(w, h):
        return (w < 420 and h < 200) or (w < 200 and h < 420)

    changed = True
    while changed:
        changed = False
        for item in list(items):
            box = item["box"]
            if item["card"] or item["highlight"] or not axis_label_shaped(box[2], box[3]):
                continue
            for big in items:
                bb = big["box"]
                if big is item or big["highlight"]:
                    continue
                if bb[2] > 600 and bb[3] > 300:
                    gap_x, gap_y, _, _ = axis_gap_overlap(box, bb)
                    if gap_x + gap_y < 50:
                        absorb(big, item)
                        items.remove(item)
                        changed = True
                        break
            if changed:
                break

    # Keep layer count manageable: merge nearest pieces.
    while len(items) > MAX_LAYERS:
        best = None
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                gx, gy, _, _ = axis_gap_overlap(items[i]["box"], items[j]["box"])
                d = gx + gy
                if best is None or d < best[0]:
                    best = (d, i, j)
        _, i, j = best
        absorb(items[i], items[j])
        items.pop(j)

    return items, raw


def classify(box, img, raw_mask, is_card, is_highlight):
    x, y, w, h = box
    region_raw = raw_mask[y : y + h, x : x + w]
    fill = float((region_raw > 0).mean())
    if is_highlight:
        return "highlight_group"
    # Real titles are wide banners; w > 700 keeps small status badges in the
    # top corners from stealing the title slot.
    if y < 185 and w > 700 and h < 260:
        return "title"
    if is_card:
        if w > 700 and h > 350 and fill < 0.13:
            return "chart"  # plot area whose crossing curves enclosed holes
        if w > 900 and h > 380:
            return "table"
        return "key_point_card"
    if w < 280 and h < 120 and (fill < 0.32 or w > 1.15 * h):
        return "arrow"
    if w < 210 and h < 210:
        return "icon"
    if w > 560 and h > 300 and fill < 0.16:
        return "chart"
    if w > 1100 and h > 380:
        return "chart"
    if min(w, h) < 100:
        return "text_block"
    return "illustration"


def extract_red_annotations(img, red_loose, box):
    """Find red annotation marks (note text, vector arrows, stars) drawn on a
    chart, separable from same-coloured data curves by glyph size and stroke
    thickness. Returns groups of {box, mask} in global coordinates."""
    x, y, w, h = box
    sub = (red_loose[y : y + h, x : x + w] > 0).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(sub, connectivity=8)
    if n <= 1:
        return []
    dist = cv2.distanceTransform(sub, cv2.DIST_L2, 5)
    members = []
    for i in range(1, n):
        cx, cy, cw, ch, area = stats[i]
        if area < 25:
            continue  # keep tiny marks like decimal points, drop pixel noise
        thick = float(dist[labels == i].max())
        if cw <= 70 and ch <= 70:
            members.append(i)  # note text character / punctuation
        elif thick >= 6.0 and cw <= 0.35 * w:
            members.append(i)  # thick annotation stroke (arrow / star / circle)
    if not members:
        return []
    boxes = [
        [int(stats[i][0]), int(stats[i][1]), int(stats[i][2]), int(stats[i][3]), i]
        for i in members
    ]

    def near(a, b):
        gap_x, gap_y, _, _ = axis_gap_overlap(a[:4], b[:4])
        return gap_x + gap_y < 80

    clusters = []
    remaining = list(boxes)
    while remaining:
        seed = remaining.pop()
        cluster = [seed]
        grew = True
        while grew:
            grew = False
            for other in list(remaining):
                if any(near(other, m) for m in cluster):
                    cluster.append(other)
                    remaining.remove(other)
                    grew = True
        clusters.append(cluster)

    groups = []
    for cluster in clusters:
        ids = [c[4] for c in cluster]
        area = sum(stats[i][4] for i in ids)
        if area < 800:
            continue
        mask = np.isin(labels, ids).astype(np.uint8) * 255
        # Pull in the faint anti-aliased skirt of the strokes (saturation too
        # low for the detection mask) so neither a pink ghost stays in the
        # chart nor the annotation glyphs come out with missing strokes.
        hsv = cv2.cvtColor(img[y : y + h, x : x + w], cv2.COLOR_RGB2HSV)
        hh, ss, vv = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        faint = (((hh < 14) | (hh > 165)) & (ss > 25) & (vv > 45)).astype(np.uint8) * 255
        near = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
        mask = cv2.bitwise_or(mask, cv2.bitwise_and(faint, near))
        mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        ys, xs = np.where(mask > 0)
        gx1, gy1 = x + int(xs.min()), y + int(ys.min())
        gx2, gy2 = x + int(xs.max()) + 1, y + int(ys.max()) + 1
        full = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
        full[y : y + h, x : x + w] = mask
        groups.append({"box": [gx1, gy1, gx2 - gx1, gy2 - gy1], "mask": full})
    return groups


ANIMATION = {
    "title": "fade-in-down",
    "key_point_card": "fade-in-up",
    "table": "fade-in-up",
    "text_block": "fade-in-up",
    "chart": "draw-in",
    "icon": "pop-in",
    "arrow": "wipe-in",
    "illustration": "zoom-in",
    "highlight_group": "pop-in",
    "annotation": "fade-in",
}


def background_fill_color(img, raw_mask):
    bg_pixels = img[raw_mask == 0]
    if len(bg_pixels) == 0:
        return (255, 255, 255)
    return tuple(int(v) for v in np.median(bg_pixels, axis=0))


def segment_slide(slide_num, debug=True):
    img = load_slide(slide_num)
    slide_dir = OUT / f"slide_{slide_num:02d}"
    plan = SLIDE_PLANS[slide_num - 1]

    # Remove previous layer exports, keep original.png.
    for old in slide_dir.glob("*.png"):
        if old.name != "original.png":
            old.unlink()

    items, raw = detect_elements(img)
    # Reading order: cluster items into rows by vertical centre, then go
    # left-to-right inside each row. (Fixed-size banding misorders rows whose
    # centres straddle a band boundary.)
    items = sorted(items, key=lambda it: it["sort_box"][1] + it["sort_box"][3] / 2)
    rows = []
    for it in items:
        cy = it["sort_box"][1] + it["sort_box"][3] / 2
        if rows and cy - rows[-1][0] <= 110:
            rows[-1][1].append(it)
            rows[-1][0] = sum(
                i["sort_box"][1] + i["sort_box"][3] / 2 for i in rows[-1][1]
            ) / len(rows[-1][1])
        else:
            rows.append([cy, [it]])
    items = [
        it
        for _, row in rows
        for it in sorted(row, key=lambda i: i["sort_box"][0])
    ]
    fill_color = background_fill_color(img, raw)

    duration = audio_duration(AUDIO / f"slide_{slide_num:02d}_voiceover.mp3")
    duration = round((duration or 6.0) + 0.55, 2)

    # Expand items with red annotations extracted from chart/table layers so
    # a note + vector arrow drawn over a chart becomes its own layer that can
    # appear later than the chart itself.
    red_loose = red_mask_loose(img)
    entries = []
    for item in items:
        layer_type = classify(item["box"], img, raw, item["card"], item["highlight"])
        entry = dict(item, type=layer_type, annot_masks=[], mask=None, src=item)
        entries.append(entry)
        if layer_type in ("chart", "table"):
            for group in extract_red_annotations(img, red_loose, item["box"]):
                entry["annot_masks"].append(group["mask"])
                entries.append(
                    {
                        "box": group["box"],
                        "type": "annotation",
                        "mask": group["mask"],
                        "annot_masks": [],
                        "card": False,
                        "highlight": False,
                        "parent": entry,
                    }
                )

    # Humans read the main title first, wherever the band sort put it.
    entries.sort(key=lambda e: 0 if e["type"] == "title" else 1)

    background = img.copy()
    layers = []
    counts = {}
    cue_gap = max(0.55, (duration - 2.2) / max(1, len(entries)))
    for i, item in enumerate(entries):
        box = item["box"]
        x, y, w, h = box
        layer_type = item["type"]
        counts[layer_type] = counts.get(layer_type, 0) + 1
        filename = f"slide_{slide_num:02d}_{layer_type}_{counts[layer_type]:02d}.png"
        crop = img[y : y + h, x : x + w].copy()
        alpha = np.full((h, w), 255, dtype=np.uint8)
        if item["mask"] is not None:
            alpha = item["mask"][y : y + h, x : x + w]
        for annot in item["annot_masks"]:
            region = annot[y : y + h, x : x + w] > 0
            crop[region] = fill_color
        if item["highlight"]:
            # Where the group's bbox covers a neighbouring card, keep only the
            # red annotation ink so that card doesn't ghost in early.
            red = red_mask(img)
            red = cv2.dilate(red, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
            for other in items:
                if other is item.get("src") or not other["card"]:
                    continue
                ox, oy, ow, oh = other["box"]
                ix1, iy1 = max(x, ox), max(y, oy)
                ix2, iy2 = min(x + w, ox + ow), min(y + h, oy + oh)
                if ix2 > ix1 and iy2 > iy1:
                    sub = alpha[iy1 - y : iy2 - y, ix1 - x : ix2 - x]
                    sub[:] = red[iy1:iy2, ix1:ix2]
        Image.fromarray(np.dstack([crop, alpha])).save(slide_dir / filename)
        cv2.rectangle(background, (x, y), (x + w - 1, y + h - 1), fill_color, -1)
        cue_text = plan["cues"][min(i, len(plan["cues"]) - 1)][1]
        if layer_type == "annotation":
            # The chart it is drawn on must be fully visible first.
            start = round(min(item["parent"]["_start"] + 0.85, duration - 0.8), 2)
        else:
            start = round(min(0.45 + i * cue_gap, duration - 1.0), 2)
        item["_start"] = start
        layers.append(
            {
                "name": filename,
                "type": layer_type,
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h),
                "z_index": 5 + i,
                "animation": ANIMATION.get(layer_type, "fade-in"),
                "start": start,
                "duration": 0.7,
                "narration_cue": cue_text,
            }
        )
    Image.fromarray(background).save(slide_dir / "background.png")
    metadata = {
        "slide": slide_num,
        "width": WIDTH,
        "height": HEIGHT,
        "duration": duration,
        "layers": layers,
    }
    (slide_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if debug:
        boxes = [[l["x"], l["y"], l["width"], l["height"]] for l in layers]
        save_debug(slide_num, img, background, boxes, layers)
    return metadata


def save_debug(slide_num, img, background, boxes, layers):
    DEBUG.mkdir(parents=True, exist_ok=True)
    annotated = img.copy()
    palette = [
        (220, 40, 40), (40, 120, 220), (30, 160, 60), (200, 120, 20),
        (140, 60, 200), (0, 150, 160), (200, 30, 120), (100, 100, 30),
    ]
    for i, (box, layer) in enumerate(zip(boxes, layers)):
        x, y, w, h = box
        color = palette[i % len(palette)]
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 3)
        cv2.putText(
            annotated, f"{i+1}:{layer['type']}", (x + 4, max(20, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA,
        )
    half = (WIDTH // 2, HEIGHT // 2)
    sheet = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    sheet[: half[1], : half[0]] = cv2.resize(img, half)
    sheet[: half[1], half[0] :] = cv2.resize(annotated, half)
    sheet[half[1] :, : half[0]] = cv2.resize(background, half)
    recon = np.array(Image.open(OUT / f"slide_{slide_num:02d}" / "background.png").convert("RGB"))
    for layer in layers:
        piece = np.array(
            Image.open(OUT / f"slide_{slide_num:02d}" / layer["name"]).convert("RGB")
        )
        x, y = layer["x"], layer["y"]
        recon[y : y + piece.shape[0], x : x + piece.shape[1]] = piece
    sheet[half[1] :, half[0] :] = cv2.resize(recon, half)
    Image.fromarray(sheet).save(DEBUG / f"slide_{slide_num:02d}_debug.jpg", quality=88)


def main():
    only = [int(a) for a in sys.argv[1:]] or range(1, 21)
    metadatas = []
    for n in only:
        meta = segment_slide(n)
        print(f"slide_{n:02d}: {len(meta['layers'])} layers, duration {meta['duration']}s")
        metadatas.append(meta)
    return metadatas


if __name__ == "__main__":
    main()
