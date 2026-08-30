# AP 工具與 MCP 規劃
**Antique Pavilion — Tooling & MCP Strategy v1.0**

> 本文件為任務 C 的產出，承接 `AP_Multi_Agent_ORG_Blueprint.md`（任務 B）。
>
> 範圍：
> 1. **Cowork 端**：Craig 個人工作流的 MCP 連接器與 Plugin 建議
> 2. **Claude Code 端**：`ap_org_bot.py` 中各 Agent 的 MCP 工具鏈
> 3. **可複製性**：MCP 配置如何模組化，使 AP 成為 template
>
> 版本：v1.0 / 日期：2026-04-27

---

## 目錄
0. [規劃原則](#0-規劃原則)
1. [Cowork 端 MCP 規劃](#1-cowork-端-mcp-規劃craig-個人工作流)
2. [Claude Code 端 MCP 規劃](#2-claude-code-端-mcp-規劃ap_org_botpy)
3. [配置與部署](#3-配置與部署)
4. [可複製性設計](#4-可複製性設計)
5. [ROI 與優先級](#5-roi-與優先級)
6. [風險與權衡](#6-風險與權衡)
7. [實作 Roadmap](#7-實作-roadmap對應任務-b)

---

## 0. 規劃原則

**最小化原則**：每個 MCP 載入都吃 context tokens、增加啟動時間、增加維運面。寧可少不要多，先驗證價值再擴張。

**配置驅動**：Agent 不應該寫死 MCP 名稱，而是宣告「我需要這類能力」，由 `mcp.yaml` 注入具體實作。這是複製到其他專案時換工具最省力的關鍵。

**共享優先**：能多 Agent 共用的 MCP（例如 Notion、GitHub）優先連，能單 Agent 獨佔的（例如 Schema validator）後連。

**成本意識**：Side Project 每月 API 預算有限，MCP 也有 token 消耗。優先選免費或已付費（如已用 Notion/GitHub）的工具。

**Core / Domain 切分**：所有 MCP 都標記是「Core 跨專案可用」還是「AP-specific 領域工具」。Domain-specific 的 MCP 在新專案啟動時要替換。

---

## 1. Cowork 端 MCP 規劃（Craig 個人工作流）

Cowork 是你日常與 AI 協作的入口（簽核、檢視、臨時動議）。這一端的 MCP 服務的是「Craig 自己」，不是 Bot。

### 1.1 已連接：Gmail + Notion 的最佳化使用

#### Gmail（已連）
**強化用法建議**
- **議題收件**：在 Gmail 設一個 label `AP-Topic`，把任何想到的點子轉寄進來，Cowork 端讀 Gmail 後可批次轉成 `#council-topics` 議題（自動化未來可做）
- **簽核通知**：Bot 在 `#council-decisions` 發新提案時，並行寄一份摘要到你的 Gmail，行動裝置才好讀
- **市場情報訂閱**：訂閱蘇富比、佳士得、邦瀚斯的 newsletter，每週讓 Research Agent 透過 Gmail 讀取彙整

**設定建議**
- 建立 filter：寄件者 `*.sothebys.com OR *.christies.com OR *.bonhams.com` → 自動套 label `AP-Industry`
- Research Agent 每週讀這個 label 的內容做彙整

#### Notion（已連）
這是你目前**最重要的資產載體**。建議建立以下 Database：

| Database | 用途 | 對應 Agent |
|---|---|---|
| `Topics` | 議題池與生命週期 | PM |
| `Decisions` | 決策日誌（append-only） | PM |
| `Knowledge Base` | 骨董條目（朝代/品類/特徵/出處） | Librarian |
| `Authentication Log` | Gemini 鑑定原始紀錄 | Curator |
| `Content Calendar` | 內容發布排程 | SEO + Editor + Marketing |
| `Incidents` | SRE 事件記錄 | SRE |
| `Research Briefs` | 市場 Brief 歸檔 | Research |
| `Agent Prompts` | 各 Agent system prompt 版本控管 | Chief of Staff（Phase 3） |

**重要設計**：每個 Database 設「跨 DB 關聯欄位」，例如 `Decisions` 連結到 `Topics`、`Content Calendar` 連結到 `Knowledge Base` 條目。這樣未來查詢「這個決策衍生了哪些內容」會非常自然。

### 1.2 強烈建議補強（Phase 1）

#### GitHub MCP [Core]
**為何需要**：你的 Frontend 部署、`ap_org_bot.py` 程式碼、issues、Actions 都在 GitHub。Cowork 端能直接讀 PR、issue、commit，等於你能在 Cowork 對話中即時審查 Bot 寫的程式碼。

**典型用法**
- "幫我看 ap_org_bot 最近三個 commit 改了什麼"
- "Frontend 的 PR #42 是不是該合併了"
- "上週 GitHub Actions 失敗的那次原因是什麼"

**成本**：免費（公開 repo），私有 repo 需 Pro 帳號（你應該有）。

#### Google Search Console MCP [Core]
**為何需要**：AP 是流量驅動的展示站，SEO 是命脈。你需要在 Cowork 對話中問「這個關鍵字最近排名」「哪頁流量掉了」。

**典型用法**
- "上週『明代銅爐辨偽』的排名變化"
- "首頁這個月的 SERP CTR"
- "哪些頁面點擊掉超過 30%"

**目前狀況**：Anthropic 官方暫無 GSC MCP，社群有實作（如 `mcp-google-search-console`）。可請 Claude Code 評估後選一個。

**成本**：免費。

#### Google Analytics 4 MCP [Core]
**為何需要**：搭配 GSC 形成完整流量分析閉環。GSC 看搜尋來源，GA4 看站內行為。

**典型用法**
- "這篇文章的平均停留時間"
- "預約看展按鈕的點擊次數"
- "從哪個來源來的訪客最後有點 LINE 加入"

**成本**：免費。

#### Google Calendar MCP [Core]
**為何需要**：簽核時間管理、看展時間規劃、Bot 排程議題對齊你的時間。

**典型用法**
- "下週還有哪天有時間做品牌會議"
- "把週一 09:00 的 PM 簡報加入行事曆"

**成本**：免費。

### 1.3 選擇性補強（Phase 2 視需要）

#### Figma MCP（如果開始做設計稿）[Core]
- **適用情境**：Design Agent 開始產 Figma 稿、UX 出線框
- **替代方案**：純文字描述線框 → Frontend 直接實作（Side Project 規模通常夠用）

#### Lucid MCP（diagram）[Core]
- 系統已連接（在 deferred tools 中可見）
- **典型用法**：畫使用者旅程、組織圖、技術架構圖
- **建議**：Phase 1 用 Mermaid（在 Markdown 中內嵌）即可，Lucid 留到要產出對外說明圖再用

#### Exa Web Search MCP [Core]
- 系統已連接（`web_search_exa`）
- **適用情境**：Research Agent、Compliance Agent 做深度網路調研
- **比 WebSearch 強在**：Exa 對「深度研究查詢」效果更好（語義搜尋而非關鍵字）

#### Hugging Face MCP [選配]
- 系統已連接
- **適用情境**：未來想用本地模型做圖像分類 / 標籤建議時
- **Phase 1 不需要**

### 1.4 不建議連接（避免 MCP 膨脹）

| MCP | 不建議理由 |
|---|---|
| Slack | 你用 Discord，連了用不到 |
| Asana / Linear | Notion DB 可取代，少一個訂閱費 |
| 多個社群平台 MCP | 社群操作交給 `ap_org_bot` 端的 Marketing Agent，Cowork 端不需要 |
| 雲端儲存類 MCP | 設計檔放 GitHub 或 Notion，不需要單獨 Drive 整合 |

---

## 2. Claude Code 端 MCP 規劃（`ap_org_bot.py`）

這一端的 MCP 服務的是 **Bot 內各 Agent**，每次 Agent 被 headless Claude Code 喚起時動態載入需要的 MCP。

**核心設計**：不是「全部 MCP 都掛在 Bot 上」，而是**每個 Agent 在其 system prompt 旁聲明需要的 MCP，啟動時動態組合**。這對 token 與啟動時間都關鍵。

### 2.1 全 Agent 共用 MCP（基礎層）

| MCP | 目的 | Core/AP |
|---|---|---|
| **Notion MCP** | 寫決策日誌、查知識庫、讀 prompts | Core |
| **Discord MCP**（自建 wrapper） | 在頻道間傳訊、讀 thread、發 Embed | Core |
| **GitHub MCP**（讀） | 讓 Agent 能看當前 codebase 上下文 | Core |

> 注意：Discord 操作其實是透過你既有的 `ap_org_bot.py` 自身（已用 discord.py），不一定要走 MCP。可以保留現有實作，僅把「讓 Agent 主動發訊」這部分包成 MCP-style tool。

### 2.2 各 Agent 專屬 MCP 對照表

| Agent | 必要 MCP / Tool | 選配 | 註記 |
|---|---|---|---|
| **PM** | Notion | — | 寫 `Topics` / `Decisions` DB |
| **Feedback PM** | Discord 讀取 | Notion | 掃描頻道、彙整 |
| **UX** | GitHub（讀） | Figma | 讀 frontend code 提建議 |
| **Design** | GitHub（讀），自建 audit script | Figma | `/audit` `/polish` 已有 |
| **Frontend** | GitHub（讀寫） | Lighthouse CLI | 改 code、發 PR |
| **Backend** | GitHub（讀寫），**GAS API** | Gemini API monitor | GAS 部署、配額管理 |
| **SEO** | Google Search Console，Schema validator | WebSearch | 規格輸出給 Frontend |
| **Editor** | Notion（讀 KB），WebSearch | — | 事實核對 |
| **Marketing** | Social Media API（Meta Graph 等） | WebSearch | 社群排程 |
| **SRE** | 自建監控 script，Discord webhook | GitHub Actions API | 心跳、告警 |
| **Curator** | **Gemini API**，Notion（讀） | — | 二次驗證鑑定結果 |
| **Librarian** | Notion（讀寫） | — | 寫入 `Knowledge Base` |
| **DevOps** | GitHub Actions API，GAS Deployment | — | Phase 2 |
| **Compliance** | WebSearch，自建規則 lint | — | Phase 2 |
| **Research** | **Exa**，WebSearch，Gmail（讀產業 newsletter） | — | Phase 2 |

### 2.3 必須自建的工具（沒有現成 MCP）

#### Gemini Quota Monitor
- **目的**：監控 Gemini API 配額使用率，達 70% / 90% 推 SRE 告警
- **實作**：簡單 Python script，定期呼叫 Google AI Studio quota endpoint
- **使用 Agent**：SRE、Backend
- **Core/AP**：Core 結構（任何用 Gemini 的專案都用得到）

#### Discord Bot Heartbeat
- **目的**：每 5 分鐘讓兩支 Bot 在 `#ap-alerts` 私下發 ping，超過 10 分鐘沒 ping 即外推 Push 通知到 Craig
- **實作**：Discord webhook + 自建 cron + Pushover/Email fallback
- **使用 Agent**：SRE
- **Core/AP**：Core

#### GAS Deployment Helper
- **目的**：把 GAS 部署從手動 web UI 改為 CLI（`clasp`）
- **實作**：`@google/clasp` + 自建 wrapper 標 semver
- **使用 Agent**：Backend、DevOps
- **Core/AP**：Core 結構（任何用 GAS 的專案都用）

#### Schema.org Validator
- **目的**：上稿前驗證 schema 標記是否合法
- **實作**：Google Rich Results Test API 包裝
- **使用 Agent**：SEO、Frontend
- **Core/AP**：Core

#### Brand Tone Linter（AP 專屬）
- **目的**：掃描文本是否違反 Editor 的調性檢核（廣告腔、形容詞堆疊等）
- **實作**：簡單 regex + 同義詞清單
- **使用 Agent**：Editor、Compliance
- **Core/AP**：AP-specific（規則本身會換，骨架可共用）

#### Authentication Confidence Checker（AP 專屬）
- **目的**：對 Gemini 鑑定結果做信心度與一致性檢查
- **實作**：對比 Notion `Knowledge Base` 中相似品項的判讀
- **使用 Agent**：Curator
- **Core/AP**：AP-specific

---

## 3. 配置與部署

### 3.1 `mcp.yaml` 設計

把所有 MCP 連接資訊集中在一個配置文件，Bot 啟動時讀取。

```yaml
# config/mcp.yaml

# Core MCPs（跨專案共用）
core_mcps:
  notion:
    type: official
    package: "@notionhq/mcp-server"
    auth_env: NOTION_API_KEY
    capabilities: [read, write, search]

  github:
    type: official
    package: "@github/mcp-server"
    auth_env: GITHUB_TOKEN
    capabilities: [pr, issue, code, actions]

  google_workspace:
    type: official
    package: "google-workspace-mcp"
    auth_env: GOOGLE_OAUTH_TOKEN
    capabilities: [gmail, calendar, drive, search_console, ga4]

  exa:
    type: third_party
    package: "exa-mcp"
    auth_env: EXA_API_KEY

# Domain-specific MCPs（AP 專屬）
domain_mcps:
  gemini_quota:
    type: custom
    path: "./tools/gemini_quota_monitor"
    auth_env: GEMINI_API_KEY

  authentication_checker:
    type: custom
    path: "./tools/auth_confidence_checker"

  brand_tone_linter:
    type: custom
    path: "./tools/brand_tone_linter"
    config: "./config/ap_brand_rules.yaml"
```

### 3.2 Agent → MCP 映射

把「哪個 Agent 需要哪些 MCP」也配置化：

```yaml
# config/agent_mcps.yaml

agents:
  pm:
    mcps: [notion]
    tools: []

  ux:
    mcps: [github]
    tools: []

  frontend:
    mcps: [github]
    tools: [lighthouse_cli]

  backend:
    mcps: [github]
    tools: [gemini_quota, gas_deployment]

  seo:
    mcps: [google_workspace]
    tools: [schema_validator]

  editor:
    mcps: [notion]
    tools: [brand_tone_linter, web_search]

  curator:
    mcps: [notion]
    tools: [authentication_checker, gemini_api]

  librarian:
    mcps: [notion]
    tools: []

  sre:
    mcps: []
    tools: [discord_heartbeat, gemini_quota, gas_logs]

  research:
    mcps: [exa, google_workspace]
    tools: [web_search]
```

啟動 Agent 時，`ap_org_bot.py` 讀這份配置動態組合 Claude Code 的 MCP 參數。

### 3.3 Secrets 管理

**原則**：絕不把金鑰寫進 git。

建議結構：
```
ap-org/
├── .env.example       # 公開範本
├── .env               # 本地實際 secrets（gitignore）
├── config/
│   ├── mcp.yaml       # 結構配置（公開）
│   ├── agents.yaml
│   └── ap_brand_rules.yaml
└── core/
```

`.env` 內容範例：
```
NOTION_API_KEY=secret_xxx
GITHUB_TOKEN=ghp_xxx
GOOGLE_OAUTH_TOKEN=ya29.xxx
EXA_API_KEY=xxx
GEMINI_API_KEY=xxx
DISCORD_BOT_TOKEN=xxx
```

**升級建議**：跑穩後可遷移到 1Password CLI / `direnv` / vault，但 Phase 1 用 `.env` + `python-dotenv` 已足夠。

### 3.4 啟動流程

```
[Bot 啟動]
  ↓
[讀 config/mcp.yaml] → 驗證所有 secrets 是否就位
  ↓
[讀 config/agents.yaml] → 載入 Agent 名冊
  ↓
[讀 config/agent_mcps.yaml] → 建立 Agent ↔ MCP 映射
  ↓
[Discord Bot 連線]
  ↓
[註冊事件 handler：訊息 / Reaction / Slash command]
  ↓
[啟動 cron schedules：Feedback PM、SRE、Research]
  ↓
[Ready]
```

每次 Agent 被觸發：
```python
# pseudo
def invoke_agent(agent_name, context):
    cfg = load_agent_config(agent_name)
    mcps = compose_mcps(cfg.mcps + cfg.tools)
    prompt = render_system_prompt(agent_name, context)

    result = claude_code_headless(
        prompt=prompt,
        mcps=mcps,
        model=cfg.model_for_phase,  # haiku / sonnet
    )

    return result
```

---

## 4. 可複製性設計

這節是把「複製到下一個 Side Project」的成本壓到最低的關鍵。

### 4.1 Core MCP 清單（跨專案共用）

| MCP / Tool | 在 AP 用途 | 在精品選物可能用途 | 在數位訂閱可能用途 |
|---|---|---|---|
| Notion | 決策日誌、知識庫 | 商品庫、選物日誌 | 訂閱戶資料、內容庫 |
| GitHub | code、PR | code、PR | code、PR |
| Google Workspace（Gmail/Cal/GSC/GA4） | 引流分析 | 訂單通訊、引流 | 訂閱者行為、引流 |
| Exa | 市場研究 | 品牌動態 | 同類訂閱研究 |
| Discord（自建 wrapper） | 團隊協作 | 團隊協作 | 團隊協作 |
| Gemini Quota Monitor | API 配額 | 若用 Gemini 同上 | 若用 Gemini 同上 |
| Discord Heartbeat | Bot 監控 | Bot 監控 | Bot 監控 |
| Schema Validator | SEO | 商品 SEO | 內容 SEO |

### 4.2 Domain-specific MCP 清單（每專案重寫）

| 在 AP | 對應在「精品選物」 | 對應在「數位訂閱」 |
|---|---|---|
| Authentication Confidence Checker | Brand Authenticity Verifier | Content Originality Checker |
| Brand Tone Linter（書卷氣） | Brand Tone Linter（精品語感） | Brand Tone Linter（訂閱社群感） |
| GAS Deployment Helper | 同上（如還用 GAS） | 同上 |
| 自建鑑定領域工具 | 自建選物標準工具 | 自建內容評分工具 |

### 4.3 新專案 onboarding 流程（Chief of Staff Agent 的工作）

當你啟動下一個 Side Project（例如「精品選物」），Chief of Staff 應該執行：

1. **Fork** 整個 `org_framework_core` repo
2. **替換** `domain/ap/` → `domain/select_shop/`
3. **重寫** 五份 Domain 文件：
   - `domain/<new>/agents/curator.md`（換成 Buyer Agent）
   - `domain/<new>/agents/librarian.md`（換成 Inventory Agent）
   - `domain/<new>/prompts/editor_tone.md`（換品牌調性）
   - `domain/<new>/config/brand_colors.yaml`
   - `domain/<new>/config/compliance_rules.yaml`
4. **重連** Domain MCP（如有）
5. **複製** Notion 模板（DB schema 一致，內容空白）
6. **建立** 新 Discord server，套用 channel 命名規範
7. **跑** 第一場議事測試（用 dummy 議題驗證流程）

理想狀態：**新專案啟動 < 2 天**（vs. 從零做要 4–6 週）。

### 4.4 「框架升級」的版本管理

當 Core 框架升級（例如議事協定優化），如何讓所有現有專案受益？

**建議：手動拉取，不自動推送**
- Core repo 用 semver（`v1.0.0` → `v1.1.0`）
- 每個 domain 專案在 README 標明依賴的 core 版本
- 升級時人工 review 變更，避免破壞性更新

---

## 5. ROI 與優先級

### 5.1 必裝（Phase 1 第 1–2 週）

| 工具 | 預估收益 | 預估成本 | 優先級 |
|---|---|---|---|
| Notion MCP（Cowork + Bot 兩端） | 極高（決策資產化） | 0（已有） | ★★★★★ |
| GitHub MCP（兩端） | 高（程式碼透明） | 0 | ★★★★★ |
| Discord 內部 wrapper | 必要 | 已有 | ★★★★★ |
| Gemini Quota Monitor（自建） | 高（避免突然斷線） | 半天工 | ★★★★★ |
| Discord Bot Heartbeat（自建） | 高（避免 Bot 死了不知道） | 半天工 | ★★★★★ |

### 5.2 強烈建議（Phase 1 第 3–4 週）

| 工具 | 預估收益 | 預估成本 | 優先級 |
|---|---|---|---|
| Google Search Console MCP | 高（SEO 是命脈） | 1 天評估+整合 | ★★★★ |
| Google Analytics 4 MCP | 高（轉化分析） | 1 天 | ★★★★ |
| Schema Validator（自建） | 中（SEO 品質） | 半天 | ★★★★ |
| Brand Tone Linter（自建） | 中（編輯效率） | 1 天 | ★★★ |

### 5.3 Phase 2 加值

| 工具 | 預估收益 | 預估成本 | 優先級 |
|---|---|---|---|
| Exa MCP | 中高（深度研究） | 0.5 天 | ★★★ |
| Google Calendar MCP | 中 | 0.5 天 | ★★ |
| GAS Deployment Helper | 中（DevOps 紀律） | 1 天 | ★★★ |
| Lighthouse CLI 整合 | 中（效能基準） | 1 天 | ★★ |

### 5.4 暫不需要

- Figma MCP（除非開始用 Figma）
- Hugging Face MCP（沒在用本地模型）
- Lucid MCP（Mermaid 已夠）
- Slack / Linear / Asana（Discord + Notion 已 cover）

---

## 6. 風險與權衡

### 6.1 主要風險

**MCP token 膨脹**
- 每個 MCP 載入時都會把工具 schema 注入 context，多了會讓每次 Agent 啟動都吃幾千 token
- **緩解**：嚴格按 `agent_mcps.yaml` 載入，不全掛。Phase 1 限制每個 Agent ≤ 3 個 MCP。

**Secrets 外洩**
- Bot 跑在 WSL2，本地 `.env` 仍是風險點
- **緩解**：`.env` 加入 `.gitignore`、定期 rotate token、敏感操作（如 GitHub 寫入）用最小權限 token

**第三方 MCP 品質參差**
- 社群實作的 MCP 可能維護不善、回應格式不穩
- **緩解**：優先用官方（Anthropic / 服務原廠）；自建 wrapper 比依賴不穩第三方好

**API rate limit**
- Gemini、GitHub、Notion 都有 rate limit；多 Agent 並行可能撞牆
- **緩解**：核心呼叫加入 retry with backoff；對 Gemini 加配額預警

**配額爆炸**
- Side Project API 預算有限，MCP 多會讓每場議事呼叫變多
- **緩解**：第一輪用 Haiku；議題分級（不是每件事都開會）；Cowork 端不需要的 MCP 不連

### 6.2 必須避免的反模式

- ❌ 全部 MCP 都掛在每個 Agent 上（token 災難）
- ❌ Secrets 寫在 yaml 配置裡（外洩災難）
- ❌ 寫死 MCP 名稱在 Agent prompt（複製困難）
- ❌ 自建工具沒文件（Phase 2 接手會痛苦）
- ❌ 沒有 fallback 機制（MCP 服務掛了 Agent 直接卡死）

---

## 7. 實作 Roadmap（對應任務 B）

對應任務 B 的 Phase 1 / 2 / 3：

### Phase 1（與任務 B 同步，4–6 週）

**Week 1（基礎設施同步進行）**
- [ ] 建立 `config/mcp.yaml` / `agent_mcps.yaml` 結構
- [ ] 把現有 Bot 連線參數搬進 `.env`
- [ ] 連 Notion MCP（Cowork + Bot 兩端）
- [ ] 連 GitHub MCP（Cowork + Bot 兩端）

**Week 2**
- [ ] 自建 Gemini Quota Monitor
- [ ] 自建 Discord Bot Heartbeat
- [ ] SRE Agent 串接這兩個工具

**Week 3–4**
- [ ] 連 Google Search Console MCP（Cowork）
- [ ] 連 Google Analytics 4 MCP（Cowork）
- [ ] 自建 Schema Validator
- [ ] SEO Agent + Frontend Agent 串接

**Week 5–6**
- [ ] 自建 Brand Tone Linter
- [ ] Editor Agent 串接
- [ ] 自建 Authentication Confidence Checker
- [ ] Curator Agent 串接
- [ ] Librarian 寫入 Notion KB 流程跑通

### Phase 2（4–6 週）

- [ ] 連 Exa MCP（Research Agent 用）
- [ ] 自建 GAS Deployment Helper（DevOps Agent 用）
- [ ] Compliance Guardrail 規則 yaml + 自建 lint
- [ ] Lighthouse CLI 整合（Frontend KPI 自動化）

### Phase 3（持續）

- [ ] Chief of Staff Agent + 跨專案模板抽取
- [ ] MCP 升級流程文件化
- [ ] 第二個 Side Project 啟動驗證複製性

---

## 附錄 A：每個 Agent 的 MCP 速查表

| Agent | Phase | MCP/Tool 清單 |
|---|---|---|
| PM | 1 | notion |
| Feedback PM | 1 | discord_read, notion |
| UX | 1 | github(read) |
| Design | 1 | github(read), audit_script |
| Frontend | 1 | github(read/write), lighthouse_cli, schema_validator |
| Backend | 1 | github(read/write), gas_deployment, gemini_quota |
| SEO | 1 | google_search_console, schema_validator |
| Editor | 1 | notion(read), brand_tone_linter, web_search |
| Marketing | 1 | social_apis, web_search |
| SRE | 1 | discord_heartbeat, gemini_quota, gas_logs |
| Curator | 1 | notion(read), authentication_checker, gemini_api |
| Librarian | 1 | notion(read/write) |
| DevOps | 2 | github_actions, gas_deployment |
| Compliance | 2 | brand_tone_linter, web_search, custom_rules |
| Research | 2 | exa, google_workspace, web_search |

## 附錄 B：Cowork 端建議連接優先序

```
立刻（Phase 1 Week 1）:
  ✅ Gmail (已連)
  ✅ Notion (已連)
  → GitHub MCP

Week 2-3:
  → Google Search Console
  → Google Analytics 4

Phase 2:
  → Google Calendar
  → Exa（如果 Research Agent 表現需要強化）

不建議 / 暫不需要:
  ✗ Figma（除非開始用）
  ✗ Lucid（Mermaid 已夠）
  ✗ Hugging Face
  ✗ Slack / Linear / Asana
```

## 附錄 C：v1.0 之後的開放問題

- [ ] MCP 健康檢查機制（哪個 MCP 掛了影響哪些 Agent）要不要做？
- [ ] 自建工具如何 unit test？（特別是 Brand Tone Linter）
- [ ] Cowork 端與 Bot 端共用同一份 Notion DB 時，寫入競爭如何處理？
- [ ] MCP 跨專案版本升級時，breaking change 如何辨識？
- [ ] 是否需要 Agent-level rate limiter（避免某 Agent 暴走打爆 API）？

---

**版本歷史**
- v1.0（2026-04-27）：初版

**配套文件**
- `AP_Multi_Agent_ORG_Blueprint.md`（任務 B：組織擴展設計）
