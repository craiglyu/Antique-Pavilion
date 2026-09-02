---
paths: ["Publish/index.html", "CHG_LOG.json"]
---
# 完工三件套提醒(AGENTS.md §12,自動注入於碰到 Publish/index.html 或 CHG_LOG.json 時)

改動 `Publish/index.html` 的每個切片,完成的定義是三樣同時存在,缺一不算完成:
1. 檔內註解 `CHANGE <前綴>-<描述>: <說明>`(大寫、連字號;裸編號是舊寫法,不再新增)。
2. `CHG_LOG.json` 新 entry,`change_tags` 陣列含上面的 tag(格式見 AGENTS.md §12.3)。
3. git commit `<type>(<scope>): <摘要>`;工作區不是交付物。

`tests/test_change_log_contract.py` 斷言每個未凍結的 CHANGE tag 都在某筆 entry 裡;
收工前跑 `/dod-check`。原因:2026-08-27 之前四個 session、1429 行前端工作躺在工作區從未提交。
