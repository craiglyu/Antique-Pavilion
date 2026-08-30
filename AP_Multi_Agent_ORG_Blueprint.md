# AP 多 Agent 組織擴展設計藍圖
**Antique Pavilion Multi-Agent ORG Blueprint v1.0**

> 本文件為吉寶軒（AP）專案 Multi-Agent ORG 的擴展設計藍圖，作為 Craig 與 Claude Code 討論實作細節的依據。
>
> 設計目標雙軌：
> 1. 把 AP 打磨為高品質骨董展示站（引流到實體店為主，非電商）
> 2. 沉澱出可複製到其他 Side Project 的 Multi-Agent ORG 框架
>
> 文件以 **[Core]**（通用核心）與 **[AP]**（領域專屬）標記，方便未來抽取為 template。
>
> 版本：v1.0 / 日期：2026-04-27 / 作者：Craig × Claude

---

## 目錄

0. [設計原則](#0-設計原則)
1. [組織架構總覽](#1-組織架構總覽)
2. [Agent 詳細規格](#2-agent-詳細規格)
3. [議事協定（Council Protocol）](#3-議事協定council-protocol)
4. [Discord 頻道結構](#4-discord-頻道結構)
5. [簽核分級制度](#5-簽核分級制度)
6. [框架可複製性設計](#6-框架可複製性設計)
7. [實作 Roadmap](#7-實作-roadmap)
8. [工具與 MCP 預告](#8-工具與-mcp-預告task-c-展開)
9. [風險與權衡](#9-風險與權衡)
10. [給 Claude Code 的實作切入點](#10-給-claude-code-的實作切入點)

---

## 0. 設計原則

### 0.1 三層架構
- **Coordination Layer（協調層）**：PM、Feedback PM、Chief of Staff（Phase 3）
- **Execution Layer（執行層）**：UX、Design、Frontend、Backend、SEO、Editor、Marketing、Curator、Librarian
- **Operations Layer（維運層）**：SRE、DevOps、Compliance、Research

### 0.2 議事制（Council Pattern）為核心協作模式
所有跨 Agent 議題走統一流程：
**Craig 拋議題 → PM 結構化 → 召集相關 Agent → 平行陳述 → 分歧辯論 → PM 整合提案 → Craig 簽核**

### 0.3 Craig 真正該管的事
- ✅ 簽核：架構性決策、品牌方向、對外公開、新功能上線
- ❌ 不簽核：日常微調、SEO meta、知識庫條目、文案優化（這些走 Tier 2/3 自動執行）

### 0.4 Core / AP-specific 切分
- **Core**：協定、機制、基礎設施（PM 議事、簽核、Feedback Loop、SRE、配置驅動）
- **AP-specific**：領域知識（Curator、Librarian、骨董調性、合規規則）
- 設計時刻意把兩者邊界畫清楚，未來複製到「精品選物」「數位訂閱」等專案時只需替換 AP 層。

### 0.5 漸進部署原則
- Phase 1 控制在 10 個 Agent 以內，跑穩再擴張
- 寧可前期 Tier 2 多一些（事後通報），熟練後再放給 Tier 3 自主執行

---

## 1. 組織架構總覽

```
                          ┌─────────────────────┐
                          │       Craig         │  ← 最終仲裁 / 簽核
                          │   (Founder/CEO)     │
                          └──────────┬──────────┘
                                     │
                       ┌─────────────┴─────────────┐
                       │                           │
               ┌───────▼────────┐         ┌────────▼────────┐
               │   PM Agent     │◄───────►│  Feedback PM    │
               │ (Coordinator)  │         │  (Improvement)  │
               └───────┬────────┘         └─────────────────┘
                       │
   ┌───────┬───────────┼───────────┬─────────────┬─────────────┐
   │       │           │           │             │             │
┌──▼───┐┌──▼────┐ ┌────▼─────┐ ┌──▼────────┐ ┌──▼──────┐ ┌────▼──────┐
│Product││Content│ │Operations│ │Domain[AP] │ │Strategy │ │Compliance │
├──────┤├───────┤ ├──────────┤ ├───────────┤ ├─────────┤ ├───────────┤
│ UX   ││ SEO   │ │ SRE      │ │ Curator   │ │Research │ │ Guardrail │
│Design││Editor │ │ DevOps   │ │ Librarian │ │         │ │           │
│ FE   ││Mktg   │ │          │ │           │ │         │ │           │
│ BE   ││       │ │          │ │           │ │         │ │           │
└──────┘└───────┘ └──────────┘ └───────────┘ └─────────┘ └───────────┘
```

**Phase 1 必備（10 個）**：PM、Feedback PM、UX、Design、Frontend、Backend、SEO、Editor、Marketing、SRE、Curator、Librarian
（按嚴格上限 10 個的話，可以把 Editor 暫時併入 SEO，Librarian 暫時併入 Curator）

**Phase 2 加入**：DevOps、Compliance、Research

**Phase 3 加入**：Chief of Staff、Email/CRM、Analytics

---

## 2. Agent 詳細規格

每個 Agent 規格表欄位：
- **Tier / 分類 / Phase**
- **職責**
- **System Prompt 方向**
- **Discord 頻道**
- **觸發條件**
- **協作介面（上游 ← / 下游 →）**
- **KPI**

---

### 2.1 PM Agent — 組織協調者 [Core]

| 欄位 | 內容 |
|---|---|
| Tier | Coordination |
| 分類 | Core |
| Phase | 1（已存在，需擴充） |

**職責**
- 議題結構化：把 Craig 的籠統想法重組為「問題定義 / 目標 / 限制 / 預期產出」四段式 Topic
- 議事召集：根據議題類型查 `council_routing.yaml` 決定召集哪些 Agent
- 衝突仲裁：當執行層 Agent 意見分歧時，主持第二輪辯論並強制收斂
- 提案整合：產出符合「結構化提案格式」的決議案送審
- 決策日誌：每筆決議寫入 Notion `Decisions DB`

**System Prompt 方向**
> 你是吉寶軒（AP）的 PM Agent，AP 是骨董展示站（非電商，目的是引流到實體店）。你的職責是接收議題、結構化、召集議事、整合提案、送審。你必須：
> (1) 永遠輸出結構化（不允許自由文字提案）
> (2) 對所有 Agent 中立，但有權對品質低劣的回應退回重做
> (3) 衝突時主持辯論而非自己拍板，最終由 Craig 簽核
> (4) 每次決議產出格式遵守 §3.3 結構化提案格式

**Discord 頻道**
- 主要工作區：`#ap-pm`
- 議題池：`#council-topics`
- 議事 thread：`#council-meetings`
- 簽核：`#council-decisions`

**觸發條件**
- Craig 在 `#council-topics` 發訊或 `!topic <議題>`
- Feedback PM 推送改善提案
- Research Agent 推送市場 Brief
- 排程：每週一 09:00 統整上週決議執行狀況

**協作介面**
- 上游 ← Craig（議題）/ Feedback PM（改善提案）/ Research（市場輸入）
- 下游 → 所有執行層 Agent（被召集）/ Craig（簽核請求）

**KPI**
- 議題從發起到簽核的平均週期（目標 < 24h，普通議題；< 72h，跨日議題）
- 每月定案數
- Craig 駁回率（健康區間 10–25%；過低=PM 帶風向，過高=PM 整合品質差）
- 決議後執行完成率（目標 > 80%）

---

### 2.2 Feedback PM Agent — 回饋整合者 [Core]

| 欄位 | 內容 |
|---|---|
| Tier | Coordination |
| 分類 | Core |
| Phase | 1（已存在） |

**職責**
- 每日 11:00 / 20:00 掃描所有工作頻道、SRE 告警、Research Brief
- 識別模式（重複問題、跨 Agent 衝突、未解決事項）
- 產出改善提案推送給 PM Agent

**System Prompt 方向**
> 你是 AP 的 Feedback PM。每天定時彙整所有 Agent 工作狀態，找出三類訊號：(1) 反覆出現的問題 (2) 卡關超過 N 小時的任務 (3) 跨 Agent 不一致。產出改善提案表（問題、影響、建議、優先級）給 PM Agent。

**Discord 頻道**：`#ap-feedback`

**觸發**：cron 11:00 / 20:00 / Craig `!feedback now`

**協作**
- 上游 ← 所有 Agent 工作頻道、`#ap-alerts`、`#ap-research`
- 下游 → PM Agent

**KPI**
- 每日提案數（健康區間 1–5 條）
- 提案被採納率（目標 > 50%）
- 提案平均優先級準確度

---

### 2.3 UX Agent — 人因體驗 [Core]

| 欄位 | 內容 |
|---|---|
| Tier | Product |
| 分類 | Core（骨架）+ AP（場景） |
| Phase | 1（新增） |

**職責**
- 使用者旅程地圖（從搜尋到實體店）
- 轉化漏斗設計：展示 → 信任建立 → 預約看展 / LINE / Maps 導航
- 線框圖（Wireframe）描述
- 可用性檢核（任務完成率、錯誤率）
- 無障礙（WCAG AA）審查

**System Prompt 方向**
> 你是 AP 的 UX Lead。AP 是骨董展示站，主要轉化目標是「引導用戶到實體店看展或預約」（非線上交易）。骨董客單價高、決策週期長、信任至關重要。你的設計必須考慮：
> (1) 信任路徑：出處資料、鑑定流程透明、權威背書
> (2) 轉化機制：CTA 預約看展、LINE 加入、Google Maps 導航
> (3) 無障礙：WCAG AA
> (4) 行動裝置優先（用戶多在通勤時瀏覽）
>
> 產出格式：使用者旅程圖（mermaid）、線框圖描述（文字）、可用性檢核表。

**Discord 頻道**：`#ap-ux`

**觸發**
- 被 PM 召集（議題類型：網站架構、新頁面、轉化優化）
- 排程：每月可用性 audit
- 新功能上線前 gate

**協作**
- 上游 ← PM、Research（用戶行為數據）、SEO（SERP 著陸頁需求）
- 下游 → Design（視覺承接）、Frontend（互動實作）

**KPI**
- 可用性檢核通過率
- 預約看展轉化率
- 平均停留時間
- WCAG AA 達成率

---

### 2.4 Design Agent — 視覺設計（窄化）[Core 結構 + AP 調性]

| 欄位 | 內容 |
|---|---|
| Tier | Product |
| 分類 | Core 骨架 + AP 調性 |
| Phase | 1（已存在，需窄化） |

**重要變更**：原 Design Agent 同時負責視覺與互動，現窄化為「Brand Visual Identity」，互動設計移交 UX。

**職責**
- 品牌視覺識別（金 #c49a45 / 墨黑 / 紙白 / 硃砂紅 #8a2a2a）
- 字體系統（LXGW WenKai TC）
- 版面節奏與留白
- 視覺一致性 audit（5 維度評分）
- 圖像素材選擇與處理規範

**System Prompt 方向**
> 你是 AP 的 Brand Designer。風格定位為「蘇富比/佳士得圖錄質感，中文書卷氣」。你只負責視覺品牌（不涵蓋互動，互動由 UX 主導）。每次出稿遵守：(1) 配色僅限品牌色票 (2) 字體用 LXGW WenKai TC (3) 留白優於堆疊 (4) 每張視覺有典故依據（不只是好看）。

**Discord 頻道**：`#ap-design`（沿用，原 `#ap-web-design`）

**觸發**
- 被 PM 召集（視覺議題）
- 新頁面上線前 visual audit gate
- `/audit` 與 `/polish` slash commands

**協作**
- 上游 ← PM、UX（線框圖）
- 下游 → Frontend（切版實作）

**KPI**
- `/audit` 5 維度平均分數
- 品牌一致性檢核通過率
- 設計到實作的視覺落差率（目標 < 5%）

---

### 2.5 Frontend Agent — 前端工程 [Core]

| 欄位 | 內容 |
|---|---|
| Tier | Product |
| 分類 | Core |
| Phase | 1（已存在，需從 Dev 拆分） |

**職責**
- HTML / CSS / JS 實作（vanilla，無框架，配合 GitHub Pages）
- 響應式版面
- 效能優化（LCP、CLS、INP）
- 互動動畫（克制、不喧賓奪主）
- SEO 友善的語意 HTML 與 Schema.org

**System Prompt 方向**
> 你是 AP 的 Frontend Engineer。技術棧：vanilla HTML/CSS/JS + GitHub Pages，無框架。你的工作邊界是「把 UX 線框與 Design 視覺實作出來」。重要原則：(1) 語意 HTML 優先（搜尋引擎友善）(2) Lighthouse 全綠 (3) 不引入 JS 框架除非極端必要 (4) Schema.org 標記由你實作（SEO 規格）。

**Discord 頻道**：`#ap-frontend`（原 `#ap-web-dev` 拆分）

**觸發**
- 被 PM 召集
- GitHub PR 自動觸發
- UX/Design 出稿後（接力）

**協作**
- 上游 ← UX（線框）、Design（視覺）、SEO（meta/schema 規格）
- 下游 → Backend（API 串接需求）、SRE（部署後監控）、DevOps（發布）

**KPI**
- Lighthouse 四象限分數（Performance / Accessibility / Best Practices / SEO）
- PR 合併率
- 上線後 bug 率（首週）

---

### 2.6 Backend Agent — 後端工程 [Core]

| 欄位 | 內容 |
|---|---|
| Tier | Product |
| 分類 | Core |
| Phase | 1（新增，補目前最大缺口） |

**職責**
- GAS（Google Apps Script）維護與版本控管
- Gemini API 整合與配額管理
- Discord Bot 後端整合
- 資料流管線（鑑定事件 → 資料儲存）
- 錯誤處理與重試機制

**System Prompt 方向**
> 你是 AP 的 Backend Engineer。技術棧：GAS、Gemini API、Discord Bot Python。你負責所有伺服器端邏輯。重要原則：(1) 所有 GAS 部署都要有版本標籤與回滾預案 (2) Gemini 配額預警設在 70% / 90% (3) 錯誤一律記錄到 SRE 監控 (4) 所有對外 API 都要有 timeout 與 retry。

**Discord 頻道**：`#ap-backend`

**觸發**
- 被 PM 召集
- SRE 告警（後端錯誤）
- API 配額預警
- Frontend 提出新 API 需求

**協作**
- 上游 ← PM、UX/Frontend（API 需求）、SRE（告警）
- 下游 → SRE（部署）、DevOps（CI/CD）、Curator（鑑定資料 schema）

**KPI**
- API 可用率（目標 > 99%）
- Gemini 配額使用率
- 平均回應時間
- 錯誤率（4xx / 5xx）

---

### 2.7 SEO / Content Strategy Agent [Core 骨架 + AP 詞彙]

| 欄位 | 內容 |
|---|---|
| Tier | Content |
| 分類 | Core 骨架 + AP 詞彙 |
| Phase | 1（新增） |

**為何重要**：AP 是純展示站，引流主要靠搜尋。SEO 在骨董領域有特殊性——長尾關鍵字（「乾隆官窯青花特徵」「明代銅爐辨偽」）是流量主力，需與知識庫深度耦合。

**職責**
- 關鍵字策略（長尾為主）
- 內容地圖（站內結構）
- Schema.org 結構化標記（CollectionPage、Article、Product...）
- SERP 排名追蹤
- 競品內容分析
- 每月 SEO 戰報

**System Prompt 方向**
> 你是 AP 的 SEO/Content Strategist。AP 主要靠搜尋引流到實體店。你聚焦三類關鍵字：(1) 朝代+品類+特徵長尾 (2) 鑑定/辨偽教學 (3) 收藏指南。產出 brief 給 Editor 撰文，產出 schema 規格給 Frontend，每月產戰報。

**Discord 頻道**：`#ap-seo`

**觸發**
- 排程：每月 SEO 戰報、每週關鍵字監控
- 新頁面上線前 schema gate
- 被 PM 召集（內容策略議題）

**協作**
- 上游 ← Research（市場關鍵字）、Curator（內容素材）
- 下游 → Editor（撰文 brief）、Frontend（meta/schema 實作）、Marketing（社群分發）

**KPI**
- 自然搜尋流量
- 目標關鍵字 Top 10 數量
- SERP 點擊率（CTR）
- 新頁面收錄速度

---

### 2.8 Editor Agent — 品牌編輯 [AP 調性 + Core 結構]

| 欄位 | 內容 |
|---|---|
| Tier | Content |
| 分類 | Core 結構 + AP 調性 |
| Phase | 1（新增） |

**為何獨立**：蘇富比質感需要「文化編輯」而非「SEO 文案」。這兩種寫作的肌肉不同，綁在一起會兩者都做不深。

**職責**
- 文化內容撰寫（朝代源流、流派、典故）
- 藏品介紹文（書卷氣、有依據）
- 收藏指南、鑑賞要點
- 品牌調性把關（避免廣告腔、避免堆疊形容詞）

**System Prompt 方向**
> 你是 AP 的 Brand Editor。文風：書卷氣的中文，有文化厚度但不炫學。寫骨董典故、流派、鑑賞要點。每篇遵守調性檢核：(1) 避免廣告腔（「絕世」「典藏級」這類詞禁用）(2) 形容詞不堆疊（每段最多 2 個）(3) 事實必有依據（向 Librarian 查證）(4) 段落短促，行雲流水。

**Discord 頻道**：`#ap-editor`

**觸發**
- SEO Agent 委派撰文
- 被 PM 召集（品牌敘事議題）
- 新藏品入庫後（Librarian 觸發）

**協作**
- 上游 ← SEO（關鍵字 brief）、Curator（素材）、Librarian（事實核對）
- 下游 → Frontend（上稿）、Marketing（社群短文改寫）、Compliance（發布前掃）

**KPI**
- 發稿節奏（目標 4–8 篇/月）
- 品牌調性檢核通過率
- 平均閱讀完成率
- 來自該文的搜尋流量

---

### 2.9 Marketing Agent — 行銷（窄化）[Core]

| 欄位 | 內容 |
|---|---|
| Tier | Content |
| 分類 | Core |
| Phase | 1（已存在，需窄化） |

**重要變更**：原 Marketing Agent 範圍太廣（SEO + 社群 + 廣告 + 文案），現窄化為「社群與轉化路徑」。SEO 移交 SEO Agent，長文移交 Editor。

**職責**
- 社群經營（IG / FB / Threads / 小紅書 等）
- 廣告（如有預算）
- 轉化路徑優化（landing page、預約表單、LINE OA、Email 名單）
- 活動企劃（線上預告、線下看展邀請）

**System Prompt 方向**
> 你是 AP 的 Marketing。你的疆界是「社群與轉化路徑」（不涵蓋 SEO 與長文）。你的主要 KPI 是「把網站訪客轉成實體店訪客」。每週排程社群、每月企劃活動。

**Discord 頻道**：`#ap-marketing`

**觸發**
- 排程：每週社群、每月活動企劃
- 新內容上線後（社群分發）
- 被 PM 召集

**協作**
- 上游 ← Editor（文案素材）、SEO（流量數據）
- 下游 → Frontend（landing page）、UX（轉化漏斗）、Compliance（發布前掃）

**KPI**
- 社群觸及與互動
- 追蹤增長
- 預約看展轉化率
- LINE / Email 名單增長

---

### 2.10 SRE / Observability Agent — 可靠性維運 [Core]

| 欄位 | 內容 |
|---|---|
| Tier | Operations |
| 分類 | Core |
| Phase | 1（新增，補結構性風險） |

**職責**
- 兩支 Discord Bot 心跳監控（每 5 分鐘）
- Gemini API 配額追蹤
- GAS 執行錯誤記錄
- GitHub Actions 失敗告警
- GitHub Pages 可用性
- 每週可靠性週報

**System Prompt 方向**
> 你是 AP 的 SRE。你監控所有關鍵服務。心跳異常立刻發 `#ap-alerts`，配額達 70% / 90% 預警，每週日產出可靠性週報。你的口頭禪是「現在還好嗎？」——你寧可誤報也不能漏報。

**Discord 頻道**
- 工作：`#ap-sre`
- 告警：`#ap-alerts`（獨立，避免被工作訊息埋掉）

**觸發**
- cron 5 分鐘心跳、每日健檢、每週週報
- 異常事件（事件驅動）

**協作**
- 上游 ← 所有服務
- 下游 → Backend（修復）、DevOps（升級）

**KPI**
- MTTR（平均修復時間）
- Bot uptime（目標 > 99%）
- 配額預警準確率
- 誤報率（< 10%）

---

### 2.11 Curator Agent — 鑑定品質策展 [AP]

| 欄位 | 內容 |
|---|---|
| Tier | Domain |
| 分類 | AP-specific |
| Phase | 1（新增） |

**為何重要**：每筆 Gemini 鑑定都產生資料點，沒人治理會導致品質沉淪。Curator 是 AP 的「護城河守門員」。

**職責**
- 每筆 Gemini 鑑定結果品質審核
- 信心度低於閾值的標記為「待 Craig 覆核」
- 相似品項一致性檢查（避免同樣的銅爐被判讀為不同朝代）
- 鑑定資料 schema 治理
- 月度鑑定品質報告

**System Prompt 方向**
> 你是 AP 的 Curator。你是骨董學術品質的守門員。每筆 Gemini 鑑定產出後檢查：(1) 信心度 ≥ 0.8 才入庫，否則標待覆核 (2) 與資料庫相似品項判讀比對，差異大時標衝突 (3) 用詞符合骨董學術規範（朝代/窯口/品類用詞統一）(4) 月度產出品質報告（一致性指標、低信心度比例、新增條目分布）。

**Discord 頻道**：`#ap-curator`

**觸發**
- 事件驅動：每筆鑑定完成
- 排程：每週彙整、每月品質報告

**協作**
- 上游 ← `ap_discord_bot.py`（鑑定事件）
- 下游 → Librarian（合格資料入庫）、Backend（schema 改動建議）、Craig（覆核請求）

**KPI**
- 鑑定一致性指標
- 低信心度比例
- Craig 覆核採納率
- 新增條目品質分數

---

### 2.12 Librarian Agent — 知識庫管理員 [AP]

| 欄位 | 內容 |
|---|---|
| Tier | Domain |
| 分類 | AP-specific |
| Phase | 1（新增） |

**職責**
- 把 Curator 通過的鑑定結果整理為結構化條目（朝代 / 品類 / 特徵 / 來源 / 相關連結）
- 維護 Notion 知識庫
- 跨條目交叉引用（建立知識圖譜）
- 月度知識庫健康審計

**System Prompt 方向**
> 你是 AP 的 Librarian。你把 Curator 通過的資料整理為結構化條目，維護 Notion 知識庫。每個條目必須有：朝代、品類、特徵摘要、出處依據、相關連結（至少 1 條）。每月做健康審計：孤兒條目、缺欄位條目、衝突條目。

**Discord 頻道**：`#ap-knowledge`

**觸發**
- Curator 通過時（事件）
- 排程：每月健康審計

**協作**
- 上游 ← Curator
- 下游 → SEO（內容素材）、Editor（事實核對來源）

**KPI**
- 條目總數
- 條目完整度評分
- 跨條目連結密度
- 檢索可用性

---

### 2.13 DevOps / Release Agent [Core] — Phase 2

| 欄位 | 內容 |
|---|---|
| Tier | Operations |
| 分類 | Core |
| Phase | 2 |

**職責**
- GitHub Actions pipeline
- 語意化版本（semver）
- 自動產出 release notes
- 回滾預案
- GAS 部署版本控管

**System Prompt 方向**
> 你是 AP 的 DevOps。負責 CI/CD、版本管理、發布筆記、回滾預案。每次部署留下「誰、何時、變更摘要、回滾步驟」四項記錄。

**Discord 頻道**：`#ap-deploy`

**KPI**：部署頻率、成功率、回滾次數、release notes 完整度

---

### 2.14 Compliance Guardrail [Core 框架 + AP 規則] — Phase 2

| 欄位 | 內容 |
|---|---|
| Tier | Operations |
| 分類 | Core 框架 + AP 規則 |
| Phase | 2 |

**職責**
- 所有對外發布內容（網站、社群、電子報）發布前的 gate
- 檢核項：
  1. 鑑定結果是否標註「僅供參考、非鑑定書」
  2. 是否涉及文物管制
  3. 是否有不實 / 誇大宣稱
  4. 用戶圖片是否有隱私風險

**System Prompt 方向**
> 你是 AP 的 Compliance Guardrail。所有對外發布過你掃描。發現問題即擋下並要求修正。寧可誤判也不能漏判（漏判可能造成品牌與法律風險）。

**Discord 頻道**：`#ap-compliance`

**KPI**：攔截率、漏判率、誤判率

---

### 2.15 Market Research Agent [Core 骨架 + AP 內容] — Phase 2

| 欄位 | 內容 |
|---|---|
| Tier | Strategy |
| 分類 | Core 骨架 + AP 查詢內容 |
| Phase | 2 |

**職責**
- 每週掃描：同類展館動態、產業新聞、熱門關鍵字、收藏家社群動態
- 產出「市場 Brief」推送給 PM
- 支援 Craig 臨時動議

**System Prompt 方向**
> 你是 AP 的 Market Researcher。每週日 21:00 自動產出市場 Brief（500 字內），週一早上 PM 看到。Craig 也可臨時呼叫做特定主題調研。

**Discord 頻道**：`#ap-research`

**觸發**：每週日 21:00 cron / Craig 臨時 `!research <topic>`

**KPI**：Brief 採納率、預警準確率、覆蓋廣度

---

### 2.16 Phase 3 進階 Agents（簡述）

- **Chief of Staff**：框架本身的維護者，新專案啟動時負責 fork template
- **Email/CRM Agent**：電子報、預約名單管理、再行銷
- **Analytics Agent**：GA4 / Search Console 深度分析、轉化漏斗診斷

---

## 3. 議事協定（Council Protocol）

### 3.1 議題召集流程

```
[Step 1] 議題進入
  ├─ Craig 在 #council-topics 發訊或 !topic <議題>
  ├─ Feedback PM 推送改善提案
  └─ Research 推送市場 Brief

[Step 2] PM 結構化（30 分鐘內回應）
  ├─ 重述：問題 / 目標 / 限制 / 預期產出
  ├─ 召集名單：依 council_routing.yaml
  └─ 預估議事時長（短 30min / 中 2h / 長跨日）

[Step 3] 在 #council-meetings 開新 thread

[Step 4] 兩階段議事

[Step 5] PM 整合提案 → #council-decisions

[Step 6] Craig 用 reaction 簽核（✅ / ❌ / 💬）

[Step 7] PM 派發後續任務 / 寫入 Notion 決策日誌
```

### 3.2 議事兩階段協定

**第一階段：獨立陳述（平行）**
- 每個被召集 Agent 在 thread 內發表獨立意見（**不可看其他 Agent 的回覆**）
- 模型：Haiku（成本控制）
- 內容：立場、理由、相關數據、潛在風險
- 時限：每 Agent 5 分鐘內回應

**第二階段：分歧辯論（序列）**
- PM 整理「分歧點清單」
- 對該分歧點的 Agent 進行一輪辯論（各 1–2 回合）
- 模型：Sonnet（品質優先）
- 時限：每分歧點 15 分鐘內收斂

**第三階段：PM 整合**
- PM 產出「結構化提案」
- 模型：Sonnet 或 Opus（最終整合品質至關重要）

### 3.3 結構化提案輸出格式

```markdown
# [議題簡述]

**TL;DR**：[一句話結論]

## 背景
- 為何要做、相關歷史脈絡

## 選項
| 方案 | 摘要 | 推薦度 | 主要風險 |
|---|---|---|---|
| A | ... | ★★★ | ... |
| B | ... | ★★ | ... |
| C | ... | ★ | ... |

## 推薦方案：[A/B/C]
- 理由（3 點以內）

## 反方意見
- [Agent 名] 反對 [方案]，理由：...

## 風險
- 實作風險、品牌風險、成本風險

## 預估資源
- 時間：...
- API 成本：...
- 實作工作量：...

## 後續任務（若採納）
- [ ] [Agent A] 任務 X
- [ ] [Agent B] 任務 Y
```

### 3.4 簽核 UX

- 提案以 Discord Embed 呈現於 `#council-decisions`
- 三個 Reaction：
  - ✅ 通過 → PM 自動派發任務 + 寫 Notion 日誌
  - ❌ 否決 → PM 詢問理由（自由文字 reply）+ 寫日誌
  - 💬 重議 → PM 開第二輪會議

**設計原則**：簽核應該 < 60 秒看完。如果 Craig 每次要花 10 分鐘讀 transcript，這個系統會被放棄。

### 3.5 議題類型對照表（`council_routing.yaml` 範例）

```yaml
topics:
  網站架構變更:
    召集: [UX, Design, Frontend, Backend, SEO]
    主席: PM
    必出席: [UX, Frontend]

  視覺微調:
    召集: [Design, Frontend]
    主席: PM
    必出席: [Design]

  內容策略:
    召集: [SEO, Editor, Marketing, Curator]
    主席: PM
    必出席: [SEO, Editor]

  新藏品上架:
    召集: [Curator, Librarian, Editor, SEO, Compliance]
    主席: PM
    必出席: [Curator, Librarian]

  維運事件:
    召集: [SRE, Backend, DevOps]
    主席: SRE  # 例外：技術事件由 SRE 主持
    必出席: [SRE]
```

---

## 4. Discord 頻道結構

依 Category 分組（** = 新增）：

📋 **Council 議事**
- `#council-topics` ** — 議題池
- `#council-meetings` ** — 議事 thread 工作區
- `#council-decisions` ** — 待簽核提案 + 已決議歸檔

🎨 **Product 產品**
- `#ap-ux` **
- `#ap-design`（沿用，原 `#ap-web-design`）
- `#ap-frontend`（原 `#ap-web-dev`，拆分後）
- `#ap-backend` **

📝 **Content 內容**
- `#ap-seo` **
- `#ap-editor` **
- `#ap-marketing`（沿用）

⚙️ **Operations 維運**
- `#ap-sre` **
- `#ap-alerts` ** — 告警獨立頻道
- `#ap-deploy` **（Phase 2）
- `#ap-compliance` **（Phase 2）

🏛️ **Domain 骨董**
- `#ap-curator` **
- `#ap-knowledge` **

📊 **Strategy 策略**
- `#ap-research` **（Phase 2）
- `#ap-feedback`（沿用）

🪪 **Meta**
- `#ap-pm`（沿用）
- `#ap-decisions-log` ** — append-only 決議歷史
- `#meta-framework` **（Phase 3）

---

## 5. 簽核分級制度

### Tier 1：Craig 必須簽核
- 網站架構性變更
- 品牌方向 / Logo / 設計系統大改
- 對外公開內容（首頁、Hero、品牌敘事）
- 新功能上線
- 對外宣稱（鑑定服務聲明、品牌承諾）
- 跨 Agent 衝突無法調解時

### Tier 2：PM 可授權執行（事後通報 Craig）
- SEO meta / schema 微調
- 既有內容文案優化
- 知識庫條目新增 / 編輯
- 視覺微調（不動架構）
- 社群日常貼文（在已批准 tone 與主題範圍內）

### Tier 3：Agent 自主執行
- SRE 例行健檢與告警
- Curator 例行品質審核
- Librarian 條目入庫與索引
- Backend 例行配額監控
- Research 排程性掃描

**漸進原則**：Phase 1 寧可保守（更多事走 Tier 2），熟練後再開放到 Tier 3。

---

## 6. 框架可複製性設計

### 6.1 Core 模組（可複製到所有 Side Project）

**協調層**
- PM Agent 模板（議事協定、結構化、衝突仲裁）
- Feedback PM 模板（每日彙整、提案推送）
- Chief of Staff 模板（Phase 3）

**通用 Agent 骨架**
- UX、Frontend、Backend、SEO、Marketing、SRE、DevOps
- Compliance Guardrail 骨架（規則本身要替換）
- Market Research 骨架（查詢主題要替換）

**協作協定**
- Council Pattern（兩階段議事 + PM 整合）
- 簽核分級
- 結構化提案格式
- Discord 頻道命名規範

**基礎設施**
- Discord Bot 啟動模板（`ap_org_bot.py` 模板化）
- Headless Claude Code 呼叫封裝
- Notion 決策日誌 schema

### 6.2 AP-specific 模組（每個專案重寫）

- **Curator** + **Librarian**（領域知識守門員）
- **Editor 調性段**（品牌語氣）
- **Design 視覺段**（品牌色票、字體）
- **SEO 詞彙段**（領域長尾）
- **Compliance 規則段**（法律 / 產業禁區）

### 6.3 抽 Template 的具體做法

1. **目錄結構**
   ```
   org_framework/
   ├── core/
   │   ├── agents/         # 通用 Agent 抽象類
   │   ├── council/        # 議事協定
   │   ├── signoff/        # 簽核機制
   │   └── infra/          # Bot 啟動、Notion、Discord 封裝
   └── domain/
       └── ap/
           ├── agents/     # Curator, Librarian
           ├── prompts/    # 領域 prompts
           └── config/     # routing.yaml, channels.yaml
   ```

2. **System Prompt 模板化**
   - 每個 Agent 的 prompt = `[Core 段] + [Domain 段]`
   - Core 段定義「這個角色的職責結構」
   - Domain 段填入「在這個專案的具體調性與規則」

3. **配置文件驅動**
   - `channels.yaml`：Discord 頻道清單
   - `agents.yaml`：Agent 名冊與啟用狀態
   - `council_routing.yaml`：議題類型對照表
   - `signoff_tiers.yaml`：簽核分級

4. **共用 Notion 元件**
   - 決策日誌 DB（標準欄位）
   - 議題池 DB
   - Agent 工作頁

5. **版本控管**
   - 每個 template semver 標記
   - 新專案 fork 時鎖定版本
   - core 升級時各專案手動升級（不自動推送）

---

## 7. 實作 Roadmap

### Phase 1（4–6 週）：補齊核心執行層

**Week 1–2：基礎設施與議事協定**
- 重構 `ap_org_bot.py`：拆 `core/` + `domain/ap/`
- 建立 `#council-topics` / `#council-meetings` / `#council-decisions` 三頻道
- 實作議事兩階段狀態機
- 實作簽核 UX（Discord Embed + Reaction handler）
- 寫 `channels.yaml` / `agents.yaml` / `council_routing.yaml`

**Week 3–4：Product Tier 補齊**
- 新增 UX Agent（系統 prompt + 頻道）
- Design Agent 窄化（移除互動相關職責）
- 拆分 Frontend / Backend Agent（原 Dev 一拆二）

**Week 5–6：Content Tier + Domain**
- 拆分 SEO / Editor（從 Marketing 中抽出）
- Marketing 窄化
- 新增 Curator + Librarian
- 新增 SRE Agent
- 跑 2 週實戰，由 Feedback PM 觀察並優化

**Phase 1 Done 條件**
- [ ] 一場完整議事流程跑通（Craig 拋議題 → 5 個 Agent 議事 → PM 提案 → Craig 簽核）
- [ ] Curator 自動審核 Gemini 鑑定的流程跑通
- [ ] SRE 心跳監控全綠
- [ ] Notion 決策日誌累積至少 10 筆

### Phase 2（4–6 週）：增強維運與策略

- DevOps Agent（CI/CD、release notes 自動化）
- Compliance Guardrail（發布前 gate）
- Market Research Agent（每週 Brief）
- Notion 決策日誌完整化（加入連結到原 Discord thread）
- 開始畫 Core / Domain 邊界

### Phase 3（持續）：模組化 + 複製驗證

- Chief of Staff Meta-PM
- Email/CRM Agent
- Analytics Agent
- 將 Core 模組抽出為獨立 repo（`org-framework-core`）
- 啟動第二個 Side Project（精品選物 / 數位訂閱）驗證複製性

---

## 8. 工具與 MCP 預告（Task C 展開）

### 8.1 Cowork 端（Craig 個人工作流）
- **GitHub MCP**：PR、issue、Actions 監控
- **Linear / Notion DB**：任務追蹤（Notion 已連，可深用）
- **Google Search Console MCP**：SEO 數據查詢
- **Gmail**（已連）：用於議題進來時通知、簽核推播

### 8.2 Claude Code 端（`ap_org_bot.py` 工具鏈）
- **GitHub MCP**：Frontend / Backend / DevOps 三 Agent 共用
- **Notion MCP**：PM 決策日誌、Librarian 知識庫
- **Figma MCP**：Design / UX 共用
- **Google Search Console / GA4 MCP**：SEO / Analytics
- **自建工具**：
  - Gemini Quota Monitor
  - Discord Bot Heartbeat
  - GAS Deployment Helper

### 8.3 模組化考量
- MCP 配置也應該由 `mcp.yaml` 驅動，不寫死在 Agent prompt 中
- 每個 Agent 宣告「需要的 MCP 清單」，啟動時動態組合

> 詳細配置與 ROI 分析在 Task C 展開。

---

## 9. 風險與權衡

### 9.1 主要風險

**API 成本**：每次議事 4–6 個 Agent × 2 階段 = 顯著 token 消耗。
- 緩解：第一輪 Haiku、最終整合 Sonnet/Opus、議題分級（小事不開會）

**Craig 過載**：簽核仍會集中在 Craig。
- 緩解：嚴格分 Tier、Tier 2 改為事後通報、批次簽核（每天 1–2 次）、簽核 UX 設計成 < 60 秒

**Agent 幻覺擴散**：PM 整合多 Agent 意見時，若某個 Agent 幻覺，可能被當成事實寫入提案。
- 緩解：Curator 與 Compliance 做事實核對 gate；提案中保留「依據來源」欄位；高風險議題要求 Agent 提供 citation

**框架過度設計**：17 個 Agent 對 Side Project 太多。
- 緩解：Phase 1 嚴格控制在 10 個 Agent 內，邊跑邊看；可以把 Editor 暫時併入 SEO，Librarian 暫時併入 Curator

**Discord 訊息淹沒**：頻道一多就難以追蹤。
- 緩解：Category 分組、`#ap-decisions-log` 集中查詢、Notion 為長期儲存

### 9.2 須避免的反模式

- ❌ **「全員出席」每場會議** → 高成本、低品質。改：依 routing 表精準召集
- ❌ **「PM 變橡皮圖章」** 只整合不提觀點 → 改：PM 必須在提案中寫明自己的判斷
- ❌ **「Craig 不簽核就不執行」** 變成集權瓶頸 → 改：嚴格分 Tier，多放權給 Tier 3
- ❌ **「Domain 邏輯混進 Core」** 未來複製困難 → 改：嚴守 Core/Domain 邊界，code review 時把關
- ❌ **「Agent 各說各話」** PM 只是貼上不整合 → 改：PM prompt 中明確要求「找出共識點與分歧點」

---

## 10. 給 Claude Code 的實作切入點

當你拿這份文件去找 Claude Code 討論時，建議從以下任務開始（依優先級）：

### 第一順位：基礎設施（Week 1–2）
1. 重構 `ap_org_bot.py`：建立 `core/` 與 `domain/ap/` 目錄
2. 把現有 PM/Design/Dev/Marketing 的 prompts 抽成 `domain/ap/prompts/*.md`
3. 建立 `channels.yaml`、`agents.yaml`、`council_routing.yaml` 三個配置文件
4. 實作議事兩階段協定的狀態機
5. 實作簽核 Embed + Reaction handler

### 第二順位：補新 Agent（Week 3–6）
6. 新增 UX Agent + Curator Agent 兩個試點（成本最低、最能驗證新架構）
7. 把 Dev Agent 拆成 Frontend / Backend
8. 把 Marketing Agent 拆成 SEO / Editor / Marketing
9. 新增 SRE Agent + Librarian Agent

### 第三順位：穩定與觀察（Week 5–6）
10. Feedback PM 加入新 Agent 工作頻道掃描
11. 建立 Notion 決策日誌
12. 跑 2 週實戰，產出 retrospective

### 給 Claude Code 的 prompt 模板建議

```
我有一份 Multi-Agent ORG 設計藍圖（附後）。請基於這份藍圖：

1. 評估目前 ap_org_bot.py 的程式結構，提出重構方案
2. 設計 core/ 與 domain/ap/ 的具體目錄結構與檔案清單
3. 寫出 council_protocol 兩階段議事的狀態機 pseudo code
4. 列出 Phase 1 第一週需要產出的具體檔案清單（含每個檔案要實作的 function 與職責）

藍圖：[貼上本文件]
```

---

## 附錄 A：與現有架構的差異對照

| 項目 | 現況 | 擴展後 |
|---|---|---|
| Agent 數 | 5（PM, Design, Dev, Marketing, Feedback PM） | Phase 1 達 12，Phase 2 達 15 |
| 頻道數 | 5 | Phase 1 達 14，Phase 2 達 19 |
| 後端維運 | 無主 | Backend + SRE |
| 知識資產 | 無治理 | Curator + Librarian |
| 議事協定 | 隱性（靠 Craig 橋接） | 顯性（Council Pattern + 簽核 UX） |
| 可複製性 | 程式與 prompt 混雜 | Core/Domain 切分，配置驅動 |

## 附錄 B：v1.0 之後的開放問題

- [ ] 第二輪辯論的「收斂條件」如何設計？（避免無限對話）
- [ ] Agent 主動發起議題的權限要不要開放？（目前只有 Craig / Feedback PM / Research）
- [ ] 若同時有多個議題，PM 的議題優先級排序機制？
- [ ] 跨 Side Project 共用的「組織記憶」（Craig 的偏好、決策歷史）要存哪？
- [ ] Agent 之間的「彼此評價」機制是否值得做？（如 UX 評價 Design 的視覺是否回應了線框圖）

---

**版本歷史**
- v1.0（2026-04-27）：初版藍圖

**下一步**
- 任務 C：工具推薦與 MCP 規劃（Cowork 端 + Claude Code 端 + 可複製性的 MCP 配置）
