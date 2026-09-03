# 吉寶軒 × Fable 5.1：現況資源包

> 產生日期：2026-09-03 · 產生者：Claude Code（Opus 5）· 性質：**唯讀盤點，不是實作授權**
> 用途：作為 Fable 5.1 進行 UX／UI、質感提升與 GAS 鑑定引擎優化討論的唯一現況依據。
> 所有數字都是本日實測，不是文件轉述。實測方法附在每一節。

---

## 0. 三十秒版

- **Sol「私人鑑賞圖錄」藍圖的 Slice 1 已 100% 完成，Slice 2 完成約 7 成，Slice 3 只完成「不顯示」那一半。**
- **Sol 的首屏目標幾何（§3.1）在 1440 已達標且超標**：要求首件器物露出 ≥240px，實測 391px。
- **Sol 的分類列清理（§3.2）完全沒動**：glyph 與圓形件數 badge 都還在。
- **v3 rubric 的「可被發現性」仍然是 0**：全站無 JSON-LD、無 deep-link、無分享、無 canonical。
- **GAS 鑑定引擎有三個可執行的修正點**，其中一個（取樣參數已被官方廢棄）直接影響「調教 Gemini 解析」的有效性。

---

## 1. 專案北極星與不可動邊界

摘自 `AGENTS.md`（唯一規則來源），Fable 的所有建議都必須落在這個框內。

- 吉寶軒是**數位展示入口，不是電商**。完成動作是促成藏家到實體藝廊賞件、預約或洽詢。
- 前端：**純 HTML / CSS / vanilla JS**，GitHub Pages。無 React／Vue／Tailwind／npm／build step。
- 後端：Google Apps Script + Google Sheets + Google Drive。
- Sheets 13 欄 V1 **凍結**；任何欄位增刪改名需 DD-XXX，且 `writeToSheet()`／`doGet()`／前端 parser 三端同步。
- `era` 9 值列舉凍結。
- **Tier 1（必須 Craig 拍板）**：首頁 IA、品牌方向、色彩／字體系統、公開內容、新功能、任何真偽／鑑定措辭。
- **仍然沒有的資料**：LINE ID、地址、營業時間、Google Maps、電話。不得為改善導流而虛構。

### 完工協議（`AGENTS.md` §12，2026-08-27 建立）

一個切片完成 = 檔內 `CHANGE <TAG>` 註解 + `CHG_LOG.json` entry + git commit，**三者缺一不算完成**。
`tests/test_change_log_contract.py` 會擋。Fable 提出的任何切片建議都要能落進這個格式。

---

## 2. Repo 現況

| 項目 | 值 | 取得方式 |
|---|---|---|
| 分支 / HEAD | `main` @ `93f86e7` | `git log` |
| 工作區 | 乾淨（僅 2 個待處理的無關檔案） | `git status --short` |
| `Publish/index.html` | **4883 行** | `wc -l` |
| 測試 | **325 passed, 2 skipped** | `pytest tests/ -q` |
| `CHG_LOG.json` | 24 筆 entry，最新 2026-09-02 | 讀檔 |
| 線上真實資料 | **62 件典藏、7 個分類分頁** | 本機預覽實跑 GAS `doGet()` |

### 前端實際消費的公開欄位

`grep` `Publish/index.html` 得到：`itemName`(5) `category`(7) `era`(4) `tags`(5) `story`(3)
`imageUrl`(5) `highlightQuote`(4) `images`(2) `displayRecommendation`(1)。

**`refItem` 與 `refPrice` 已完全不被前端消費**（0 次）——這是 Sol §3.4 fail-closed 要求的一半，已達成。

---

## 3. Sol 藍圖逐項完成度盤點

比對對象：`GPT Design/jibao_xuan_design_pack/` 的提案全文與 delta map。
狀態欄：✅ 完成 ／ 🟡 部分 ／ ❌ 未做 ／ ⛔ 被鎖住。

### Slice 1 — P0／Tier 2：真實性與裝飾減法 → ✅ **100% 完成**

| Sol 要求 | 狀態 | 實測證據（`grep -c` on `Publish/index.html`） |
|---|:--:|---|
| 移除 `LOT` 序號 | ✅ | `lot-number` = 0 |
| 移除 `.card::before/::after` 四角金線 | ✅ | `card::before` = 0 |
| 移除 `.vignette-cloud` | ✅ | 0 |
| 移除 `.moving-cloud` | ✅ | 0 |
| 移除 `.focus-border` | ✅ | 0 |
| 移除 `initCardTilt()` 3D 傾斜 | ✅ | `initCardTilt` = 0、`tilt-active` = 0 |
| `.info-box` 去錦格紙紋 | ✅ | `CHANGE SOL-OBJECT-FIRST`：改為 `background: var(--paper-200)` 純色暖紙 |
| 移除未具備資訊的承諾 | ✅ | `CHANGE A4-HONEST`（2026-08-27）：disabled LINE 按鈕與「24 小時內回覆」皆已移除 |

### Slice 2 — P1／Tier 1：Hero art direction → 🟡 **約 7 成**

| Sol 要求 | 狀態 | 實測證據 |
|---|:--:|---|
| 移除 WebGL 全螢幕霧 | ✅ | `#glCanvas` = 0、`initWebGLFog` = 0 |
| 移除固定 `ink-vignette` | ✅ | 0 |
| 背景改 Hero 專用 art panel，不再 fixed 鋪滿 | ✅ | `.bg-layer` 改為 `position: absolute`，桌機 `height: 460px`、手機 `330px` |
| **目標幾何**：1440 首件器物露出 ≥240px | ✅ **超標** | 1440×1024 實測：hero panel 430px、分類列 top 438px、**第一張卡片露出 391px** |
| 如意雲不再持續浮動 | ❌ | `ruyiCloudBreathe 16s ease-in-out infinite` 仍在（2 處） |
| 無持續霧 | ❌ | WebGL 霧移除後，**CSS 霧補了回來**：`heroMistFar 32s infinite alternate`、`heroMistNear 28s infinite`（4 處） |
| 1440／1024／375 各有明確山水 crop | ❌ | 未依 Sol 的「右側山峰＋左側素紙」構圖重做 |

> ⚠️ **本機預覽的 hero 是空白素紙，這不是 bug。** `.bg-layer` 以 `./seedream-*.webp` 引用，
> 而該檔只在 repo 根目錄、不在 `Publish/`。`.github/workflows` 的部署腳本會把它複製到
> 公開 repo 的根目錄，所以**線上有圖、本機沒圖**。Fable 若在本機審 hero，看到的不是真相；
> 要看真實 hero 必須開 GitHub Pages 線上站。

### Slice 3 — P1／Tier 1＋DD-103：Modal dossier 與市場參考 → 🟡 **只完成「不顯示」那一半**

| Sol 要求 | 狀態 | 實測證據 |
|---|:--:|---|
| `#modalAppraisal` 統稱「鑑定參考」退場 | ✅ | `modalAppraisal` = 0；已拆為「圖錄索引／器物脈絡／陳設筆記」三區 |
| `refPrice` 不得在 `refItem` 缺失時單獨顯示 | ✅ | 兩者前端皆 0 次消費；檔內留有 `DD-103` 註解說明暫不呈現 |
| `displayRecommendation` 不得補位到市場區 | 🟡 | 已不在市場區，但**仍公開於「陳設筆記」自成一區**（1 處）。需 Craig 確認這樣是否可接受 |
| 10 項完整性欄位（拍賣行／專場／日期／Lot／價格類型／幣別／數值／來源頁／比較理由／人工覆核） | ⛔ | **DD-103 未通過，欄位不存在**。Sheets V1 凍結，需三端同步 |
| 固定聲明「僅作市場參考…」 | ⛔ | 隨 DD-103 一起卡住 |

### Sol 其他章節

| Sol 要求 | 狀態 | 實測證據 |
|---|:--:|---|
| §3.2 分類列移除首字 glyph 與圓形件數 badge | ❌ | 1440 實測：`glyph` 節點 8 個、`count` 節點 7 個，**全部還在** |
| §3.2 375 採水平滑動 | ✅ | 小螢幕 `overflow-x: auto`。delta map §5-A 的「wrap vs scroll」衝突**已朝 scroll 解決** |
| §3.3 卡片資訊順序（分類/年代→品名→metadata→摘要→細看） | ❓ | 未驗證，需真實資料逐筆檢視 |
| §3.5 contact 現階段策略 | ✅ | 已誠實化（見 Slice 1） |
| §4.2 字體系統 | ❌ | Tier 1，未動 |
| §5 動態收斂 | 🟡 | 卡片動態已收斂；hero 霧與如意雲仍持續（見 Slice 2） |

---

## 4. Sol 藍圖沒涵蓋、但 v3 rubric 指出仍為 0 的維度

`AP_Design_Loop_v3_Strategy.md` 的診斷是：5 維美學尺已飽和 20/20，真正的梯度在「產出型」維度。
以下是本日實測，**全部為 0**：

| 維度 | 實測 | 證據 |
|---|:--:|---|
| 結構化資料 | **0** | `application/ld+json` = 0 |
| 藏品 deep-link | **0** | `location.hash` = 0、`pushState` = 0 |
| 原生分享 | **0** | `navigator.share` = 0 |
| canonical | **0** | `rel="canonical"` = 0 |
| 可用對外導流路徑 | **0** | contact 已誠實化但無出口——⛔ 卡在 owner 資料，非技術問題 |

**含意**：62 件典藏目前無法被 Google 以 Rich Results 收錄、無法單件分享、重新整理不保留狀態。
對「決策期以月計、會反覆回訪與轉傳」的高端藏家，這是比視覺質感更硬的缺口。

---

## 5. GAS 鑑定引擎現況與 Gemini API 檢查

### 5.1 現況

| 項目 | 值 |
|---|---|
| 檔案 | `scripts/GAS/AntiqueAnalysis_AI.md`（156KB，**已 gitignore**） |
| 金鑰 | 已全部改由 Script Properties 讀取，原始碼無硬編碼 ✅ |
| API base | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` |
| 模型 fallback 鏈 | `gemini-3.7-flash`(medium) → `gemini-3.6-flash`(medium) → `gemini-3.5-flash`(medium) → `gemini-3.5-flash-lite`(**minimal**) |
| thinking 設定 | `generationConfig.thinkingConfig.thinkingLevel` |
| 取樣參數 | `temperature: 0.65`、`topP: 0.92`、`topK: 40`、`maxOutputTokens: 2200` |
| 結構化輸出 | `response_mime_type: "application/json"` + `response_schema`（OBJECT，含 `isValid` / `objectGrouping` / `views[]` 等） |
| 相關測試 | `test_antique_gas_gemini_fallback.py`、`_multi_image.py`、`_preflight.py`、`_queue_reliability.py` |

### 5.2 對照官方文件（2026-09-03 查核）的四個發現

**① 取樣參數已被官方廢棄 —— 這條最重要，直接影響「調教解析」**

官方 changelog 2026-07-21：`temperature`、`top_p`、`top_k` 已 deprecated。3.8 Flash 的
migration checklist 明寫：「Strip `temperature`, `top_p`, and `top_k` from generation configs.」

GAS 目前仍送 `temperature: 0.65 / topP: 0.92 / topK: 40`。程式碼註解記載 v9.2 曾把
temperature 從 0.55 調到 0.65「增加表達多樣性，減少套版」——**如果這些參數已被忽略，
那次調校很可能是 no-op**。要調教解析品質，槓桿已經從取樣參數移到 `thinkingLevel`、
system instruction 與 `response_schema` 的欄位描述。

**② `thinkingLevel: "minimal"` 的合法性存疑**

generateContent 文件列出的 thinking level 是 `low` / `medium`(預設) / `high`，並明寫
「minimal is not supported on 3.8 Flash and will return an error」。GAS 對
`gemini-3.5-flash-lite` 使用 `minimal`。該值在 3.5-flash-lite 上是否仍合法需實測——
這是 fallback 鏈的**最後一環**，壞掉時不會有人發現，只會表現為「全鏈失敗」。

**③ 模型鏈落後一代**

`gemini-3.8-flash` 已於 **2026-09-02 GA**（官方描述：長時程軟體工程、自主 agent 與複雜企業流程）。
GAS 鏈頂是 `gemini-3.7-flash`（2026-08-13 GA，仍有效，不是失效模型）。
是否升頂是**成本 vs 解析品質**的取捨，不是 bug——需要用真實藏品照片做 A/B 才有答案。

**④ `generateContent` 已被標記為 Legacy**

官方文件已將 generateContent 頁面標為 Legacy，主推 **Interactions API**
（`https://generativelanguage.googleapis.com/v1beta/interactions`）。
generateContent 未宣告停用日期，**不緊急**，但這是未來 12 個月的架構議題。

> 已驗證正確、不需要動的：`thinkingConfig.thinkingLevel` 的 JSON 路徑正確；
> `response_schema` 用 snake_case 混在 camelCase 的 `generationConfig` 裡雖不一致，
> 但 proto3 JSON 兩種寫法都接受，可正常運作。

**來源**：
[Models](https://ai.google.dev/gemini-api/docs/models?hl=zh-tw) ·
[What's new in Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/latest-model) ·
[generateContent latest-model (Legacy)](https://ai.google.dev/gemini-api/docs/generate-content/latest-model) ·
[Changelog](https://ai.google.dev/gemini-api/docs/changelog)

---

## 6. 資源索引：Fable 要看哪些檔案

| 檔案 | 是什麼 | 怎麼用 |
|---|---|---|
| `AGENTS.md` | **唯一規則來源**，含 §12 完工協議 | 先讀。與直覺衝突時，檔案贏 |
| `Publish/index.html` | **唯一的公開頁實作主體**（4883 行） | 所有改動只能落在這裡 |
| `GPT Design/jibao_xuan_design_pack/` | Sol 提案全文 + delta map + 6 張 mockup | 設計方向的基線 |
| `AP_Design_Loop_v3_Strategy.md` | rubric v3（5 美學地板 + 7 產出天花板）、5 個 epic | 為什麼不該再追 20/20 |
| `scripts/GAS/AntiqueAnalysis_AI.md` | GAS 鑑定引擎全文（gitignore） | Gemini 調教的主體 |
| `CHG_LOG.json` | 24 筆結構化完工紀錄 | 「現在做到哪」的權威答案 |
| `.claude/commands/design-review.md` | v3.0 主審 skill | 既有評分程序，不要另建一套 |

### 兩個已知的環境陷阱

1. **本機預覽看不到 hero 山水**（見 §3 的警告框）。要審 hero 請開線上站。
2. `AGENTS.md` 的指令是 WSL2 路徑；本機 session 跑在 Windows。跑測試走
   `wsl bash -c "cd '/mnt/c/...' && python3 -m pytest tests/ -q"`。

---

## 7. 需要 Fable 回答的問題

### A. 質感與高奢感（主命題）

1. Slice 1 的裝飾減法做完之後，頁面「乾淨了，但是否也變平了」？**在不加回任何古典符號的前提下**，
   質感應該從哪三個地方長回來？請對應到 header／分類列／卡片／modal／contact 五個既有位置。
2. Sol §4.1 主張「使用密度比換色更重要」，並保留四個核心 token。
   以現況實測（hero 430px、卡片素紙資料欄、朱紅只用於印記與底線），這條路走完了嗎？
   還是已經減過頭、需要重新引入層級對比？
3. 對照 Sotheby's Asia／中國嘉德／故宮的圖錄語言，吉寶軒現在最缺的是**排版節奏、影像規格、還是資訊密度**？
   請只挑一個並說明為什麼另外兩個是次要的。

### B. 未完成的 Sol 項目（請給取捨，不要只說「照做」）

4. hero 的 CSS 霧與如意雲呼吸：Sol 要求全部移除。但 WebGL 移除後留下的 CSS 版本成本極低。
   **保留還是移除？** 請針對「靜態頁面是否需要生命感」給出立場，而不是照抄提案。
5. 分類列的 glyph 與圓形件數 badge：Sol 要求移除。目前 8 個 glyph／7 個 count 仍在。
   移除後分類列會不會變得**太像純文字選單、失去圖錄目次感**？
6. `displayRecommendation`（陳設筆記）自成一區公開，這是否符合「證據先於裝飾」？

### C. GAS 解析調教

7. 若取樣參數確實已失效，要提升鑑定文字品質，**system instruction、`response_schema` 欄位描述、
   `thinkingLevel` 三者的優先順序**應該是什麼？
8. 現行 `maxOutputTokens: 2200` 搭配「反 padding」意圖。以骨董敘事而言這個上限是否合理？
9. 是否值得升到 `gemini-3.8-flash`？請給一個**可執行的 A/B 驗證設計**（用哪幾件藏品、比什麼指標）。

### D. 排序

10. 綜合以上，**下一個唯一切片**應該是什麼？請給出：檔案範圍、成功條件、
    1440／1024／375 驗收方式、以及明確的「不該做什麼」。

---

## 8. 停止線（Fable 不得越過）

- 本文件是**現況盤點與討論材料**，不是實作、部署或欄位變更授權。
- 不得提出虛構的 LINE ID、地址、營業時間、Google Maps 或任何實體藝廊資料。
- 不得產生任何「真品」「保真」「鑑定服務」措辭，或無來源的拍賣紀錄、Lot 號、成交價。
- 不得建議引入 React／Vue／Tailwind／npm／build step，或取代現有純前端架構。
- 不得建議在 DD-103 通過前接上市場參考的任何新欄位。
- 不得建議通用奢侈品網站語彙：霓虹、粒子、marquee、3D carousel、custom cursor、
  hover-only 主互動、電商徽章、倒數、稀缺性。
- 觸及 Tier 1（首頁 IA、品牌方向、色彩／字體系統、公開內容、新功能）時，
  **標示為 Tier 1 並交回 Craig**，不得當成可自行執行的切片。
