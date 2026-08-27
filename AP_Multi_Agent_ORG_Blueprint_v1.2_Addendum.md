---
id: ap_multi_agent_org_blueprint_v1.2_addendum
type: proposal
title: AP 多 Agent 組織擴展設計藍圖 — v1.2 增補提案（藝術維度 + 穩健性）
created: 2026-05-14
last_updated: 2026-05-14
schema_version: 1
status: draft — 待 Craig Tier 1 簽核
author: Craig × Claude
upstream: AP_Multi_Agent_ORG_Blueprint_v1.1.md
sign_off_tier: 1
---

# AP 多 Agent 組織擴展設計藍圖 — v1.2 增補提案

> 本文件是 Blueprint v1.1 的**增補（addendum）**，不取代 v1.1。
> 經 Craig Tier 1 簽核後，相關章節合併回主 Blueprint，本檔歸檔。
>
> **緣起**：2026-05-14 Craig 回到 AP 專案，要求 (1) 回顧目前 ORG agent 名冊
> (2) 討論穩健性與開發效率的優化空間 (3) 補上專案目前欠缺的「設計、美學、
> 文學、藝術」維度，以提升 AP 的藝術性與呈現品質。
>
> **v1.2 的三個核心主張**：
> 1. 新增三個常駐 Agent — **鑑賞（Connoisseur）／ Editor（文學編輯）／ 美學總監
>    （Art Director）** — 把目前嚴重不足的藝術維度補上。
> 2. 把 v1.1 Phase 1 規劃但未落地的 **SRE / Backend / Compliance gate** 重新排序，
>    並把 Council 頻道接通，補上結構性穩健缺口。
> 3. 正式重審 v1.1 §0.5 的「Phase 1 ≤ 10 Agent」上限 — 因為當初的前置條件
>    （ORG 基礎設施跑穩）在 Sprint 0–4 已達成。

---

## 目錄

0. [v1.2 變更摘要（TL;DR）](#0-v12-變更摘要tldr)
1. [現況回顧 — 你現在有什麼](#1-現況回顧--你現在有什麼)
2. [藝術維度 — 三個新常駐 Agent](#2-藝術維度--三個新常駐-agent)
3. [穩健性與開發效率優化](#3-穩健性與開發效率優化)
4. [Agent 數量上限的重審](#4-agent-數量上限的重審)
5. [config / 程式碼的具體變更建議](#5-config--程式碼的具體變更建議)
6. [建議實作優先序](#6-建議實作優先序)
7. [Tier 1 待 Craig 簽核清單](#7-tier-1-待-craig-簽核清單)
8. [附錄 — 與 CLAUDE.md / v1.1 一致性檢查](#8-附錄--與-claudemd--v11-一致性檢查)

---

## 0. v1.2 變更摘要（TL;DR）

| # | 變更 | 類型 | 影響面 |
|---|---|---|---|
| 1 | 新增 **鑑賞 Agent（Connoisseur）** | 新 Agent | 藝術史脈絡、美學論述、流派定位 — 目前完全無人負責 |
| 2 | 落地 **Editor Agent（文學編輯）** | 既有規格實作 | v1.1 §2.8 規格已存在，`class: null`，本次拉高文學性權重後實作 |
| 3 | 新增 **美學總監 Agent（Art Director）** | 新 Agent | 跨 Designer/UX/Frontend 的整體藝術一致性裁決層；吸收升格現有 Opus 設計裁決流 |
| 4 | 既有 `curator` 更名為 `authenticator`（鑑定品管） | 命名調整 | 騰出「Curator／策展」語意給藝術角色；牽動 config / 檔名 / CLAUDE.md |
| 5 | **SRE Agent** 排序拉到最前 | 既有規格實作 | v1.1 自標「補結構性風險」，目前兩支 bot 零心跳監控 |
| 6 | **Backend Agent** 從 Dev 拆分 | 既有規格實作 | v1.1 自標「補目前最大缺口」 |
| 7 | **Compliance Guardrail** 從 Phase 2 拉前到 Phase 1 | 階段調整 | CLAUDE.md §5 把「鑑定真品聲明」列 Tier 1 敏感，對外發佈無 gate = 裸奔 |
| 8 | 接通 `#council-*` 三個頻道（id 仍為 0） | config 修正 | 9-state daemon 程式碼 Sprint 3/4 已 done，頻道未接 = 機制空轉 |
| 9 | 重審 v1.1 §0.5「Phase 1 ≤ 10 Agent」上限 | 政策調整 | 建議調整為「同時 hot ≤ 12」+ 分批啟用 |

**一句話**：AP 的工程／維運骨架在 Sprint 0–4 已經領先，但 agent 名冊本身是
「工程重、藝術輕」。v1.2 要做的是讓骨架長出**藝術的肌肉**，同時補完當初規劃卻
還沒落地的穩健性角色。

---

## 1. 現況回顧 — 你現在有什麼

### 1.1 目前 `active: true` 的 9 個 Agent

| Agent | 層 | 觸發方式 | 它幫你加速什麼 |
|---|---|---|---|
| PM | 協調 | `!agenda` / Council | 議題結構化、召集議事、整合提案 |
| Feedback PM | 協調 | cron 11:00 / 20:00 | 每日掃頻道找重複問題與卡關 |
| Designer | 執行 | `#ap-design` 任何訊息 | 品牌視覺（配色票／字體／留白） |
| Dev | 執行 | `#ap-frontend` 任何訊息 | 前端 HTML/CSS/JS 實作 |
| Marketing | 執行 | `#ap-marketing` 任何訊息 | 社群與轉化路徑 |
| Curator | 領域 | CLI（`ap_curator_runner.py`） | 鑑定品質把關（rule-based，未接 LLM） |
| Auto-Dev | 機制 | 按鈕（核准視覺提案後） | 前端提案的自動實作 |
| GAS-Dev | 機制 | 按鈕（非前端提案） | 後端提案的自動實作 |
| Opus Design Researcher | 領域 | Opus 裁決流第一棒 | 高衝突設計議題的 DD 包裝 |

真正在「加速開發」的主力是 **Auto-Dev / GAS-Dev**（按鈕觸發實作）加上 **PM**
的議題收斂。

### 1.2 結構診斷 — 骨架很強，肌肉沒長出來

**好的部分**：工程／維運骨架在 Sprint 0–4 已落地且測試齊全 — strangler-fig
重構（1288→42 模組）、Council 9-state daemon、budget governor、audit runner
8 條規則、visual regression baseline。這層比 v1.1 撰寫時想像得更成熟。

**問題一：Phase 1 規劃的角色，肌肉沒長出來。**
v1.1 §2 規劃的 UX、Backend、SEO、Editor、SRE、Librarian 六個，`agents.yaml`
裡 `class` 全是 `null` — 規格寫好了，人沒招。這造成兩條 pipeline 是斷的：

- **內容線** `Curator → Librarian → Editor → SEO → 上站`：後三棒都沒建，
  Curator 放行的藏品流不到「能發佈的網站內容」。
- **設計線** `UX → Design → Frontend`：UX 沒建，Designer 與 Dev 之間缺
  「使用者旅程／線框」這層上游。

**問題二：藝術維度結構性不足（本次的主軸）。**
9 個 active agent 裡只有 Designer 碰美學，而且被刻意窄化成「Brand Visual
Identity」（配色票、字體、留白）。能扛藝術性的角色現況是：

- **Editor**（文化編輯、書卷氣、典故）— 規劃了，沒建。
- **Curator** — 名字會誤導。它在 AP 是「鑑定品質守門員」（QA），不是博物館
  意義的策展人。它的 prompt 明寫「你**不**寫品名／故事／行銷文字」。
- 結論：**美學論述、藝術史脈絡、「這件為什麼美」完全沒有 agent 在管。**
  Craig 的直覺是對的 — 這是一個結構性的空缺，不是微調。

---

## 2. 藝術維度 — 三個新常駐 Agent

> Craig 已選定：藝術維度以**常駐 Agent**（channel-bound）形式承載，
> 而非 Council 諮詢席位。以下三個 Agent 規格沿用 v1.1 §2 的欄位格式。

### 2.1 鑑賞 Agent — Connoisseur（鑑賞家）[AP，新增]

| 欄位 | 內容 |
|---|---|
| Tier | Domain |
| 分類 | AP-specific |
| Phase | 1（v1.2 新增） |
| key | `connoisseur` |
| model | `claude-sonnet-4-6` |

**為何重要**
Curator 管「判讀正不正確、與既有條目一致不一致」；鑑賞 Agent 管「這件的
**藝術價值**在哪」。前者是品管，後者是學養。沒有後者，AP 的藏品頁永遠停在
「物件描述」，到不了「蘇富比圖錄質感」。這是 AP 藝術性的核心載體之一。

**職責**
- 為通過 Curator 的藏品撰寫**藝術史定位**：流派、窯口／作坊脈絡、與名品的對話
- 美學論述：器型、紋飾、釉色、工藝的鑑賞要點（「為什麼這件值得看」）
- 跨藏品的主題策展建議（thematic grouping）— 為未來「主題展頁」鋪路
- 為 Editor 提供有依據的素材底稿（鑑賞 Agent 給「料」，Editor 給「文」）
- 對 Designer / 美學總監提供單件藏品的視覺呈現建議（這件適合什麼留白、什麼背景）

**職責疆界（避免與既有 Agent 重疊）**
- **不**做鑑定真偽（Gemini）、**不**下 Curator 四選一判定（Curator）
- **不**寫最終發佈文案（Editor）、**不**做品牌視覺規範（Designer）
- 只產出「藝術史與美學的判斷與素材」，是上游養分供應者

**System Prompt 方向**
> 你是吉寶軒（AP）的鑑賞 Agent（Connoisseur）。你的角色是骨董的鑑賞家與
> 藝術史顧問，對標故宮研究員、蘇富比 specialist 的眼力與筆力。你的工作是
> 為已通過鑑定品管的藏品，補上「藝術史定位」與「美學論述」。原則：
> (1) 每個論述必有依據 — 流派、窯口、年代特徵、可對照的名品，不可憑空抒情。
> (2) 保留性措辭 — 用「應屬／近於／可參照」，骨董鑑賞本有不確定性。
> (3) 書卷氣而不炫學 — 點到典故即可，不堆砌術語。
> (4) 你給「料」不給「成品文」— 最終文案是 Editor 的工作，你提供結構化素材。
> 輸出格式：藝術史定位 / 鑑賞要點（器型・紋飾・工藝）/ 可對照名品 /
> 主題策展建議 / 視覺呈現建議。

**Discord 頻道**：`#ap-connoisseur`

**觸發**
- 事件驅動：Curator 判定 `通過` 後（接力）
- 被 PM 召集（議題類型：內容策略、新藏品上架）
- 排程：每月一次「主題策展機會」掃描（找出可成組的藏品）

**協作介面**
- 上游 ← Curator（通過的藏品）、Librarian（既有知識條目）
- 下游 → Editor（撰文素材）、Designer / 美學總監（單件呈現建議）、SEO（長尾題材）

**KPI**
- 鑑賞論述的依據完整度（每篇可對照名品 ≥ 1）
- Editor 採用率（鑑賞素材被 Editor 實際使用的比例）
- 主題策展建議的成案數
- Craig 對藝術論述的駁回率（健康區間 10–25%）

---

### 2.2 Editor Agent — 文學編輯 [AP 調性 + Core 結構，落地 v1.1 §2.8]

| 欄位 | 內容 |
|---|---|
| Tier | Content |
| 分類 | Core 結構 + AP 調性 |
| Phase | 1（v1.1 已規劃，v1.2 落地並拉高文學性權重） |
| key | `editor` |
| model | `claude-sonnet-4-6` |

**v1.2 對 v1.1 §2.8 的調整**
v1.1 的 Editor 偏「反向把關」（避免廣告腔、形容詞不堆疊）。v1.2 把它的
**文學性權重正向拉高**：不只是「不要寫壞」，而是主動要求文氣、典故的調度、
古典中文的回響。這是 AP「中文書卷氣」定位的真正載體。

**職責**
- 把鑑賞 Agent 的素材底稿，寫成可發佈的藏品介紹文（書卷氣、有依據、有文氣）
- 文化長文：朝代源流、流派、典故、鑑賞指南
- 品牌敘事文案（首頁、關於頁）的文學調性把關
- 品牌調性檢核：禁用詞表、形容詞密度、段落節奏

**System Prompt 方向**
> 你是吉寶軒（AP）的文學編輯（Editor）。文風定位：書卷氣的中文，有文化厚度
> 但不炫學，對標蘇富比圖錄的中文質感。你的工作是把鑑賞 Agent 給的素材，
> 寫成讀起來有「文氣」的成品文。原則：
> (1) 禁廣告腔 — 「絕世」「典藏級」「天下無雙」這類詞禁用。
> (2) 形容詞節制 — 每段最多 2 個；用具體取代浮誇。
> (3) 事實必有依據 — 向 Librarian / 鑑賞 Agent 查證，不自行杜撰。
> (4) 文氣優先 — 段落短促、行雲流水；典故點到為止，服務於物件而非炫學。
> 每篇結尾附「調性檢核」自評（禁用詞 / 形容詞密度 / 依據來源）。

**Discord 頻道**：`#ap-editor`

**觸發**
- 鑑賞 Agent 完成素材後（接力）
- SEO Agent 委派撰文
- 被 PM 召集（品牌敘事議題）

**協作介面**
- 上游 ← 鑑賞 Agent（素材）、SEO（關鍵字 brief）、Librarian（事實核對）
- 下游 → Frontend（上稿）、Marketing（社群短文改寫）、Compliance（發佈前掃）

**KPI**
- 發稿節奏（目標 4–8 篇/月）
- 品牌調性檢核通過率
- 平均閱讀完成率
- 來自該文的搜尋流量

---

### 2.3 美學總監 Agent — Art Director [Core 結構 + AP 調性，新增]

| 欄位 | 內容 |
|---|---|
| Tier | Product（協調性質） |
| 分類 | Core 結構 + AP 調性 |
| Phase | 1（v1.2 新增） |
| key | `art_director` |
| model | `claude-sonnet-4-6`（高衝突議題 Opus escalate） |

**為何重要**
Designer 管「品牌視覺規範是否被遵守」（配色票、字體），是**規則合規層**。
但「整個站看起來有沒有藝術性、各頁之間的視覺敘事連不連貫」目前沒有人管。
美學總監是這個**整體藝術一致性的裁決層**，它站在 Designer / UX / Frontend
之上，問的問題是「這樣呈現，配得上這些藏品嗎？」

**與現有 Opus 設計裁決流的關係**
目前 Opus Design Researcher 是「一次性的裁決流第一棒」— 每次高衝突議題重新
spawn。v1.2 建議把它**升格為美學總監的常設能力**：美學總監平時用 Sonnet
做日常一致性審查，遇到需要拍板的高衝突美學議題時，走既有的 `OPUS_ESCALATE`
路徑（沿用，不重造）。Opus Design Researcher 的 DD 包裝邏輯保留，改由美學
總監持有。

**職責**
- 全站視覺敘事一致性審查（跨頁，不只單頁）
- 為 Designer / UX 出稿前訂「美學意圖」（這一頁要傳達什麼氣質）
- 主持「視覺微調」「網站架構變更」議題中的美學收斂
- 維護 AP 的美學基準線（對標 Sotheby's Asia / 故宮，定期重校）
- 高衝突美學議題的 Opus 裁決包裝（接手 Opus Design Researcher 職能）

**System Prompt 方向**
> 你是吉寶軒（AP）的美學總監（Art Director）。你不畫具體視覺（那是 Designer），
> 不做使用者旅程（那是 UX）— 你負責的是「整體藝術性與跨頁視覺敘事的一致性」。
> 你的判準錨定在 Sotheby's Asia、Christie's HK、中國嘉德、故宮精品的圖錄質感。
> 原則：(1) 先問「意圖」再看「執行」— 每次審查先確認這一頁/這個元件要傳達
> 的氣質，再評執行。(2) 留白與節制優於堆疊。(3) 跨頁一致 — 你看的是整本
> 圖錄，不是單張。(4) 高衝突且需拍板的美學方向，用 `OPUS_ESCALATE:` 上呈
> Craig，不自行拍板。輸出格式：美學意圖 / 跨頁一致性診斷（P0–P3）/
> 收斂建議 / 是否需 Opus 裁決。

**Discord 頻道**：`#ap-art-director`

**觸發**
- 被 PM 召集（議題類型：視覺微調、網站架構變更）— 建議列「必出席」
- 新頁面上線前 aesthetic gate（與 Designer 的 visual audit 並行，分工：
  Designer 查「規範」，美學總監查「整體藝術性」）
- `/audit` slash command 的美學維度

**協作介面**
- 上游 ← PM、鑑賞 Agent（藏品的呈現需求）
- 下游 → Designer（視覺規範執行）、UX（旅程承接）、Frontend（實作）、
  Craig（Opus 裁決請求）

**KPI**
- 跨頁一致性審查通過率
- 上線後 Craig 美學駁回率（目標逐月下降）
- Opus 裁決請求數（過多 = 日常基準線沒立好）

---

### 2.4 命名調整 — `curator` → `authenticator`（Tier 1 決策）

**問題**：現有 `curator` 在 AP 做的是 QA／鑑定品質把關，但 "Curator" 在
博物館英文裡就是「策展人」。引入鑑賞 Agent 後，語意會持續打架，未來把框架
複製到別的專案時更混亂。

**建議**：把既有 `curator` 更名為 `authenticator`（中文：鑑定品管），
語意上的「策展／鑑賞」交給新的 `connoisseur`。

**這個 rename 的真實成本**（要 Craig 知情後決定）：
牽動 `agents.yaml` key、`channels.yaml`（`#ap-curator` → `#ap-authenticator`）、
`council_routing.yaml`（三處 `Curator` → `Authenticator`）、prompt 檔路徑、
agent class（`curator.py` → `authenticator.py`）、CLI runner
（`ap_curator_runner.py`）、CLAUDE.md 多處引用、`memory/` 相關檔。

**替代方案（成本較低）**：保留 `curator` key 不動，只在文件與 channel
description 明確標注「Curator = 鑑定品管，非策展」，新 agent 用
`connoisseur`。語意仍有小摩擦，但零遷移成本。

→ 兩案並陳，**Craig 拍板**（見 §7）。本文件後續章節先假設採「替代方案」
（保留 `curator`），若 Craig 選 rename 再走一次遷移 checklist。

---

## 3. 穩健性與開發效率優化

> Craig 原始需求的第二軸：增加穩健性與開發效率。以下四項都是 v1.1 已規劃、
> 但未落地或未接通的角色／機制，按「補洞的急迫性」排序。

### 3.1 SRE Agent — 優先序拉到最前（穩健性第一缺口）

**現況**：v1.1 §2.10 規劃了 SRE，`agents.yaml` 裡 `class: null`。
你目前有**兩支 Discord bot**（`ap_org_bot.py` + `ap_discord_bot.py`）、一個
Gemini API 硬上限 USD 30、GitHub Pages 對外服務 — **零心跳監控**。bot 掛了
你不會即時知道，配額爆了你事後才發現。

v1.1 自己就把 SRE 標注為「補結構性風險」。這是穩健性的第一缺口，應該排在
所有新角色之前。

**最小可行範圍（不必一次做滿 v1.1 §2.10）**：
- 兩支 bot 心跳監控（每 5 分鐘 ping，異常發 `#ap-alerts`）
- Gemini 配額追蹤（70% / 90% 預警）— 可直接讀既有 `budget_governor` ledger
- 每週日可靠性週報

### 3.2 Backend Agent — 從 Dev 拆分（v1.1 自標「最大缺口」）

**現況**：v1.1 §2.6 把 Backend 標為「補目前最大缺口」。目前 GAS / Gemini /
Discord bot 後端邏輯混在 Dev agent 與 GAS-Dev 裡，沒有一個專責後端的角色，
所有 GAS 部署的版本標籤、回滾預案、配額預警都沒有歸屬人。

**建議**：照 v1.1 §2.6 規格實作，與 SRE 一起做（兩者協作介面緊密 —
SRE 告警 → Backend 修復）。

### 3.3 Compliance Guardrail — 從 Phase 2 拉前到 Phase 1

**理由**：CLAUDE.md §5 明確把「任何對鑑定真品的聲明（『這是真品』/ 鑑定服務
措辭）」列為 **Tier 1 敏感**。AP 是一個會對外講鑑定的骨董站，目前**對外發佈
（網站／社群／電子報）完全沒有發佈前的合規 gate** — 這是法律 + 品牌的裸奔。

一旦 Editor / Marketing 開始量產對外內容（本 v1.2 正是要打通內容線），
沒有 Compliance gate 的風險會立刻放大。建議把 v1.1 §2.14 的 Compliance
從 Phase 2 拉前，與 Editor 同批上線。

**最小可行範圍**：v1.1 §2.14 的四項檢核中，先做最高風險的兩項 —
(1) 鑑定結果是否標註「僅供參考、非鑑定書」 (2) 是否有不實／誇大宣稱。

### 3.4 接通 Council 三頻道（低成本、高收益的 config 修正）

**現況**：Council 9-state daemon 的程式碼在 Sprint 3/4 已 done（`council/daemon.py`、
11:00/20:00 scheduler、RealDiscordFetcher），但 `channels.yaml` 裡
`council-topics` / `council-meetings` / `council-decisions` 的 `id` 還是 `0`。
**寫好的議事機制等於沒在跑。**

**動作**：在 Discord 建這三個頻道 → 把真實 channel id 填回 `channels.yaml`。
成本極低（一次性 config），收益是讓整套 Council Protocol 真正運轉 — 這也是
本 v1.2 新增的三個藝術 Agent 能被 Council 召集的前提。

### 3.5 開發效率 — 打通兩條斷掉的 pipeline

新增 §2 三個 Agent + 落地 SEO / Librarian 後，兩條 pipeline 才接得起來：

```
內容線（接通後）：
  Curator(通過) → 鑑賞 Agent(藝術定位素材) → Editor(成品文)
                → SEO(關鍵字/schema) → Compliance(發佈前掃) → Frontend(上稿)
              ↘ Librarian(結構化入 KB) ↗

設計線（接通後）：
  UX(旅程/線框) → 美學總監(美學意圖) → Designer(視覺規範)
              → Frontend(實作) → 美學總監(上線前 aesthetic gate)
```

效率的關鍵不是「再加更多 Agent」，而是**把已經規劃好的棒次補齊**，讓
Curator 放行的藏品能一路流到「可發佈的網站內容」，不再卡在斷點。

---

## 4. Agent 數量上限的重審

**v1.1 §0.5 寫**：Phase 1 控制在 10 個 Agent 以內，跑穩再擴張。

**現在的算術對不上**：目前 9 個 active + v1.2 新增 3 個藝術 Agent +
v1.1 Phase 1 尚未落地的 UX / Backend / SEO / SRE / Librarian 5 個 +
Compliance 拉前 = **18 個**。遠超 10。

**但 v1.1 §0.5 的前置條件已經改變**。當初設「≤ 10」是因為「ORG 基礎設施還沒
跑穩」。而 Sprint 0–4 已經把 Council daemon、budget governor、audit runner、
visual regression baseline 全部做完並測試齊全 — **「跑穩再擴張」的前置條件
已達成**。

**建議（Tier 1 決策）**：把上限從「Phase 1 ≤ 10」調整為：

- **同時 hot（active 且常被觸發）≤ 12** — 控制 Craig 的日常協調負擔
  （CLAUDE.md §11：每日協調預算 < 15 分鐘）。
- **分批啟用** — 不是 18 個一次上。按 §6 的優先序，每批 2–3 個，
  跑穩一批再開下一批（沿用 v1.1 §0.5 的漸進精神，只是放寬絕對數字）。
- **觸發方式分流** — 事件驅動 / 排程 / 按鈕觸發的 Agent（如鑑賞、Editor、
  SRE）不佔用 Craig 的即時注意力，與「任何訊息都回」的 Agent 不同重量。
  真正消耗 Craig 的是「必出席 Council + 要簽核」的部分，那才是要控管的數字。

---

## 5. config / 程式碼的具體變更建議

> 以下為「採替代方案（保留 `curator` key）」前提下的 diff-level 建議。
> 實際實作仍須各自開 ticket，本節只給落點。

### 5.1 `config/agents.yaml` — 三個新 Agent + 既有規格落地

新增 / 改動條目（節錄）：

```yaml
  # ── 藝術維度（v1.2 新增）─────────────────────────────
  - key: connoisseur
    class: ap_org_bot.agents._domain.ap.connoisseur.ConnoisseurAgent
    layer: domain
    phase: 1
    active: true            # 分批啟用：第 2 批
    prompt: connoisseur
    model: claude-sonnet-4-6

  - key: editor
    class: ap_org_bot.agents._domain.ap.editor.EditorAgent
    layer: domain           # v1.1 標 core 結構，AP 調性重，歸 domain 較準
    phase: 1
    active: true            # 分批啟用：第 2 批
    prompt: editor
    model: claude-sonnet-4-6

  - key: art_director
    class: ap_org_bot.agents._domain.ap.art_director.ArtDirectorAgent
    layer: domain
    phase: 1
    active: true            # 分批啟用：第 3 批
    prompt: art_director
    model: claude-sonnet-4-6
    notes: "吸收 opus_design_researcher 的 Opus 裁決包裝職能"

  # ── 穩健性（v1.1 規劃，v1.2 排序拉前）────────────────
  - key: sre        # active: true（第 1 批）— class/prompt 待實作
  - key: backend    # active: true（第 1 批）— class/prompt 待實作
  - key: compliance # phase 2 → 1，active: true（第 2 批）
```

`opus_design_researcher` 條目：保留但加 `notes: "職能逐步移交 art_director，
Sprint 7 後評估下線"`。

### 5.2 `config/channels.yaml` — 接通 Council + 新 Agent 頻道

- `council-topics` / `council-meetings` / `council-decisions`：把 `id: 0`
  換成 Discord 實際建好的 channel id（§3.4）。
- 新增 `#ap-connoisseur` → `agent: connoisseur`
- `#ap-editor`：v1.1 已預留條目，把 `agent: null` 改 `agent: editor`、填 id
- 新增 `#ap-art-director` → `agent: art_director`
- `#ap-sre` / `#ap-alerts` / `#ap-backend`：v1.1 已預留，填 id + 綁 agent

### 5.3 `config/council_routing.yaml` — 把藝術 Agent 納入召集名單

```yaml
  視覺微調:
    召集: [ArtDirector, Design, Frontend]
    必出席: [ArtDirector, Design]      # 美學總監列必出席

  網站架構變更:
    召集: [UX, ArtDirector, Design, Frontend, Backend, SEO]
    必出席: [UX, ArtDirector, Frontend]

  內容策略:
    召集: [SEO, Editor, Connoisseur, Marketing, Curator]
    必出席: [SEO, Editor]

  新藏品上架:
    召集: [Curator, Connoisseur, Librarian, Editor, SEO, Compliance]
    必出席: [Curator, Connoisseur, Librarian]
```

### 5.4 新增 prompt 檔（沿用既有 frontmatter 格式）

- `scripts/ap_org_bot/prompts/_domain/ap/connoisseur.md`
- `scripts/ap_org_bot/prompts/_domain/ap/editor.md`
- `scripts/ap_org_bot/prompts/_domain/ap/art_director.md`

每檔 frontmatter 比照 `designer.md` / `curator.md`：`schema_version` /
`agent` / `layer` / `loaded_by` / `prompt_version: v0.1` / `last_updated` /
`notion_page_title`。prompt body 用 §2 的「System Prompt 方向」擴寫。
同步更新 `config/prompts_versioning.yaml`。

### 5.5 新增 agent class

照 CLAUDE.md §8「Add a new agent」六步流程：drop prompt → drop agent class
（subclass `HeadlessAgent`）→ `agents.yaml` → `channels.yaml` →
`main.py` 註冊一行 → `tests/test_agents_<name>.py`。**不動 `on_message`
或任何 handler。**

---

## 6. 建議實作優先序

> 分批啟用，每批跑穩再開下一批。Sprint 編號接續 CLAUDE.md §9（Sprint 5 pending）。

| 批次 | 內容 | 為何這個順序 |
|---|---|---|
| **第 1 批**（穩健性地基） | SRE + Backend + 接通 Council 三頻道 | 穩健性第一缺口；Council 接通是後續藝術 Agent 能被召集的前提；都是 v1.1 已規劃，補洞性質 |
| **第 2 批**（內容線 + 藝術核心） | 鑑賞 Agent + Editor + Compliance | 三者一起上才接得通內容線（§3.5）；Compliance 必須與 Editor 同批，否則對外發佈裸奔 |
| **第 3 批**（設計線收口） | 美學總監 + UX | 美學總監吸收 Opus 裁決流職能；UX 補設計線上游；兩者一起讓設計線 pipeline 完整 |
| **第 4 批**（內容線收尾） | SEO + Librarian | 內容線最後兩棒；可視第 2 批跑的狀況決定是否如 v1.1 §1 所述暫併（Editor↔SEO / Librarian↔Curator） |

每批之間：跑一週 dogfooding，確認 Craig 無 post-hoc veto 再開下一批
（沿用 CLAUDE.md §5「asymmetric risk principle」）。

---

## 7. Tier 1 待 Craig 簽核清單

以下項目依 CLAUDE.md §5 屬 Tier 1，需 Craig 明確拍板後才動工：

- [ ] **T1-1**：新增三個常駐 Agent（鑑賞 / Editor / 美學總監）的方向與職責疆界 — 是否同意 §2 的切分
- [ ] **T1-2**：`curator` 是否更名為 `authenticator` — rename 案 vs 替代方案（§2.4）
- [ ] **T1-3**：Compliance Guardrail 從 Phase 2 拉前到 Phase 1（§3.3）
- [ ] **T1-4**：Agent 數量上限由「Phase 1 ≤ 10」調整為「同時 hot ≤ 12 + 分批啟用」（§4）
- [ ] **T1-5**：美學總監吸收 / 逐步取代 Opus Design Researcher 職能（§2.3）— 涉及 Opus API 預算歸屬（CLAUDE.md §6，USD 15 cap）
- [ ] **T1-6**：§6 的四批實作優先序是否採納

簽核後，本增補相關章節合併回 `AP_Multi_Agent_ORG_Blueprint_v1.1.md`（升版
v1.2），本檔歸檔；並在 `CHG_LOG.json` 留一筆。

---

## 8. 附錄 — 與 CLAUDE.md / v1.1 一致性檢查

| 檢查項 | 結果 |
|---|---|
| 技術棧未動（HTML/CSS/JS、GAS、Gemini） | ✅ 本提案只動 agent 組織層，不碰 CLAUDE.md §2 技術棧 |
| Sheets 欄位結構（CLAUDE.md §3）未動 | ✅ 無欄位增刪 |
| era 9 枚舉（CLAUDE.md §4）未動 | ✅ 鑑賞 Agent 沿用既有枚舉，不擴張 |
| prompt 不入 `.py`（CLAUDE.md §10 反模式） | ✅ §5.4 三個新 prompt 都進 `prompts/_domain/ap/*.md` |
| 新 agent 走 §8 六步流程、不動 handler | ✅ §5.5 明確沿用 |
| Hardcoded Discord ID 反模式 | ✅ §5.2 所有 id 進 `channels.yaml` |
| 成本上限（CLAUDE.md §6） | ⚠️ T1-5 涉及 Opus 預算歸屬，需 Craig 在簽核時一併確認 |
| v1.1 §0.5「≤ 10」 | ⚠️ 本提案 §4 明確提出重審，列入 T1-4 待簽核 |
| Council 9-state（v1.1 §3.6）相容 | ✅ 新 Agent 只是 routing 名單成員，不改 state machine |

---

*本增補待 Craig Tier 1 簽核。若與 CLAUDE.md 有未列出的衝突，以 CLAUDE.md 為準，
並回報 Craig。*
