<!-- CHANGE AP-BOT-LAUNCHER: local browser control center for the two AP Bots. -->

# 吉寶軒 AP 專案 — 背景服務啟動手冊

> 每次重啟電腦後，需手動在 WSL2 重啟以下服務。
> 兩個 Bot 必須**同時在線**，功能才完整。

---

## 背景服務一覽

| 服務 | 檔案 | 職責 | 必須常駐 |
|------|------|------|---------|
| **鑑定助理 Bot** | `ap_discord_bot.py` | #antique-analysis 圖片鑑定 → GAS → Gemini | ✅ |
| **ORG Bot** | `scripts/ap_org_bot.py` | PM/設計/開發/行銷 Agent + Feedback PM 排程 | ✅ |

> GAS（Google Apps Script）是 serverless，不需要手動啟動。

---

## 啟動前置確認（第一次或懷疑環境異常時）

```bash
# 1. 確認 claude CLI 可用
claude -p "test"

# 2. 確認 .env.antique 存在
ls "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion/.env.antique"
```

---

## 標準啟動流程（Web Control Center，推薦）

在 WSL2 執行：

```bash
cd "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion"
python3 -u scripts/ap_launcher_web.py
```

瀏覽器會開啟 `http://127.0.0.1:8610`；若該 port 已使用，會在 8610–8620 自動選擇。
Launcher 啟動時**不會自動啟動任何 Bot**，由你在 GUI 分別選擇：

- 鑑定助手：啟動／停止／重新啟動。
- AP ORG：啟動／停止／重新啟動。
- 啟動兩個 Bot／停止所有由 Launcher 管理的 Bot。
- 查看 PID、uptime、Discord／GAS 健康與即時遮蔽 Log。

Launcher 只監聽 loopback；它不顯示 token／secret，也不會停止原本由 tmux 或其他 terminal
啟動的外部 Bot。若要只開控制台、不自動開瀏覽器：

```bash
python3 -u scripts/ap_launcher_web.py --no-browser
```

只有在離線 UI 測試時才使用 `AP_LAUNCHER_HEALTHCHECKS=0`；正式運行維持預設值 `1`。

關閉 Launcher（Ctrl+C）時，只會停止由本次 Launcher 啟動的 Bot process group。

---

## 備用啟動流程（tmux）

### tmux（可隨時 detach，關閉 terminal Bot 繼續跑）

```bash
# 開啟新 tmux session
tmux new-session -s ap

# ── 在 tmux 內 ──

# 進入專案目錄
cd "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion"

# 開 window 1 — 鑑定助理 Bot
python3 -u ap_discord_bot.py

# 按 Ctrl+B, C 開新 window

# 開 window 2 — ORG Bot
python3 -u scripts/ap_org_bot.py

# 按 Ctrl+B, D 離開（detach）— 兩個 Bot 繼續在背景跑
```

#### tmux 常用指令

| 動作 | 指令 |
|------|------|
| 回到 session | `tmux attach -t ap` |
| 列出 sessions | `tmux ls` |
| 切換 window | `Ctrl+B, 數字（0/1/2）` |
| 關閉 Bot | 切到該 window → `Ctrl+C` |
| 刪除 session | `tmux kill-session -t ap` |

---

### 快速啟動腳本（一鍵開兩個 Bot）

```bash
cd "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion"
bash start_bots.sh
```

> `start_bots.sh` 會自動建立 tmux session 並啟動兩個 Bot。
> 首次使用先執行一次即可建立腳本（見下方）。

---

## start_bots.sh（一次性建立）

在 WSL2 執行以下指令建立啟動腳本：

```bash
cat > "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion/start_bots.sh" << 'EOF'
#!/bin/bash
# 吉寶軒 AP Bot 快速啟動腳本
set -e

PROJECT="/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion"
SESSION="ap"

# 若 session 已存在，先殺掉重建
tmux has-session -t "$SESSION" 2>/dev/null && tmux kill-session -t "$SESSION"

# 建立 detached session
tmux new-session -d -s "$SESSION" -n "antique-bot"

# Window 0：鑑定助理 Bot
tmux send-keys -t "$SESSION:0" "cd \"$PROJECT\" && python3 -u ap_discord_bot.py" Enter

# Window 1：ORG Bot
tmux new-window -t "$SESSION" -n "org-bot"
tmux send-keys -t "$SESSION:1" "cd \"$PROJECT\" && python3 -u scripts/ap_org_bot.py" Enter

echo "✅ 兩個 Bot 已在 tmux session 'ap' 啟動"
echo "   查看狀態：tmux attach -t ap"
echo "   切換視窗：Ctrl+B, 0（鑑定助理）/ Ctrl+B, 1（ORG Bot）"
EOF

chmod +x "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion/start_bots.sh"
echo "start_bots.sh 建立完成"
```

---

## ⚡ 一次性 Git 設定（自動部署前提，只需做一次）

ORG Bot 批准前端任務後會自動 `git push` 到 GitHub Pages。  
首次使用前需在 WSL2 執行以下設定：

```bash
cd "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion"

# 初始化 git（若尚未 init）
git init
git remote add origin https://github.com/craiglyu/Antique-Pavilion.git

# 設定預設分支
git branch -M main

# 設定 git 身分（只需一次）
git config user.email "craiglyu@email.com"
git config user.name "Craig"

# 第一次推送（需 GitHub 登入）
git add .
git commit -m "Initial: project setup"
git push -u origin main
```

> 之後 ORG Bot 的 auto-push 就能在無人值守時自動部署到 GitHub Pages。

---

## 驗證 Bot 正常運行

啟動後 log 應出現以下關鍵字：

**鑑定助理 Bot（ap_discord_bot.py）：**
```
鑑定助理 Bot 上線：...
Slash commands 同步：...
[CatchUp] 完成
```

**ORG Bot（scripts/ap_org_bot.py）：**
```
ORG Bot ready as ...
Synced X slash commands.
排程啟動：Poll 11:00 / 20:00，Expiry 00:30（台北時間）
```

若 ORG Bot 沒出現「排程啟動」那行 → scheduler 未正常初始化，重啟 Bot。

---

## Feedback PM 手動觸發

排程自動在 **11:00 / 20:00（台北時間）** 執行。
不想等排程，在 Discord 任意頻道輸入：

```
/poll-now
```

---

## 常見問題

### Bot 沒上線（無 ready 訊息）
```bash
# 確認 token 正確
grep DISCORD_ORG_BOT_TOKEN "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion/.env.antique"
grep DISCORD_BOT_TOKEN     "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion/.env.antique"
```

### 缺少 Python 套件
```bash
cd "/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion"
pip3 install discord.py aiohttp pytz apscheduler python-dotenv
```

### ORG Bot 的 Claude CLI 無回應
```bash
# 測試 claude stdin 管道
echo "請回答：1+1=?" | claude -p --model claude-sonnet-4-6 --max-turns 1
```

若有正常輸出 → CLI 正常，問題在 Bot 邏輯。
若無輸出或報錯 → `claude auth login` 重新授權。

---

## 重啟電腦後 Checklist

- [ ] 開啟 WSL2 terminal
- [ ] `python3 -u scripts/ap_launcher_web.py`（或使用備用 tmux）
- [ ] 確認兩個 Bot 的 ready log 出現
- [ ] Discord `/poll-now` 測試 Feedback PM 流程（若有待處理 feedback）
