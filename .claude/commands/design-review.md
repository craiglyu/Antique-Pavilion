---
id: skill_design_review
type: skill
layer: domain/ap
loaded_by: [Designer, PM]
version: v2.0
schema_version: 1
last_updated: 2026-05-07
change_notes: "v2: 明確串接 /taste-skill + /audit + /emil-skill，輸出 Claude Design task prompt"
---

# /design-review — Claude Design Loop Review

**用途**：作為 Claude Design 多輪優化 Loop 的「大腦」。
讀取 Git 上最新的 `Publish/index.html`，透過 AP 專案的三個設計 skills 進行深度 review，
輸出一份可直接貼入 Claude Design text window 的 task prompt。

> 這是 Loop 的 STEP 1。Craig 執行後，複製輸出的 prompt 貼入 Claude Design。

---

## 執行流程

### Phase A — 讀取最新狀態

```bash
# 取得 Git 上最新版本的 index.html
git log --oneline -3 -- Publish/index.html

# 如果 Claude Design 有開 PR，讀取 PR branch 的最新版
git fetch origin
git log --oneline -3 origin/design/round-$(git branch -r | grep design | wc -l)
```

讀取 `Publish/index.html` 全文，確認目前版本狀態。

---

### Phase B — 三層 AP Skills 深度 Review

依序執行以下三個 skill 的核心審查邏輯（不需用戶另外輸入指令）：

#### B1. /taste-skill 審查（高奢品牌品味）

參照 `.claude/commands/taste-skill.md` 的規則，審查：
- 是否達到 Sotheby's Asia / Christie's Hong Kong 的視覺水準？
- 動畫是否有「撥雲見寶」的質感，而非 AI generic 效果？
- 字型三層系統是否正確運用？
- 有無任何「AI slop」特徵（過度圓角、過飽和漸層、多餘陰影）？

#### B2. /audit 審查（5 維度設計評分）

參照 `.claude/commands/audit.md` 的 5 維度，每項 0–4 分：

| 維度 | 評分 | 主要發現 |
|---|---|---|
| 可及性 | /4 | WCAG AA、觸控目標、motion preference |
| 視覺層次 | /4 | 字型大小節奏、留白、對齊 |
| 品牌一致性 | /4 | 色彩、字型、詞彙 |
| 動畫品質 | /4 | Emil 原則、exit 速度、compositor |
| 程式碼品質 | /4 | 無 framework、無硬編碼 hex、SVG 正確 |

**總分：/20**

#### B3. /emil-skill 審查（動畫細節）

參照 `.claude/commands/emil-skill.md`，具體檢查：
- Exit 動畫是否比 Enter 快 2× ？
- 有無在 `width/height/top/left` 上做動畫？
- `will-change` 是否在動畫結束後清除？
- hover 互動是否有 `cubic-bezier(0.34, 1.56, 0.64, 1)` spring 感？

---

### Phase C — 生成 Claude Design Task Prompt

根據 Phase B 的發現，生成以下格式的 prompt。
**這份 prompt 就是 Craig 要貼進 Claude Design text window 的內容。**

---

```
═══════════════════════════════════════════════════════════════
📋 CLAUDE DESIGN TASK PROMPT — Round [N]
（複製以下全文，貼入 Claude Design text window）
═══════════════════════════════════════════════════════════════

你是吉寶軒（Jibao Xuan）的首席設計師。
吉寶軒是一個高奢中式古董展覽網站，品牌定位等同
Sotheby's Asia、Christie's Hong Kong、中國嘉德。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【設計系統】（必須嚴格遵守，違反則整輪作廢）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
色彩（僅此四色 + scale）：
  --ink   #2c2c2c  墨  | --paper  #f7f4ed  宣紙
  --gold  #c49a45  黃銅 | --seal-red #8a2a2a 朱砂
  → 無任何 blue / teal / purple / aurora gradient

四層字型：
  Plaque ：Ma Shan Zheng → 標楷體（品牌大字）
  Display：標楷體 → DFKai-SB（標題、印章）
  Body   ：LXGW WenKai TC → 標楷體（故事文字）
  Latin  ：Cormorant Garamond（批號、年份，僅 Latin 字元）
  → font-weight: 400 only，絕對不用 bold

動畫原則（Emil Kowalski）：
  → 只 animate transform / opacity / filter
  → exit 速度 2× enter
  → will-change 在 animationend 後清除
  → prefers-reduced-motion 必須覆蓋所有動畫

佈局：
  → 單欄交錯卡片（奇右偶左），絕不用 3-column grid
  → 8px grid，觸控目標 ≥ 44×44px

技術：
  → 純 HTML/CSS/vanilla JS
  → 所有改動在 Publish/index.html 一個檔案內完成

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【上一輪 Review 發現】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Phase B 的評分與主要發現]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【本輪任務】（優先序）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[根據 audit 結果填入，最多 3 項，每項有明確驗收標準]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【輸出要求】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 請先從 GitHub repo craiglyu/Antique-Pavilion，
   branch [當前 branch 名稱] 讀取 Publish/index.html

2. 完成優化後，開 Pull Request：
   - base: main
   - head: design/round-[N]
   - title: design: Round [N] — [本輪任務摘要]
   - 只修改 Publish/index.html

3. 每個改動處加上 /* CHANGE [代號]: 說明 */ 註解

═══════════════════════════════════════════════════════════════
```

---

### Phase D — 儲存與顯示

1. 將完整 prompt 寫入 `DESIGN_BRIEF_NEXT.md`
2. 在終端顯示評分摘要與 prompt
3. 提示 Craig 複製 prompt 貼入 Claude Design

---

## 觸發時機

每次 GitHub Actions 完成後（收到通知或看到 Actions 綠勾），
在 Claude Code CLI 輸入：

```
/design-review
```

Claude 會自動完成 Phase A → B → C → D，輸出下一輪 prompt。
