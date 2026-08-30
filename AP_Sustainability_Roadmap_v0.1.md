---
id: ap_sustainability_roadmap_v0.1
type: project
title: AP 永續成長路徑 — V0.1 (Mirror Thor's Memory Infrastructure as Code)
created: 2026-04-28
last_updated: 2026-04-28
schema_version: 1
status: draft
parent_framework: Thor docs/memory_infrastructure_roadmap.md
---

# AP 永續成長路徑 — V0.1 草案

> **本文件對標 Thor 今天（2026-04-28）的 `memory_infrastructure_roadmap.md`**，把同樣的「永續性投資」概念套到 AP，並考慮 AP 未來會複製到精品選物 / 數位訂閱等其他電商專案。

---

## 0. 今天 Thor 做了什麼（永續方向 TL;DR）

| 元素 | 內容 |
|---|---|
| **Memory 重構** | V2.0 單檔 839 行 → V3.0 Tiered（140 行 MEMORY.md + sprint_history/ + diagnostics/ + 5 detail files） |
| **3 永續心態** | (1) Documentation is code — doc 改動跟 code 一樣走 PR gate (2) Lifecycle is design — 歸檔策略前置定義 (3) Index, never duplicate — 單一真理來源 + 指標 |
| **4 core automation** | `memory_lint.py` + pre-commit hook / `archive_rotate.py` + policy.yaml / Schema versioning（frontmatter）/ `memory/_org_shared/` 跨專案命名空間 |
| **Trigger-based defer** | usage telemetry / SQLite query / persona auto-gen / CHG_LOG partitioning — 不到 trigger 不做（避免 over-engineer） |
| **長期願景** | V0.1（now） → V0.2（Q3 2026） → V0.3（Q4） → V1.0（mid-2027 multi-engineer） |
| **核心 insight** | 對標 Notion / Confluence 撐 100+ 人 5 年；Thor 自家撐 1-2 人 6-12 月。**enterprise tooling 全缺**（schema lock、auto-archive、usage analytics、ACL、onboarding wikis） |

---

## 1. AP vs Thor 對標 Enterprise 的差距盤點

對照 Thor 截圖的 9 項 enterprise feature gap + 4 項軟體工程 benchmark：

### 1.1 知識管理基礎建設

| Feature | AP 現狀 | Thor V3.0 | Enterprise (Notion/Confluence) | AP 差距嚴重度 |
|---|---|---|---|---|
| **Hierarchical pages** | ✅ 有（Notion DBs + .md docs） | ✅ memory/ + docs/ tiered | ✅ Yes | 🟢 OK |
| **Cross-link 健全** | 🟡 Manual（.md 內 reference 部分有效） | 🟡 Manual | ✅ Auto-broken-link detection | 🔴 跟 Thor 同水準，缺 lint |
| **Search** | 🟡 Notion 內建 search 算 OK；本地 .md 需 grep | 🔴 grep only | ✅ Full-text + filter + tag | 🟡 比 Thor 好（有 Notion） |
| **Versioning** | 🔴 git history only | 🔴 git history only | ✅ Page-level diff + revert（Notion 有） | 🟡 Notion 部分有 |
| **Permissions** | 🔴 N/A（single user） | 🔴 N/A（single user） | ✅ ACL | 🔴 同 Thor |
| **Schema enforcement** | 🔴 None | 🔴 None | ✅ Database/template lock | 🔴 同 Thor，**且 AP 有 8 個 Notion DBs，schema 不鎖未來複製專案會崩** |
| **Lifecycle policy** | 🔴 None | 🔴 None（V0.1 要做 archive_rotate） | ✅ Auto-archive/retention | 🔴 同 Thor |
| **Usage analytics** | 🔴 None | 🔴 None | ✅ Page views/dwell time | 🔴 同 Thor |
| **Onboarding flow** | 🔴 None | 🔴 None | ✅ Onboarding wikis | 🔴 同 Thor |

### 1.2 軟體工程 benchmark

| Tool | AP 現狀 | Thor 現狀 | Enterprise target | AP 差距 |
|---|---|---|---|---|
| **Bazel/pants（dep graph）** | 🔴 無 | 🔴 無（要做 file dep graph） | ✅ Bazel | 🔴 同 Thor |
| **Sphinx（PR gate + cross-link validation）** | 🔴 無 | 🔴 無（V0.1 第 1 項要做 memory_lint） | ✅ Sphinx | 🔴 同 Thor |
| **OpenTelemetry（usage telemetry）** | 🔴 無 | 🔴 無（V0.1 deferred） | ✅ OTEL | 🔴 同 Thor |

### 1.3 AP 額外的維度（Thor 沒有的）

| 維度 | AP 現狀 | 永續目標 |
|---|---|---|
| **Bot 韌性**（Discord catchup） | 🟡 部分（鑑定 Bot 啟動會處理 backlog 但無 rate limit） | 🟢 完整 Catchup Protocol（仿 Thor V11） |
| **跨專案複製性**（AP → 精品選物 → 數位訂閱） | 🔴 藍圖有提，未抽 Core | 🟢 Core/Domain 切分、template repo |
| **Notion DB schema 演進**（8 個 DB） | 🔴 schema 寫死，DB 改動需手動同步 8 處 | 🟢 schema versioning + migration script |
| **Skill library 版本控管** | 🟡 8 個 skills 在 .claude/commands/，Notion 有 v0.1 baseline | 🟢 skills 加 schema_version + 對應 Notion DB 紀錄 |
| **Bot 程式碼測試** | 🔴 0 pytest, 0 lint, 0 CI | 🟢 pytest + ruff + pre-commit |

---

## 2. AP 永續挑戰 vs Thor 不同的地方

### Thor 的永續壓力 = 「**深度 + 時間**」
- 1-2 人，6-12 月內 memory.md 將膨脹
- 多年後 multi-engineer 接手時的 onboarding 成本
- Sprint history 無限增長

### AP 的永續壓力 = 「**廣度 + 複製**」
- 未來會複製到精品選物 / 數位訂閱
- 每個複製專案都要重寫 system prompt / Notion DB schema / .claude/commands skills
- **若 Core/Domain 沒切清楚，複製成本 = 從零開始**

### 結論：AP 要優先解決的是 Thor 還沒重點處理的問題

| 議題 | Thor 優先級 | AP 優先級 |
|---|---|---|
| Memory 規模膨脹 | 🔴 高 | 🟢 低（AP 文件量小） |
| Sprint history 自動歸檔 | 🔴 高 | 🟢 低（AP 不跑訓練 sprint） |
| **Core/Domain 切分為複製做準備** | 🟡 中（V11.8 才做） | 🔴 **高**（AP V0.1 必做） |
| **Notion DB schema 版本控管** | 🟢 低（用 .md） | 🔴 **高**（AP 用 8 個 Notion DB） |
| Bot 程式碼測試 | 🟡 中 | 🔴 高（AP 已 production） |
| Catchup Protocol | 🔴 高（V11.1） | 🔴 高（已遇 quota 爆 case） |

**AP 的 V0.1 不是 Thor 的 V0.1 翻譯，是「適配 AP 痛點的並行版本」。**

---

## 3. AP 永續 V0.1 — 3-month 路徑

### 3 永續心態（沿用 Thor）

1. **Documentation is code** — `.claude/commands/skills` + Notion DB schema 改動走 PR gate
2. **Lifecycle is design** — Notion DB 條目歸檔策略（哪些算 active、哪些 archive）前置定義
3. **Index, never duplicate** — Bot prompts、skill files、Notion DB schema 三層各有單一真理來源

### V0.1 scope（4 + 1 core 自動化，立即做）

#### Item 1 — `skill_lint.py`（mirror Thor's memory_lint）

**Purpose**: 驗證 .claude/commands/*.md 結構 + cross-reference 完整性。

**Implementation**:
- `scripts/skill_lint.py`（~200 LoC）
- 對 .claude/commands/ 所有 .md 跑：
  - frontmatter 必含 `schema_version: 1` + `loaded_by`（哪些 Persona 載入）
  - markdown links + backtick paths 解析驗證（避免「.claude/commands/impeccable-audit.md 不存在」這種 bug 重演）
  - Voice Layer 強制檢查（每個 skill 標明 Layer 1 / Layer 2 / Both）
- 模式：`--strict`（PR gate）/ `--warn`（dev）/ `--json`
- `.claude/hooks/pre_commit_skills.sh` 呼叫

**Anti-pattern prevented**: 我們今天就遇過這個 bug（Designer prompt 引用不存在的 `impeccable-audit.md`，沒有 lint 之前 silently fail）

#### Item 2 — `notion_schema.yaml` + `notion_schema_check.py`

**Purpose**: AP 8 個 Notion DBs 的 schema 鎖定 + 演進機制。未來複製到精品選物時，schema 變更可追蹤。

**Implementation**:
- `config/notion_schema.yaml` — 記錄 8 個 DB 的 properties / select options / relations
- `scripts/notion_schema_check.py` — 對比實際 Notion DB 跟 yaml，偵測漂移
- 任何 DB schema 變更要先更新 yaml + 對應 migration note

**Anti-pattern prevented**: AP 複製到精品選物時，新專案要建同樣 8 個 DB，沒 schema source 會永遠手動對比

#### Item 3 — `prompts_versioning.yaml`

**Purpose**: ap_org_bot.py 內的 prompts 跟 Notion Agent Prompts DB 同步。

**Implementation**:
- `config/prompts_versioning.yaml`
  ```yaml
  pm_prompt:
    current_version: v0.1
    notion_page_id: ...
    last_changed: 2026-04-28T07:30
    change_notes: ...
  marketing_prompt:
    current_version: v0.2
    notion_page_id: ...
    last_changed: 2026-04-28T08:15
    change_notes: 加 Voice Layers + scope routing
  ...
  ```
- ap_org_bot.py 啟動時讀 yaml，若 prompt 跟 yaml 紀錄版本不符，warn
- 每次 patch prompt → 更新 yaml + push 到 Notion

**Anti-pattern prevented**: Marketing prompt 已從 v0.1 升 v0.2，Notion DB 還寫 v0.1，未來不知道線上跑的是哪個版本

#### Item 4 — `ap_org_shared/` 命名空間（mirror Thor's `_org_shared`）

**Purpose**: 為「複製到其他電商專案」預留共用知識空間。

**Implementation**:
- `.claude/commands/_core/` — Core skills（跨專案共用，如 audit.md、polish.md、Voice Layers part of copywriting）
- `.claude/commands/_domain/ap/` — AP 專屬（taste-skill 古董調性、marketing-psychology 古董買家原型）
- 未來複製：fork 整個 `.claude/commands/`，重寫 `_domain/<new>/`，保持 `_core/` 不動

**Anti-pattern prevented**: 複製到精品選物時 8 個 skills 全部從零開始

#### Item 5 — `CHG_LOG.json` for AP（mirror Thor）

**Purpose**: 變更紀錄留存。每次 prompt patch / skill 改動 / DB schema 演進都寫一筆。

---

### Trigger-based deferred items

| Item | Trigger | Estimated when |
|---|---|---|
| `bot_telemetry.py`（記錄 prompt invocation count、平均 latency） | Bot 跑 ≥ 1 個月後問「哪個 Persona 被用最多」 | 1 month after V0.1 |
| `notion_dbs_query.py`（離線索引 8 個 DB） | Notion DB 條目 > 100 | 3-6 months（看 AP 真實使用量） |
| `replicate_template.py`（一鍵 fork AP → 精品選物） | 真的要啟動第二個電商專案時 | 自然 trigger |
| Bot pytest 套件 | 第一個 Bot bug 引起 production 問題 | 自然 trigger |

---

### Watchpoints（monthly review）

| Metric | Threshold | Action |
|---|---|---|
| `.claude/commands/` 檔案數 | > 15 | Refactor 抽 _core/ |
| `ap_org_bot.py` 行數 | > 1500 | 拆模組（agents/、handlers/） |
| Bot crash 次數 / 月 | > 3 | 補 pytest + error handling |
| Notion DB schema drift（vs yaml） | 任何 1 處 | 補 migration note |
| Marketing / Designer prompt 版本差距 | v0.x → v0.x+5 沒同步 Notion | 強制同步 |

---

### Testing strategy

`skill_lint.py` 跟 `notion_schema_check.py` 都加 pytest：
- `tests/test_skill_lint.py` — frontmatter 驗證、broken-link case
- `tests/test_notion_schema.py` — schema drift detection、migration test

目標：兩個 script ≥ 90% line coverage，加 GitHub Action 在 PR 跑。

---

### Migration plan（safety）

| Phase | Action | Backward compat |
|---|---|---|
| Day 1 | 部署 skill_lint `--warn` mode | 現有 skill files 缺 frontmatter 只 warn 不 fail |
| Day 1+1 | 把 8 個 skill 加 frontmatter | manual ~ 8 files |
| Day 1+3 | 切 `--strict`（PR gate active） | |
| Day 1+7 | notion_schema.yaml 建好 + first dry-run | nothing changed yet |
| Day 30 | 第一次跑 `bot_telemetry`（如有），review usage | |

---

### Success criteria

**1 週**：
- [ ] `skill_lint.py` 對所有 skill files exit 0
- [ ] 8 skill files 都有 `schema_version: 1` frontmatter
- [ ] `prompts_versioning.yaml` 紀錄當前 8 個 prompts 版本

**1 月**：
- [ ] `.claude/commands/` 已重組為 `_core/` + `_domain/ap/`
- [ ] notion_schema.yaml 完整覆蓋 8 個 DB
- [ ] Bot 至少跑過 1 次完整 lifecycle（idea → council → DP → 上線）

**3 月**：
- [ ] Bot pytest 套件雛型（覆蓋核心函式）
- [ ] 跑過第一次 schema_version 升級（v1 → v2）
- [ ] Replicate template 草稿（為下個電商專案做 dry-run）

---

## 4. 長期願景

**V0.2**（Q3 2026，Phase A 串 Notion 穩定後）：
- Bot telemetry 全面化（prompt invocation log）
- 第一次 prompt A/B test（v0.x vs v0.y）
- skill_lint 升級為 GitHub Action

**V0.3**（Q4 2026，啟動下個電商專案前）：
- Replicate template 真實 fork 一次（精品選物 dry-run）
- AP_Multi_Agent_ORG_Blueprint 升 v2.0（含複製 SOP）

**V1.0**（mid-2027，下個專案 onboard 後）：
- 跨專案共用 skills（`_org_shared/`）真實內容
- AP + 第二專案兩位以上 owners 共同維護
- Onboarding curriculum（給未來夥伴看）

---

## 5. 不需要 LINE ID 也能先做的（這個 session）

按優先級：

| # | 動作 | 投入 | 為何 |
|---|---|---|---|
| 1 | **Phase A 啟用**（NOTION_API_KEY 設定）| 5 min | Marketing v0.2 / Designer audit / Bot 鑑定 全部會自動寫進 Notion，永續資產化從今天開始 |
| 2 | **Auto-Dev 跑 DP-001 / DP-003 / DP-004**（不需 LINE ID） | 你貼 3 條訊息到 #ap-web-dev | Phase B Designer 提的 P0 至少清掉 3 個 |
| 3 | **更新 Marketing prompt v0.2 + copywriting v0.2 寫入 Notion Agent Prompts DB** | 我幫你寫，5 min | 開始建立 prompt 版本歷史（V0.1 step 3 的雛型）|
| 4 | **加 frontmatter 到 8 個 skill files**（V0.1 Item 1 prep） | 我幫你做，10 min | 為 skill_lint.py 鋪路 |
| 5 | **建 `config/prompts_versioning.yaml`**（V0.1 Item 3） | 我幫你寫，10 min | prompt 版本紀錄起點 |

只做 #1-2 就能讓 AP 大幅前進。剩下 #3-5 一週內找空檔做。

---

## 6. References

- **Thor 對標文件**：`Thor agent/Dreamer EVO/docs/memory_infrastructure_roadmap.md`
- **Thor V3.0 memory restructure**：`Thor agent/Dreamer EVO/memory/v8_sprint_map.md`
- **AP 現有藍圖**：`AP_Multi_Agent_ORG_Blueprint.md`（已有，待擴張永續層）
- **AP MCP 計畫**：`AP_MCP_Tools_Plan.md`
- **AP STARTUP**：`STARTUP.md`（V0.2 要補 V0.1 Item 4 段）

---

*本文件由 Cowork Claude 與 Craig 協作產出，基於 Thor 2026-04-28 memory_infrastructure_roadmap.md 對標完成。*
