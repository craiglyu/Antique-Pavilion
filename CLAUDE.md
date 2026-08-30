# CLAUDE.md — 指標檔（內容不在這裡）

**本專案的規則來源是 [`AGENTS.md`](AGENTS.md)。這個檔案不含任何規則內容，只負責指過去。**

@AGENTS.md

如果上面那行 import 沒有生效，**現在就用 Read 工具讀 `AGENTS.md` 全文再繼續**。
沒讀過 `AGENTS.md` 就開始動手，等於沒有讀過本專案的規則。

---

## 為什麼是這樣安排

在 2026-08-27 之前，`CLAUDE.md` 與 `AGENTS.md` 是**兩份各 312 行、內容重複的檔案**——
`AGENTS.md` 是 `CLAUDE.md` 的機械字串取代複製。取代動作弄壞了兩行：

| 行 | 應為 | 被改成 | 後果 |
|---|---|---|---|
| 34 | `.claude/commands/*.md` | `.Codex/commands/*.md` | `.Codex/` 是空目錄，Codex 與 GPT 讀不到任何一個 skill |
| 131 | `Anthropic CLI (Claude MAX/Pro)` | `Anthropic CLI (Codex MAX/Pro)` | 該列講的是 Anthropic 訂閱計費，改成 Codex 是錯的 |

雙份維護必然漂移，而漂移的那一份還被交接文件指定為權威。
**現在只有一份真檔**，這一整類問題就此消失。

要改規則就改 `AGENTS.md`。不要把內容搬回這裡。

---

## 給不讀 `AGENTS.md` 就想動手的 agent 的三句話

1. **純 HTML / CSS / vanilla JS**——沒有 React / Vue / Tailwind / npm / build step。
2. **未 commit 不算完成**——完工要同時留下檔內 `CHANGE` 註解、`CHG_LOG.json` entry、
   git commit 三樣東西（`AGENTS.md` §12，有 pytest 把關）。
3. **碰到 Tier 1 就停手**——首頁 IA、品牌方向、公開內容、新功能、任何真偽／鑑定措辭、
   任何需要真實藝廊資料（LINE / 地址 / 營業時間 / Maps）的事項，交回 Craig 決定。
