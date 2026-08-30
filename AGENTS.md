# AGENTS.md — Antique Pavilion (吉寶軒) Project Reference

> **這份檔案是本專案唯一的規則來源。** `CLAUDE.md` 只是指向這裡的指標，不含內容。
> 任何 agent（Claude / Codex / GPT / Grok / 未來的任何一個）都以本檔為準。

> Single source of truth for technical constraints, architecture, and quick references that all
> agents (PM, Designer, Dev, Marketing, Curator, Auto-Dev, GAS-Dev) must respect.
>
> If you are an agent: **read this file first**. If something is documented here and your
> instinct says otherwise, the file wins — flag the conflict back to Craig instead of
> overriding silently.

---

## 1. Project mission

吉寶軒 (Jibao Xuan / "Antique Pavilion") is a **digital showcase site** for Chinese antiques —
**not an e-commerce site**. Primary conversion goal is "**funnel visitors to the physical
gallery**" (booking, LINE, Google Maps), not online checkout.

Buyer profile: high-net-worth, decision cycle in months, signal sensitivity to provenance
and craftsmanship. Aesthetic reference points: Sotheby's Asia, Christie's Hong Kong,
中國嘉德 (China Guardian), 保利拍賣, 故宮 (National Palace Museum).

---

## 2. Technical stack — DO NOT change without Tier 1 Council sign-off

| Layer | Tech | Why |
|---|---|---|
| Frontend | **Pure HTML / CSS / vanilla JS** — NO React/Vue/Tailwind/etc. | GitHub Pages compatibility, simplicity, longevity |
| Backend | **Google Apps Script (GAS) v9** | Runs free under Craig's Google account, no infra cost |
| Storage | Google Sheets (catalog) + Google Drive (images) | Same — free, durable |
| AI judgment | **Gemini 2.5 Flash** via GAS | $30/month hard cap |
| Discord I/O | **Python bot in WSL2** (`scripts/ap_org_bot.py`) | GAS IP is blocked by Discord (error 40333) |
| Knowledge base | **Notion (8 DBs)**, opt-in via `NOTION_API_KEY` | Long-form, structured, queryable |
| Skills | `.claude/commands/*.md` (9 skills) | Plain markdown — readable by ANY agent, not just Claude |

**Hard constraints**:
- No JS framework / npm packages / build step
- No Sheets column changes without DD-XXX (see §4)
- No prompt text in `.py` files — all prompts live in `scripts/ap_org_bot/prompts/<layer>/<agent>.md`
- No Discord bot may directly call Gemini API — that goes through GAS (so Gemini billing is
  centralized under one Google account)

---

## 3. Sheets column structure — V1 frozen

Any column add/remove/rename must update **all three places** synchronously:
`writeToSheet()` (GAS) / `doGet()` (GAS) / frontend `fetch()` parser (`Publish/index.html`).

| Col # | Field | GAS key (JSON) |
|---|---|---|
| 0 | UUID | — |
| 1 | 入庫時間 | — |
| 2 | 用戶描述 | `userCaption` |
| 3 | 品名 | `itemName` |
| 4 | 分類 | `category` |
| 5 | 年代 | `era` |
| 6 | 故事 | `story` |
| 7 | 拍賣參考品 | `refItem` |
| 8 | 參考價格 | `refPrice` |
| 9 | Drive URL | `imageUrl` |
| 10 | 標籤 | `tags` |
| 11 | 狀態 | `status` |
| 12 | 展示建議 | `displayRecommendation` |

**Pending DD approval (NOT yet enabled)**: `condition` (col 13), `provenance` (col 14).
Code is staged in `analyzeWithGemini()` but commented out — see
`memory/Antique_GAS_v9_Discord.md`.

**v9.1 added field** (already in schema, not yet wired to frontend):
`highlightQuote` — 16-28 字金句 used in Discord embed and (future) card overlay.

---

## 4. era enum — DO NOT extend silently

Gemini's `response_schema` enforces these 9 values; the frontend filter ALSO assumes them.
Extending without updating both = filter UI breaks for unrecognised eras.

```
史前與高古 | 唐宋元(含之前) | 明朝 | 清朝 | 民國 | 近現代 | 外國骨董 | 時代不詳 | 其他
```

The Curator agent (`scripts/ap_org_bot/agents/_domain/ap/curator.py`) uses this exact set
as its allowlist. Any era outside this set is flagged `衝突` (conflict, not auto-promoted).

---

## 5. Sign-off / approval gates — when does Craig HAVE to weigh in?

Three tiers from `config/signoff_tiers.yaml`:

### Tier 1 — Craig only (must sign off)
- Site architecture changes (new pages, IA reshuffles, Hero rewrites)
- Brand direction (logo, color palette, type system)
- Public-facing content (homepage, brand narrative)
- New feature launches
- Any explicit claim about authentication ("這是真品" / 鑑定服務 wording)
- When agents disagree and PM cannot reconcile

### Tier 2 — PM-authorised, Craig sees digest
- SEO meta / schema tweaks
- Existing content copy refinement
- Knowledge base entry add/edit
- Visual micro-tweaks (no IA change)
- Daily social posts (within already-approved tone + theme)

Tier 2 is auto-merge-eligible **once GitHub branch protection ships in Sprint 5** — three
required labels (`lighthouse-passed` / `brand-tone-passed` / `compliance-passed`) plus
`tier-2-or-below`.

### Tier 3 — Agent autonomous (Craig sees nothing unless alerted)
- SRE routine health checks + alerts
- Curator routine quality reviews
- Librarian KB indexing
- Backend routine quota monitoring
- Research scheduled scans

**Asymmetric risk principle**: bias toward Tier 2 in early sprints. Move things to Tier 3
only after a week of zero post-hoc Craig vetoes.

---

## 6. Hard cost ceilings

| Provider | Monthly hard cap | Enforcement |
|---|---|---|
| Gemini API | **USD 30** | `infra/budget_gate.py` SQLite ledger; raise BudgetExceeded |
| Opus API (design rulings) | **USD 15** | Same — must require Craig confirmation per call |
| Notion API | n/a (free tier) | Throttle abuse only |
| Anthropic CLI (Claude MAX/Pro) | n/a (subscription) | Throttle runaways |

`/usage-status` shows live ledger. `infra/budget_gate.MONTHLY_CAPS` is the source of truth.

---

## 7. Repository layout (post Sprint 0 refactor)

```
Antique Digital Pavilion/
├── AGENTS.md                           ← THIS FILE
├── AP_Multi_Agent_ORG_Blueprint_v1.1.md  ← architecture vision
├── AP_Sustainability_Roadmap_v0.2.md     ← 90-day execution plan
├── CHG_LOG.json                          ← append-only change log（§12 完工協議強制寫入）
├── index.html                            ← local dev gallery
├── Publish/index.html                    ← what GitHub Pages serves
├── config/
│   ├── channels.yaml                     ← Discord channel registry (id → agent)
│   ├── agents.yaml                       ← active agents list
│   ├── council_routing.yaml              ← topic type → convened agents
│   ├── signoff_tiers.yaml                ← Tier 1/2/3 mapping
│   ├── notion_desired_state.yaml         ← 8 DB schema SoT (Sprint 3 enforces)
│   ├── prompts_versioning.yaml           ← prompt version metadata
│   └── migrations/                       ← future schema migrations (Sprint 4)
├── scripts/
│   ├── ap_org_bot.py                     ← thin shim → ap_org_bot.main:main
│   ├── ap_org_bot/                       ← ★ refactored package (42 modules)
│   │   ├── infra/                        # paths, env, ssl, claude_cli, budget_gate, notion
│   │   ├── discord_io/                   # split, embeds, views, opus_parse
│   │   ├── prompts/                      # 8 prompts as .md (NOT in .py)
│   │   ├── agents/                       # base + registry + 8 agent classes
│   │   ├── handlers/                     # message dispatcher, scheduler, slash, feedback
│   │   ├── council/                      # 9-state machine (3-state pilot in Sprint 1)
│   │   └── main.py                       # 227-line entry — wires all dependencies
│   ├── ap_org_bot_legacy.py              ← 1288-line preserved monolith (rollback target)
│   ├── ap_council_runner.py              ← Council CLI: list/new/show/advance/signoff
│   ├── ap_curator_runner.py              ← Curator CLI: classify/review (Sprint 1)
│   └── notion_writer.py                  ← Phase A — 7 create_xxx() to Notion DBs
├── memory/
│   ├── feedback_state.json               ← gitignored
│   ├── budget_state.sqlite               ← gitignored
│   ├── ap_council_state/                 ← gitignored except _schema.json
│   └── opus_inbox/, opus_rulings/        ← gitignored
├── tests/                                ← 292+ tests, run via `pytest -q`
│   └── test_change_log_contract.py       ← §12 完工協議的機器檢查
└── ap_discord_bot.py                     ← separate bot for Gemini authentication pipeline
```

---

## 8. Quick references — common operations

### Add a new agent (Phase 1+ from blueprint v1.1)

1. Drop `scripts/ap_org_bot/prompts/_domain/ap/<name>.md` (with YAML frontmatter)
2. Drop `scripts/ap_org_bot/agents/_domain/ap/<name>.py` (subclass HeadlessAgent or standalone class)
3. Add entry under `agents:` in `config/agents.yaml` (`active: true`)
4. Bind to a Discord channel in `config/channels.yaml` (or leave channel-less if button-triggered)
5. Register in `scripts/ap_org_bot/main.py` (one line: `registry.register_instance(...)`)
6. Add tests under `tests/test_agents_<name>.py`

**No edits to `on_message` or any handler.** That's the win.

### Change an existing prompt

1. Edit `scripts/ap_org_bot/prompts/<layer>/<agent>.md` body
2. Bump `prompt_version` in the frontmatter
3. Update `config/prompts_versioning.yaml` (`current_version`, `last_changed`, `change_notes`)
4. Restart bot: `python3 -u scripts/ap_org_bot.py`

**No `.py` edit, no full file backup.**

### Run tests

```bash
cd "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion"
python3 -m pytest tests/ -q                   # all tests
python3 -m pytest tests/test_council.py -v    # one file
python3 -m pytest tests/ -k curator           # match keyword
```

### Boot the bot (from WSL2)

```bash
cd "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion"
python3 -u scripts/ap_org_bot.py
```

Expected log within 30 seconds: `active agents:` (8 keys) → `ORG Bot ready as AP_org_bot#3797`
→ `Synced 4 slash commands.` → `[scheduler] poll @ 11:00 / 20:00`.

### Run a Council topic from CLI

```bash
python3 scripts/ap_council_runner.py list                            # all active topics
python3 scripts/ap_council_runner.py new "<議題>" --type 視覺微調     # new topic
python3 scripts/ap_council_runner.py show <topic_id>                 # full JSON
python3 scripts/ap_council_runner.py signoff <topic_id> approve      # accept
```

### Inspect API budget

```bash
# In Discord:
/usage-status

# Or programmatically:
python3 -c "import sys; sys.path.insert(0, 'scripts'); \
            from ap_org_bot.infra.budget_gate import usage_summary; \
            import json; print(json.dumps(usage_summary(), indent=2))"
```

### Apply Auth Log DB schema migration (Sprint 2 follow-up — Craig action)

Prereq: `NOTION_API_KEY` 已在 `.env.antique`（`ntn_26310350…`），`NOTION_AUTH_LOG_DB` = `d20ed582-…`。

```bash
cd "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion"
source .env.antique       # 或 export $(grep -v '^#' .env.antique | xargs)
python3 scripts/ap_authlog_schema_migrate.py apply
```

這一步把 `era` (select 9-enum) + `category` (select 6 options) + `isValid` (checkbox) 加到
Notion Auth Log DB，讓 Curator `pull-pending` + `--apply` 可以 write-back 完整 verdict。

### Rollback the Sprint 0 refactor (emergency)

If the refactored bot misbehaves within the first 14 days:

```bash
mv scripts/ap_org_bot.py scripts/ap_org_bot.py.shim
mv scripts/ap_org_bot_legacy.py scripts/ap_org_bot.py
python3 -u scripts/ap_org_bot.py    # legacy 1288-LoC bot back online
```

Detailed rollback rationale: `scripts/ap_org_bot/MIGRATION.md`.

---

## 9. Sprint timeline (vs Roadmap v0.2)

| Sprint | Status | Scope |
|---|---|---|
| **0** | ✅ done (2026-04-30) | Strangler-fig refactor 1288→42 modules + budget_gate + Council 3-state pilot + 51 tests + 4 optimisation lines (拆檔/budget/state-machine/migrations) |
| **1** | ✅ done (2026-04-30) | First real Council session + Curator agent + AGENTS.md + Discord reaction handler + 109 tests |
| **2** | ✅ done (2026-04-30) | Curator --apply / Auth Log schema migration spec / catchup_protocol skeleton / audit_runner 4-rule MVP (AP-1/5/6/7) / Council 9-state extension / notion_reconciler drift mode — 183 tests, 6.87s |
| **3** | ✅ done (2026-05-02) | Council 9-state daemon (`council/daemon.py`) + catchup active replay + Gemini quota reconcile + audit AP-2/3/4/8 (8-rule full set) + notion_reconciler enforce mode — 253 tests, 3.60s |
| **4** | ✅ done (2026-05-03) | CouncilDaemon → 11:00/20:00 scheduler + daemon-poll CLI + RealDiscordFetcher + Emil UI audit (10 items) + visual regression baseline (10 screenshots) + MigrationsRunner (Notion drift audit on startup, opt-in auto-apply via `AP_MIGRATIONS_AUTO_APPLY=1`) + BudgetGovernor (USD ledger + daily/weekly/monthly caps + Council-token attribution) — 284 passed + 2 skipped (apscheduler-only) |
| **5** | ⬜ pending | GitHub branch protection + auto-merge (3-label gate) + replace `budget_gate.record_call_attempt()` callsites with `BudgetGovernor.record_call()` |

Authoritative source: `AP_Sustainability_Roadmap_v0.2.md`.

---

## 10. Anti-patterns we explicitly avoid

- ❌ Putting prompts in `.py` files (legacy `ap_org_bot.py` bug — caused 3 `.bak` files in 1 day)
- ❌ Module-level SSL bypass (legacy — silently broke tests; now opt-in via `apply_enterprise_ssl_bypass()`)
- ❌ `if/elif` channel dispatch (legacy — now `AgentRegistry` driven from yaml)
- ❌ Duplicating `_spawn_*_headless` per agent (legacy — now `HeadlessAgent` base class)
- ❌ "Use the legacy file as reference, don't touch it" without dating the rollback plan
- ❌ Skipping budget gate "just this once" — it exists because Council sessions burn token fast
- ❌ Hardcoded Discord IDs in code — use `config/channels.yaml` so dev / staging / prod can diverge

---

## 11. People

**Craig** (`DISCORD_CRAIG_USER_ID=566565645483769863`):
- Sole policy owner. Approves Tier 1 + reviews Tier 2 digest.
- Prefers Traditional Chinese for conversational text; English for code/filename/proper nouns.
- Strong design opinions; aesthetic anchored on first ~40 hours of hand-crafted prototyping.
- Daily coordination budget: target < 15 minutes (so the system has to be ergonomic).

**Partner / collaborator** (`1495302135112401067`):
- Authorised to leave feedback in `#ap-feedback` (gets 📝 reaction, no agent fires immediately).
- NOT authorised for Tier 1 sign-off.

---

## 12. 完工協議（Definition of Done）— 所有 agent 一律適用

> 這一節是 2026-08-27 補上的。在此之前，本檔從頭到尾沒有規定「完工要記錄」，
> `CHG_LOG.json` 只在 §7 目錄樹裡出現過一次、當一個標籤。結果是四個 session、
> 1429 行的前端工作躺在工作區從未提交，接手的 agent 無從得知專案真實進度。
>
> **不是 agent 不守規矩，是沒有規矩可守。**

### 12.1 一個切片完成 = 三樣東西同時存在

缺任何一樣都**不算完成**，不得回報「已完成」：

| # | 產出 | 格式 | 為什麼 |
|---|---|---|---|
| 1 | **檔內註解** | `CHANGE <TAG>: <說明>` | 唯一在 Claude / Codex / GPT 三方都存活下來的慣例——因為它就寫在被改的檔案裡，不需要記得去開第二個檔 |
| 2 | **`CHG_LOG.json` entry** | 見 §12.3 | 讓 repo 本身能回答「現在做到哪」，不依賴任何人的記憶或 session 歷史 |
| 3 | **git commit** | `<type>(<scope>): <摘要>` | **未 commit 不算完成。** 工作區不是交付物 |

`<TAG>` 命名格式：**`<前綴>-<描述>`**，大寫、以連字號分隔。
範例：`R9-IMG`、`A4-HONEST`、`SOL-OBJECT-FIRST`。
裸編號（`A1`、`D3`、`ROUND5`）是協議之前的歷史寫法，**不再新增**。

### 12.2 這條規則有牙齒

`tests/test_change_log_contract.py` 會斷言：`Publish/index.html` 裡每一個
不在凍結清單中的 `CHANGE` tag，都必須出現在某筆 `CHG_LOG.json` entry 的
`change_tags` 陣列裡。漏登錄 = `pytest` 紅燈。

```bash
python3 -m pytest tests/test_change_log_contract.py -q
```

凍結清單 `LEGACY_TAGS` 收錄協議建立當下已存在的 41 個 tag，**只能縮小，不能增加**。

### 12.3 `CHG_LOG.json` entry 最小範本

必要欄位：`ts` / `category` / `scope` / `summary`。
動到 `Publish/index.html` 的 entry **必須**再加 `change_tags`。新 entry 放在陣列**最前面**。

```json
{
  "ts": "2026-08-27T00:00:00Z",
  "category": "design",
  "scope": "epic-discover.c3",
  "summary": "注入 VisualArtwork + ItemList JSON-LD",
  "change_tags": ["C3-JSONLD"],
  "rationale": "全站原本無任何結構化資料，Rich Results 偵測不到藏品。",
  "breaking": false,
  "rollback": "git revert <sha>"
}
```

`category` 用 commit 的 type：`design` / `feat` / `fix` / `chore` / `docs` / `perf`。

### 12.4 交付前的自檢清單

回報「完成」之前，逐項確認：

```bash
git status --short                 # 工作區乾淨？沒有該提交卻沒提交的檔案？
python3 -m pytest tests/ -q        # 全綠？（含 §12.2 的協議檢查）
git diff --check                   # 無行尾空白／衝突標記？
git --no-pager log --oneline -3    # 我的 commit 真的在裡面？
```

動到 `Publish/index.html` 時，額外做 inline `<script>` 的 `node --check`，
並在 1440 / 1024 / 375 用**真實 GAS 資料**驗證（不是 mock）。

### 12.5 停手條件

命中以下任一項，**停下來交回 Craig**，不要自行決定：

- Tier 1 事項（見 §5）：首頁 IA、品牌方向、公開內容、新功能、任何真偽／鑑定措辭
- 需要真實藝廊資料：LINE ID、地址、營業時間、Google Maps、電話
- 需要動到凍結欄位或 `era` 列舉（見 §3、§4）→ 需 DD-XXX
- 規則檔之間互相矛盾 → 回報衝突，不要靠猜

### 12.6 不要新增平行紀錄系統

本專案曾同時存在四套紀錄（git commit / `CHG_LOG.json` /
`memory/gpt_polish_log.md` / 檔內註解），沒有一套是完整的。
**現在只有兩套**：`CHG_LOG.json`（結構化事實）＋ git（差異與時序）。
`memory/gpt_polish_log.md` 已凍結為歷史檔案，不再寫入。

需要長篇敘述就寫進 commit message body，不要再開新檔。

---

*This file is the contract. If you're an agent and find a discrepancy between this file and
`memory/`, the more recently dated one wins — but raise the conflict to Craig instead of
silently using your guess.*
