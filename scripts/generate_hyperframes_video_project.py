import asyncio
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import cv2
import fitz
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PDF = ROOT / "sources" / "50_Startups_Feature_Selection.pdf"
OUT = ROOT / "output"
AUDIO = ROOT / "audio"
NARRATION = ROOT / "narration"
HYPER = ROOT / "hyperframes"
FINAL = ROOT / "final"
WIDTH = 1920
HEIGHT = 1080
FPS = 30


SLIDE_PLANS = [
    {
        "title": "專案總覽",
        "script": "這份簡報會用 Kaggle 五十家新創公司的資料，示範如何用 CRISP-DM 流程做特徵選擇。重點不是只追求最高分，而是理解哪些支出真的能解釋獲利。",
        "cues": [("title", "專案主題"), ("subtitle", "資料與預測任務"), ("main_visual_object", "學習方向")],
    },
    {
        "title": "預測目標",
        "script": "我們的預測目標是公司的最終利潤，也就是 Profit。資料中每一筆都是一家新創公司，模型要學習支出配置 and 地區資訊，如何對利潤產生影響。",
        "cues": [("title", "預測目標"), ("key_point_card", "資料內容"), ("key_point_card", "模型任務")],
    },
    {
        "title": "核心問題",
        "script": "接著要找出最有預測力的特徵組合，並建立穩健的迴歸模型。這裡的重點是比較不同特徵，而不是把所有欄位直接丟進模型。",
        "cues": [("title", "核心問題"), ("key_point_card", "特徵組合"), ("key_point_card", "穩健模型")],
    },
    {
        "title": "CRISP-DM 流程",
        "script": "整體流程依照 CRISP-DM 展開，從商業理解、資料理解、資料準備、建模，到特徵選擇與結論。這次特別聚焦在評估階段的特徵選擇。",
        "cues": [("title", "流程"), ("arrow", "步驟推進"), ("key_point_card", "特徵選擇")],
    },
    {
        "title": "商業實驗設計",
        "script": "第一組實驗用商業直覺設計五種模型。從只看 R&D Spend 開始，再逐步加入 Marketing、Administration，以及 State，觀察每個特徵是否真的帶來幫助。",
        "cues": [("title", "實驗設計"), ("chart", "五種模型"), ("key_point_card", "初步結論")],
    },
    {
        "title": "V4 擴充",
        "script": "後續版本把特徵選擇擴充到十種演算法，讓結果不只依賴單一方法。這可以幫助我們分辨穩定訊號，和偶然出現的模型偏好。",
        "cues": [("title", "V4 升級"), ("icon", "想法提示"), ("key_point_card", "十種演算法")],
    },
    {
        "title": "三類特徵選擇",
        "script": "這十種方法可以分成過濾法、封裝法 and 嵌入法。過濾法看統計關係，封裝法反覆訓練模型，嵌入法則利用模型本身的係數或重要度。",
        "cues": [("title", "方法分類"), ("key_point_card", "過濾法"), ("key_point_card", "封裝法"), ("key_point_card", "嵌入法")],
    },
    {
        "title": "移除不適合方法",
        "script": "有些演算法被移除，不是因為它們一定錯，而是它們的結果太發散，會壓縮圖表尺度，讓其他演算法的趨勢變得不容易閱讀。",
        "cues": [("title", "刪除原因"), ("icon", "叉號"), ("key_point_card", "圖表尺度")],
    },
    {
        "title": "觀點轉換",
        "script": "這一頁說明分析視角的轉換。原本只看全局最佳組合，後來改成比較每個演算法自己選出的前五名特徵，解讀會更公平。",
        "cues": [("title", "觀點轉換"), ("key_point_card", "Before"), ("arrow", "轉換"), ("key_point_card", "After")],
    },
    {
        "title": "RMSE 趨勢",
        "script": "從 RMSE 圖可以看到，使用單一 R&D Spend 時誤差已經很低。加入更多特徵後，不一定會更好，反而可能讓測試誤差上升。",
        "cues": [("title", "RMSE"), ("chart", "圖表"), ("decorative_shape", "最佳點")],
    },
    {
        "title": "R-squared 趨勢",
        "script": "R-squared 圖也支持類似結論。最好的單一特徵模型已經有很高的解釋力，後面加入更多欄位時，表現並沒有穩定提升。",
        "cues": [("title", "R-squared"), ("chart", "解釋力圖"), ("decorative_shape", "下降趨勢")],
    },
    {
        "title": "最強驅動特徵",
        "script": "最穩定的核心特徵是 R&D Spend，也就是研發支出。十種特徵選擇方法都把它排在第一，代表它和新創公司的獲利高度相關。",
        "cues": [("title", "最強特徵"), ("icon", "皇冠"), ("key_point_card", "R&D Spend"), ("key_point_card", "十種方法一致")],
    },
    {
        "title": "第二輔助特徵",
        "script": "Marketing Spend 通常是第二個有用的輔助特徵。它可能放大產品價值和市場曝光，但效果通常建立在 R&D 已經有解釋力的基礎上。",
        "cues": [("title", "Marketing"), ("icon", "擴音器"), ("key_point_card", "輔助特徵"), ("key_point_card", "市場曝光")],
    },
    {
        "title": "不穩定特徵",
        "script": "Administration 和 State 需要更保守地解讀。Administration 比較像營運成本，State 則受樣本數太小限制，都不適合作為主要結論。",
        "cues": [("title", "其他特徵"), ("key_point_card", "Administration"), ("key_point_card", "State"), ("icon", "放大鏡")],
    },
    {
        "title": "最佳單特徵模型",
        "script": "最佳測試結果來自 SelectKBest 的單一特徵模型，只使用 R&D Spend。它的 RMSE 約為七千七百一十四，R-squared 約為零點九二六五。",
        "cues": [("title", "最佳模型"), ("key_point_card", "SelectKBest"), ("key_point_card", "R&D Spend"), ("key_point_card", "指標")],
    },
    {
        "title": "最佳 Top-5 模型",
        "script": "如果限定每個演算法選出前五個特徵，最佳 Top-5 仍然由 SelectKBest 產生。這裡 R&D 和 Marketing 仍是最值得先關注的訊號。",
        "cues": [("title", "Top-5"), ("key_point_card", "演算法"), ("key_point_card", "特徵列表"), ("key_point_card", "績效")],
    },
    {
        "title": "輸出檔案",
        "script": "完成分析後，程式輸出 CSV 表格和多張 PNG 圖。這些檔案讓我們可以回頭檢查每種演算法的選擇，以及不同特徵數量下的表現。",
        "cues": [("title", "輸出"), ("icon", "資料夾"), ("key_point_card", "CSV 與 PNG"), ("key_point_card", "執行指令")],
    },
    {
        "title": "版本同步",
        "script": "專案也把程式與結果同步到 Git。這代表分析過程可以被追蹤、重跑，也方便之後擴充成網頁展示或互動式工具。",
        "cues": [("title", "Git"), ("icon", "節點圖"), ("key_point_card", "最新 commit"), ("key_point_card", "同步完成")],
    },
    {
        "title": "最終結論",
        "script": "總結來說，R&D Spend 是最可靠的獲利驅動因素，Marketing 是輔助放大器，Administration 和 State 則要謹慎看待。最終模型應同時考慮指標與商業邏輯。",
        "cues": [("title", "結論"), ("key_point_card", "Model A"), ("key_point_card", "CRISP-DM"), ("key_point_card", "商業解讀")],
    },
    {
        "title": "技術資源",
        "script": "簡報到這裡結束。若要重現結果，可以從 README 的指令開始，重新執行分析腳本，並檢查輸出的表格、圖表和影片專案檔。",
        "cues": [("title", "結束"), ("key_point_card", "README"), ("key_point_card", "重現流程"), ("main_visual_object", "資源")],
    },
]


def clean_dirs():
    for path in [OUT, AUDIO, NARRATION, HYPER, FINAL]:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def render_pdf():
    doc = fitz.open(SOURCE_PDF)
    rendered = []
    for idx, page in enumerate(doc, 1):
        scale = min(WIDTH / page.rect.width, HEIGHT / page.rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        canvas = Image.new("RGB", (WIDTH, HEIGHT), "white")
        x = (WIDTH - img.width) // 2
        y = (HEIGHT - img.height) // 2
        canvas.paste(img, (x, y))
        slide_dir = OUT / f"slide_{idx:02d}"
        slide_dir.mkdir(parents=True, exist_ok=True)
        canvas.save(slide_dir / "original.png", quality=95)
        rendered.append(np.array(canvas))
    return rendered


def foreground_mask(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    # Keep dark ink and saturated color, ignore white paper texture.
    mask = ((gray < 238) | (hsv[:, :, 1] > 35)).astype(np.uint8) * 255
    mask[:18, :] = 0
    mask[-18:, :] = 0
    mask[:, :18] = 0
    mask[:, -18:] = 0
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 15))
    mask = cv2.dilate(mask, kernel, iterations=1)
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (19, 11))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=1)
    return mask


def merge_boxes(boxes):
    boxes = [list(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        merged = []
        used = [False] * len(boxes)
        for i, a in enumerate(boxes):
            if used[i]:
                continue
            ax, ay, aw, ah = a
            ar = [ax, ay, ax + aw, ay + ah]
            for j in range(i + 1, len(boxes)):
                if used[j]:
                    continue
                bx, by, bw, bh = boxes[j]
                br = [bx, by, bx + bw, by + bh]
                gap_x = max(0, max(ar[0], br[0]) - min(ar[2], br[2]))
                gap_y = max(0, max(ar[1], br[1]) - min(ar[3], br[3]))
                overlap_x = min(ar[2], br[2]) - max(ar[0], br[0])
                overlap_y = min(ar[3], br[3]) - max(ar[1], br[1])
                if (gap_x < 34 and overlap_y > 10) or (gap_y < 24 and overlap_x > 20):
                    ar = [min(ar[0], br[0]), min(ar[1], br[1]), max(ar[2], br[2]), max(ar[3], br[3])]
                    used[j] = True
                    changed = True
            used[i] = True
            merged.append([ar[0], ar[1], ar[2] - ar[0], ar[3] - ar[1]])
        boxes = merged
    return boxes


def classify_box(idx, box, total, slide_plan):
    x, y, w, h = box
    if y < 165 and w > 360:
        return "title"
    if w > 650 and h > 250:
        return "chart"
    cue_types = [c[0] for c in slide_plan["cues"]]
    if idx < len(cue_types):
        return cue_types[idx]
    if w < 190 and h < 190:
        return "icon"
    if w > 360 and h > 120:
        return "key_point_card"
    return "decorative_shape"


def animation_for(layer_type, index):
    mapping = {
        "title": "fade-in-down",
        "subtitle": "fade-in-up",
        "key_point_card": "fade-in-up",
        "chart": "draw-in",
        "icon": "pop-in",
        "arrow": "wipe-in",
        "illustration": "pop-in",
        "decorative_shape": "fade-in",
        "main_visual_object": "zoom-in",
    }
    return mapping.get(layer_type, "fade-in")


def segment_slide(img, slide_num, slide_plan, duration):
    slide_dir = OUT / f"slide_{slide_num:02d}"
    mask = foreground_mask(img)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < 9000 or w < 70 or h < 45:
            continue
        if area > WIDTH * HEIGHT * 0.72:
            continue
        pad = 12
        x = max(0, x - pad)
        y = max(0, y - pad)
        w = min(WIDTH - x, w + pad * 2)
        h = min(HEIGHT - y, h + pad * 2)
        boxes.append((x, y, w, h))
    boxes = merge_boxes(boxes)
    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))
    boxes = boxes[:10]

    background = img.copy()
    layers = []
    cue_gap = max(0.75, (duration - 1.4) / max(1, len(boxes)))
    for i, box in enumerate(boxes):
        x, y, w, h = box
        layer_type = classify_box(i, box, len(boxes), slide_plan)
        safe_type = layer_type.replace("_", "-")
        count = sum(1 for l in layers if l["type"] == layer_type) + 1
        if layer_type == "title":
            filename = f"slide_{slide_num:02d}_title.png" if count == 1 else f"slide_{slide_num:02d}_title_{count:02d}.png"
        elif layer_type == "chart":
            filename = f"slide_{slide_num:02d}_chart.png" if count == 1 else f"slide_{slide_num:02d}_chart_{count:02d}.png"
        else:
            filename = f"slide_{slide_num:02d}_{safe_type}_{count:02d}.png"
        crop = img[y : y + h, x : x + w]
        alpha = np.full((h, w), 255, dtype=np.uint8)
        rgba = np.dstack([crop, alpha])
        Image.fromarray(rgba).save(slide_dir / filename)
        cv2.rectangle(background, (x, y), (x + w, y + h), (255, 255, 255), -1)
        cue_text = slide_plan["cues"][min(i, len(slide_plan["cues"]) - 1)][1]
        start = round(0.35 + i * cue_gap, 2)
        layers.append(
            {
                "name": filename,
                "type": layer_type,
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h),
                "z_index": 5 + i,
                "animation": animation_for(layer_type, i),
                "start": start,
                "duration": 0.75,
                "narration_cue": cue_text,
            }
        )
    Image.fromarray(background).save(slide_dir / "background.png")
    metadata = {"slide": slide_num, "width": WIDTH, "height": HEIGHT, "duration": duration, "layers": layers}
    (slide_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def estimate_duration(script):
    chars = len(re.sub(r"\s|[，。！？、,.!?]", "", script))
    return max(5.2, round(chars / 2.45 + 1.8, 1))


def ffprobe_path():
    local = ROOT / "node_modules" / "ffprobe-static" / "bin" / "win32" / "x64" / "ffprobe.exe"
    if local.exists():
        return str(local)
    return shutil.which("ffprobe")


def audio_duration(path):
    probe = ffprobe_path()
    if not probe:
        return None
    result = subprocess.run(
        [probe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def update_metadata_to_audio_durations(metadatas):
    updated = []
    for meta in metadatas:
        slide_num = meta["slide"]
        duration = audio_duration(AUDIO / f"slide_{slide_num:02d}_voiceover.mp3")
        if duration:
            meta["duration"] = round(duration + 0.55, 2)
            layers = meta["layers"]
            cue_gap = max(1.2, (meta["duration"] - 2.4) / max(1, len(layers)))
            for i, layer in enumerate(layers):
                layer["start"] = round(0.45 + i * cue_gap, 2)
        slide_dir = OUT / f"slide_{slide_num:02d}"
        (slide_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        updated.append(meta)
    return updated


def srt_time(seconds):
    ms = int(round((seconds - math.floor(seconds)) * 1000))
    whole = int(seconds)
    h = whole // 3600
    m = (whole % 3600) // 60
    s = whole % 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def vtt_time(seconds):
    return srt_time(seconds).replace(",", ".")


def write_narration_and_timing(metadatas):
    timing = {}
    md_lines = ["# 繁體中文女聲旁白稿", ""]
    srt = []
    vtt = ["WEBVTT", ""]
    cursor = 0.0
    for i, plan in enumerate(SLIDE_PLANS, 1):
        key = f"slide_{i:02d}"
        duration = metadatas[i - 1]["duration"]
        start = round(cursor, 2)
        end = round(cursor + duration, 2)
        md_lines += [f"## Slide {i:02d} - {plan['title']}", "", plan["script"], ""]
        cues = []
        for layer in metadatas[i - 1]["layers"]:
            cues.append(
                {
                    "time": round(start + layer["start"], 2),
                    "layer": layer["name"],
                    "action": layer["animation"],
                    "spoken_content": layer["narration_cue"],
                }
            )
        timing[key] = {
            "voiceover_file": f"audio/slide_{i:02d}_voiceover.mp3",
            "start": start,
            "end": end,
            "script": plan["script"],
            "cues": cues,
        }
        srt.append(str(i))
        srt.append(f"{srt_time(start)} --> {srt_time(end - 0.35)}")
        srt.append(plan["script"])
        srt.append("")
        vtt.append(f"{vtt_time(start)} --> {vtt_time(end - 0.35)}")
        vtt.append(plan["script"])
        vtt.append("")
        cursor = end + 0.5
    (NARRATION / "narration_script.md").write_text("\n".join(md_lines), encoding="utf-8")
    (NARRATION / "narration_timing.json").write_text(json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8")
    (NARRATION / "subtitles.srt").write_text("\n".join(srt), encoding="utf-8")
    (NARRATION / "subtitles.vtt").write_text("\n".join(vtt), encoding="utf-8")
    return timing


async def tts_one(slide_num, text):
    import edge_tts

    communicate = edge_tts.Communicate(
        text=text,
        voice="zh-TW-HsiaoChenNeural",
        rate="-8%",
        volume="+0%",
    )
    await communicate.save(str(AUDIO / f"slide_{slide_num:02d}_voiceover.mp3"))


async def generate_tts():
    for i, plan in enumerate(SLIDE_PLANS, 1):
        await tts_one(i, plan["script"])


def write_hyperframes_files(metadatas, timing):
    project = {
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "slides": metadatas,
        "timing": timing,
    }
    (HYPER / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    (HYPER / "index.html").write_text(
        """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>50 Startups HyperFrames Preview</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main id="stage" aria-label="video preview">
    <div id="slide"></div>
    <div id="caption"></div>
  </main>
  <div id="controls">
    <button id="play">Play</button>
    <button id="subtitles">Subtitles On</button>
  </div>
  <script src="animation.js"></script>
</body>
</html>
""",
        encoding="utf-8",
    )
    (HYPER / "styles.css").write_text(
        """html, body {
  margin: 0;
  min-height: 100%;
  background: #202124;
  color: #111;
  font-family: Arial, "Noto Sans TC", sans-serif;
}

#stage {
  position: relative;
  width: min(100vw, calc(100vh * 16 / 9));
  aspect-ratio: 16 / 9;
  margin: 0 auto;
  overflow: hidden;
  background: white;
}

#slide, .bg, .layer {
  position: absolute;
  inset: 0;
}

.bg, .layer {
  width: 100%;
  height: 100%;
  object-fit: contain;
  user-select: none;
  pointer-events: none;
}

.layer {
  inset: auto;
  opacity: 0;
  transform-origin: center;
}

.show.fade-in-down { animation: fadeDown var(--dur) ease forwards; }
.show.fade-in-up { animation: fadeUp var(--dur) ease forwards; }
.show.fade-in { animation: fade var(--dur) ease forwards; }
.show.pop-in { animation: pop var(--dur) cubic-bezier(.2, .85, .25, 1.2) forwards; }
.show.zoom-in { animation: zoom var(--dur) ease forwards; }
.show.wipe-in { animation: wipe var(--dur) ease forwards; }
.show.draw-in { animation: draw var(--dur) ease forwards; }

#caption {
  position: absolute;
  left: 8%;
  right: 8%;
  bottom: 4%;
  min-height: 48px;
  padding: 10px 16px;
  display: none;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #fff;
  background: rgba(0,0,0,.58);
  font-size: 28px;
  line-height: 1.35;
}

#caption.on { display: flex; }

#controls {
  position: fixed;
  left: 16px;
  bottom: 16px;
  display: flex;
  gap: 8px;
}

button {
  border: 0;
  border-radius: 6px;
  padding: 10px 14px;
  background: #f6f7f8;
  cursor: pointer;
}

@keyframes fadeDown { from { opacity: 0; transform: translateY(-22px); } to { opacity: 1; transform: none; } }
@keyframes fadeUp { from { opacity: 0; transform: translateY(24px); } to { opacity: 1; transform: none; } }
@keyframes fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes pop { from { opacity: 0; transform: scale(.86); } to { opacity: 1; transform: scale(1); } }
@keyframes zoom { from { opacity: 0; transform: scale(.94); } to { opacity: 1; transform: scale(1); } }
@keyframes wipe { from { opacity: 0; clip-path: inset(0 100% 0 0); } to { opacity: 1; clip-path: inset(0); } }
@keyframes draw { from { opacity: 0; transform: translateY(10px) scale(.98); } to { opacity: 1; transform: none; } }
""",
        encoding="utf-8",
    )
    (HYPER / "animation.js").write_text(
        """const slideRoot = document.getElementById('slide');
const caption = document.getElementById('caption');
const playButton = document.getElementById('play');
const subtitleButton = document.getElementById('subtitles');
let subtitlesOn = true;

subtitleButton.addEventListener('click', () => {
  subtitlesOn = !subtitlesOn;
  subtitleButton.textContent = subtitlesOn ? 'Subtitles On' : 'Subtitles Off';
  caption.classList.toggle('on', subtitlesOn);
});

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function loadProject() {
  const res = await fetch('project.json');
  return res.json();
}

function layerPath(slideNumber, name) {
  return `../output/slide_${String(slideNumber).padStart(2, '0')}/${name}`;
}

function audioPath(slideNumber) {
  return `../audio/slide_${String(slideNumber).padStart(2, '0')}_voiceover.mp3`;
}

function showSlide(slide, timing) {
  slideRoot.innerHTML = '';
  const base = document.createElement('img');
  base.className = 'bg';
  base.src = layerPath(slide.slide, 'background.png');
  slideRoot.appendChild(base);
  for (const layer of slide.layers) {
    const img = document.createElement('img');
    img.className = `layer ${layer.animation}`;
    img.src = layerPath(slide.slide, layer.name);
    img.style.left = `${layer.x / slide.width * 100}%`;
    img.style.top = `${layer.y / slide.height * 100}%`;
    img.style.width = `${layer.width / slide.width * 100}%`;
    img.style.height = `${layer.height / slide.height * 100}%`;
    img.style.zIndex = layer.z_index;
    img.style.setProperty('--dur', `${layer.duration}s`);
    slideRoot.appendChild(img);
    window.setTimeout(() => img.classList.add('show'), layer.start * 1000);
  }
  caption.textContent = timing.script;
  caption.classList.toggle('on', subtitlesOn);
}

async function play() {
  playButton.disabled = true;
  const project = await loadProject();
  for (const slide of project.slides) {
    const key = `slide_${String(slide.slide).padStart(2, '0')}`;
    const timing = project.timing[key];
    showSlide(slide, timing);
    const audio = new Audio(audioPath(slide.slide));
    audio.volume = 1;
    try { await audio.play(); } catch (e) {}
    await sleep(slide.duration * 1000);
    await sleep(500);
  }
  playButton.disabled = false;
}

playButton.addEventListener('click', play);
loadProject().then(project => showSlide(project.slides[0], project.timing.slide_01));
""",
        encoding="utf-8",
    )


def write_readme():
    (ROOT / "README.md").write_text(
        """# HyperFrames Segmented PPTX Video Project

This project treats every slide as a full-page image. It renders the source PDF/PPTX-derived deck to 1920x1080 PNG, detects large visual regions, exports transparent PNG layers with original coordinates, generates Traditional Chinese narration timing first, and builds a browser preview composition.

## Outputs

- `output/slide_##/background.png`
- `output/slide_##/*.png` transparent animation layers
- `output/slide_##/metadata.json`
- `audio/slide_##_voiceover.mp3`
- `narration/narration_script.md`
- `narration/narration_timing.json`
- `narration/subtitles.srt`
- `narration/subtitles.vtt`
- `hyperframes/index.html`
- `hyperframes/styles.css`
- `hyperframes/animation.js`
- `hyperframes/project.json`

## Regenerate

```powershell
python scripts/generate_hyperframes_video_project.py
```

## Preview

Because the preview loads JSON and MP3 files, use a local static server:

```powershell
python -m http.server 8080
```

Then open:

```text
http://localhost:8080/hyperframes/index.html
```

## Voiceover

The generated MP3 files use Microsoft Edge TTS:

- Voice: `zh-TW-HsiaoChenNeural`
- Language: Traditional Chinese / zh-TW
- Rate: `-8%`
- Format: MP3

To switch providers, replace the files in `audio/` while keeping the same filenames. Good alternatives are ElevenLabs, Azure TTS, OpenAI TTS, and Google Cloud TTS. Keep the final durations aligned with `narration/narration_timing.json`.

## Render MP4

This workspace did not include a system `ffmpeg` executable when the project was generated. Install ffmpeg or use `ffmpeg-static`, then render frames from the browser/HyperFrames composition and mux the narration audio.

Suggested ffmpeg workflow after frames and a concatenated narration track are available:

```powershell
ffmpeg -r 30 -i frames/frame_%06d.png -i narration.wav -c:v libx264 -pix_fmt yuv420p -c:a aac final/final_video_with_voiceover.mp4
ffmpeg -i final/final_video_with_voiceover.mp4 -vf subtitles=narration/subtitles.srt -c:a copy final/final_video_with_voiceover_and_subtitles.mp4
```

If you use the HyperFrames CLI, keep the timeline in `hyperframes/project.json` as the source of truth, because animation cues were scheduled from narration timing rather than the other way around.
""",
        encoding="utf-8",
    )


def maybe_write_silent_mp4(metadatas):
    path = FINAL / "final_video_preview_silent.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, FPS, (WIDTH, HEIGHT))
    if not writer.isOpened():
        return False
    for meta in metadatas:
        slide_dir = OUT / f"slide_{meta['slide']:02d}"
        bg = cv2.cvtColor(np.array(Image.open(slide_dir / "background.png").convert("RGB")), cv2.COLOR_RGB2BGR)
        layer_imgs = []
        for layer in meta["layers"]:
            rgba = cv2.imread(str(slide_dir / layer["name"]), cv2.IMREAD_UNCHANGED)
            layer_imgs.append((layer, rgba))
        total_frames = int(meta["duration"] * FPS)
        for f in range(total_frames):
            t = f / FPS
            frame = bg.copy()
            for layer, rgba in layer_imgs:
                if t < layer["start"]:
                    continue
                progress = min(1.0, (t - layer["start"]) / max(0.01, layer["duration"]))
                opacity = progress
                x, y = layer["x"], layer["y"]
                h, w = rgba.shape[:2]
                w = min(w, WIDTH - x)
                h = min(h, HEIGHT - y)
                rgba_view = rgba[:h, :w]
                rgb = rgba_view[:, :, :3]
                alpha = (rgba_view[:, :, 3] / 255.0 * opacity)[:, :, None]
                roi = frame[y : y + h, x : x + w].astype(np.float32)
                blended = roi * (1 - alpha) + rgb.astype(np.float32) * alpha
                frame[y : y + h, x : x + w] = blended.astype(np.uint8)
            writer.write(frame)
        for _ in range(int(0.5 * FPS)):
            writer.write(frame)
    writer.release()
    return True


def main():
    clean_dirs()
    images = render_pdf()
    metadatas = []
    for i, img in enumerate(images, 1):
        duration = estimate_duration(SLIDE_PLANS[i - 1]["script"])
        metadatas.append(segment_slide(img, i, SLIDE_PLANS[i - 1], duration))
    asyncio.run(generate_tts())
    metadatas = update_metadata_to_audio_durations(metadatas)
    timing = write_narration_and_timing(metadatas)
    write_hyperframes_files(metadatas, timing)
    write_readme()
    print("Generated segmented layers, narration, audio, subtitles, and HyperFrames preview.")


if __name__ == "__main__":
    main()
