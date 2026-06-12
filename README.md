# HW99 — HyperFrames Segmented PPTX Video Project

把 NotebookLM 生成的「圖片型 PPTX」（20 頁，每頁是一張完整圖片、沒有可編輯元件）轉成：
有逐元素載入動畫、繁體中文女聲旁白、可選字幕的 1920x1080 / 30fps MP4。

## Pipeline

```
sources/*.pdf ──> output/slide_##/original.png      (PDF 轉 1920x1080 PNG)
                        │
                        ▼  scripts/segment_elements.py
        output/slide_##/  透明 element layers + background.png + metadata.json
                        │
                        ▼  scripts/rebuild_timeline.py
        narration/narration_timing.json + subtitles + hyperframes/project.json
                        │
                        ▼  scripts/render_final_video.py
        final/final_video_with_voiceover(.../_and_subtitles).mp4
```

旁白時間軸為主、反向安排動畫出現時間（layer 的進場時間排在該頁旁白窗口內）。

## Element segmentation 邏輯（scripts/segment_elements.py）

每頁 slide 被當成一張圖片處理，切圖規則是和人工 review 來回校正出來的：

1. **卡片／流程方格／表格**：用「被邊框包圍的內部白色區域（contour hierarchy 的洞）」偵測。
   箭頭尖端就算畫到方格邊框上（墨水相連）也不影響；表格相鄰格自動併成一張表。
2. **箭頭／icon／獨立文字**：把卡片區域從墨水遮罩中擦掉後，再偵測剩餘連通塊，
   所以箭頭切圖不會吃到鄰格邊線。
3. **虛線箭頭**：多段不相連的小線段用「虛線鏈」規則串成一支完整箭頭。
4. **文字**：同一句話合併成一個 layer（詞距門檻隨字高縮放，大字體空格較大）。
5. **紅圈 highlight**：紅圈＋被圈的卡片＋紅字註記＋手繪箭頭合成一個 `highlight_group`，
   不拆散、也不誤吞旁邊的卡片（重疊區用 alpha 挖洞）。
6. **圖表上的紅色註記**（註記文字＋向量箭頭／星號）：用筆畫粗細（≥6px 半寬）和字元尺寸
   與同色的數據曲線區分，切成獨立 `annotation` layer（紅筆畫遮罩 alpha），
   從圖表 crop 中塗白，圖表完整出現後再 fade-in。
7. **軸標籤歸圖表**：「R-squared」直式標籤、「Number of Features」caption、刻度數字
   都吸附進圖表 layer。
8. **碎片清理**：過小（<2000px²）或過細（窄邊 <26px）且緊貼卡片的殘邊併回卡片，
   不獨立成層；右下角 NotebookLM 浮水印留在背景。
9. **出場順序**：列分群（垂直中心相近為一列）→ 列內由左到右；title 永遠最先。
10. **品質門檻**：每頁所有 layers 疊回 background 必須和原圖**零像素差異**（20/20 通過）。

切圖過程可視化：`work_preview/element_debug/slide_##_debug.jpg`（原圖／偵測框／挖空背景／重組驗證），
攤開圖：`work_preview/slide_##_layer_gallery.jpg`（每層的透明 PNG、座標、出場時間）。

## 重新生成

```powershell
# 1. 重切全部 20 頁（或指定頁碼，例如 3 5 11）
python scripts/segment_elements.py

# 2. 依新 metadata 重建旁白時間軸 + 字幕 + HyperFrames 專案
python scripts/rebuild_timeline.py

# 3. 渲染最終影片（旁白版 + 燒錄字幕版，約 2-3 分鐘）
python scripts/render_final_video.py
```

> 注意：`final/` 內現有的兩支 MP4 是較早一版 layers 渲染的。
> 最新的切圖（slide 1/4/5/11/15/18/20 的修正）已反映在 `output/` 與 `hyperframes/`，
> 重跑步驟 3 即可得到同步的最新影片。

`scripts/generate_hyperframes_video_project.py` 是最初的完整 pipeline
（PDF 轉圖、旁白稿、edge-tts 配音），只有在改旁白文字或重轉 slide PNG 時才需要。

## 瀏覽器預覽（HyperFrames）

```powershell
python -m http.server 8080
```

開 <http://localhost:8080/hyperframes/index.html> 按 Play：
背景＋透明 layers 按 `project.json` 的時間軸逐個進場，同步播放各頁旁白 MP3。

## 旁白 / Voiceover

- 引擎：Microsoft Edge TTS，聲音 `zh-TW-HsiaoChenNeural`（自然女聲、語速 -8%）
- 檔案：`audio/slide_##_voiceover.mp3`（20 段）
- 旁白稿：`narration/narration_script.md`
- 時間軸：`narration/narration_timing.json`（每頁起迄、每個 layer 的 cue）
- 字幕：`narration/subtitles.srt` / `subtitles.vtt`

要換 TTS 供應商（ElevenLabs、Azure TTS、OpenAI TTS、Google Cloud TTS）：
換掉 `audio/` 內同名 MP3 後重跑步驟 1–3，各頁長度與動畫時間會自動依新音檔調整。

## 輸出清單

| 路徑 | 內容 |
|---|---|
| `output/slide_##/` | original.png、background.png、透明 element layers、metadata.json |
| `audio/` | 20 段 zh-TW 女聲旁白 MP3 |
| `narration/` | 旁白稿、timing JSON、SRT/VTT 字幕 |
| `hyperframes/` | index.html、styles.css、animation.js、project.json（瀏覽器預覽） |
| `final/` | 無字幕版與燒錄字幕版 MP4 |
| `work_preview/` | 切圖 debug 圖與 layer 攤開圖 |
| `sources/` | 來源 PPTX/PDF 與參考文件 |
