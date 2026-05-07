---
id: skill_design_review
type: skill
layer: domain/ap
loaded_by: [Designer, PM]
version: v1.0
schema_version: 1
last_updated: 2026-05-07
change_notes: "初版 — Claude Design 多輪優化 Loop 的 review + brief 生成器"
---

# /design-review — Claude Design Loop Review

**Purpose**: 讀取最新一次 git commit 中 Claude Design 對 `Publish/index.html` 的改動，
用吉寶軒設計系統規則進行審查，並輸出下一輪可直接貼入 Claude Design 的設計 brief。

---

## 執行步驟

### Step 1 — 取得上一輪 diff

```bash
git log --oneline -5                                      # 確認最新幾筆 commit
git show HEAD --stat                                      # 確認哪些檔案被改動
git diff HEAD~1 HEAD -- Publish/index.html                # 取得完整 diff
```

如果 `Publish/index.html` 不在最新 commit 裡，往前找到最近一次包含它的 commit：

```bash
git log --oneline -- Publish/index.html | head -3
git show <commit-hash> -- Publish/index.html | head -200
```

### Step 2 — 審查 diff（吉寶軒設計系統規範）

逐一核查以下規則，標注 ✅ 通過 / ⚠️ 待改 / ❌ 違規：

**品牌 & 色彩**
- [ ] 只使用 `--gold / --ink / --paper / --seal-red` 及其 scale 變數；無硬編碼 hex（除 fallback 之外）
- [ ] 無 blue / green / purple / teal / aurora gradient 出現
- [ ] seal-red 僅用於 CTA、印章、進度條；不作大面積 fill

**字型**
- [ ] 所有中文字用 `--font-plaque / --font-display / --font-body` 三層之一
- [ ] Latin 數字（Lot #、年份）用 `--font-latin`（Cormorant Garamond）
- [ ] 無 `font-weight: bold` 套在 brush/kai 字型上
- [ ] SVG `<text>` 不用 `font-family="var(--font-display)"` presentation attr（用 CSS class）

**動畫**
- [ ] 只 animate `transform / opacity / filter`；禁 `width / height / top / left / margin`
- [ ] Exit 動畫速度 ≥ 2× 快於 Enter
- [ ] `@media (prefers-reduced-motion: reduce)` 覆蓋所有動畫
- [ ] `will-change` 在動畫結束後清除（animationend listener）

**佈局**
- [ ] 卡片維持單欄交錯排列（奇左偶右）；無 3-column grid
- [ ] 間距符合 8px grid
- [ ] 觸控目標 ≥ 44×44px

**文案語境**
- [ ] 繁體中文為主；無簡體字混入
- [ ] 無「商品 / 查看 / 日期 / 倉庫」等俗字（用設計系統詞彙替換）
- [ ] Empty state 用 `庫房目前空置` 不用 "No items found"

**結構**
- [ ] 無新增 npm / framework / build step 依賴
- [ ] Sheets 欄位對應不變（UUID, itemName, category, era, story...）

### Step 3 — 輸出 Review 報告

格式：

```
## 吉寶軒 Design Review — Round [N]
**Commit**: [hash] [message]
**審查時間**: [timestamp]

### ✅ 通過項目
...

### ⚠️ 建議改善（不阻擋上線）
...

### ❌ 違規項目（必須修正）
...

### 評分
| 維度 | 分數 |
|---|---|
| 品牌一致性 | /4 |
| 動畫品質 | /4 |
| 排版正確性 | /4 |
| 可及性 | /4 |
| 程式碼品質 | /4 |
| **總分** | **/20** |
```

### Step 4 — 生成下一輪 Claude Design Brief

根據 Review 結果，輸出一份可直接貼入 Claude Design 的 prompt：

```
## 📋 Round [N+1] — Claude Design Brief
（複製以下全文貼入 Claude Design）

---

你是吉寶軒（Jibao Xuan）的首席設計師，正在優化一個高奢中式古董展覽網站。
品牌定位等同 Sotheby's Asia、Christie's Hong Kong。

**設計系統規範**（必須嚴格遵守）：
- 色彩：sumi ink (#2c2c2c) / rice paper (#f7f4ed) / aged brass (#c49a45) / cinnabar seal (#8a2a2a)
- 字型三層：--font-plaque（Ma Shan Zheng）/ --font-display（標楷體）/ --font-body（LXGW WenKai TC）
- 動畫：只用 transform/opacity/filter；exit 2× 快於 enter
- 佈局：單欄交錯卡片，8px grid，無 3-column grid

**上一輪完成的工作**：
[從 Review 報告摘要]

**本輪任務**（優先序由高到低）：
1. [修正 ❌ 違規項目]
2. [改善 ⚠️ 建議項目]
3. [下一個功能目標]

**技術約束**：
- 純 HTML/CSS/vanilla JS，無 npm / framework
- 全部改動在 Publish/index.html 這一個檔案內完成
- Google Apps Script API 端點不可動

請直接輸出完整的 index.html。
---
```

### Step 5 — 儲存輸出

將 brief 寫入 `DESIGN_BRIEF_NEXT.md`（git-ignored，工作暫存）：

```bash
# Claude Code 會自動將 Step 4 的內容寫入這個檔案
```

並在終端顯示：

```
✅ Review 完成 → DESIGN_BRIEF_NEXT.md 已更新
   複製其中內容貼入 Claude Design 開始 Round [N+1]
```

---

## 快速觸發

```
/design-review
```

不需要任何參數。Claude 會自動讀取 git 狀態決定 diff 範圍。
