---
id: ap_sustainability_roadmap_v0.2
type: project
title: AP 永續成長路徑 — V0.2 (Mirror Thor V11.1 Wave 2A+2B Daemon Layer)
created: 2026-04-28
last_updated: 2026-04-29
schema_version: 1
status: draft
parent_framework:
  - Thor docs/memory_infrastructure_roadmap.md (V0.1 對標基礎)
  - Thor memory/v11_sprint_map.md V11.1 Wave 2A+2B (V0.2 新增對標, 94/94 pytest GREEN @ 2026-04-28T07:30 UTC)
upstream_blueprint: AP_Multi_Agent_ORG_Blueprint_v1.1.md
---

# AP 永續成長路徑 — V0.2 草案

> **本文件 V0.2 在 V0.1 基礎上**，納入 Thor 2026-04-28 當日完成的 V11.1 Wave 2A+2B daemon layer（V0.1 撰寫時尚未完成）。同時把 V0.1 的 4+1 core 自動化擴充到 8 core，並加入「AP 領先 Thor 試水溫」三方向（auto-merge / reconciler / auto-rollback）。

---

## 0. 今天 Thor 做了什麼（永續方向 TL;DR）

| 元素 | 內容 |
|---|---|
| **Memory 重構** | V2.0 單檔 839 行 → V3.0 Tiered（140 行 MEMORY.md + sprint_history/ + diagnostics/ + 5 detail files） |
| **3 永續心態** | (1) Documentation is code — doc 改動跟 code 一樣走 PR gate (2) Lifecycle is design — 歸檔策略前置定義 (3) Index, never duplicate — 單一真理來源 + 指標 |
| **4 core automation** | `memory_lint.py` + pre-commit hook / `archive_rotate.py` + policy.yaml / Schema versioning（frontmatter）/ `memory/_org_shared/` 跨專案命名空間 |
| **6 daemon scripts (V0.2 新增, 對標 Thor V11.1 Wave 2A+2B)** | `council_runner.py` (9-state machine, 30 tests) + `catchup_protocol.py` (Watermark + 6 source types, 15 tests) + `auto_progression_runner.py` (gate/dry-run/veto/execute, 22 tests) + `audit_runner.py` (9 anti-pattern + BL Compliance score, 27 tests) + `discord_bot_v2.py` 7 Council slash commands + `orchestrator.py` V11.1 catchup hook integration — **全套 94/94 pytest GREEN in 2.10s @ 2026-04-28T07:30 UTC** |
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
| **Council 議事可審計（V0.2 新增）** | 🔴 None | ✅ Thor V11.1 9-state JSON-persisted | ✅ Confluence workflow | 🔴 嚴重，**AP 議題比 Thor 多（網站架構、新藏品上架、維運事件），更需要可審計 state 流** |

### 1.2 軟體工程 benchmark

| Tool | AP 現狀 | Thor 現狀 | Enterprise target | AP 差距 |
|---|---|---|---|---|
| **Bazel/pants（dep graph）** | 🔴 無 | 🔴 無（要做 file dep graph） | ✅ Bazel | 🔴 同 Thor |
| **Sphinx（PR gate + cross-link validation）** | 🔴 無 | 🔴 無（V0.1 第 1 項要做 memory_lint） | ✅ Sphinx | 🔴 同 Thor |
| **OpenTelemetry（usage telemetry）** | 🔴 無 | 🔴 無（V0.1 deferred） | ✅ OTEL | 🔴 同 Thor |
| **Anti-pattern grep auto-scan（V0.2 新增）** | 🔴 無 | ✅ `audit_runner.py` (Thor V11.1, 9 rules + BL Compliance score 0-4 + Documentation 0-4) | ✅ SonarQube / CodeRabbit | 🔴 嚴重，AP 缺品牌違規自動偵測 |
| **Auto-merge policy gate（V0.2 新增）** | 🔴 無 | 🔴 無（Thor 也未做，ML 訓練 ckpt 大不適合） | ✅ GitHub branch protection + Required checks | 🟡 **AP 可領先 Thor 試水溫**（vanilla HTML/CSS/JS 完美場域） |
| **Declarative state reconciliation（V0.2 新增）** | 🔴 無 | 🔴 無（Thor 也未做） | ✅ K8s Operators / Terraform | 🟡 **AP 可領先 Thor 試水溫**（8 Notion DB 完美場域） |
| **Sandbox + auto-rollback（V0.2 新增）** | 🔴 無 | 🔴 無（Thor 也未做，ckpt 回滾代價高） | ✅ Replit Agent / Devin pattern | 🟡 **AP 可領先 Thor 試水溫**（git tag auto-snap + branch reset） |

### 1.3 AP 額外的維度（Thor 沒有的）

| 維度 | AP 現狀 | 永續目標 |
|---|---|---|
| **Bot 韌性**（Discord catchup） | 🟡 部分（鑑定 Bot 啟動會處理 backlog 但無 rate limit） | 🟢 完整 Catchup Protocol（仿 Thor V11.1, **V0.2 升級為 immediate, 直接 fork**） |
| **跨專案複製性**（AP → 精品選物 → 數位訂閱） | 🔴 藍圖有提，未抽 Core | 🟢 Core/Domain 切分、template repo + **V0.2 加 declarative reconciler** |
| **Notion DB schema 演進**（8 個 DB） | 🔴 schema 寫死，DB 改動需手動同步 8 處 | 🟢 schema versioning + migration script + **V0.2 升級為 desired_state.yaml + reconciler** |
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
| **Council state machine 落地（V0.2 新增）** | 🔴 高（Thor 已完成 Wave 2B） | 🔴 **高**（V0.2 必做，fork Thor） |
| **Auto-merge policy gate（V0.2 新增）** | 🟡 低（ML 訓練不適合） | 🔴 **高**（**AP 領先 Thor 試水溫方向 #1**） |
| **Declarative reconciler（V0.2 新增）** | 🟡 低（用 .md） | 🔴 **高**（**AP 領先 Thor 試水溫方向 #2**） |
| **Auto-rollback safety net（V0.2 新增）** | 🟡 低（ckpt 回滾代價高） | 🔴 **高**（**AP 領先 Thor 試水溫方向 #3**） |

**AP 的 V0.2 不是 Thor 的 V0.1 翻譯，是「適配 AP 痛點的並行版本 + AP 反向領先 Thor 的三方向試點」。**

---

## 3. AP 永續 V0.2 — 3-month 路徑

### 3 永續心態（沿用 Thor + V0.2 補強）

1. **Documentation is code** — `.claude/commands/skills` + Notion DB schema 改動走 PR gate
2. **Lifecycle is design** — Notion DB 條目歸檔策略（哪些算 active、哪些 archive）前置定義
3. **Index, never duplicate** — Bot prompts、skill files、Notion DB schema 三層各有單一真理來源
4. **【V0.2 新增】Declarative over imperative** — 任何配置（Notion DB / Discord 頻道 / Agent registry）都用 `desired_state.yaml` 表達，runtime 由 reconciler 修正，禁止寫一次性 migration script

### V0.2 scope（**8 core 自動化** + 1 CHG_LOG，立即做）

#### V0.1 既有 Items（保持不變）

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

> **【V0.2 升級提示】** Item 2 在 V0.2 升級為 Item 9 `notion_reconciler.py`（K8s Operator pattern, declarative reconciliation）。本 Item 保留為 V0.1 過渡方案。

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

#### V0.2 新增 Items（對標 Thor V11.1 Wave 2A+2B daemon layer + AP 領先三方向）

#### Item 6 — `ap_council_runner.py`（fork Thor V11.1 Wave 2B council_runner.py, ~520 LoC）

**Purpose**: 議事 9-state machine + JSON persistence，把 AP_Blueprint v1.1 §3.6 spec 落地。

**Implementation**:
- 直接 fork Thor `scripts/council_runner.py`（30 tests GREEN）
- 改動：
  - dispatch target: `ap_agent_tasks.yaml`（非 Thor 的 agent_tasks.yaml）
  - state JSON 路徑: `memory/ap_council_state/<topic_id>.json`
  - 議題召集名單來源: `config/council_routing.yaml`（AP_Blueprint v1.1 §3.5 8 議題類型）
- 9 state: NEW → STRUCTURED → PHASE1_INDEPENDENT → PHASE2_DEBATE → PHASE3_INTEGRATION → AWAITING_SIGNOFF → {SIGNED_OFF | REJECTED | REOPENED}
- Idempotency contract（同一 topic_id 同一 transition 不重複扣 Gemini 配額）

**估算**: ~520 LoC + 30 tests, wallclock ~1 day

**Anti-pattern prevented**: V0.1 議事流程依賴 Discord thread 即時 message，Bot crash 議題狀態全失。State machine + JSON persistence 解決。

#### Item 7 — `ap_catchup_protocol.py` + `memory/ap_catchup/_schema.json`（fork Thor V11.1 Wave 2A）

**Purpose**: Bot 韌性。Discord outage / Gemini quota burst / Bot 重啟後自動 catch up，不漏單也不重複扣配額。

> V0.1 §3 把這項列為 deferred「Bot pytest 套件 — 第一個 Bot bug 引起 production 問題」的關聯。**V0.2 升級為 immediate**（直接 fork Thor，無重新設計成本）。

**Implementation**:
- 直接 fork Thor `scripts/catchup_protocol.py`（15 tests GREEN）
- 6 source types → AP 改為 5：
  1. Discord messages (last_processed_message_id)
  2. Gemini API calls (last_request_timestamp)
  3. Notion DB writes (last_page_id)
  4. Council state (last_council_transition_timestamp)
  5. Bot heartbeat (last_heartbeat)
- Watermark schema: `memory/ap_catchup/_schema.json`
- Cold-restart hook 在 `ap_org_bot.py` 啟動時呼叫

**估算**: ~300 LoC + 15 tests, wallclock ~半 day

**Anti-pattern prevented**: V0.1 §1.3 標紅「Bot 韌性 🟡 部分」— 已遇過 quota 爆 case 但無系統處理。

#### Item 8 — `ap_audit_runner.py`（fork Thor V11.1 Wave 2B audit_runner.py, ~500 LoC）

**Purpose**: 自動偵測品牌違規 + Lighthouse 閾值 + Compliance 聲明，作為 §5.4 Auto-merge Policy Gate 的 CI gate。

**Implementation**:
- 直接 fork Thor `scripts/audit_runner.py`（27 tests GREEN）
- 9 anti-pattern 改為 AP 品牌規則：
  1. **AP-1**: Editor 文章禁用詞掃描（「絕世」「典藏級」「天下無雙」等廣告腔，AP_Blueprint §2.8 列出）
  2. **AP-2**: 形容詞堆疊偵測（每段 > 2 個形容詞 → flag）
  3. **AP-3**: Lighthouse 4 象限分數 < 90 → flag
  4. **AP-4**: Curator 鑑定信心度 < 0.8 未標「待覆核」→ flag
  5. **AP-5**: Compliance 聲明缺失（鑑定結果未標「僅供參考、非鑑定書」）→ flag
  6. **AP-6**: Schema.org 標記缺失（新頁面未含 CollectionPage / Article）→ flag
  7. **AP-7**: 圖片 alt text 缺失（無障礙 AA 違規）→ flag
  8. **AP-8**: GAS 部署無版本標籤 → flag
  9. **AP-9**: Notion DB schema drift（vs `notion_desired_state.yaml`）→ flag
- Score 0-4: 5 維度（Brand Tone / Performance / Compliance / Accessibility / Schema）
- 模式：`--strict`（PR gate）/ `--warn`（dev）/ `--json`（CI）

**估算**: ~500 LoC + 27 tests, wallclock ~1 day

**Anti-pattern prevented**: V0.1 §3 完全沒有自動 brand QA，全靠 Craig 人工 review，scaling bottleneck。

#### Item 9 — `notion_reconciler.py`（V0.2 升級 V0.1 Item 2，K8s Operator pattern）

**Purpose**: AP 領先 Thor 試水溫方向 #2 — Declarative reconciliation。把 V0.1 Item 2 的 "check only" 升級為 "check + reconcile"。

**Implementation**:
- `config/notion_desired_state.yaml`（升級自 V0.1 `notion_schema.yaml`）
  - 8 DB 完整 schema：properties / select options / relations / sort / view filters
- `scripts/notion_reconciler.py`（~400 LoC）：
  1. 讀 yaml desired state
  2. 讀 Notion API actual state
  3. Diff
  4. **drift mode**（預設）: 印 diff，發 Council 議題請 Craig 簽核（透過 ap_council_runner Item 6）
  5. **enforce mode**（dev/staging only）: 自動 reconcile
- 跨專案 fork: 改 yaml → `--enforce` → 自動建新專案 8 個 DB
- 配 `tests/test_notion_reconciler.py`（estimated 20 tests）

**估算**: ~400 LoC + 20 tests + 1 yaml 文件, wallclock ~1.5 day

**Anti-pattern prevented**: V0.1 schema_check.py 只 check 不修，schema 漂移每次手動修 N 個 DB。Reconciler 把 N 次手動 → 0 次。

---

### Trigger-based deferred items

| Item | Trigger | Estimated when |
|---|---|---|
| `bot_telemetry.py`（記錄 prompt invocation count、平均 latency） | Bot 跑 ≥ 1 個月後問「哪個 Persona 被用最多」 | 1 month after V0.1 |
| `notion_dbs_query.py`（離線索引 8 個 DB） | Notion DB 條目 > 100 | 3-6 months（看 AP 真實使用量） |
| `replicate_template.py`（一鍵 fork AP → 精品選物） | 真的要啟動第二個電商專案時 | 自然 trigger |
| Bot pytest 套件 | 第一個 Bot bug 引起 production 問題 | 自然 trigger |
| **【V0.2 新增】`ap_auto_progression_runner.py`**（Tier 2 議題自動 merge, fork Thor V11.1 Wave 2A） | GitHub Branch Protection 設定完成 + 三 gate label CI 跑通 | Sprint 2（V0.2 Item 8 audit_runner ✅ 後） |
| **【V0.2 新增】`git tag auto-snap` rollback hook**（AP 領先 Thor 試水溫方向 #3） | 第一次 Auto-Dev 引發 production bug | 自然 trigger |
| **【V0.2 新增】`discord_reconciler.py` + `agent_registry_reconciler.py`**（K8s Operator pattern 補完） | Item 9 notion_reconciler 跑穩 1 個月 | Q3 2026 |

---

### Watchpoints（monthly review）

| Metric | Threshold | Action |
|---|---|---|
| `.claude/commands/` 檔案數 | > 15 | Refactor 抽 _core/ |
| `ap_org_bot.py` 行數 | > 1500 | 拆模組（agents/、handlers/） |
| Bot crash 次數 / 月 | > 3 | 補 pytest + error handling |
| Notion DB schema drift（vs yaml） | 任何 1 處 | 補 migration note，**V0.2 升級**：notion_reconciler 自動發 Council 議題 |
| Marketing / Designer prompt 版本差距 | v0.x → v0.x+5 沒同步 Notion | 強制同步 |
| **【V0.2 新增】Council 議題平均週期** | 簽核 > 24h（普通議題）/ > 72h（跨日議題） | Feedback PM 拋 retrospective 議題 |
| **【V0.2 新增】Auto-merge Tier 2 PR 駁回率** | > 15% | 收緊 Tier 2 範圍（移回 Tier 1）|
| **【V0.2 新增】Auto-rollback 觸發次數** | 同一 Agent 連續 3 次 | 暫停該 Agent + 升 Tier 1 議事 |

---

### Testing strategy

`skill_lint.py` 跟 `notion_schema_check.py` 都加 pytest：
- `tests/test_skill_lint.py` — frontmatter 驗證、broken-link case
- `tests/test_notion_schema.py` — schema drift detection、migration test

**【V0.2 新增 testing】** Item 6/7/8/9 直接 fork Thor 對應 test 檔案：
- `tests/test_ap_council_runner.py` ← Thor `tests/test_council_runner.py` (30 tests)
- `tests/test_ap_catchup_protocol.py` ← Thor `tests/test_catchup_protocol.py` (15 tests)
- `tests/test_ap_audit_runner.py` ← Thor `tests/test_audit_runner.py` (27 tests)
- `tests/test_notion_reconciler.py` ← 新寫 (estimated 20 tests, AP 領先項目)

目標：所有 script ≥ 90% line coverage，加 GitHub Action 在 PR 跑。

---

### Migration plan（safety）

| Phase | Action | Backward compat |
|---|---|---|
| Day 1 | 部署 skill_lint `--warn` mode | 現有 skill files 缺 frontmatter 只 warn 不 fail |
| Day 1+1 | 把 8 個 skill 加 frontmatter | manual ~ 8 files |
| Day 1+3 | 切 `--strict`（PR gate active） | |
| Day 1+7 | notion_schema.yaml 建好 + first dry-run | nothing changed yet |
| Day 30 | 第一次跑 `bot_telemetry`（如有），review usage | |
| **【V0.2 新增】Day 30+** | Item 6 council_runner 部署 + 第一次真實 Council 議事 | 平行執行不影響舊 Bot 流程 |
| **【V0.2 新增】Day 45** | Item 7 catchup_protocol 部署 + 模擬 Discord outage 測試 | 模擬時 Bot 整個 stop 5 min, 驗證 catchup 正確 |
| **【V0.2 新增】Day 60** | Item 8 audit_runner 部署 + warn mode | warn mode 跑 1 週才切 strict |
| **【V0.2 新增】Day 75** | Item 9 notion_reconciler drift mode 部署 | drift mode 不自動修改任何 DB |
| **【V0.2 新增】Day 90** | Auto-merge Policy Gate 啟動（GitHub Branch Protection） | 三 gate label 全亮才 merge，否則手動 |

---

### Success criteria

**1 週**（V0.1 既有）：
- [ ] `skill_lint.py` 對所有 skill files exit 0
- [ ] 8 skill files 都有 `schema_version: 1` frontmatter
- [ ] `prompts_versioning.yaml` 紀錄當前 8 個 prompts 版本

**1 月**（V0.1 既有）：
- [ ] `.claude/commands/` 已重組為 `_core/` + `_domain/ap/`
- [ ] notion_schema.yaml 完整覆蓋 8 個 DB
- [ ] Bot 至少跑過 1 次完整 lifecycle（idea → council → DP → 上線）

**3 月**（V0.1 + V0.2 合併）：
- [ ] Bot pytest 套件雛型（覆蓋核心函式）
- [ ] 跑過第一次 schema_version 升級（v1 → v2）
- [ ] Replicate template 草稿（為下個電商專案做 dry-run）
- [ ] **【V0.2 新增】** Item 6 ap_council_runner 全 30 tests GREEN
- [ ] **【V0.2 新增】** Item 7 ap_catchup_protocol 全 15 tests GREEN，至少 1 次模擬 outage 通過
- [ ] **【V0.2 新增】** Item 8 ap_audit_runner 全 27 tests GREEN，9 anti-pattern 對 AP 內容 0 false positive
- [ ] **【V0.2 新增】** Item 9 notion_reconciler 全 20 tests GREEN，drift mode 跑 1 週 0 誤判
- [ ] **【V0.2 新增】** 第一次真實 multi-session Council 議事完成（Phase 1 → Craig 簽核 → dispatch）
- [ ] **【V0.2 新增】** 第一個 Tier 2 Auto-merge PR 通過 + Craig 事後駁回 = 0

---

## 4. 長期願景

**V0.2**（已交付，2026-04-29）：
- 對標 Thor V11.1 Wave 2A+2B daemon layer
- 新增 Item 6/7/8/9 共 4 個 daemon scripts（fork Thor + AP 化）
- 啟動 AP 領先 Thor 試水溫三方向（auto-merge / reconciler / auto-rollback）
- Bot telemetry 全面化（prompt invocation log）
- 第一次 prompt A/B test（v0.x vs v0.y）
- skill_lint 升級為 GitHub Action

**V0.3**（Q4 2026，啟動下個電商專案前）：
- Replicate template 真實 fork 一次（精品選物 dry-run）
- AP_Multi_Agent_ORG_Blueprint 升 v2.0（含複製 SOP）
- **【V0.2 新增 cross-pollinate 機制】** AP 試成的 auto-merge / reconciler / auto-rollback 三方向，回頭 PR 給 Thor V11.4+ 採用，反向回饋 Thor 擴充框架
- AP 第一個跑通 Auto-merge policy gate，產出案例研究文件，給其他 Side Project 借鏡

**V1.0**（mid-2027，下個專案 onboard 後）：
- 跨專案共用 skills（`_org_shared/`）真實內容
- AP + 第二專案兩位以上 owners 共同維護
- Onboarding curriculum（給未來夥伴看）
- **【V0.2 新增】** Cross-project framework registry：AP / 精品選物 / 數位訂閱 三專案共用一份 `org_framework_core` repo，各自只維護 `domain/<project>/` 子目錄
- **【V0.2 新增】** Cross-pollinate cadence：每季 review AP / Thor / 其他專案各自試成的新模式，整合為 Core 升版

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
| 6 | **【V0.2 新增】fork Thor `scripts/council_runner.py` + 30 tests → `ap_council_runner.py`** | 我幫你做，30 min | V0.2 Item 6 的最小可執行起點 — fork + 改 dispatch path 即可，pytest 直接 GREEN |

只做 #1-2 就能讓 AP 大幅前進。剩下 #3-6 一週內找空檔做。**#6 是 V0.2 daemon layer 的入口**，跑通後 Item 7/8/9 fork pattern 一致，會非常順。

---

## 6. References

- **Thor V0.1 對標文件**：`Thor agent/Dreamer EVO/docs/memory_infrastructure_roadmap.md`
- **Thor V3.0 memory restructure**：`Thor agent/Dreamer EVO/memory/v8_sprint_map.md`
- **【V0.2 新增】Thor V11.1 Wave 2A+2B daemon layer**：`Thor agent/Dreamer EVO/memory/v11_sprint_map.md` §1 Compass + §3 DoD（94/94 pytest GREEN @ 2026-04-28T07:30 UTC）
- **【V0.2 新增】Thor V11.1 council_runner 參考**：`Thor agent/Dreamer EVO/scripts/council_runner.py`（9-state machine spec source）
- **【V0.2 新增】Thor V11.1 audit_runner 參考**：`Thor agent/Dreamer EVO/scripts/audit_runner.py`（9 anti-pattern + scoring spec source）
- **AP 現有藍圖**：`AP_Multi_Agent_ORG_Blueprint.md` v1.0
- **【V0.2 新增】AP 升版藍圖**：`AP_Multi_Agent_ORG_Blueprint_v1.1.md`（同期交付，含 §3.6 state machine / §5.4 auto-merge / §6.4 reconciler / §8.4 daemon layer / §9.3 auto-rollback / §10 第四五六順位）
- **AP MCP 計畫**：`AP_MCP_Tools_Plan.md`
- **AP STARTUP**：`STARTUP.md`（V0.2 要補 V0.1 Item 4 段 + V0.2 Item 6/7/8/9 daemon 啟動順序）

---

## 7. V0.1 → V0.2 Diff Summary

**Frontmatter**:
- `id`: v0.1 → v0.2
- `title`: 加 "Mirror Thor V11.1 Wave 2A+2B Daemon Layer"
- `last_updated`: 2026-04-28 → 2026-04-29
- `parent_framework`: 加 Thor V11.1 sprint map reference
- `upstream_blueprint`: NEW，pin AP_Blueprint_v1.1 同期交付

**§0 today TL;DR**: 加 row "6 daemon scripts (V0.2 新增)"

**§1.1 知識管理**: 加 row "Council 議事可審計"

**§1.2 軟工 benchmark**: 加 4 rows
- Anti-pattern grep auto-scan
- Auto-merge policy gate（**AP 領先 Thor 方向 #1**）
- Declarative state reconciliation（**AP 領先 Thor 方向 #2**）
- Sandbox + auto-rollback（**AP 領先 Thor 方向 #3**）

**§2 結論**: 加 4 rows 對照 Thor 優先級 vs AP 優先級

**§3 V0.2 scope**: 4+1 → 8+1
- 新增 Item 6 `ap_council_runner.py`
- 新增 Item 7 `ap_catchup_protocol.py`
- 新增 Item 8 `ap_audit_runner.py`
- 新增 Item 9 `notion_reconciler.py`（升級 V0.1 Item 2）

**§3 trigger-based deferred**: 加 3 items
- `ap_auto_progression_runner.py`
- `git tag auto-snap` rollback hook
- `discord_reconciler.py` + `agent_registry_reconciler.py`

**§3 Watchpoints**: 加 3 metrics
- Council 議題平均週期
- Auto-merge Tier 2 PR 駁回率
- Auto-rollback 觸發次數

**§3 Migration plan**: 加 5 phases (Day 30/45/60/75/90)

**§3 Success criteria 3 月**: 加 6 V0.2 specific items

**§4 V0.2 段**: 從原 V0.2 願景 → 已交付狀態 + 加 cross-pollinate 機制

**§4 V0.3 段**: 加 cross-pollinate / 案例研究輸出

**§4 V1.0 段**: 加 Cross-project framework registry / Cross-pollinate cadence

**§5 立即可做**: 加 #6 fork Thor council_runner

**§6 References**: 加 4 entries (Thor V11.1 sprint map / Thor council_runner / Thor audit_runner / AP_Blueprint_v1.1)

**§7 (本節)**: NEW，diff summary 便於 review

---

*本文件 V0.2 由 Cowork Claude 與 Craig 協作產出，基於 Thor 2026-04-28 V11.1 Wave 2A+2B daemon layer 完成 (94/94 pytest GREEN) 對標升版。下一步：Claude Code 接手執行 Item 6/7/8/9 fork + AP 化 + 90 天 migration plan。*
