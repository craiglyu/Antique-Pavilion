# CLAUDE.md — 指標檔 + Claude Code 作業層(2026-09-02 升級)

**專案規則的唯一來源是 [`AGENTS.md`](AGENTS.md)。** 本檔不重述規則,只做兩件事:把 `AGENTS.md`
匯入,以及說明 Claude Code 這個 harness 在本專案怎麼跑(模型、指令、hook)。

@AGENTS.md

若上面的 import 沒有生效,先用 Read 讀完 `AGENTS.md` 再動手;沒讀過它等於沒讀過本專案規則。
2026-08-27 之前 `CLAUDE.md` 與 `AGENTS.md` 是兩份互相漂移的複本,合併後只留一份真檔;
要改規則就改 `AGENTS.md`,不要把內容搬回這裡。

---

## Claude Code 在本專案的作業方式

**平台事實**:session 跑在 Windows(PowerShell / Git Bash),`AGENTS.md` 與 `STARTUP.md` 裡的
指令全是 WSL2 路徑(`/mnt/c/...`、`python3`)。要執行 Python 或 pytest 時走 WSL:

```bash
wsl bash -c "cd '/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion' && python3 -m pytest tests/ -q"
```

靜態站預覽用 `.claude/launch.json`(`antique-pavilion`,port 8080,serve `Publish/`)。
Bot / GAS 的啟動程序在 `STARTUP.md`,不要憑印象重打。

**完工三件套(`AGENTS.md` §12)**:檔內 `CHANGE <TAG>` 註解、`CHG_LOG.json` entry、git commit,
三樣同時存在才算完成,`tests/test_change_log_contract.py` 會擋。碰 `Publish/index.html` 時
`.claude/rules/publish_dod.md` 會自動提醒;收工前跑 `/dod-check`。

**Tier 1 就停**:首頁 IA、品牌方向、公開內容、新功能、真偽鑑定措辭、真實藝廊資料,交回 Craig
(`AGENTS.md` §5)。這是不可逆的對外事項,不是流程繁文。

**模型分流**:SessionStart hook(`.claude/hooks/model_profile.py`)會依本次 session 的模型注入
`.claude/model_profiles.md` 對應段落——同一句指令在 Opus 5 / Fable 5.1 / Sonnet 5 上效果相反,
所以校準放那裡,規則放 `AGENTS.md`。hook 沒偵測到模型時,自己讀對應段落。

| 工作型態 | 建議模型 / effort |
|---|---|
| 設計分岔、審稿、對外文案定稿 | Fable 5.1 或 Opus 5,`high` |
| 有完整規格的實作、測試、重構 | Sonnet 5,`xhigh`(難)/ `high`(一般);`/model opusplan` 讓 Opus 規劃、Sonnet 執行 |
| 機械式批次改字、格式轉換 | Haiku 4.5,規格寫死 |

**Skills**(`.claude/commands/`,純 markdown,Codex/GPT 也讀得到):`design-review`(v3.0 主審)、
`audit` / `impeccable-audit` / `polish`(設計稽核與打磨)、`emil-skill` / `taste-skill`(設計工程)、
`copywriting` / `marketing-psychology` / `social-content`(文案與社群)、`dod-check`(完工檢查)。
設計類工作先跑 `design-review`,再決定要不要 `polish`。

**Bot 模型 pin**(2026-09-02 更新):headless agent 預設 `claude-sonnet-5`(`config/agents.yaml`、
`scripts/ap_org_bot/infra/claude_cli.py:DEFAULT_MODEL`、`agents/base.py`);Opus 設計仲裁用 `claude-opus-5`
(`agents/_domain/ap/opus_flow.py:OPUS_MODEL`)。換代時只改這四處,blueprint 文件裡的舊 id 是歷史。

**已知待整理**(不要在無關任務裡順手動):`.claude/worktrees/` 有 13 個 5 月的棄置 worktree 會汙染
全域搜尋;根目錄約 300KB 多版本 blueprint 未歸檔。各自開票處理。
