# 吉寶軒 Design Brief — 完整美學／UI-UX 優化（Consolidated Backlog）

> 由 Claude Sonnet 5 依一次完整 UX/UI 稽核 session 產生 · 稽核日期 2026-07-23
> 性質：**整合型 backlog**，不是單一 epic 的 5 項任務 prompt。
> 整合 QW1–5／D1–D6（已併入 main @0776c94）之後、以及本 session 內完成但**尚未提交**的
> 4 輪 P2-* 修正，並向前規劃下一階段的美學＋UX 優化。
> 延伸（不是取代）`AP_Design_Loop_v3_Strategy.md` 的 7 維產出天花板——本文件把「美學精修」
> 也放進同一套產出框架，而不是重啟已飽和的 5 維地板。
>
> **狀態關係**：`DESIGN_BRIEF_NEXT.md` 已過時（其 Phase A 狀態早於本文件）。
> `DESIGN_BRIEF_QuickWins.md`／`DESIGN_BRIEF_EpicD_A11y.md` 兩者內容皆已完成並併入 main，
> 只剩歷史參考價值。**本文件是目前 live 的 backlog。**

---

## 0. 使用說明（給即將執行本 backlog 的任何 Claude session）

- 這份文件是「內容」，不是「啟動指令」。啟動請用 §13 附的貼上用 kickoff prompt。
- 執行前務必先 `git status --short --branch` + `git diff -- Publish/index.html`。
  **`Publish/index.html` 目前很可能不是乾淨的 main HEAD。** 本 session 已在工作區留下
  4 輪未提交的 Tier 2 修正（見 §1）。看到這些改動屬正常狀態——**不要 revert、不要假設有個
  「乾淨版本」而重做一次**。
- 本文件所有數字皆為 2026-07-23 對線上真實 GAS 資料（85 件、11 個分類字串）實測所得。
  執行前，尤其要拿來當驗收基準的數字，建議用 DOM 重新量一次確認——特別是 §1 的改動
  已經改變了若干原始基準值（例如分類分頁數從 12 變 7、手機 rail 隱藏比例從 56% 變 0%）。
- 真實 Core Web Vitals（LCP/INP）與實機觸控手感**從未量測過**。任何關於這兩者的結論
  之前都被本 session 自己撤回過一次（見 §7 的更正說明）——不要重蹈覆轍，沒量到就不要下結論。

---

## 1. 現況：已完成但尚未提交的 4 輪（本 session 內，全部在 `Publish/index.html`，皆無 commit/branch/PR）

| 輪次 | Tag（用 `grep -n` 可定位） | 內容 | 驗證狀態 |
|---|---|---|---|
| R1 | `CHANGE P2-ZOOM` | Lightbox 加入可見「＋ 點按細看／拖曳移動・點按還原」提示；`aria-pressed`／`aria-label`／可見提示三態同步（原本 aria-label 只寫一次、放大後仍顯示「放大檢視」，狀態矛盾） | 1440/1024/375 已驗證 |
| R2 | `CHANGE P2-BOX` | 修正 `.modal-left`／`.modal-right` 手機 `content-box` 溢出——375px 下故事文 30 行中 25 行被裁字、器物影像中心偏移 +20px；改 `box-sizing:border-box` | 已驗證，器物影像尺寸不變 |
| R3 | `CHANGE P2-LIFE` | 修正 modal 關閉逾時競態（260ms 內重開會被舊逾時關掉剛開的 modal）+ focus-trap 監聽器洩漏（重入 5 次累積 6 個、關閉後仍殘留 5 個，形成鍵盤陷阱） | 已驗證 |
| R4 | `CHANGE P2-RAIL` | 分類長尾收斂（單件分類併入「其他」，12→7 分頁）+ 手機改折行（375px 下隱藏比例 56%→0%）+ **順帶修正既有 tablist bug**（點擊切換時兩個分頁同時 `aria-selected="true"`，根因是過期的 `btns` 快照） | 已驗證，三者一致（badge＝篩選卡片數＝aria-live 播報） |

這四輪**不需要重做、不需要覆核**——各自都跑過 1440/1024/375 三斷點、a11y（focus trap／aria-live／鍵盤）、console 零錯誤驗證。

---

## 2. 稽核方法與可信度邊界

量測方式：把 `Publish/index.html` 載入瀏覽器、對線上真實 GAS API 回應（85 件、真實圖片）
抓取實際渲染後的 `getBoundingClientRect()`／`getComputedStyle()`／Range 行框／`artifactsData`
原始欄位，現算而非估計。對比度用 WCAG 相對亮度公式現算，**背景一律取實際生效的祖先底色**
（這點很關鍵，見 §5 的根因）。

沒量過的兩件事，本文件不對其下結論：
1. 真實 Core Web Vitals（LCP/INP/TBT）——本機 `file://` 載入、分頁常處於背景，計時不可信。
2. 實機觸控手感——合成 TouchEvent 只能證明邏輯正確，證明不了體感。

---

## 3. Rubric v3 對照表（本 backlog 如何嵌入既有框架）

| Rubric v3 產出維度 | 對應本 backlog 位置 |
|---|---|
| 導流有效性 Funnel Efficacy | §8（F1，Craig 已指示暫緩，**不在本輪範圍**） |
| 真實 CWV Measured CWV | 部分見 §7（字型/will-change/圖片瘦身），**仍無 Lighthouse harness，未量真實數字** |
| 可被發現性 Discoverability | §4（分類長尾已收斂；年代軸線／deep-link 待決或待做） |
| 輔助科技實地體驗 A11y Lived | §5（對比）+ §7 首位（語意骨架）+ 已完成的 P2-LIFE/P2-ZOOM |
| 跨裝置韌性 Cross-Device | 手機 rail 折行已完成；卡片變體手機塌陷、era 越界值韌性**未做** |
| 信任/敘事深度 Trust & Narrative | §6（完整句子取代截斷）+ 待決 Decision B/C（feature 卡待遇） |
| 邊緣狀態品質 Edge-State | QW5 已完成，本輪無新項目 |

---

## 4. F2 — 發現性：剩餘項目

**已完成**（P2-RAIL）：12 分頁 → 7 分頁（單件分類併「其他」）；手機從橫向捲動改折行，
375px 下隱藏比例 56% → 0%。

**分類分布**（真實資料，count > 1 者維持獨立分頁）：

| 分類 | 件數 | 分類 | 件數 |
|---|---:|---|---:|
| 玉器 | 35 | 書畫 | 1（併「其他」） |
| 銅器 | 28 | 木器 | 1（併「其他」） |
| 陶瓷 | 10 | 銅香爐 | 1（併「其他」） |
| 雜項 | 8 | 金屬器 | 1（併「其他」） |
| 香爐 | 3 | 手爐 | 1（併「其他」） |
| | | 祭祀器 | 1（併「其他」） |

**年代分布**（目前完全沒有篩選軸線，但資料已存在）：

| 年代 | 件數 |
|---|---:|
| 清朝 | 52 |
| 史前與高古 | 10 |
| 明朝 | 9 |
| 民國 | 6 |
| 唐宋元(含之前) | 5 |
| 近現代 | 2 |
| 清末至民國初年 (約19世紀末至20世紀初) | 1（**超出凍結的 9 值 era enum**，見 §7） |

**待決 Decision A（年代副軸）**——見 §9。**不要**自行實作；先用 `marketing-psychology`
skill 檢驗「年代是不是買家真正的第一分類軸線」，資料分布（清朝 52 件最大宗）不能代替買家研究。

**deep-link 的誠實限制**：卡片上的 `LOT 001`–`LOT 085` 是陣列索引即時算出，**不是穩定 ID**。
新增/刪除藏品會讓所有 LOT 號整批位移，今天的 `#lot-042` 明天可能指向另一件。
真正穩定的單件 deep-link 需要 GAS `doGet()` 輸出 UUID（欄位已存在，只是沒輸出）——
這超出「只改 `Publish/index.html`」的範圍。**可以先做的**：分類與年代的篩選狀態
還原（`#玉器/清朝` 這類），沒有漂移問題，且已能解決分享篩選結果與回訪的需求。

---

## 5. F3 — 對比：已核准的規則與剩餘項目

**根因**：`--fg-muted #6b6b6b`（Round 22 註解宣稱「5.09:1 符合 AA」）是對紙色
`--paper #f7f4ed` 算的；但卡片實際底色是 `--paper-400 #ede8dc`，**實測只有 4.36:1**，
差 0.14 功虧一簣。

**目前失敗清單**（WCAG AA 正常字需 4.5:1，大字 24px/400 需 3:1）：

| 元素 | 承載什麼 | 實測對比 | 結果 |
|---|---|---:|---|
| `.brand-slogan` | 品牌承諾 | 2.15 | 連 3:1 都不到 |
| `.cat-glyph` | 分類導航 | 2.15 | 連 3:1 都不到 |
| `.site-footer` | 版權 | 3.27 | 未達 |
| `.item-era` | 規格 | 4.23 | 未達 |
| `.badge` | 規格 | 4.23 | 未達 |
| `.cat-label` | 分類導航 | 4.27 | 未達 |
| `.lot-number` | 規格 | 4.36 | 未達 |
| `.tag` | 規格 | 4.36 | 未達 |
| `.contact-note` | 版權 | 4.36 | 未達 |
| `.item-story` | 敘事 | 7.25 | 通過 |
| `.item-name` | 敘事 | 11.42 | 通過 |
| `.brand-title` | 敘事 | 11.52 | 通過 |

**金色階梯實測**（零新增顏色，答案已在既有 token 裡）：

| Token | Hex | 對紙 | 對卡片底 | 結果 |
|---|---|---:|---:|---|
| `--gold-500` | `#c49a45` | 2.37 | 2.13 | 失敗——只能畫線/框/印章 |
| `--gold-700` | `#8a6f2f` | 4.35 | 3.91 | 失敗——目前的文字金 |
| `--gold-900` | `#6b5220` | 6.70 | 6.02 | **通過，已存在的 token** |
| `--gold-500` on 頁尾墨底 `#1a1a1a` | — | — | 6.68 | **通過**，且比目前灰色更有品牌感 |

**規則**：文字承載金色時用 `--gold-900`；金色畫線、描框、蓋印時 `--gold-500` 完全不動。
頁尾文字灰色可直接換成金色，同時修對比又多還一分品牌色。

**明確提醒**：不要機械式地把每個元素都推到 4.5。純裝飾、不獨立承載資訊的東西
（如意雲、印章光暈、卡片四角 L 型角飾、髮絲線）本來就在 WCAG 豁免範圍，硬拉高
只會讓畫面變吵、階層變平。這條規則只適用於**承載可讀資訊**的文字。

---

## 6. F4 — 版面與閱讀性：剩餘項目

### 完整句子取代截斷五行（投報最高，建議優先）

目前 `-webkit-line-clamp:5` 任意位置截斷、蓋漸層遮罩。真實資料統計句子結構：

| 統計 | 最小 | 中位數 | 75% | 90% | 最大 |
|---|---:|---:|---:|---:|---:|
| 首句字數 | 16 | 39 | 48 | 60 | 91 |
| 前兩句字數 | 51 | 86 | 104 | 119 | 145 |

三個卡片變體的五行容量：feature 105 字／landscape 115 字／portrait 170 字。
**前兩句中位數 86 字，三個變體全部放得下。** 建議改為「依序取完整句子，直到超過容量為止」，
每張卡片都停在句號上；漸層遮罩隨之取消（沒有東西被切斷，不需要遮蔽切口）；
在原本遮罩的位置改放一個克制的「全文」提示，語彙沿用 P2-ZOOM 的細看提示
（`pointer-events:none`、無發光、radius ≤2px、無持續動畫）。

### feature 卡是三個變體裡文字欄最窄的（倒置）

桌面 1440px 實測行長：feature 21 字/行（最差）、landscape 23 字/行、portrait 34 字/行
（最佳）。中文舒適行長是 30–45 字——**本該最隆重的 feature 卡文字欄最窄，最普通的
portrait 反而最舒適**。

### 手機上三個卡片變體完全塌陷（未做）

`@media (max-width:768px)` 對 `.img-box` 用 `width:100%!important`＋`height:260px!important`，
**覆蓋掉全部三個變體的圖框規則**——85 張卡片在手機上幾何完全相同，DP-002 的比例節奏
（13 feature / 27 landscape / 45 portrait）在主要瀏覽裝置上是隱形的。建議給三級各自的
手機圖高（例：feature 340、portrait 300、landscape 220），純呈現層、Tier 2、可自主。

### 8px 網格稽核缺口（未做，低優先）

卡片內垂直間距實測：`.item-name` marginBottom 10px、`.material-badges` marginBottom 12px、
`.item-story` marginBottom 20px——皆不在 8px 網格上，儘管程式碼註解宣稱已對齊。
低優先，因為視覺影響極小，但既然是明文原則就該一致。

### 待決 Decision B／C（見 §9，未實作）

feature 卡改「圖上文下」（我的首選建議，同時解決倒置與「沒被特別對待」兩個問題）；
feature 圖版加高 520→640＋前後間距 80→120（建議在 B 定案後再評估，B 可能已解決一半節奏問題）。

---

## 7. F5 — 結構與效能：已修正優先序

**重要更正**：本 session 曾把「Noto Serif TC 五個字重」講成整頁最大流量浪費，**這是錯的**。
未被 CSS 匹配的 `@font-face` 不會下載字檔。實測整頁只下載三個字檔（Cormorant Garamond 400、
LXGW WenKai TC 400、Ma Shan Zheng 400），Noto Serif TC 五個字重**一個都沒下載**。
真實成本是樣式表本身偏大：877 條 `@font-face` 規則，只留 400 可降到 325 條（−63%）。
**不能整個刪掉 Noto Serif TC**——它是 Android/Linux 沒有標楷體時的安全網，只是不需要五個字重。

修正後優先序：

1. **語意骨架**（上修，建議優先）：無 `<main>`、無 `<nav>`、無 skip link；
   87 個 `<h2>`（85 品名 + 2 其他）完全平行掛在單一 `<h1>` 底下，無層級。
   成本極低、純 markup，是 Epic D 投資（D4 卡片語意化）的收尾——D4 讓 85 個品名
   可被報讀器 H 鍵列出，卻沒給它們層級。
2. **will-change 常駐 85 張**：`.card` 基礎規則無條件宣告
   `will-change: transform, opacity` ＋ `perspective:1000px` ＋ `preserve-3d`，
   JS 清理邏輯（動畫結束設回 auto）被基礎規則抵銷。無法在此環境量測 GPU 記憶體，
   不宣稱具體數字；但違反同一份檔案自己在 `.brand-title` 上寫下的原則
   （「動畫結束後保留 will-change 會浪費一個合成圖層」）。
3. **字型請求瘦身**（下修）：877 條 → 325 條（只留 400），**保留 Noto Serif TC**。
4. **響應式圖片**（下修，重新算過 dpr 後沒有原本想的嚴重）：手機 dpr 3 需要
   約 1125px，目前 `w1000` 其實還略嫌不足；真正浪費的是 1× 桌面
   （圖框只有 462–682px 卻載 1000px，約 1.5–2× 過剩）。
5. **era 越界值前端韌性**：一件典藏年代是「清末至民國初年 (約19世紀末至20世紀初)」，
   超出凍結的 9 值列舉，把年代 chip 撐成兩行 303×49px 方塊。前端該做韌性處理
   （超長字串降級字級/字距），但**根因在資料端**——按規則超出列舉的值本該被
   Curator 標為衝突、不該上架。前端修的是症狀。

---

## 8. F1 — 已延後（不在本輪範圍）

**Craig 已明確指示**：「這些資訊未來會補齊，目前先討論設計的部分」。本 backlog
不安排 F1（實體藝廊資訊：地址／開放時間／預約方式／Google Maps／LINE ID）相關任務。
**不要主動詢問這些資訊，不要因為 F1 未解而阻塞其他項目**，也不要實作聯絡區 CTA
（LINE 按鈕啟用、modal CTA 改直接導向等）——那些全部卡在缺資料，不是技術問題。

---

## 9. 待 Craig 拍板的三個構圖決定（尚未實作，已備妥可互動對照原型）

| 決定 | 內容 | 建議 |
|---|---|---|
| **A** | 年代副軸要不要加（見 §4） | 先用 `marketing-psychology` skill 驗證，別用資料分布代替買家研究 |
| **B** | feature 卡改「圖上文下」（見 §6） | **首選建議**——同時解決倒置與待遇問題，只影響 13 張卡 |
| **C** | feature 圖版加高 520→640、間距 80→120 | 建議排在 B 之後評估，B 可能已解決一半節奏問題 |

對照原型（現況 vs 提案可切換，真實器物照片＋真實文案）：
`https://claude.ai/code/artifact/ad9a3712-b8e0-4a82-a42b-8a24285877f0`
——這是 Craig 個人帳號下的私有 artifact，若執行者無法存取，**不要憑空猜測版面**，
請依本文件 §6/§9 的文字描述與數字重建對照，或請 Craig 重新開放存取。

**這三項在 Craig 回覆前不得實作**——它們會改變 Craig 已看了幾十小時的畫面構圖，
不該由任何 agent 代決。

---

## 10. 建議執行順序（Tier 2 自主軌，逐輪各一個已驗證切片）

| 輪次 | 內容 | 依據 |
|---|---|---|
| R5 | 對比補正（§5）＋ 語意骨架（§7 第 1 項）＋ era 越界值前端韌性（§7 第 5 項） | 純 CSS/markup，回歸面最小 |
| R6 | 完整句子截斷＋閱讀全文提示（§6）＋ will-change 動態化（§7 第 2 項） | 投報最高的可見改動 |
| R7 | 字型瘦身（§7 第 3 項，保留 Noto Serif TC）＋ 響應式圖片（§7 第 4 項） | 效能收尾 |
| R8 | 待 Craig 回覆 Decision A/B/C 後，依核准項目實作 | 需人為拍板 |
| （延後） | F1 相關 | 等 Craig 提供資料 |

---

## 11. 明確禁止事項（本 backlog 全程適用，見 CLAUDE.md/AGENTS.md 完整版）

- 純 HTML/CSS/vanilla JS；不加 React/Vue/Tailwind/Next.js/Framer Motion；不加 npm/CDN JS/build step
- 本輪只能修改 `Publish/index.html`；不修改 `index.html`、`scripts/`、`config/`、GAS、Sheets schema、
  API URL、era enum、真實藏品資料
- 不新增 `condition`／`provenance` 欄位；不作任何真偽、鑑定或 provenance 強化聲明
- 不改 Hero、logo、palette、type system、IA 或品牌敘事；不新增公開頁區段或新功能
- 色彩沿用既有四色 token；動畫只 animate transform/opacity/filter，必須支援
  `prefers-reduced-motion`；明確排除 200vh Text Reveal、hover-only Reveal Images、
  shader/aurora/particle/marquee、3D carousel、custom cursor、autoplay gallery
- 不建立或切換 branch；不 `git add`；不 commit；不 push；不開 PR；不清理任何
  untracked/modified 檔案；不修改 `memory/gpt_polish_log.md`、`AGENTS.md`、`CLAUDE.md`
  或任何 design brief；不啟動 Discord bot、GAS migration 或任何外部寫入
- 如需 staging、commit、Tier 1 公開內容、地址、LINE ID 或 Google Maps 資料，
  **停止並向 Craig 請求明確授權**

---

## 12. 每輪回報格式（沿用本 session 慣例）

完成一個已驗證切片後，以繁體中文回報：

1. Outcome
2. Live repo / branch / HEAD
3. Findings first（修正前的實測證據，不是形容詞）
4. `Publish/index.html` 實際修改內容與行號
5. 1440 / 1024 / 375 驗證矩陣（真實 GAS 資料，不是 mock）
6. Accessibility 與 reduced-motion 結果
7. git diff 邊界（`git diff --check`、`node --check` inline script、`git diff --name-status`）
8. 尚未實作的候選（附優先度理由）
9. 建議下一個最小回合

完成一個已驗證的 Tier 2 slice 後即停止，不擴張範圍。最後一行輸出：
`STOP_AFTER_ONE_VERIFIED_TIER2_SLICE`

---

## 13. 附：貼上即可使用的 kickoff prompt

見對話訊息本身（本文件的姊妹交付物）；或直接複製下方區塊：

```
你是 Claude，接手「吉寶軒 Antique Digital Pavilion」前端設計優化 session。
工作模式：implementation，範圍限縮為一輪一個已驗證的 Tier 2 切片。

一、啟動程序（依序執行，不要跳過）
1. pwd
2. git status --short --branch
3. git diff -- Publish/index.html
   → 若有未提交修改，先讀懂它是什麼（很可能是 4 輪 P2-* 修正，見下方文件 §1），
     不要 revert、不要假設有個「乾淨版本」。
4. 完整閱讀：CLAUDE.md、AGENTS.md、DESIGN_BRIEF_Complete_AestheticUX.md

二、本輪任務
從 DESIGN_BRIEF_Complete_AestheticUX.md §10 的建議執行順序取下一輪（預設 R5），
只做那一輪列出的項目，做完就停。

三、鐵律
- 只改 Publish/index.html
- 不 git add／commit／push／建 branch／開 PR
- 不主動處理 F1（實體藝廊資訊）——Craig 已指示暫緩
- Decision A/B/C（見文件 §9）未經 Craig 回覆不得實作
- 完成後用文件 §12 的格式回報，最後一行輸出 STOP_AFTER_ONE_VERIFIED_TIER2_SLICE
```
