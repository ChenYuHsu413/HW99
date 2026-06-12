# 工作報告：50 Startups 專案重構與多媒體交付

日期：2026-06-12
（更早的開發紀錄見 [archive/log.md](archive/log.md)，記錄 6/9 的初版建模與統計診斷過程）

---

## 總覽

| # | 工作 | 主要產出 | 狀態 |
|---|---|---|---|
| 1 | 專案清理與重構 | `src/` + `outputs/` 結構、`requirements.txt`、`.gitignore` | ✅ commit `4e3097e` |
| 2 | V2 簡報影片 | `startup-presentation-video-v2/renders/*.mp4`（76.5s） | ✅ commit `e109489` |
| 3 | 特徵選擇整合比較 | `src/compare_feature_selections.py` + 圖表 | ✅ commit `d32d724` |
| 4 | PPT 教學網頁 | `tutorial/index.html` | ✅ commit `d32d724` |
| 5 | Streamlit 互動 app | `streamlit_app.py` | ✅ commit `d32d724` |
| 6 | GitHub Pages 部署 | README Demo 連結（已驗證 HTTP 200） | ✅ commit `bb36a76` |

Demo 網址（已上線）：

- 教學網頁：<https://chenyuhsu413.github.io/HW6-Kaggle-50-Startup/tutorial/>
- V2 影片：<https://chenyuhsu413.github.io/HW6-Kaggle-50-Startup/startup-presentation-video-v2/renders/startup-profit-presentation-v2.mp4>
- V1 影片：<https://chenyuhsu413.github.io/HW6-Kaggle-50-Startup/startup-presentation-video-pptx/renders/startup-profit-presentation.mp4>

---

## 1. 專案清理與重構

刪除 429 MB 暫存物（node_modules、重複簡報圖、舊輸出、快取），將專案改為標準資料分析結構：主程式 `50_startups_crisp_dm_v2.py` → `src/modeling.py`，圖表輸出至 `outputs/figures/`、CSV 至 `outputs/metrics/`，舊版草稿移入 `archive/`。

```powershell
# git 擁有者例外（.git 由其他帳號建立）
git config --global --add safe.directory 'D:/AI Class ChenYu/AIClass/hw6'

# 重構後執行驗證（最佳模型不變：R&D Only，Adj R² 0.9173、RMSE 7,714）
pip install scikit-learn matplotlib
python src/modeling.py
```

## 2. V2 簡報影片（hyperframes）

針對三個不滿意點改版：節奏（165s → 76.5s、11 段 → 6 段故事線）、畫面（固定卡片 → 全幅 Ken Burns 運鏡 + whip-pan 快切 + 收斂印章動畫）、旁白（講稿重寫 + Edge TTS 台灣中文男聲）。V1 完整保留供比較。

```powershell
# 環境：hyperframes 需要 Node >= 22
nvm use 24.14.0

# 中文旁白（6 段，共 67.5 秒）
pip install edge-tts
edge-tts --voice zh-TW-YunJheNeural --rate=+8% --text "講稿內容" --write-media assets/narration/seg-01.mp3

# 量測音檔長度（排時間軸用）
node_modules\ffprobe-static\bin\win32\x64\ffprobe.exe -v error -show_entries format=duration -of csv=p=0 seg-01.mp3

# 品質檢查 → 渲染
cd startup-presentation-video-v2
npm install                          # ffmpeg-static / ffprobe-static
npx hyperframes@0.6.90 lint          # 0 errors
npx hyperframes@0.6.90 validate      # 無 console error、WCAG AA 全過
npx hyperframes@0.6.90 inspect       # 0 layout issues
npm run render:local                 # 1080p30 H.264，2 分 39 秒完成
```

## 3. 特徵選擇整合比較

四個特徵選擇分析（Sequential FS / 商業引導 / 五演算法 / 行銷vs行政探針）使用同一模型與切分，僅「挑特徵的方式」不同，因此可整合去重為單一排名。

```powershell
python src/compare_feature_selections.py
# 輸出：outputs/figures/feature_selection_integrated_comparison.png
#       outputs/metrics/feature_selection_integrated_comparison.csv
```

整合結論：

1. 四種視角收斂到同一贏家：`[R&D Spend]`（RMSE 7,714、Adj R² 0.917，共被評估 8 次）
2. R&D 之後加任何特徵都不會降低測試誤差（7,714–9,284）
3. 不含 R&D 的組合全面崩潰（RMSE 27,200–31,057，差 3–4 倍）
4. 唯一分歧：CV 前向選擇第二特徵挑行政、測試集偏好行銷——小樣本下 CV 與測試可能背離

## 4. PPT 教學網頁

PPTX 內投影片為整頁圖片（無文字框），故沿用高解析 PNG，教學註解依內容撰寫。支援鍵盤 ← → 與數字鍵換頁、目錄跳轉、進度條。

```powershell
pip install python-pptx     # 驗證 pptx 內容結構（結果：11 頁皆為圖片）
# 產出：tutorial/index.html（純靜態，直接開啟或由 GitHub Pages 服務）
```

## 5. Streamlit 互動 app

四分頁：📖 教學投影片 / 📊 資料探索 / ⚖️ 模型比較（即時訓練 Models A–E）/ 🎯 互動預測（滑桿 what-if + 回歸線視覺化）。

```powershell
pip install streamlit
streamlit run streamlit_app.py      # 本機（注意：8765/8901/9000 在 Windows 保留範圍，預設 8501/8502 可用）

# 自動化驗證（官方 AppTest 框架，0 例外）
python -c "from streamlit.testing.v1 import AppTest; at = AppTest.from_file('streamlit_app.py'); at.run(); print(len(at.exception))"
```

部署選項：Streamlit Community Cloud（share.streamlit.io）→ 選 repo → 主檔案 `streamlit_app.py`。

## 6. 部署與版本紀錄

```powershell
git push origin main
# GitHub Pages：Settings → Pages → Deploy from a branch → main / (root)
# 驗證：tutorial/ 與兩支 mp4 皆回應 HTTP 200
```

| Commit | 內容 |
|---|---|
| `4e3097e` | 重構為 src/ + outputs/ 結構並清理暫存物 |
| `5340f61` | 移除 .agents 影片工具檔 |
| `79ddf1d` | 還原 .agents（影片工作恢復） |
| `e109489` | V2 簡報影片 |
| `d32d724` | 整合比較 + 教學網頁 + Streamlit app |
| `bb36a76` | README 加入 Demo 連結 |

## 環境備忘

- Python 3.14（`pip`：scikit-learn 1.9.0、matplotlib 3.10.9、streamlit 1.55.0、edge-tts、python-pptx）
- Node：系統預設 18.20.8，hyperframes 需 `nvm use 24.14.0`
- Windows 保留 port 範圍會擋 streamlit/hyperframes 部分 port，遇到 "Port not available" 換 port 即可
- `.matplotlib_cache/` 每次跑分析會重新生成（已 gitignore，毋須理會）
