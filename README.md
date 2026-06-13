# HW99 — Image-PPTX → Animated Narrated Video

把 NotebookLM 生成的「圖片型 PPTX/PDF」（每頁是一張完整圖片、沒有可編輯元件）
轉成有逐元素載入動畫、繁體中文女聲旁白、可選字幕的 1920x1080 / 30fps MP4。

整套流程已抽成可重用 Claude Code skill：`.claude/skills/pptx-to-animated-video/`
（在任何專案目錄下對 Claude Code 輸入 `/pptx-to-animated-video <deck.pdf>` 即可重跑同樣 pipeline）。

> 本專案的演進歷程、所有 user prompt、與設計決策的「為什麼」：
> - 流水帳：[`PROMPTS.md`](PROMPTS.md)
> - 完整 work report：[`WORK_REPORT.md`](WORK_REPORT.md)

## 兩個 deck

| 目錄 | Deck | 頁數 | 狀態 |
|---|---|---|---|
| `./` （root） | NotebookLM 投影片（20 頁） | 20 | session 1 完成，奠定 segmentation 規則 |
| `writing-os/` | The A-Z Writing OS.pdf | 13 | session 2-3 完成，最新影片在 `writing-os/final/` |

兩個 deck 都跑相同的 pipeline，所有公用邏輯都在 skill 裡。

## Pipeline

```
sources/*.pdf ──> output/slide_##/original.png            (PDF 轉 1920x1080 PNG)
                        │
                        ▼  scripts/segment_elements.py
        output/slide_##/  透明 element layers + background.png + metadata.json
                        │
                        ▼  scripts/build_timeline.py
        narration/narration_timing.json + subtitles + hyperframes/project.json
                        │
                        ▼  scripts/render_final_video.py
        final/final_video_with_voiceover(.../_and_subtitles).mp4
```

旁白時間軸為主、反向安排動畫出現時間（layer 的進場時間排在該頁旁白窗口內）。

## 重新生成（writing-os 子專案）

```powershell
cd writing-os

# 1. 重生 TTS（可換語速：-8% 教學語速、+38% ≈ 1.5× 快）
python "../.claude/skills/pptx-to-animated-video/scripts/tts_edge.py" zh-TW-HsiaoChenNeural +38%

# 2. 重切全部 13 頁（或指定頁碼如：python scripts/segment_elements.py 2 4）
python scripts/segment_elements.py

# 3. 依新 metadata 重建旁白時間軸 + 字幕 + HyperFrames 專案
python scripts/build_timeline.py

# 4. 渲染最終影片（無字幕版 + 燒錄字幕版，背景跑）
python scripts/render_final_video.py
```

只改字幕樣式時，不需要重 render，直接重燒字幕即可：
```powershell
./node_modules/ffmpeg-static/ffmpeg.exe -y -i final/final_video_with_voiceover.mp4 `
  -vf "scale=1920:960,pad=1920:1080:0:0:color=0x101010,subtitles=narration/subtitles.srt:force_style='FontName=Microsoft JhengHei,FontSize=11,PrimaryColour=&H00FFFFFF,BorderStyle=3,Outline=8,Shadow=0,BackColour=&H66000000,MarginL=30,MarginR=30,MarginV=10'" `
  -c:v libx264 -preset veryfast -crf 18 -c:a copy `
  final/final_video_with_voiceover_and_subtitles.mp4
```

## Element segmentation 邏輯（`scripts/segment_elements.py`）

每頁 slide 被當成一張圖片處理，切圖規則是和人工 review 來回校正出來的：

1. **卡片／流程方格／表格／半版面 panel**：用「被邊框包圍的內部白色區域（contour hierarchy 的洞）」偵測。
   面積上限放寬到 0.48× 投影片，允許 slide 2 那種左右兩半 panel 各自成為單一卡片。
   箭頭尖端就算畫到方格邊框上（墨水相連）也不影響；表格相鄰格自動併成一張表。
2. **箭頭／icon／獨立文字**：把卡片區域從墨水遮罩中擦掉後，再偵測剩餘連通塊，
   所以箭頭切圖不會吃到鄰格邊線。
3. **虛線箭頭**：多段不相連的小線段用「虛線鏈」規則串成一支完整箭頭。
4. **文字**：同一句話合併成一個 layer（詞距門檻隨字高縮放，大字體空格較大）。
5. **拼貼物（collage_cluster）**：3+ 個 piece 在 80px 內、有重疊軸、bbox 不超過 30%、
   raw ink ratio ≥ 0.17、無欄位走廊 → 合併為單一 illustration。
   讓 slide 2 紙堆 + REJECTED 章自動合成一塊。
6. **紅圈 highlight**：紅圈＋被圈的卡片＋紅字註記＋手繪箭頭合成一個 `highlight_group`，
   不拆散、也不誤吞旁邊的卡片（重疊區用 alpha 挖洞）。
7. **圖表上的紅色註記**（註記文字＋向量箭頭／星號）：用筆畫粗細（≥6px 半寬）和字元尺寸
   與同色的數據曲線區分，切成獨立 `annotation` layer，從圖表 crop 中塗白，圖表出現後再 fade-in。
8. **軸標籤歸圖表**：直式 y-label、x-caption、刻度數字都吸附進圖表 layer。
9. **碎片清理**：過小（<2000px²）或過細（窄邊 <26px）且緊貼卡片的殘邊併回卡片。
10. **trim/absorb 規則**：piece 邊緣與卡片重疊時，cut 必須同時 `> 14px` 且 `> 0.20×piece 對應邊`
    才合併進卡片；否則 trim 掉重疊部分。避免 footer banner 拖垮整張卡片 bbox。
11. **出場順序**：列分群（垂直中心相近為一列）→ 列內由左到右；title 永遠最先。
    兩 panel 版面自動「左 → 右」。
12. **品質門檻**：每頁所有 layers 疊回 background 必須和原圖**零像素差異**（>20 強度差才算）。

切圖過程可視化：`work_preview/element_debug/slide_##_debug.jpg`（原圖／偵測框／挖空背景／重組驗證），
攤開圖：`work_preview/slide_##_layer_gallery.jpg`（每層的透明 PNG、座標、出場時間）。

## 旁白 / Voiceover

- 引擎：Microsoft Edge TTS，聲音 `zh-TW-HsiaoChenNeural`
- 預設語速：`-8%`（教學）；快版 `+38%`（≈ 1.5× 快）
- 旁白稿：`narration/narration_script.md`
- 時間軸：`narration/narration_timing.json`（每頁起迄、每個 layer 的 cue）
- 字幕：`narration/subtitles.srt` / `subtitles.vtt`，已自動分塊（每 cue ≤ 32 個 CJK 字）

要換 TTS 供應商（ElevenLabs、Azure、OpenAI、Google）：
換掉 `audio/` 內同名 MP3 後重跑步驟 2–4，各頁長度與動畫時間會自動依新音檔調整。

## 字幕排版

最終影片用 **letterbox** 模式：投影片內容縮到上方 1920x960，下方留 120px 暗條當字幕專用區。
無論 deck 底部有什麼內容（footer、alert box、子問題），字幕都不會遮到。
半透明黑底 + 白字、ASS BorderStyle=3 + BackColour=&H66000000。
`+38%` 配 32-char chunk 通常一行一句，順暢易讀。

## 瀏覽器預覽（HyperFrames）

```powershell
cd writing-os
python -m http.server 8080
```

開 <http://localhost:8080/hyperframes/index.html> 按 Play：
背景＋透明 layers 按 `project.json` 的時間軸逐個進場，同步播放各頁旁白 MP3。

## 輸出清單（writing-os/）

| 路徑 | 內容 |
|---|---|
| `output/slide_##/` | original.png、background.png、透明 element layers、metadata.json |
| `audio/` | 13 段 zh-TW 女聲旁白 MP3 |
| `narration/` | 旁白稿、timing JSON、SRT/VTT（已分塊） |
| `hyperframes/` | index.html、styles.css、animation.js、project.json（瀏覽器預覽） |
| `final/` | 無字幕版 MP4 + 燒錄字幕（letterbox）版 MP4 |
| `work_preview/` | 切圖 debug 圖、layer 攤開圖、字幕檢查 frame |

## Skill 結構

```
.claude/skills/pptx-to-animated-video/
├── SKILL.md          # workflow、segmentation 品質規則、字幕規範
└── scripts/
    ├── render_slides.py        # PDF → PNG
    ├── tts_edge.py             # Edge TTS（可指定語速）
    ├── segment_elements.py     # 切圖（含 collage_cluster、panel-card、trim fraction）
    ├── build_timeline.py       # 字幕分塊、HyperFrames、SRT/VTT
    └── render_final_video.py   # 字幕 letterbox 燒錄
```

未來在任何專案要把圖片型投影片轉成旁白動畫 MP4，呼叫 `/pptx-to-animated-video` 即可。
