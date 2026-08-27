---
id: skill_design_review
type: skill
layer: domain/ap
loaded_by: [Designer, PM]
version: v3.0
schema_version: 1
last_updated: 2026-07-08
change_notes: "v3: rubric v3（5 美學地板 + 7 產出天花板）+ 雙軌 loop（自主軌/Craig軌）+ 真實量測 harness + 停手條件換血 + epic branch。取代 v2「20/20 即完成」的飽和判準。詳見 AP_Design_Loop_v3_Strategy.md"
---

# /design-review — Claude Design Loop Review（v3）

**用途**：作為 Claude Design 多輪優化 Loop 的「大腦」。
v3 的核心改變：**loop 的目標函數從「對設計系統的靜態合規度」升級為「追逐真實世界的五條曲線」**——
因為既有 5 維美學 audit 已飽和在 20/20，沒有梯度可爬（診斷見
`AP_Design_Loop_v3_Strategy.md` §1）。

> 這是 Loop 的 STEP 1。Craig 執行後，複製輸出的 prompt 貼入 Claude Design。
> **權威藍圖是 `AP_Design_Loop_v3_Strategy.md`；本 skill 是它的執行程序。**

---

## 執行流程

### Phase A — 讀取最新狀態

```bash
git log --oneline -3 -- Publish/index.html
git fetch origin
# 若某 epic branch 有開 PR，讀該 branch 最新版
git log --oneline -5 origin/design/epic-a11y
```

讀取 `Publish/index.html` 全文，確認目前版本狀態與「當前正在推進的 epic」。

---

### Phase B — Rubric v3 深度 Review

**兩層分開計分**（不要合成一個總分——那正是 v2 飽和的原因）。

#### B-地板：既有 5 美學維度（維持 20/20 為「不得回歸」門檻）

沿用 `/taste-skill` + `/emil-skill` 審查（見 `.claude/commands/taste-skill.md`、`emil-skill.md`）：

| 維度 | 評分 | 判準 |
|---|---|---|
| 可及性 | /4 | WCAG AA、觸控目標、motion preference |
| 視覺層次 | /4 | 字型節奏、留白、對齊 |
| 品牌一致性 | /4 | 四色、四層字型、詞彙 |
| 動畫品質 | /4 | Emil 原則、exit 2× enter、compositor |
| 程式碼品質 | /4 | 無 framework、無硬編碼 hex、SVG 正確 |

**地板總分：/20** — 任何 epic round 讓此分回歸即作廢。

#### B-天花板：7 個「產出型」維度（用真實量測，非 grep）

**不要只 grep 樣式。要實際啟動頁面量測**（見 Phase B'）：

| 產出維度 | 量測方式（客觀） |
|---|---|
| 導流有效性 | 可用（非 disabled）且抵達真實動作的路徑數、死路 CTA 計數、modal→下一步互動次數 |
| 真實 CWV | Lighthouse LCP/INP/TBT、滾動 frame-time、同屏 active `backdrop-filter` 層數、捲離 hero 後 GPU 軌道 |
| 可被發現性 | 每件 deep-link、Rich Results Test schema 型別、原生分享入口、axe landmark/heading |
| 輔助科技實地體驗 | `aria-live` 播報、JS 動畫尊重 reduced-motion、焦點落點、標題數==卡片數、放大鍵盤可達 |
| 跨裝置韌性 | 320/360/375/768/1024+橫向無破版、`safe-area`、觸控手勢可用 |
| 信任/敘事深度 | About/策展聲音/provenance 存在、modal 故事先於價格、5 秒測試複述「這是誰、為何可信」 |
| 邊緣狀態品質 | empty/sparse/error/離線品牌化、error 無洩漏 GAS URL / JS 例外 |

#### Phase B' — 真實量測 harness（v3 新增）

接續 §9 Sprint 4 已交付的 visual regression baseline，**不是從零建**：

- `preview_start` 起本地 server + headless 瀏覽器 → 實跑 **Lighthouse**（LCP/INP/TBT）。
- **axe** 掃 a11y / landmark / heading-order。
- **Rich Results / Schema Validator** 驗 JSON-LD。
- 合成 **TouchEvent** / `readPixels` 驗互動與動畫 gate。
- 每個維度的「驗收」直接採用該 epic round 已寫好的 `acceptanceCriteria` 當測試斷言。

> ⚠️ **預算護欄**（CLAUDE.md §6 / §10）：量測 + Council/Opus token 受硬上限約束
> （Opus USD 15、Gemini USD 30），**不得跳過 `budget_gate`**。跑 harness 前確認 `/usage-status`。

---

### Phase C — 生成 Claude Design Task Prompt（依 epic）

依 `AP_Design_Loop_v3_Strategy.md` §3 選定「當前 epic」與「本輪 round」，生成 prompt。
**每輪最多 3 個 round 任務，每個含明確 `acceptanceCriteria`。**

```
═══════════════════════════════════════════════════════════════
📋 CLAUDE DESIGN TASK PROMPT — [Epic X · Round N]
（複製以下全文，貼入 Claude Design text window）
═══════════════════════════════════════════════════════════════

你是吉寶軒（Jibao Xuan）的首席設計師。
品牌定位等同 Sotheby's Asia、Christie's Hong Kong、中國嘉德。

━━━ 【設計系統】（違反則整輪作廢）━━━
色彩（僅此四色 + scale）：ink #2c2c2c / paper #f7f4ed / gold #c49a45 / seal-red #8a2a2a
  → 無 blue / teal / purple / aurora gradient
四層字型：Plaque(Ma Shan Zheng→標楷體) / Display(標楷體→DFKai-SB) /
  Body(LXGW WenKai TC→標楷體) / Latin(Cormorant Garamond，僅 Latin 字元)
  → font-weight: 400 only
動畫（Emil）：只 animate transform/opacity/filter；exit 2× enter；
  will-change 在 animationend 後清除；prefers-reduced-motion 覆蓋所有動畫
佈局：單欄交錯卡片；絕不用 3-column grid；8px grid；觸控 ≥44×44px
技術：純 HTML/CSS/vanilla JS；所有改動在 Publish/index.html 一個檔案內完成

━━━ 【本輪 Epic 與量測目標】━━━
[Epic 名稱 + 該 epic 的 metric（如 LCP<1.5s / 有效 CTA≥3 / axe a11y 100）]

━━━ 【上一輪 Review 發現】━━━
[Phase B 地板分數（須 20/20 無回歸）+ 天花板維度目前量測值]

━━━ 【本輪任務】（最多 3 項，每項有量測級驗收標準）━━━
[從 strategy §3 對應 epic 的 rounds 填入]

━━━ 【輸出要求】━━━
1. 從 GitHub repo 讀取 branch [當前 epic branch] 的 Publish/index.html
2. 完成後開 Pull Request：base main、head design/epic-[name]、
   title "design(epic-[name]): [Round N] — [摘要]"，只改 Publish/index.html
3. 每個改動處加 /* CHANGE [round代號]: 說明 */ 註解
4. ⚠️ 不得觸碰 Tier 1 / 真實藝廊資料 / provenance 欄位（見下方停手條件）
═══════════════════════════════════════════════════════════════
```

---

### Phase D — 雙軌分流 + 儲存

依 round 的 Tier / blockedBy 決定走哪一軌（見 strategy §4）：

- **自主軌**（loopSuitable 且 Tier 2/3）：metric 綠燈即推進。
  ⚠️ **Sprint 5 branch protection（⬜ pending）上線前，自主軌只能停在 PR，不得自動併 main。**
- **Craig 軌**（`blockedBy` 真實資料 / Tier 1 / DD-gated）：停在「PR 骨架 + digest」，
  明列需要 Craig 提供什麼、簽什麼核。**loop 不自撰「真品/鑑定/認證」或 provenance 文字。**

1. 將完整 prompt 寫入 `DESIGN_BRIEF_NEXT.md`（或對應 epic 的 brief 檔）。
2. 終端顯示：地板分數 + 天花板量測值 + prompt + 走哪一軌。
3. 提示 Craig。

---

## 停手條件（Definition of Done 換血）

round 的完成從「無違規 / 20/20」改為：

> **「該 epic 的 metric 打到目標 + 美學 20/20 無回歸」**

一旦某 round 命中以下任一，**loop 必須停手、交回 Craig**（不得在合規區間繼續抖 2px）：

- Tier 1：公開內容 / 品牌方向 / 新頁面或 IA 改動 / 任何「真品・鑑定・認證」宣稱。
- 需要真實藝廊資料（LINE ID / 地址 / 營業時間 / Maps / `tel:`）。
- DD-gated 凍結欄位（provenance col 14 / condition col 13，未經 DD-XXX 核准）。

---

## 觸發時機

```
/design-review
```

Claude 依當前 epic 完成 Phase A → B/B' → C → D，輸出下一輪 prompt。
權威藍圖與 epic 拆解見 `AP_Design_Loop_v3_Strategy.md`。
