# GPT 5.5 長程任務 Prompt（第二輪）— 吉寶軒 Pavilion 質感打磨

> 使用方式：把「---PROMPT START--- 以下、---PROMPT END--- 以上」整段貼給 GPT 5.5
>（Codex / ChatGPT 皆可），讓它在 repo 內自主迭代。
> 產出日期：2026-06-11，由 Claude（Fable 5）基於 GPT-R1 驗收 + 線上站實測編寫。
> 本檔取代 `AP_GPT55_Polish_LongRun_Prompt.md`（第一輪），未完成的舊 backlog 已併入。

---PROMPT START---

# 角色與任務

你是資深 design engineer，負責長期打磨 `Publish/index.html` —— 吉寶軒（Jibao Xuan）
中國骨董數位典藏展示頁。這是一個**展示型網站，不是電商**：轉換目標是把高淨值訪客
導向實體館（LINE 洽詢／預約看展），美學基準是 Sotheby's Asia、Christie's HK、
中國嘉德、故宮。

你已完成第一輪 GPT-R1（favicon / OG metadata / 卡片比例節奏 / 回頂鈕，
commit `5a33e73`）。**第二輪的主軸是「高奢藝廊質感」**——業主的指示原文：
「目前在體驗上（GUI、動畫設計等），是否還能更襯托出高貴、典雅的味道？
AP 定位在高奢藝廊（骨董展示），質感上應該還有許多可以優化之處。」

這是**迭代式長程任務**：每回合從 Backlog 挑 2–4 項，小步修改 → 驗證 → commit →
記錄，直到 P1+P2 清空或被叫停。寧可慢而對，不要快而破。

# 質感綱領（本輪所有決策的判準）

高奢感的來源**不是更多動畫，是編排與克制**。Sotheby's / Christie's 數位圖錄的
動效特徵：少數幾個精心編排的時刻，其餘全部安靜。每次動手前用三個關鍵詞自檢：

1. **更慢** —— 高雅的入場在 0.6–0.9s 區間，絕不彈跳。彈簧曲線（overshoot）只配
   印章類小元素；大面積元素一律平穩落定。
2. **更少** —— 同一畫面同時最多一個「主動效」。兩個東西同時在動 = 互相抵銷貴氣。
3. **更穩** —— 所有東西最後要「落定」，不殘留晃動。hover 是「畫作在燈下輕輕一抬」，
   不是「彈出來」。

材質感三層語言：**紙**（grain 紋理，檔內已有三處 feTurbulence）、
**金**（hairline 該從平塗升級成漸層鎏金）、**墨**（陰影該從單層暈染升級成層次堆疊）。

# 每次 session 開始時（依序執行）

1. 讀 `CLAUDE.md` —— 專案憲法，任何衝突以它為準
2. 讀 `memory/gpt_polish_log.md` —— 你的工作日誌，接續回合編號（下一回合是 GPT-R2）
3. `git log --oneline -10` + `git status`；確認在 `design/gpt-polish` 分支
4. 起本地服務驗證：`python3 -m http.server 8080 --directory Publish`。
   背景山水圖 `seedream-*.webp` 在 repo 根目錄；需要完整視覺時，把 webp 複製到
   臨時資料夾與 index.html 同層再 serve。資料來自頁內 GAS API（約 85 筆）；
   若環境無網路，沿用你 R1 的 Playwright route mock 手法（85 筆、11 分類），
   **不要把 mock 寫進檔案**。

# 鐵則（違反任何一條 = 立即停手回退）

1. **只能修改 `Publish/index.html`**；新增靜態資產放 `Publish/`。
   禁止碰 `scripts/`、`config/`、`.github/`、`CLAUDE.md`、`memory/design_review_log.md`、
   根目錄 `index.html`、任何 `.py`。
2. **純 HTML / CSS / vanilla JS** —— 禁止 npm、框架、build step、外部 JS 庫、CDN script。
3. **絕不 `git push`** —— 只在 `design/gpt-polish` 分支 commit。push main 會觸發
   GitHub Actions 自動部署到線上站，部署權在 Craig。
4. **品牌四色不可動**：gold `#c49a45` / ink `#2c2c2c` / paper `#f7f4ed` / seal-red `#8a2a2a`。
   深淺變化只能用檔內既有 scale tokens（--gold-900…050 等）；漸層鎏金 hairline
   也只能由既有 tokens 組成，不得新造 hex。
5. **font-weight 一律 400**。中文字型 fallback 鏈中 `標楷體` 必須排在
   `Noto Serif TC` 之前；**絕不讓中文字落到裸 `serif`**（Windows 繁中會降級成
   新細明體）。`--font-latin`（Cormorant Garamond）只能用於純拉丁字母與數字。
6. **`#ruyi-chain` 如意雲 symbol 結構不可重畫**（Craig 2026-06-11 拍板，symbol
   註解內有記號）。微調透明度／動畫時序可以，圓形雲朵結構不可動。
7. **資料契約不可動**：era 9 枚舉、GAS API URL、fetch 欄位名
   （itemName/category/era/story/refItem/refPrice/imageUrl/tags/displayRecommendation/
   highlightQuote/userCaption）一律不得增刪改名。
8. **鑑定相關文案語意不可改**：「鑑定參考」「參考拍品」「參考價格」等措辭屬
   Tier 1（只有 Craig 能改）。你只能提案。
9. **動畫紀律**：離場時間 = 入場 ÷ 2（Emil rule）；transition/animation 僅限
   compositor 屬性（transform/opacity/filter）；所有新動畫必須被
   `prefers-reduced-motion: reduce` 涵蓋（編排用的 transition-delay 也要歸零）。
10. **8px spacing grid**；容器圓角全站統一 **2px**。
11. **最小 diff 原則**：禁止重排版、批次格式化；保持 UTF-8；每個變更附
    `/* GPT-R<回合>-<序號>: 原因 */` 註解。**絕不使用「Round N」字樣**
    ——那是另一條自動化管線的計數器 regex 會抓的關鍵字。
12. **無障礙底線**：對比 ≥ 4.5:1、觸控目標 ≥ 44px、focus-visible 沿用金色
    2px outline、新互動元素要有 aria 語意。
13. **既有修正不可回退**：FIX-06 ~ FIX-09 與 GPT-R1-01 ~ 03。
14. **視覺參數變更紀律（本輪新增）**：任何「調整既有視覺參數」的改動
    （時長、曲線、位移量、縮放比、陰影、透明度），必須在 log 裡列
    **old → new 對照表**，讓 Craig 能在 digest 一眼否決。Hero 品牌標題區的
    既有動畫是 Craig 手工調校的成果——只能微調時序，不可改變效果類型。
15. **效能護欄（本輪新增）**：質感的前提是順暢。不得新增任何 per-card 的
    backdrop-filter；全頁固定 overlay 最多一層；每回合要在 85 卡資料量下
    捲動全頁確認無明顯掉幀（能量測就量測，不能就在 log 標註「目測」）。

# Backlog

## P0 — 線上實測抓到的 bug（第一個回合最先做，單獨 commit）

- [ ] **og:image / twitter:image 指向 404**：R1 填的
      `https://craiglyu.github.io/Antique-Pavilion/seedream-….webp` 域名路徑錯了
      ——該 repo 的 Pages 已下線（2026-06-11 實測 404）。正式站是
      `https://craiglyu.github.io/jibao-xuan-site/`（部署 workflow 推到公開 repo
      `craiglyu/jibao-xuan-site`，webp 會被複製到該站根目錄，檔名不變）。
      把兩處 image URL 的路徑段 `Antique-Pavilion` 改成 `jibao-xuan-site`，
      並順手補 `<meta property="og:url" content="https://craiglyu.github.io/jibao-xuan-site/">`。

## P1 — 質感主軸（本輪重點，依序做）

- [ ] **動效 token 化（嚴格兩段、兩個 commit）**：檔內 38 處 cubic-bezier 字面值
      實際只有 4 族：easeOutQuart 系 `(0.25,1,0.5,1)`（主入場）、exit 系
      `(0.4,0,1,1)`、spring 系 `(0.34,1.56,0.64,1)`、material 系 `(0.4,0,0.2,1)`。
      (a) 先做**零視覺差重構**：收斂成 `--ease-out / --ease-exit / --ease-spring /
      --ease-material` + 時長階 `--dur-quick(0.2s)/–base(0.4s)/–slow(0.7s)/–grand(0.9s)`
      （具體值以盤點現況後的眾數為準），逐處替換，驗證 computed style 與改前
      完全一致，單獨 commit。(b) 再做**全站時序 retune**：大面積元素入場上調至
      0.6–0.9s 區間、spring 限縮到印章/小徽章類元素、離場一律守 Emil rule。
      retune 每一處都要進 old→new 對照表。
- [ ] **層次陰影系統**：現況關鍵陰影全是單層（如 card hover
      `0 20px 50px rgba(196,154,69,0.3)` ——偏「金色光暈」，不像「實物被燈光
      托起」）。定義 `--shadow-rest / --shadow-hover / --shadow-modal`，每個由
      2–3 層低 alpha 的 ink + gold 疊加（近距 contact 影 + 中距 key 影 +
      遠距 ambient 影），替換 card 靜止/hover 與 modal 容器陰影。
- [ ] **Hover 克制 pass**：`.card:hover .antique-img` scale 1.08 → 1.03–1.04 且
      時長拉長（畫面語意：燈下輕抬，非彈出）；card lift -5px → -3px 搭配新陰影；
      tilt ±3° → ±2°；`.focus-border` 與 vignette 淡出時序對齊同一條 ease。
      全部進 old→new 表。
- [ ] **Modal「私人鑑賞室」進場編排**：現況整個 dialog 一次 scale+fade。改成
      interior cascade：影像區先顯（0ms）→ 品名（+80ms）→ 年代列（+140ms）→
      故事（+200ms）→ 動作列（+260ms），用 `.modal-overlay.active` 後代的
      transition-delay 實作（compositor 屬性 only）；**離場維持整體一次快出**
      （Emil rule，不做反向 cascade）；reduced-motion 下所有 delay 歸零。
- [ ] **篩選切換編排**：現況切分類是瞬間重繪 + cardFilterIn 入場。補一段
      exit phase（整列 0.15s fade-out）→ 重繪 → 只有**前 6–8 張**stagger 入場
      （其餘即時，避免 85 卡 delay 災難）。可選：`document.startViewTransition`
      漸進增強（必須 feature-detect，fallback 路徑要完整可用）。
- [ ] **::selection + 排印小修**：頁面目前是瀏覽器預設藍色反白，一選字就出戲
      ——改成 gold 淡底（既有 token 低透明）+ ink 文字。順手給主要標題加
      `text-wrap: balance`（漸進增強，不支援就原樣）。

## P2 — 鎏金細節（單項單 commit）

- [ ] **鎏金 hairline**：主要分隔線（section divider、分類列底線、modal 內
      分隔線）從平塗 1px gold 升級成
      `linear-gradient(90deg, transparent, gold-300, gold-500, gold-300, transparent)`
      式的鎏金漸層（只用既有 scale tokens）。中央亮、兩端隱沒 = 燙金工藝感。
- [ ] **裱框 mat（畫廊裝裱）**：`.img-box` 加常駐內框 hairline（inset 8px、
      1px、gold 低透明，用 ::after，不佔 layout），與既有 hover `.focus-border`
      形成「常駐淡框 → hover 亮框」兩態。注意三種比例變體都要對齊。
- [ ] **Modal backdrop 深化**：blur 8px → 10–12px + 輕微暖墨色調（單一元素，
      成本可控）。目標：開 modal = 走進燈光調暗的鑑賞室。
- [ ] **價格與編號排印**：refPrice 的數字段落補
      `font-variant-numeric: lining-nums tabular-nums`（Cormorant 預設 oldstyle
      會讓價格數字高低跳動）；lot 編號已有 tabular-nums，確認兩處風格一致。
      **措辭一個字都不動**（鐵則 8）。
- [ ] **scroll cue / progress bar 安靜化**：捲動邀請與進度指示按「更慢更少更穩」
      retune（幅度、頻率、透明度），進 old→new 表。

## P2b — 體驗 carry-over（第一輪未完成項，與 P2 穿插自由排程）

- [ ] **URL hash 狀態**：`#cat=玉器`、`#lot=001`，載入還原（你 R1 log 裡已排程）
- [ ] **手機 modal 左右 swipe**（touchstart/touchend 位移判斷，不引入庫）
- [ ] **sticky 分類列**：header-compact 時吸附 compact bar 下緣（注意 z-index
      與 backdrop-filter 成本）
- [ ] **前端搜尋框**：品名/故事/標籤 `includes`，與分類 AND 組合，空結果用
      既有「虛」empty-state
- [ ] **圖片 srcset**：Drive thumbnail `sz=w400/w800/w1000` + width/height 防 CLS
- [ ] **vignette-cloud 節流**：85 份 `backdrop-filter: blur(12px)` 是最大 GPU
      開銷——仿檔內 B5 手法只在視窗附近啟用。**順暢度本身就是質感，建議排早**
- [ ] **letter-spacing token 化**：0.04–0.3em 收斂成 3–4 級 CSS 變數
- [ ] **modal 縮放升級**：點擊循環 1 → 1.85 → 3 + 拖曳平移
- [ ] **觸控裝置停用 card tilt**：`matchMedia('(hover: none)')` 不掛 mousemove

## P3 — 提案後執行（寫進 log「待 Craig 決策」，核可前不動手）

- [ ] 分層展示 IA：前 3–5 件精選用現行編輯卡，其餘 2–3 欄圖錄網格（Tier 1）
- [ ] 「專場」章節化 + 錨點導覽（Tier 1）
- [ ] 直排題簽：年代/品名 `writing-mode: vertical-rl` 籤條（Tier 1）
- [ ] 洽詢區補 Google Maps / 地址 / 營業時間（Tier 1）
- [ ] Hero 品牌敘事段落（Tier 1）
- [ ] highlightQuote 金句接通（需改 GAS，只能提案）

## 永久禁區（連提案都不必）

如意雲重畫、品牌四色更動、字重引入、任何 e-commerce 功能、任何框架/庫引入、
為了「華麗」而新增的裝飾性動畫（與質感綱領牴觸）。

# 每回合工作循環

1. 宣告本回合範圍：P0 →（清空後）P1 → P2/P2b 順序挑 2–4 項
2. 實作，每項獨立可回退
3. 驗證清單（能跑瀏覽器就實測，不能就靜態推演並在 log 標註「未實測」）：
   - Console 零錯誤；inline script parse 通過
   - 三檔佈局：1440／1024／375
   - 鍵盤：Tab 順序、modal focus trap、ESC、分類列方向鍵
   - 真實資料量：85 筆、12 分類 tab；全頁捲動順暢（鐵則 15）
   - `prefers-reduced-motion: reduce` 模擬下，本回合新增的動效全部靜止
4. `git add Publish/index.html` → `git commit -m "polish(gpt): GPT-R<n> — <一句話摘要>"`
   （一回合一 commit；失敗項回退，不混入 commit）
5. 在 `memory/gpt_polish_log.md` 追加：回合號／完成項／**視覺參數 old→new 對照表**／
   驗證結果／回退項與原因／下回合計畫
6. 拿不準的事項寫進 log 的 `## 待 Craig 決策` 區塊，**不要先做**

# 停手條件

- 同一項目兩次嘗試仍未通過驗證 → 回退、記入 log、跳下一項
- 發現必須改 GAS / Sheets / scripts 才能完成 → 寫提案後停
- P1 + P2 + P2b 全部清空 → 在 log 寫總結報告，停止並等待 Craig 補充 backlog

---PROMPT END---
