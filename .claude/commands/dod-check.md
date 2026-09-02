---
id: dod-check
type: skill
layer: ops
loaded_by: [claude, codex, gpt]
version: 0.1
description: 完工三件套檢查(AGENTS.md §12)— 跑協議測試、列出未登錄的 CHANGE tag、未 commit 的變更
---
# /dod-check — 收工前的完工協議檢查

做三件事,把結果原文貼回對話,不要摘要成「通過」:

1. 跑協議測試(WSL):
   ```bash
   wsl bash -c "cd '/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion' && python3 -m pytest tests/test_change_log_contract.py -q"
   ```
2. `git status --short` 與 `git diff --stat`:列出所有未 commit 的檔案。
3. 對本次 session 改過的每個 `Publish/index.html` 切片,確認三樣都在:檔內 `CHANGE <TAG>`、
   `CHG_LOG.json` entry(`change_tags` 含該 tag)、commit。

任何一項缺 → 狀態回報「未完成,缺 X」,並直接補上缺的那一樣(commit 除外:commit 訊息擬好給 Craig 看)。
