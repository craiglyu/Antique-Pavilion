# 交接包 — 吉寶軒前端設計優化 Design Loop（Claude → Codex）

> 產生者：Claude（Sonnet 5）· 交接日期 2026-08-21
> 交接原因：Craig 要求換到 Codex 中繼續開發，本文件是唯一需要的啟動上下文。
> 性質：**交接包（handoff packet）**，包含現況快照、已完成工作證據、硬性規則、待決事項、
> 下一輪建議。Codex 讀完本文件應該可以直接開工，不需要再回頭問 Craig「目前狀態是什麼」。

---

## 0. 三秒版摘要

- Repo：`C:\Users\A50529\Desktop\Craig\Antique Digital Pavilion`（Windows 路徑）／
  `/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion`（Git Bash / WSL2 路徑）
- Branch：`main`　HEAD：`0776c94`（`merge: design/epic-a11y (QW1–5 + D3–D6) → main`）
- **唯一有實質改動的檔案**：[`Publish/index.html`](Publish/index.html)（3795 行，工作區未提交，
  `git diff --stat` 顯示 550 insertions / 91 deletions）
- 目前工作區還有一個**跟本輪設計無關**的既有修改：`.claude/commands/design-review.md`
  （session 開始前就存在，不是這條 design loop 的產物，不要動它，也不要當作「未完成的一部分」）
- 本輪（R5 → R6 → R7）已完成並逐輪在瀏覽器內用真實 GAS 資料（85 件典藏）驗證，**未 commit**。
- 下一輪建議 **R8**：響應式圖片 `srcset`（§7-4）＋ `.empty-glyph` 補 `aria-hidden`（見 §5）。
- **三項待 Craig 拍板的構圖決定（Decision A/B/C）未經回覆前不得實作**（見 §4）。

---

## 1. 讀取順序（Codex 開工前務必依序讀完）

1. `pwd` 確認工作目錄
2. `git status --short --branch` + `git --no-pager diff -- Publish/index.html`
   → 會看到大量未提交修改，那是 4 輪 P2-* 修正（P2-ZOOM/P2-BOX/P2-LIFE/P2-RAIL，本 session
   接手前就已存在於工作區）+ 本 session 完成的 R5/R6/R7。**不要 revert，不要假設有個
   「乾淨版本」**。
3. 完整閱讀（依重要性排序）：
   - [`CLAUDE.md`](CLAUDE.md) 或 [`AGENTS.md`](AGENTS.md)（兩者內容幾乎相同，只是 Codex 慣例
     讀 `AGENTS.md`、Claude 慣例讀 `CLAUDE.md`；`AGENTS.md` 是較新版本，May 20 vs May 3，
     若兩者衝突以 `AGENTS.md` 為準）
   - [`DESIGN_BRIEF_Complete_AestheticUX.md`](DESIGN_BRIEF_Complete_AestheticUX.md) —
     這是本輪 design loop 的**權威 backlog**，§10 訂出建議執行順序（R5→R6→R7→R8），§11 是
     明確禁止事項，§12 是每輪回報格式
   - 本文件（`HANDOFF_Codex_DesignLoop_R8.md`）— 記錄 R5/R6/R7 實際做了什麼、怎麼驗證、
     下一步是什麼

---

## 2. 已完成工作總覽（R5 / R6 / R7，全部在 `Publish/index.html`，全部未 commit）

每項改動在檔案內都有 `/* CHANGE R{5,6,7}-{TAG}: ... */` 或 `<!-- CHANGE R{5,6,7}-{TAG}: ... -->`
註解，可用 `grep -n "CHANGE R5-\|CHANGE R6-\|CHANGE R7-" Publish/index.html` 一次列出全部
48 處。註解裡都寫了**實測數字**（改之前的對比度/字數/高度等），不是空話。

| 輪次 | Tag（`grep -n` 可定位） | 出現次數 | 首次出現行號 | 內容摘要 |
|---|---|---:|---:|---|
| R5 | `CHANGE R5-CONTRAST` | 19 | 92 | WCAG AA 對比修正（`--fg-muted` ink-500→ink-600；金色文字統一走 `--gold-900`；頁尾改用 `--gold-500` 對墨底），16 項全數通過 4.5:1（大字 3:1） |
| R5 | `CHANGE R5-SEMANTIC` | 6 | 1952 | 語意骨架：新增 skip link、`<main>`、`<nav>`（分類列 div→nav）、`<section aria-labelledby>`（洽詢區）、品名 h2→h3（建立正確的 h1→h2→h3 層級） |
| R5 | `CHANGE R5-ERA` | 3 | 903 | era 越界值前端韌性：`eraFitClass()` 依字數（>8/>14）套用 `.is-long`/`.is-xlong` 降級樣式，修正唯一一筆超出凍結 9 值列舉的髒資料撐破版面的問題 |
| R6 | `CHANGE R6-STORY` | 8 | 1610 | 完整句子截斷：`fitStories()` 二分搜尋找出五行容量放得下的最大句數，取代任意位置 `-webkit-line-clamp:5`；移除漸層遮罩；新增「⋯ 全文見詳情」提示 |
| R6 | `CHANGE R6-LAYER` | 10 | 564 | `will-change` 動態化：移出 `.card` 常駐基礎規則，改為 `.card.is-animating` 只在入場/hover/篩選進退場期間掛上；`perspective`/`preserve-3d` 同理移到 `.card.tilt-active` |
| R7 | `CHANGE R7-FONT` | 1 | 28 | Google Fonts 請求瘦身：`@font-face` 宣告從 877 條降到 320 條（只留 400 normal），**Noto Serif TC 整組保留**（Android/Linux 無標楷體時的安全網） |
| R7 | `CHANGE R7-VARIANT` | 1 | 1807 | 手機三卡片變體圖高分化：`@media (max-width:768px)` 下 feature/portrait/landscape 從統一 260px 改為各自 340/300/220px，找回 DP-002 比例節奏 |

**這 7 類改動不需要重做、不需要覆核**——每一項都在 1440/1024/375（部分含 768/769 邊界）
三斷點對線上真實 GAS 資料（85 件）驗證過，console 零錯誤，橫向溢出為 0，`git diff --check`
與 inline `<script>` 的 `node --check` 皆通過。

### 尚未做、但已在文件中列為候選的既有 4 輪（P2-*，Codex 接手前已存在）

這 4 輪**不是本 session 做的**，是本 session 接手時工作區已有的修改，一併留在
`Publish/index.html` 內未提交：

| Tag | 首次出現行號 | 內容 |
|---|---:|---|
| `CHANGE P2-ZOOM` | 1256 | Lightbox 可見「＋ 點按細看」提示，三態同步 |
| `CHANGE P2-BOX` | 1899 | 修正 modal 手機 `content-box` 溢出 |
| `CHANGE P2-LIFE` | 2979 | 修正 modal 關閉逾時競態 + focus-trap 監聽器洩漏 |
| `CHANGE P2-RAIL` | 1606 | 分類長尾收斂（12→7 分頁）+ 手機改折行 |

同樣不需要重做。

---

## 3. 硬性規則（Tier 2 自主軌適用，違反前先停下問 Craig）

摘自 `CLAUDE.md` / `AGENTS.md` / `DESIGN_BRIEF_Complete_AestheticUX.md` §11：

- **只改 `Publish/index.html`**。不動 `index.html`（本地開發版，不同檔案）、`scripts/`、
  `config/`、GAS、Sheets schema、API URL、era 9 值枚舉、真實藏品資料
- **純 HTML/CSS/vanilla JS**。不加 React/Vue/Tailwind/Next.js/Framer Motion，不加
  npm/CDN JS/build step
- 色彩沿用既有 token（`--gold-*` / `--ink-*` / `--paper-*` / `--seal-*`），不新增顏色
- 動畫只 animate `transform`/`opacity`/`filter`，必須支援 `prefers-reduced-motion`；
  明確排除 200vh Text Reveal、hover-only Reveal Images、shader/aurora/particle/marquee、
  3D carousel、custom cursor、autoplay gallery
- 不新增 `condition`/`provenance` 欄位；不作任何真偽/鑑定/provenance 強化聲明
- 不改 Hero、logo、palette、type system、IA 或品牌敘事；不新增公開頁區段或新功能
- **不建立/切換 branch；不 `git add`；不 commit；不 push；不開 PR**；不清理任何
  untracked/modified 檔案；不修改 `memory/gpt_polish_log.md`、`AGENTS.md`、`CLAUDE.md`
  或任何 design brief（包含本交接文件——如果要更新交接狀態，開新檔案，不要改這份）
- **不主動處理 F1**（實體藝廊資訊：地址/開放時間/預約方式/Google Maps/LINE ID）——
  Craig 已指示暫緩，資料未補齊前不要問、不要因此阻塞其他項目
- 一輪只做一個已驗證的 Tier 2 切片，做完就停，不擴張範圍
- 如需 staging、commit、Tier 1 公開內容、地址、LINE ID 或 Google Maps 資料，
  **停止並向 Craig 請求明確授權**

---

## 4. 待 Craig 拍板、目前不得實作的三項（Decision A/B/C）

出自 `DESIGN_BRIEF_Complete_AestheticUX.md` §9：

| 決定 | 內容 | 目前建議 |
|---|---|---|
| **A** | 年代副軸要不要加（分類列旁邊加一條年代篩選軸） | 先用 `marketing-psychology` skill 驗證買家研究，別用「清朝 52 件最大宗」的資料分布代替 |
| **B** | feature 卡改「圖上文下」 | 首選建議——同時解決 R6/R7 驗證中發現的「feature 卡文字欄最窄（21 字/行 vs portrait 33 字/行）」與「本該最隆重卻沒被特別對待」兩個問題，只影響 13 張卡 |
| **C** | feature 圖版加高 520→640、間距 80→120 | 建議排在 B 之後評估，B 可能已解決一半節奏問題 |

對照原型（現況 vs 提案可切換）：`https://claude.ai/code/artifact/ad9a3712-b8e0-4a82-a42b-8a24285877f0`
——Craig 個人帳號下的私有 artifact，Codex 大概率無法存取；**不要憑空猜測版面**，
請依文件 §6/§9 文字描述重建對照，或請 Craig 重新開放存取／截圖分享。

**這三項在 Craig 回覆前不得實作。**

---

## 5. 下一輪建議：R8

依 `DESIGN_BRIEF_Complete_AestheticUX.md` §10 排序，R8 原定「待 Craig 回覆 Decision A/B/C
後實作」，但在 R7 完成時我建議了一個不依賴 Decision 拍板、可以先做的候選組合：

### R8 建議內容

1. **響應式圖片 `srcset`（文件 §7-4）**
   現況：`Publish/index.html` 內兩處組 Drive 縮圖 URL 都固定 `sz=w1000`
   （卡片縮圖約在 `fetchArtifacts()` 內、modal 高解圖在 `openModal()` 內，兩處都用
   `https://drive.google.com/thumbnail?id=${idMatch[1]}&sz=w1000` 這個模式，
   `grep -n "sz=w1000\|sz=w2000"` 可定位）。
   實測落差（R7 交接時量測，1440/375，dpr 1–3）：
   - 桌面 1440 landscape 圖框實寬 638px，送 1000px → 1.57× 過剩
   - 桌面 1440 portrait 圖框實寬 462px，送 1000px → 2.16× 過剩
   - 手機 375 @dpr3 需要 ~1029px，送 1000px → **略嫌不足**
   建議：依卡片變體（`.card--feature`/`.card--portrait`/`.card--landscape`）與斷點組出
   對應寬度的 `sz=`，用 `srcset` + `sizes` 或至少依斷點動態組 URL（Drive thumbnail 的
   `sz=` 參數支援任意寬度，成本低）。

2. **`.empty-glyph` 補 `aria-hidden="true"`**
   `.empty-state` 內的 `<span class="empty-glyph">吉/軍/虛</span>` 目前沒有 `aria-hidden`。
   R7 驗證期間 GAS API 端點短暫真實回過 404，錯誤態上場時報讀器實測讀出「**軍**典藏連線
   暫時中斷…」——裝飾用的印章字被當內容念出來。1 個屬性、零視覺影響，之前只是注入模擬量測，
   現在已有真機驗證支持。三處 markup（載入中/QW5 錯誤態/篩選無結果）都要補，
   `grep -n "empty-glyph" Publish/index.html` 定位。

### 其他候選（按投報排序，供你參考，不代 Craig 決定）

- **Decision B 一旦拍板** → feature 卡改「圖上文下」，同時解決文字欄過窄與節奏倒置
- **分類/年代篩選狀態還原**（URL hash，如 `#玉器/清朝`）——文件 §4 已標定、無 LOT 編號
  漂移問題，能解決分享篩選結果與回訪定位，投報高
- **窄欄對齊**：feature/landscape 卡的 `.item-story` 目前 `text-align:justify`，
  但只有 21–22 字/行，兩端對齊在窄欄容易把調整量集中到少數字距；portrait（33 字/行）
  保留 justify、feature/landscape 改 `text-align:start` 值得評估，但會改變 Craig
  已看慣的質地，建議先問過再動
- **8px 網格缺口**：`.item-name` marginBottom 10px / `.material-badges` 12px /
  `.item-story` 20px 皆不在 8px 網格上，低優先
- **landscape 卡高落差**（R6 完整句子截斷的副作用）：375 下 585–695px、1440 下
  411–488px，落差比修正前大；是否需要 `min-height` 收斂屬美學判斷，建議親眼看過再決定

---

## 6. 驗證方法論（Codex 沒有 GUI 截圖能力時的替代做法）

本輪全程**沒有用截圖驗收**，因為此環境的 preview pane 對本專案會逾時
（`memory/project_preview_env_quirks.md` 有記錄，Codex 若有類似限制可比照）。改用瀏覽器
`javascript_exec` 現場執行量測腳本，量的是**真實 DOM 狀態**，不是視覺猜測。核心手法：

1. **對比度**：WCAG 相對亮度公式現算，背景一律用 `getComputedStyle` 沿 DOM 父鏈找到
   第一個 alpha>0.5 的 `background-color`（不是讀 CSS 宣告，是讀「實際生效」的顏色）
2. **文字截斷/容量**：用 `Range.setStart/setEnd` + `getClientRects()` 二分搜尋找出
   「最後一個不溢出容器的字元位置」，比對是否落在句末標點
3. **will-change 生命週期**：`getComputedStyle(el).willChange` 現讀，不是看 CSS 原始碼；
   搭配 `element.getAnimations()` 確認真正在跑的動畫數量
4. **resize 驗證**：此環境的 `resize_window` 工具**不保證派送原生 `resize` 事件**
   （實測同一輪內事件計數從 0 跳到 3，順序不可靠），改用
   `window.dispatchEvent(new Event('resize'))` 手動觸發已註冊的 handler 驗證
5. **字型下載**：`document.fonts` 逐 face 讀 `.status === 'loaded'`，不是數 CSS 裡
   宣告了幾個 `@font-face`

如果 Codex 的環境有可靠的截圖/視覺 diff 能力，直接用截圖驗收即可，不必照搬這套腳本手法；
但**對比度數字、文字截斷是否切在句中、will-change 是否釋放**這三類問題本質上肉眼不可靠，
建議無論如何都用 DOM 現算驗證，不要只憑截圖判斷通過。

---

## 7. 環境雷區（避免重踩）

- **GAS API 端點會短暫回 404**：`https://script.google.com/macros/s/AKfycbz.../exec`
  在 R7 驗證期間對瀏覽器分頁間歇性回過 404（同時間直接從主機 `curl`/`Invoke-WebRequest`
  是 200），重試後恢復。這是外部服務的暫時性問題，不是程式碼壞掉；遇到 empty-state
  先重試一次 `fetchArtifacts()` 再判斷。
- **inline `<script>` 語法檢查**：修改 JS 後務必抽出 `<script>...</script>` 內容跑
  `node --check`（注意用 UTF-8 無 BOM 寫檔，PowerShell 預設編碼會產生亂碼導致誤判語法錯誤）
- **`git diff --check`**：每輪收尾前跑一次，確認沒有空白/換行錯誤
- Windows 路徑與 Git Bash/WSL2 路徑不同：`C:\Users\A50529\Desktop\Craig\Antique Digital Pavilion`
  vs `/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion`（Git Bash）
  vs `/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion`（WSL2，`AGENTS.md`/`CLAUDE.md`
  裡的 bash 指令範例用的是這個）——三者依 Codex 實際跑在哪個 shell 選用
- 真實 Core Web Vitals（LCP/INP/TBT）、FPS、GPU 記憶體**從未量測過**，本輪任何關於這些的
  結論都只到「規則層檢查」為止，不宣稱具體數字改善多少
- 工作區內 `eval-review-iteration-1.html`、`Publish/pasted-1777028068404-0.png`、
  `scripts/GAS/`、`scripts/discord_setup_phase1a.py` 等 untracked 檔案與本 design loop
  **無關**，是其他工作留下的，不要誤認為是本輪產物或依賴

---

## 8. 相關檔案路徑清單

| 路徑（相對於 repo 根目錄） | 用途 |
|---|---|
| [`Publish/index.html`](Publish/index.html) | **唯一要改的檔案**。GitHub Pages 實際發布版 |
| [`CLAUDE.md`](CLAUDE.md) | 專案硬性規則（Claude 慣例讀這個） |
| [`AGENTS.md`](AGENTS.md) | 同上內容，Codex/agent-agnostic 慣例讀這個，版本較新 |
| [`DESIGN_BRIEF_Complete_AestheticUX.md`](DESIGN_BRIEF_Complete_AestheticUX.md) | Design loop 權威 backlog，§9 Decision A/B/C、§10 執行順序、§11 禁止事項、§12 回報格式 |
| [`DESIGN_BRIEF_EpicD_A11y.md`](DESIGN_BRIEF_EpicD_A11y.md) | 已完成，僅供歷史參考 |
| [`DESIGN_BRIEF_QuickWins.md`](DESIGN_BRIEF_QuickWins.md) | 已完成，僅供歷史參考 |
| [`AP_Design_Loop_v3_Strategy.md`](AP_Design_Loop_v3_Strategy.md) | Rubric v3 七維產出框架，design brief 是延伸這套框架而非取代 |
| `HANDOFF_Codex_DesignLoop_R8.md`（本文件） | 本次交接包 |
| `memory/design_review_log.md` | 較早期（Round N 命名法）的設計輪次紀錄，唯讀參考，不要修改 |
| `memory/project_preview_env_quirks.md` | Preview 環境限制記錄（screenshot 逾時問題），唯讀參考 |

**不在本輪範圍內、不要動的檔案**：`index.html`（本地開發版）、`config/*.yaml`、
`scripts/ap_org_bot/**`、任何 `.py` 檔案、`CHG_LOG.json`、GAS 相關程式碼。

---

## 9. 每輪回報格式（沿用 design brief §12 慣例）

完成一個已驗證切片後，用繁體中文回報：

1. Outcome
2. Live repo / branch / HEAD
3. Findings first（修正前的實測證據，不是形容詞）
4. `Publish/index.html` 實際修改內容與行號
5. 1440 / 1024 / 375 驗證矩陣（真實 GAS 資料，不是 mock）
6. Accessibility 與 reduced-motion 結果
7. git diff 邊界（`git diff --check`、`node --check` inline script、`git diff --name-status`）
8. 尚未實作的候選（附優先度理由）
9. 建議下一個最小回合

完成一個已驗證的 Tier 2 slice 後即停止，不擴張範圍。

---

## 10. 附：貼給 Codex 的啟動 prompt（可直接複製）

```
你是 Codex，接手「吉寶軒 Antique Digital Pavilion」前端設計優化 session，
從 Claude 手上交接。工作模式：implementation，範圍限縮為一輪一個已驗證的 Tier 2 切片。

一、啟動程序（依序執行，不要跳過）
1. pwd
2. git status --short --branch
3. git --no-pager diff -- Publish/index.html
   → 會看到大量未提交修改，是 4 輪 P2-* 修正 + R5/R6/R7，全部已驗證完成，
     不要 revert、不要假設有個「乾淨版本」。
4. 完整閱讀：AGENTS.md（或 CLAUDE.md）、DESIGN_BRIEF_Complete_AestheticUX.md、
   HANDOFF_Codex_DesignLoop_R8.md（本次交接包，記錄 R5/R6/R7 做了什麼、怎麼驗證）

二、本輪任務
從交接包 §5「R8 建議內容」開始：響應式圖片 srcset（§7-4）＋ .empty-glyph 補 aria-hidden。
只做這兩項，做完就停。

三、鐵律
- 只改 Publish/index.html
- 不 git add／commit／push／建 branch／開 PR
- 不主動處理 F1（實體藝廊資訊）——Craig 已指示暫緩
- Decision A/B/C（見交接包 §4）未經 Craig 回覆不得實作
- 完成後用交接包 §9 的格式回報
```

---

*本文件是交接快照，不是活文件——不會被後續 session 更新。若 Codex 完成 R8 後要繼續交接，
請開新檔案（例如 `HANDOFF_Codex_DesignLoop_R9.md`），不要改寫本文件。*
