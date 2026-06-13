# Work Report — Image-PPTX → Animated Narrated Video

期間：2026-06-12 ~ 2026-06-13（三個 Claude Code session）
專案：`HW99/`（NotebookLM 圖片型 PPTX）、`HW99/writing-os/`（The A-Z Writing OS PDF）
最終產出：
- 可重用的 Claude Code skill：`.claude/skills/pptx-to-animated-video/`
- 兩支動畫旁白 MP4（無字幕版 / 燒錄字幕版，writing-os 子專案）
- 完整 segmentation + 旁白 + 字幕 + HyperFrames 預覽 pipeline

---

## 1. 起點與目標

把 NotebookLM 出的「圖片型 PPTX/PDF」（每頁是一張平面圖、沒有可編輯元件）變成 1920x1080 / 30fps 動畫 MP4：
- 把每頁切成可動畫化的 element layers（卡片、箭頭、icon、illustration、highlight、annotation 等）
- 用旁白時間軸反向安排各 layer 進場時間
- 燒錄繁中女聲 TTS 旁白與字幕

第一版 segmentation 太粗（只切大區塊）。整個專案的價值在「每一次人工 review 之後把學到的規則寫回演算法」——讓 skill 在下個 deck 仍然能用。

---

## 2. Session 1 — 切圖規則奠基（HW99/，NotebookLM deck）

### 主要進展
- 建立 PDF→PNG→segmentation→narration→timeline→render 全 pipeline。
- segmentation 從「大區塊偵測」改成兩階段：偵測卡片（hole+border ring）→ 擦除卡片後切剩餘 ink。
- 紅圈 highlight、虛線箭頭、紅色圖表註記三類特殊規則進演算法。
- 文字行合併：詞距與字高耦合，欄位走廊（cross-column corridor）vetoes 防止跨欄串接。
- 13 頁 layers 全部通過「重組原圖 0px 差異」驗證。

### 人工 review 改動
- slide 11：`arrow_01 + table_01` 視為整體；highlight 群組概念引入。
- slide 01：閱讀順序 5/6/7 修正為符合人類由上而下、左到右。
- slide 04：左右箭頭切法一致化。
- slide 05、15、18：小面積 fragment 折回卡片，不獨立成 layer。

### Skill 化
- 將整套流程包成 `.claude/skills/pptx-to-animated-video/`，描述 + 7 個 workflow 步驟 + segmentation 品質規則。
- 推到 GitHub `ChenYuHsu413/HW99`。

---

## 3. Session 2 — Skill 首次跨專案使用（writing-os）

### 主要進展
- 在 `writing-os/` 子資料夾使用 `/pptx-to-animated-video` skill 處理「The A-Z Writing OS.pdf」（13 頁）。
- 自動產生：13 頁切圖、繁中旁白稿、TTS MP3、subtitle、HyperFrames 預覽、兩支 MP4。

### 演算法回授
- chevron-letter 字體大、空心（hollow），與普通文字行的合併規則衝突 → 加入「letter 字高 ≥ 130 且密度 < 0.22 不合併」例外。
- 連結器網（connector skeleton）被偵測成單一巨型 contour → 用 morphology close 把網絡內的高密度節點（字、卡片）救回成 piece，網本身留在背景。
- 殘留長細條（divider line 餘骸）排除。
- 0.35 size cap 與 0.9 width/height cap 用來區別「真正的卡片」與「裝飾外框」。

---

## 4. Session 3 — 把 skill 練成可重用工具（今天）

User 一開始就強調：「I want to develop a skill, not just only for these slides」——所以這 session 的核心是把每次人工 review 學到的東西**內化進演算法**，不是堆疊 per-slide override。

### 4.1 Slide 2 切圖再深化
| 問題 | 解決 |
|---|---|
| Paper pile + REJECTED 應該是一個元素 | 預設改為合併 stamp 進入底層 illustration（移除 `exclude_red: True`）。 |
| 右側 DIAGNOSTIC TERMINAL 區塊應該是一個元素 | OVERRIDE 提供合併框；之後在演算法層發現可由 `detect_cards` 自動偵測。 |
| 左側內容要先於右側 | OVERRIDE 加 `order` regions；之後因兩個 panel 都被 cards 偵測，row-cluster sort 自動正確排序。 |
| 問題: 為什麼…? 要先於右側 diagnostic | OVERRIDE 加 order 區隔。 |
| 元素 1（[TRADITIONAL header）不必要 | 後續演算法升級後 left panel 被當作整體卡片，TRADITIONAL 自然被包進去。 |
| 左側其實是一塊「連續元素」 | 抬高 `detect_cards` 面積上限 0.35→0.48，讓 ring=1.0 的半版面 panel 可成為卡片。 |
| Footer banner 被吞進 right card 撐大成全螢幕 | 修正 trim/absorb 規則：絕對 cut > 14 不夠，還要 `cut > 0.20 * perpendicular_dim`。 |

### 4.2 Slide 4 切圖修正
- Column C 「Cure:」label 因過短被遺漏 → 新增 `tight` merge spec 拉回。

### 4.3 三大演算法升級（內化進 `segment_elements.py`）

**A. 半版面 panel-card（提升 `detect_cards` 面積上限 0.35 → 0.48）**

  Half-slide 邊框完整的區域（ring fraction = 1.0、面積 35–48%）視為 single panel-card。0.9 width/height cap 仍擋住整版 chrome。slide 2 左右 panel 雙雙自動偵測成功。

**B. `collage_cluster` 通用 pass**

  在 word/line merge 之後跑：找 3+ 個 piece，gap ≤ 80px，axis overlap，並通過六道閘：
  - 連通分量大小 ≥ 3
  - bbox ≤ 30% 投影面積
  - piece-bbox 密度 ≥ 30%
  - 長寬比 ≤ 4
  - **raw ink ratio ≥ 0.17**（slide 2 paper pile 0.19 過、slide 4 A/B chevron grid 0.14 退）
  - 無 cross-column corridor

  Paper pile 從此自動合併，不靠 OVERRIDE。

**C. trim/absorb fraction rule**

  原本 `cut > 14` 直接 absorb 會讓 footer banner 被卡片吞掉、bbox 暴漲至全螢幕。改成同時要求 `cut > 0.20 * perpendicular_dim`：15px 切口在 124px 高的 footer 上只是 12%，應 trim 不應 absorb。

### 4.4 影片產生

- TTS 速率從 `-8%`（教學語速）→ `+38%`（≈1.5× 之前速度），重生 13 段 MP3。
- 解決 ffprobe 找不到的問題：建立 `writing-os/node_modules` → `../node_modules` junction。
- 重新 segment、build timeline、render：83 layers、4:02 min、20 MB 無字幕版 + 23 MB 字幕版。

### 4.5 字幕優化

**問題：** 每頁旁白 100–160 字塞成一個 SRT cue，跨 12–23 秒；FontSize=11 下換行 4–5 行，遮住投影片底部內容。

**解法（兩階段）：**
1. **Chunking（`build_timeline.py`）：** 新增 `chunk_narration()`，先以 `。！？` 切句，過長者再用 `，：；、` 切子句，每 chunk ≤ 32 個 CJK 字，按字數比例分配時間。
2. **字幕樣式（`render_final_video.py`）：** 半透明黑底 box（`BorderStyle=3` + `BackColour=&H66000000`），白字（`PrimaryColour=&H00FFFFFF`——注意 libass alpha 反過來，`FF=透明`、`00=不透明`，第一次寫成 `&HFFFFFFFF` 結果文字消失）。

**再深化：letterbox**

  使用者反映「有些 slide 底部本來就有內容」。最終 Filter chain：
  ```
  scale=1920:960,pad=1920:1080:0:0:color=0x101010,subtitles=...
  ```
  畫面下方 120px 變成字幕專用暗條；無論 deck 怎麼設計，字幕永遠不會碰到 slide 內容。輕微 11% 垂直壓縮，肉眼幾乎察覺不出。

  「只重燒字幕、不重 render」用獨立 ffmpeg 指令完成，省下 ~10 分鐘。

### 4.6 Skill 同步更新

`.claude/skills/pptx-to-animated-video/` 收到本日所有改動：

- **`SKILL.md`** 新增 / 改寫：
  - Step 3 TTS：`+38%` 1.5× 加速指引、`node_modules` junction 解法。
  - Panel-card 規則（面積上限 0.48）。
  - `collage_cluster` 規則（6 道閘的閾值來源）。
  - Stamp/highlight 預設併入底層元素（`exclude_red` 改成 opt-in）。
  - trim/absorb 必須是 fraction-of-piece（避免 footer 吞卡片）。
  - 字幕分塊（`chunk_narration`）章節。
  - 字幕燒錄 letterbox + ASS style + libass alpha 反向警告。
  - 「Per-slide OVERRIDES vs algorithm changes」：算法優先、override 最後手段。

- **`scripts/segment_elements.py`** baseline 版：`OVERRIDES = {}`，但保留所有 flag 的 inline 註解。三大演算法升級全部內建。
- **`scripts/build_timeline.py`**：`chunk_narration` 函式 + `SUB_CHUNK_MAX = 32` 常數 + 比例分配時間。
- **`scripts/render_final_video.py`**：letterbox + 修正後的 ASS style。

---

## 5. 量化成果

| 指標 | Day 1 結束 | Day 3 結束 |
|---|---|---|
| Skill 是否可跨 deck 重用 | 初版 | 演算法成熟、覆蓋多 case |
| Slide 2 layer 數 | 6（碎） | 4（左 panel / REJECTED annotation / 右 panel / 底部 footer） |
| Slide 4 layer 數 | 14（缺 C 欄 label） | 14（完整） |
| Per-slide OVERRIDE entries（writing-os） | 7 條 | 4 條（slide 2 整條移除） |
| 字幕單 cue 字數上限 | 全頁旁白（100–160 字） | 32 字 |
| 字幕是否會遮 slide 內容 | 會 | 不會（letterbox 專用暗條） |
| 旁白語速 | -8%（慢） | +38%（≈1.5× 快） |

---

## 6. 未完成 / 後續可優化

- 字幕同步精度：目前按字數比例分配 chunk 時間。若要逐字 timestamp，可改用 whisper-timestamped 或 forced-alignment。
- TTS 多語：目前 zh-TW 預設，英語 deck 要替換 voice + 詞距、字距規則。
- 黑色 letterbox 顏色：`0x101010` 與字幕 box 顏色接近一致，若 slide 主視覺也是深色可能融在一起；可改 deck-specific 背景色。
- collage 偵測：`ink_ratio ≥ 0.17` 閾值僅在 writing-os deck 校準，未來其他 deck 仍需 layer gallery review。
