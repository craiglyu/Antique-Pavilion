---
id: skill_impeccable_audit
type: skill
layer: core
loaded_by: [Designer, Audit]
version: v0.1
schema_version: 1
last_updated: 2026-04-28
change_notes: "Phase B 新建 — Designer 載入用 5 維度評分（更詳盡版）"
---

# Impeccable Design Audit — 5 Dimensions Framework

**Source**: github.com/pbakaus/impeccable (Apache 2.0)
**Purpose**: Systematic quality assessment for Designer Agent. Generates scored report with P0-P3 severity ratings.
**Loaded by**: Designer Agent (when proposing changes), Audit Agent (pre-ship review)

> 跟 `/audit` slash command 互補：slash command 是 Craig 手動觸發的快速版，這份是 Agent 在輸出設計提案前必須先吸收的完整框架。

---

## Scoring (0-4 per dimension, 20 total)
| Score | Rating | Action |
|-------|--------|--------|
| 18-20 | Excellent | Ship-ready |
| 14-17 | Good | Polish pass acceptable |
| 10-13 | Acceptable | List P1/P2 fixes before ship |
| 6-9   | Poor | P0/P1 fixes required, no ship |
| 0-5   | Critical | Reject, redesign required |

---

## 5 Dimensions

### 1. Accessibility (0-4)
- WCAG AA contrast compliance（normal text ≥ 4.5:1，large text ≥ 3:1）
- ARIA labels on all interactive elements（按鈕、modal、表單）
- Keyboard navigation logical Tab order（Esc 關 modal、Enter 觸發 primary action）
- Alt text on all antique images（不是 generic「圖片」，要描述朝代+品類）
- Form usability：labels 在 input 之上不疊加，error messages 即時顯示

**P0 違規範例**：alt 是空字串 / contrast < 3:1 / Tab focus 跳到不可見元素

### 2. Performance (0-4)
- Image optimization：WebP 格式、lazy-load、預設尺寸限制（max-width: 1200px）
- CSS/JS 不阻擋首屏 render（critical CSS inline、非 critical defer）
- GAS API fetch：loading state 必須顯示（skeleton / spinner），error 必須有 fallback UI
- No layout shift（CLS < 0.1，圖片預留 aspect-ratio container）
- Background images 不在 scroll 時 re-fetch（用 background-attachment 或預載）

**P0 違規範例**：Lighthouse Performance < 70 / 圖片無壓縮 4MB+ / GAS 失敗時白屏

### 3. Responsive Design (0-4)
- All breakpoints tested：375 (iPhone SE)、768 (iPad)、1440 (desktop)
- Touch targets ≥ 44×44px（特別是手機 nav、close button）
- No overflow / horizontal scroll at any breakpoint
- Text readable at all sizes（min 16px body、line-height 1.5+）
- Modal / overlay 在小螢幕也能完整顯示（不超出 viewport）

**P0 違規範例**：375px 破版 / hamburger menu 無法點擊 / Footer 文字 < 12px

### 4. Theming (0-4)
- All colors via CSS variables，NO hardcoded hex
- Brand palette consistent：`--gold: #c49a45` / `--ink: #2c2c2c` / `--paper: #f7f4ed` / `--seal-red: #8a2a2a`
- Dark/light behavior（如有）— 用 `prefers-color-scheme`
- Font loading 不造成 FOUT（用 `font-display: swap` + 預載）
- Spacing rhythm 用 CSS variables（如 `--space-1: 8px`）

**P0 違規範例**：style 內出現 `color: #ffd700` 而非 `var(--gold)` / 字體 fallback 是 sans-serif 而非 LXGW WenKai TC

### 5. Anti-Patterns (0-4)
- NO generic 3-column equal-card layouts（用 asymmetric / masonry 替代）
- NO purple gradients、neon colors、oversaturated（飽和度限制 < 80%）
- NO placeholder content in production（沒有「藏品 001」「Lorem ipsum」）
- NO console errors / warnings
- NO unused CSS / JS（dead code）
- NO Inter / Roboto for premium contexts（必須用 LXGW WenKai TC / Ma Shan Zheng）
- NO 散戶廣告腔（「絕世逸品」「典藏級」這類詞禁用）
- NO 強迫滾動的 hero（high-fold 必須有實質內容）

**P0 違規範例**：頁面 console 噴 50 個 errors / Hero 圖佔 90vh 但無內容 / 用 Inter

---

## Severity Taxonomy

- **P0 BLOCKING**：違反 brand 核心或無障礙基本要求，**必須修才能 ship**
- **P1 MAJOR**：明顯影響體驗，建議 ship 前修
- **P2 MINOR**：細節品質，可下個 sprint 改
- **P3 POLISH**：微調，nice-to-have

---

## Output Format（Designer Agent 跑 audit 時用）

```
AUDIT REPORT — [target file/section]
Overall: XX/20 [Rating]

Dim 1 (Accessibility):    X/4
Dim 2 (Performance):      X/4
Dim 3 (Responsive):       X/4
Dim 4 (Theming):          X/4
Dim 5 (Anti-Patterns):    X/4

[P0 BLOCKING]
- [Issue] | [Fix recommendation with line reference]

[P1 MAJOR]
...

[P2 MINOR]
...

[POSITIVE FINDINGS]
- [What works well]

Recommended next: /polish, taste-skill check, ...
```

---

## When loading this skill, Designer Agent should

1. 先把這 5 維度當「審視鏡」過一遍當前 `Publish/index.html`
2. 在輸出設計提案時，每個提案附帶 5 維度自評分
3. 若提案會降低某維度分數，明確標記 trade-off

**Pre-Flight Checklist**（Designer 出稿前自查）：
- [ ] 5 維度都 ≥ 3/4？
- [ ] 任何 P0 都已標記 + 提供 fix？
- [ ] 跟 taste-skill.md 的 anti-AI-slop rules 對照過？
- [ ] 跟 emil-skill.md 的 motion 規範對照過（如涉及動畫）？
