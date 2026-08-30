# Phase A 啟用設定指引 — Bot 寫入 Notion DBs

> **狀態**：程式碼已完成（`scripts/notion_writer.py` + ap_org_bot.py / ap_discord_bot.py 整合），等你做完以下三步就能啟用。
>
> **設計**：Phase A 是 **opt-in**——`.env.antique` 裡沒設 `NOTION_API_KEY` 時，所有 Notion 寫入會被跳過，Bot 行為跟啟用前 100% 一致。**安全性**：可以隨時開關，啟用後若有問題清掉 key 即可關掉。

---

## Phase A 整合點總覽（已完成）

| Bot | 觸發事件 | 寫入 Notion DB | 函式 |
|---|---|---|---|
| **ap_org_bot** | Feedback PM 產出提案（11:00 / 20:00） | Topics DB | `create_topic()` |
| **ap_org_bot** | Marketing Agent 完成輸出 | Content Calendar DB | `create_content_calendar()` |
| **ap_org_bot** | Auto-Dev 完成（commit + push） | Decisions DB | `create_decision()` |
| **ap_discord_bot** | 鑑定失敗 | Authentication Log DB | `create_authentication_log()` |
| **ap_discord_bot** | 鑑定退回（仿品） | Authentication Log DB | 同上 |
| **ap_discord_bot** | 鑑定成功 | Authentication Log DB | 同上 |

---

## 啟用三步驟

### Step 1：建立 Notion Internal Integration

> 為什麼要新建：Cowork 的 Notion 連線是 OAuth，Bot 是另一個 process 沒辦法共用。Bot 需要自己的 internal integration token。

1. 開啟 https://www.notion.so/my-integrations
2. 按 **+ New integration**
3. 命名：`AP Bot Internal Integration`
4. **Associated workspace**：選 **Craig Lyu's Notion**（AP DBs 所在 workspace）
5. **Type**：Internal
6. 建立後，按 **Show** 複製 **Internal Integration Token**（`secret_xxxxxxxxxxxxx` 格式）
7. **保存好**——下一步要用

### Step 2：把 Integration 加到 8 個 AP DBs

對 Craig Lyu's Notion 的這些頁面，**每個都要做一次**：

#### 路徑：Commerce Lab → Active Projects → 🏛️ Antique Pavilion (AP) — Project Hub

打開 AP Project Hub → 看到 8 個 sub-databases：

1. Topics 議題池
2. Decisions 決策日誌
3. Knowledge Base 骨董知識庫
4. Authentication Log 鑑定原始紀錄
5. Content Calendar 內容排程
6. Incidents 事件紀錄
7. Research Briefs 市場 Brief
8. Agent Prompts Prompt 版本控管

#### 對每個 DB 做：

1. 進入 DB
2. 右上角 **`···`** → **Connections** → **Add connection**
3. 找 `AP Bot Internal Integration` → 點選加入

> **效率小技巧**：實際上你只要對 **Commerce Lab 頂層頁** add connection，所有子頁（含 8 個 DB）會自動繼承權限。但保險起見，建議至少對 **AP Project Hub** add 一次。

### Step 3：填 NOTION_API_KEY 到 .env.antique

```bash
cd "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion"
nano .env.antique
```

找到這一行（目前是註解狀態）：

```
# NOTION_API_KEY=
```

改成（把 `secret_xxx` 換成 Step 1 拿到的 token）：

```
NOTION_API_KEY=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

存檔（Ctrl+O Enter, Ctrl+X）。

### Step 4：重啟兩個 Bot

```bash
# 停掉舊 bot
tmux kill-session -t ap

# 重啟
bash start_bots.sh
```

或單獨啟動 ORG Bot：
```bash
python3 -u scripts/ap_org_bot.py
```

---

## 驗證 Phase A 上線成功

### 驗證 1：smoke test notion_writer 模組

```bash
cd "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion"
python3 scripts/notion_writer.py
```

預期看到：
```
NOTION_API_KEY set: True
DB Topics:           62205b5f-4923-4efa-8ece-1250d0c7b5a9
DB Decisions:        a7616e26-3e68-46d7-8e6f-acb33ebd7357
...

=== Smoke test: 寫一筆 dummy Topic ===
[notion] ✅ Topic created: [notion_writer self-test] 2026-04-...
Result: <page_id>
```

去 Notion Topics DB 看，應該多一筆 `[notion_writer self-test] ...`，可手動刪除。

如果看到：
- `NOTION_API_KEY set: False` → .env.antique 還沒填或格式錯
- `HTTP 401: API token is invalid` → token 拼錯了
- `HTTP 404: Could not find database` → 該 DB 還沒 add integration

### 驗證 2：跑 Marketing 測試

去 Discord `#ap-marketing`：
```
為一件「清乾隆粉彩穿花鳳紋瓶」寫一則 Instagram caption
```

Bot 出 Embed 後，去 Notion **Content Calendar DB** 看，應該多一筆 `[T-XXXXXXXX-XXXXXX] ...`。

Bot terminal log 應該出現：
```
[notion] ✅ Content Calendar created: [T-XXXXXXXX-XXXXXX] ...
```

### 驗證 3：跑 Feedback PM 測試

任何頻道：
```
/poll-now
```

如果 #ap-feedback 有累積訊息，Feedback PM 跑完後，每筆 P0-P3 提案都會寫到 Topics DB。

---

## 失敗應對

### 症狀 A：`HTTP 401 Unauthorized`
→ `NOTION_API_KEY` 格式錯，重新從 Notion integration 頁面複製。

### 症狀 B：`HTTP 404 Could not find database`
→ 對應的 DB 還沒 add integration。回到 Step 2 對該 DB 加。

### 症狀 C：`HTTP 400 validation_error`
→ schema property 名稱不符。可能 DB schema 有手動修改過。對照 notion_writer.py 的欄位定義。

### 症狀 D：Bot 啟動 crash 因 import notion_writer 失敗
→ notion_writer.py 還在 scripts/ 目錄嗎？路徑問題請查 ap_org_bot.py 第 60 行附近的 import 邏輯。

### 症狀 E：寫入很慢（每次 5+ 秒）
→ Notion API 偶爾慢，timeout 設 15s。如果常態慢，可能是企業網路代理問題。

---

## 退場策略（萬一 Phase A 不穩需要關閉）

```bash
nano .env.antique
# 把 NOTION_API_KEY=secret_xxx 改回 # NOTION_API_KEY=（前面加 #）
# 存檔

# 重啟 bot
tmux kill-session -t ap
bash start_bots.sh
```

Bot 行為立刻回到 Phase A 啟用前狀態，所有 Notion 寫入會被跳過。**已經寫進 Notion 的 entries 不會被刪除**（保留歷史）。

---

## 之後的延伸（不在 Phase A 範圍內）

- **Approval workflow**：目前只有 Feedback PM 提案 → Topics。Craig 在 Discord 按 ✅ 後**還沒**自動寫 Decisions（需要在 button handler 加 hook）。下個 sprint 補。
- **Curator review flow**：Authentication Log 寫進去後是 `未審`，要有 review 機制把通過的同步到 Knowledge Base。下個 sprint 補。
- **Bidirectional sync**：目前只是 Bot → Notion 單向。Notion → Bot（如 Notion 改 task status，Bot 收到通知）尚未實作。

---

*Phase A 程式碼於 2026-04-28 完成。需 Craig 手動啟用上面三步驟。*
