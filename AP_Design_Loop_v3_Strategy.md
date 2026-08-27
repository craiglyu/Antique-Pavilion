# AP Design Loop v3 — Strategy Blueprint（吉寶軒設計 Loop 升級藍圖）

> 產生日期：2026-07-08 · 作者：Claude Code（Opus 4.8）· 授權：Craig「全部」指示
> 來源：18-agent 多視角審查 workflow（run `wf_652dde5b-e07`），8 視角深讀 `Publish/index.html`
> → 事實查核 → 綜合 → 對抗性 critique（已把 critique 的修正整合進本文）
>
> **這份文件是 v3 loop 的 single source of truth。** `/design-review` skill v3.0 依此運作；
> 各 epic 的 paste-ready prompt 見 `DESIGN_BRIEF_*.md`。

---

## 0. TL;DR

- 27+ 輪 loop 已把內部 **5 維美學 audit 推到 20/20 飽和**。原因有二：視覺工藝真的到位了；
  更關鍵的是**那把尺量的是「工藝輸入」而非「產出結果」**，一旦合規度到頂就沒有梯度，
  只剩 `border-radius 4→2px`、`padding 50→48px` 這種合規區間內的抖動。
- 查核揭露最大單一問題，正好是這把尺量不到的：**全站每一條轉換路徑都終止在一顆 `disabled` 的
  LINE 按鈕**——無地址、無 Google Maps、無營業時間、無 `tel:`、無預約。CLAUDE.md §1 北極星是
  「導流到實體藝廊」，**轉換率不是低，是結構性等於 0**。
- 解法：把 loop 的目標函數從「靜態合規」升級為 **rubric v3**（5 美學地板 + 7 產出天花板），
  以真實量測（Lighthouse / axe / Rich Results / 合成事件）定義高度，並用**雙軌機制**把
  「loop 可自動」與「需 Craig / Tier 1 / DD-gated」清楚分流。

---

## 1. 診斷：為何 loop 卡在 20/20（Local Maximum）

現行 5 維尺（可及性、視覺層次、品牌一致性、動畫品質、程式碼品質）本質上**全是「內部工藝」維度，
且靠靜態樣式比對評分**（有沒有 `@media reduced-motion`、有沒有 `will-change`、`font-weight` 是不是 400），
而非量測真實產出。六個系統性盲點：

1. **從不檢查 CTA 是否可用、是否抵達真實目的地**——一顆 `disabled` 按鈕在這把尺上是「乾淨的
   a11y 實作」而非「壞掉的漏斗」。
2. **reduced-motion 只 grep CSS `@media`**——看不到整頁最大的動態元素：WebGL 縹霧的 JS
   `requestAnimationFrame` 迴圈根本沒被 gate。
3. **動畫品質量的是「只 animate transform/opacity」的合規，不是真實 LCP/INP/frame-time 數字**
   （Hero 揭示動畫把 LCP 拖到 ~2s+、每卡 `backdrop-filter` 拖累滾動，尺都看不到）。
4. **視覺層次量單卡靜態外觀**，不量整頁合成層數與滾動掉幀。
5. **完全沒有「可被發現性」概念**——無 deep-link、無結構化資料、無分享入口都不扣分。
6. **完全沒有「信任/敘事/provenance」概念**——匿名掌櫃、無 About、參考價懸空都不扣分。

> **根本問題**：這把尺可以被「設計系統 100% 合規」完全滿足。合規度到頂後，剩下能動的只有合規
> 區間內的 2px 抖動。**尺收斂了，產品沒有。近幾輪只能做像素微調，不是 loop 變笨，而是它被要求
> 最佳化的目標函數已經沒有梯度了。**

### 1.1 critique 修正的過度宣稱（已納入）

- ❌「loop 從不跑瀏覽器」→ ✅ §9 Sprint 4 已交付 **visual regression baseline（10 張截圖）**+
  Emil UI audit，本機也用 `preview_eval` 做 DOM 量測。v3 是**在既有 harness 上加真實量測維度**，
  不是從零打造。
- ❌「WebGL 縹霧在每台裝置永遠在動」→ ✅ `initWebGLFog()` 開頭已有裝置閘
  （`cores<=4 || memGB<4` 時 `return` 並隱藏 canvas，見 index.html L2660-2667），多數手機/弱機根本不啟動 fog。
  reduced-motion 缺口與捲離不暫停仍屬實，但**適用面僅 ≥4 核・≥4GB 機（如 MacBook Air）**。
- ⚠️「60 屏長頁」為檔內既有註解（L1006）的估值，非精確可量測事實，不宜當硬數據引用。

---

## 2. Rubric v3 — 新的目標函數

**兩層分開計分**：美學維度確保不退步（**地板**），產出維度提供新梯度（**天花板**）。

### 2.1 地板：既有 5 美學維度（維持 20/20 為「不得回歸」門檻）

可及性 · 視覺層次 · 品牌一致性 · 動畫品質 · 程式碼品質。任何 epic round 若讓這 20/20 回歸即作廢。

### 2.2 天花板：7 個「產出型」維度（用真實量測定義高度）

| 新維度 | 量什麼（客觀、可自動驗證） |
|---|---|
| **導流有效性 Funnel Efficacy** | 全站「可用（非 disabled）且抵達真實動作」的路徑數、死路 CTA 計數、modal 到下一步的互動次數（目標 ≤1） |
| **真實 CWV Measured CWV** | headless 實跑 Lighthouse 的 LCP/INP/TBT 中位數、滾動 frame-time、同屏 active `backdrop-filter` 合成層數、捲離 hero 後 GPU/Scripting 軌道是否歸零 |
| **可被發現性 Discoverability** | 每件藏品有無穩定 deep-link、Rich Results Test 偵測到的 schema 型別（VisualArtwork/ItemList/LocalBusiness）、有無原生分享入口、axe landmark/heading 分數 |
| **輔助科技實地體驗 A11y Lived** | 狀態變更有無 `aria-live` 播報、JS 動畫（非只 CSS）有無尊重 reduced-motion、焦點落點、標題數 == 卡片數、放大是否鍵盤可達 |
| **跨裝置韌性 Cross-Device** | 320/360/375/768/1024 寬 + 橫向無重疊/溢出/magic-number 破版、`safe-area` 是否處理、觸控手勢（swipe/pan-zoom）可用 |
| **信任/敘事深度 Trust & Narrative** | 有無 About/策展聲音/provenance/鑑賞準則；modal 是否故事先於價格；5 秒測試能否複述「這是誰、為何可信」 |
| **邊緣狀態品質 Edge-State** | empty/sparse/error/離線各態是否品牌化（印章插圖 + 品牌字型 + 下一步）、error 有無洩漏 GAS URL 或 JS 例外字串 |

---

## 3. 五個 Epic（多輪主題式長程任務）

每個 epic 一條 branch、追自己的 metric，不再共用一個 20/20 gate。
Tier 分類已按 critique 修正（**新增首頁頂層區塊/新功能/公開內容/認證措辭一律不是「完全自動」**）。

| Epic | 目標 | 首選順位 | 自動 vs 交接 |
|---|---|---|---|
| **D — 輔助科技與真機韌性** | 報讀器/純鍵盤/真機使用者拿到與視覺等值的體驗 | ⭐ **先跑** | D1–D6 **全自動**（無需真實資料、無 Tier 1） |
| **B — 效能硬指標 CWV** | LCP<1.5s、INP p75<200ms、無風扇機滾動穩 60fps | 🟢 第二 | B1–B5 自動；**B6 Hero LCP 需 Craig**（Tier 1 品牌體感） |
| **C — 可被發現性與病毒導流** | 每件可搜到/可私訊分享/地理搜尋找得到 | 🟡 第三 | C1–C4 自動但**屬新功能，建議加輕簽核**；C6 LocalBusiness 需真實 NAP（Craig） |
| **A — 轉換漏斗骨架化** | 每條路徑都有可兌現出口 | 🔴 需 Craig | A1/A3/A4 自動；**A2 Visit 區塊 + A5 真實資料 = Tier 1** |
| **E — 信任與敘事策展** | 從「Sheet 匯出」升級為「被選過、可信任」的收藏 | 🔴 需 Craig | E1/E2/E3 自動；**About/策展引言 = Tier 1；provenance = DD-gated 凍結欄位** |

### Epic D — 輔助科技與真機韌性（A11y & Real-Device Resilience）⭐
**Metric**：axe/Lighthouse a11y 分數、報讀器標題數 == 卡片數、reduced-motion 下 fog `rAF` 未啟動、斷點重疊/溢出測試通過數。

| Round | 任務 | 驗收 |
|---|---|---|
| D1 | 新增 `sr-only role=status aria-live=polite`，於 fetch 完成/每次篩選/空狀態更新 textContent（如「青銅專場・共 8 件典藏」） | 逐一切分類皆播報且文字與可見卡片數一致 |
| D2 | `.modal-content` 加 `tabindex=-1`，轉場結束後只 focus 容器一次、**移除所有 `setTimeout` 補焦 hack**；`navigateModal` 後把新品名寫入 aria-live | 開啟後 `activeElement === .modal-content` 且僅一次；Tab/Shift+Tab 不逸出；切上/下件報讀新品名 |
| D3 | `#glCanvas`/`.bg-layer`/`.ink-vignette` 補 `aria-hidden`；放大圖改 `role=button`+`tabindex`，Enter/Space 切換 zoom、`aria-pressed` 反映狀態 | a11y tree 不再出現三裝飾節點；純鍵盤可切換放大 |
| D4 | 卡片改 `<article>` + 內部一顆真 `<button>`/`<a>` 掛在品名 h2，保留大點擊區與鍵盤開啟 | 報讀器 H 鍵標題清單列出每件品名、數量 == 可見卡片數；無回歸 |
| D5 | JS 於載入/resize 量測 header 實際高度動態設 rail `margin-top`（**取代 `300px` magic number**）；`brand-title` 加 `clamp()` 降級字級/字距 | 320–1024+橫向下 rail 頂緣恆在 hero 底緣下、間距誤差 <8px；`brand-title` 不溢出、左右 ≥24px 呼吸 |
| D6 | modal 綁 `touchstart/touchend` 水平 >40px 且垂直 <30px 切換藏品；放大態加拖曳平移可達四角；`meta` 加 `viewport-fit=cover`、固定 UI bottom 改 `calc(基準 + env(safe-area-inset))` | 合成 TouchEvent 左右滑正確變 index 不越界；放大拖曳達四角；瀏海模擬下背景延伸到邊緣、`backToTop` 底緣距窗底 ≥34px+基準 |

### Epic B — 效能硬指標（Performance Hard-Metrics / CWV）
**Metric**：Lighthouse LCP/INP/TBT 中位數趨勢、同屏 active `backdrop-filter` 層數、捲離 hero 後 GPU 軌道 idle 秒數、封鎖字型後 FCP。

| Round | 任務 | 驗收 |
|---|---|---|
| B1 | 卡片/modal `img` 加 `onerror` → 品牌 SVG 佔位圖，並加 `referrerpolicy=no-referrer`、`decoding=async` | 指向無效 Drive id 顯示佔位圖而非破圖 icon；封鎖 `drive.google.com` 後全頁無破圖 |
| B2 | `initWebGLFog` 開頭加 reduced-motion gate；IntersectionObserver 監看 hero sentinel，捲離即 `cancelAnimationFrame` | 開 OS 減少動態後未排程 `rafId`、兩幀 `readPixels` 一致；捲離 hero 後 GPU/Scripting 軌道歸零 |
| B3 | 縹霧改 0.5–0.6× 內部解析度渲染（buffer 縮小 CSS 放大）、octaves 6→4 或砍 Layer B 一次 domain warp | DevTools GPU/frame time 下降約 2–4×；並排截圖柔霧外觀無可辨差異 |
| B4 | 字型 CSS 改 `media=print onload` 或 `preload+onload`，讓 proxy 擋 Google 時即時以本地標楷體 fallback 出字 | 封鎖 `fonts.googleapis.com` 後 FCP 不被 stylesheet timeout 拖住；Lighthouse「text remains visible during webfont load」通過 |
| B5 | 快取 `scrollHeight`（僅 resize/render/filter 後重算）、`backToTop` 僅在可見狀態改變才寫屬性；`vignette` `backdrop-filter` 比照 in-center/hover 才啟用 | scroll handler 不再觸發 Forced reflow 警告；同屏 active `backdrop-filter` 層數大幅下降；INP p75 下降 |
| B6 🔴 | **（Craig 拍板）** 縮短 `brand-title` 1s 揭示延遲或讓標題更早以最終位置 paint | LCP 中位數（快連線+桌機）從 2–3s 降到 <1.5s；Craig 確認「沉澱一拍再浮現」體感可接受 |

> ⚠️ **B4 風險**：index.html L104-112、L233-234 明載 `brand-title` 的 1s delay 是刻意工程，讓
> 吉/寶/軒 各自的 woff2 subset 載入完成、避免逐字換字 FOUT。改 async 若未同步處理 CJK subset 時序，
> 會重新引入被刻意消除的 FOUT。B4 這輪要謹慎、需驗證逐字 swap 不回歸。

### Epic C — 可被發現性與病毒導流（Discoverability & Viral Loop）
**Metric**：deep-link 覆蓋率、Rich Results 通過的 schema 型別數、分享入口存在與否、axe landmark/heading 分數。

| Round | 任務 | 驗收 |
|---|---|---|
| C1 | 以 `itemName` 產生穩定 slug（**勿用會隨庫存變動的 index**）做 hash/History 路由：開 modal/切分類更新 URL、上一頁關 modal、帶 hash 重整還原 | 造訪 `#item/<slug>` 直開正確 modal；上一頁關閉 modal 或還原篩選；重整還原狀態 |
| C2 | modal 加 Web Share API 鈕（手機叫原生面板帶 title+深層 URL），桌機 fallback 複製連結 + toast | 手機 https 下點分享開原生面板且帶正確深層 URL；桌機複製到剪貼簿並顯示 toast |
| C3 | fetch 後動態注入 VisualArtwork + ItemList JSON-LD，並於 `<head>` 放靜態 CollectionPage/Organization stub | Rich Results Test 偵測到 VisualArtwork 無錯；head 有靜態 stub |
| C4 | 加 `<main>`、逐件 `<article>`、gallery 章節 h2「館藏一覽」、修 h1→h2→h4 跳階、補 `<link rel=canonical>` | axe/Lighthouse landmark 與 heading-order 通過；恰一個 canonical |
| C5 | 補 `og:image:width/height/alt`、`og:image:type/secure_url`、`twitter:image:alt`；預留改用主打藏品 hero 圖接點 | Facebook/Twitter Card Validator 顯示卡片含正確寬高/alt、即時渲染不空白 |
| C6 🔴 | **（Craig + Tier 1）** 注入 ArtGallery/LocalBusiness schema（address+geo+openingHours+telephone）+ 頁面可見 NAP | Rich Results 偵測到含 address+geo+openingHours+telephone；可見 NAP 與 schema 一致 |

> ⚠️ **critique 提醒**：C1 hash/History 路由 + C2 原生分享改變 URL 行為與瀏覽器歷史，屬 §5「新功能上線」，
> 建議加一道**輕簽核**（Craig 看 digest 後放行），不宜全程無簽核自動 merge。

### Epic A — 轉換漏斗骨架化（Conversion Funnel Scaffold）🔴
**Metric**：有效（非 disabled）對外動作數：目前 **0 → 目標 ≥3**（LINE/tel:/Maps）；死路 CTA 計數 → 0；modal 到可用下一步 ≤1 次互動。

| Round | 任務 | Tier |
|---|---|---|
| A1 | 持續性浮動「洽詢」CTA（捲過首屏後浮現，沿用 `backToTop` 進出場模式，平滑捲至 #contact） | 自動（但見下方擁擠護欄） |
| A2 | **蒞臨鑑賞（Visit）區塊骨架**：Maps iframe/靜態圖佔位、地址槽、營業時間 skeleton、預約 CTA 佔位 | 🔴 **Tier 1**（新增首頁頂層區塊 = IA + 公開版面，即使佔位骨架合併到 Pages 即對外可見） |
| A3 | modal「洽詢典藏」改為產生帶 `item.itemName`/LOT 的 `line.me` deep-link 或 mailto 預填樣板（端點常數集中，未就緒 fallback 到誠實 pending） | 自動（骨架）；啟用需端點 |
| A4 | pending 狀態誠實化：收斂 `contact-desc`「24 小時內回覆」承諾為「貴賓洽詢管道整備中」，補可被報讀的 pending 說明 | Tier 2（PR + digest，不自動 commit） |
| A5 | **真實資料填入 + 啟用 CTA**：換入真實 LINE URL（移除 disabled）、填地址/營業時間/`tel:`/Maps、啟用預約 | 🔴 **Craig only + Tier 1** |

### Epic E — 信任與敘事策展（Trust & Curatorial Narrative）🔴
**Metric**：5 秒測試複述「這是誰、為何可信」通過率、modal 故事先於價格、三態截圖通過、provenance 欄位串接完成度。

| Round | 任務 | Tier |
|---|---|---|
| E1 | modal-right DOM/flex order 改為 **故事→金句→鑑定參考→洽詢**（目前先價後事） | 自動 |
| E2 | empty/no-data/error 各給印章插圖+品牌字型文案+下一步；**error 態移除 `e.message` 與 GAS URL** | 自動 |
| E3 | gallery 每 N 張後插 ornamental 分隔/章節序號/專場小標（**純視覺節奏，不重排卡片實際順序以免觸 Tier 1 IA**） | 自動 |
| E4 | hero 與 gallery 間或之後新增 `#about` 骨架（掌櫃介紹+收藏理念版位，內容佔位） | 🔴 **Tier 1**（首頁公開內容 + IA） |
| E5 | gallery 頂端策展引言槽（2–4 句掌櫃選件/本季主題），loop 做版位、Craig 填真實文字 | 🔴 **Craig 內容 + Tier 1** |
| E6 | 經 compliance 通過的「鑑賞準則/來源說明」敘事區，串接解鎖後的 provenance 欄位（GAS 三處同步） | 🔴 **Craig + DD-gated**（provenance = §3 col 14 凍結欄位，DD-XXX 未核准前不得動 GAS） |

---

## 4. loop 機制升級（已納入 critique 護欄）

1. **rubric v3** = 5 美學維度（地板，20/20 不得回歸）+ 7 產出維度（新天花板），**分開計分**。
2. **量測 harness**：接續既有 visual regression baseline，加 headless Lighthouse（LCP/INP/TBT）、
   axe（a11y/landmark/heading）、Rich Results/Schema Validator、合成 TouchEvent 與 `readPixels`。
   每個新維度的「驗收」直接採用機會清單裡已寫好的 verification 欄位當測試斷言，避免主觀評分被再次 game。
   → **受 CLAUDE.md §6 硬上限約束**：Opus 設計裁決 USD 15、Gemini USD 30，**不得跳過 `budget_gate`**（§10）。
3. **一 epic 一 branch**：`design/epic-a11y`、`design/epic-perf`、`design/epic-discover`、
   `design/epic-funnel`、`design/epic-narrative`，各追自己的 metric 目標，而非共用 20/20 gate。
4. **雙軌 loop**：
   - **自主軌** = 所有 loopSuitable 且 Tier 2/3 的 round，metric 綠燈即可推進。
     ⚠️ **修正**：Tier 2 auto-merge 要等 §9 **Sprint 5 branch protection**（目前 ⬜ pending）上線，
     在那之前**自主軌只能停在 PR，不得自動併 main**。
   - **Craig 軌** = `blockedBy` 真實資料或 Tier 1 的 round，停在「PR 骨架 + digest」，明列需要 Craig
     提供什麼資料、簽什麼核。**loop 不自行填內容、不自撰任何「真品/鑑定/認證」或 provenance 文字。**
5. **停手條件（definition of done 換血）**：round 的完成從「無違規/20/20」改為**「該 epic 的 metric
   打到目標 + 美學 20/20 無回歸」**；一旦某 round 命中 Tier 1（公開內容/品牌方向/新 IA/認證宣稱）
   或需要真實藝廊資料，**loop 必須停手、交回 Craig**，而不是在合規區間繼續抖 2px。
6. **操作護欄**：
   - 所有結構改動落在 **`Publish/index.html`**（§7；root `index.html` 為本機開發檔，視需要同步）。
   - **固定定位 UI 擁擠**：A1 浮動 CTA / D6 safe-area 會疊進右下已擁擠的固定層
     （`backToTop` right:16/bottom:24、`scroll-progress-wrap` right:16/top:20、`scroll-seal`）——
     手機窄屏務必處理 bottom-right 碰撞與 `safe-area` 疊加。

> **本質**：把 loop 從「最佳化一把已經滿分的尺」改成「追逐五條真實世界的曲線」，每條曲線都有客觀
> 量測與明確的 Craig 交接點。天花板因此被抬高且可持續下降。

---

## 5. 執行順序建議

1. **暖身輪（跨 epic Quick-Win Sprint）** — 見 `DESIGN_BRIEF_QuickWins.md`。挑 5 個最高 CP 的
   自主項（圖片韌性、WebGL 減動、a11y 三件套、modal 敘事重排、邊緣三態），一輪拿下、順手驗證新 harness。
2. **Epic D（a11y & 真機韌性）** — 見 `DESIGN_BRIEF_EpicD_A11y.md`。最純粹的自主主戰場。
   *若已跑暖身輪，D1–D3 的 a11y 三件套已完成，Epic D 從 **D4** 起跑。*
3. **Epic B（效能）** → **Epic C（可被發現性，加輕簽核）**。
4. **Craig 交接**：Epic A / E 的 Tier 1 與真實資料項（見 §6）。

---

## 6. 需要 Craig 的交接清單（loop 無法自動完成）

| 項目 | 類型 | 卡在哪 |
|---|---|---|
| 真實 LINE URL / ID | Tier 1（啟用對外主要 CTA） | A3 啟用、A5 |
| 藝廊地址 / 營業時間 / `tel:` / Google Maps URL | Tier 1（公開 NAP + 新 IA） | A2、A5、C6 |
| 「蒞臨鑑賞」Visit 區塊上線 | Tier 1（IA + 公開版面） | A2 |
| `#about` / 掌櫃介紹 / 收藏理念 | Tier 1（首頁公開內容） | E4 |
| 策展引言 / 本季主題文字 | Tier 1（公開品牌內容） | E5 |
| provenance 欄位解鎖 + 內容 | **DD-gated**（§3 col 14 凍結，需 DD-XXX + GAS 三處同步） | E6 |
| Hero LCP 揭示體感取捨 | Tier 1（品牌方向） | B6 |
| 參考價呈現策略（維持/「價格請洽詢」/級距） | Tier 1（定位方向） | 定位判斷 |
| deep-link / Web Share 上線 | §5 新功能（建議輕簽核） | C1、C2 |

---

## 附錄：來源

- Workflow run：`wf_652dde5b-e07`（18 agents、48 條經事實查核存活的優化機會、對抗性 critique）。
- 完整逐條機會與查核紀錄：session `subagents/workflows/wf_652dde5b-e07/journal.jsonl`。
- 審查基準：`Publish/index.html`（commit `5e4de87` 附近）、`CLAUDE.md`、`DESIGN_BRIEF_NEXT.md`。
