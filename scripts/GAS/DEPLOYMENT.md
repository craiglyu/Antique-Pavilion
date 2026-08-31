<!-- CHANGE GAS-PREFLIGHT: AP GAS deployment gate and zero-cost canary runbook. -->
<!-- CHANGE GAS-QUEUE-SAFETY: v10.2 locked queue, durable payload, retry and dead-letter runbook. -->
<!-- CHANGE GAS-CATALOG-PREVIEW: read-only redacted Catalog contract diagnosis before migration. -->

# AP GAS v10.2.1 部署與驗收手冊

這份手冊適用於 `AntiqueAnalysis_AI.md` 主資料管線與 `review_desk/` 人工覆核台。
所有診斷預設唯讀；本地提交不代表線上已部署。

## 部署前：主 AP GAS

1. 在 Apps Script「專案設定 → 指令碼屬性」確認：
   - `DISCORD_BOT_TOKEN`：必要。
   - `GEMINI_API_KEY`：必要。
   - `AP_INGEST_SECRET`：只有仍使用舊 HTTP `doPost` 入口時才需要；Discord polling 不需要。
2. 貼上新版 `AntiqueAnalysis_AI.md` 後先儲存，不要先執行 `mainTick`。
3. 在編輯器執行 `diagPredeployAudit()`。這個函式不呼叫 Gemini，也不修改 Sheet、Drive、
   trigger 或 queue；report 不含任何 secret 值。
4. 原則上只有 `status: PASS` 才繼續。首次升級若唯一的 `FAIL` 是 `media.sheet` 找不到
   `AP_MEDIA`，而 Catalog、Drive、Properties 與 queue 均通過，可進入下一步由受控 setup 建立；
   其餘 `FAIL` 必須先處理。Trigger 缺少或重複是 `WARN`，也由下一步重建。
5. 首次升級到 v10.2、缺少 `AP_MEDIA`，或 trigger 不健康時，執行 `setupAntiquePipeline()`。
   它只會在缺少時建立 `AP_MEDIA`、驗證凍結契約，再重建唯一的每分鐘 `mainTick` trigger。
6. 再跑一次 `diagPredeployAudit()`，確認 `mainTick=1`、legacy `processJobAsync=0`。

## 必須停手的 FAIL

- `catalog.headers`：Catalog A:M 不等於凍結契約。不要直接改欄名、移欄或讓程式自動遷移；
  先比對 DD-XXX 與前端 parser，再交 Craig 決定。
- `media.headers`：既有 `AP_MEDIA` 不符合 DD-104。不要覆寫標題列。
- `CATALOG_UUID_*`、`MEDIA_ORPHAN`、`MEDIA_ID_DUPLICATE`：可能是部分寫入或歷史重複；
  先執行 `diagMediaReconcilePlan()` 取得唯讀問題清單，不可自動刪列。
- `MEDIA_PRIVACY_STATE_MISMATCH`：未上架藏品卻有 `approved` 媒體；先用 Review Desk 撤回。
- `PUBLISHED_WITHOUT_APPROVED_MEDIA`：新多圖藏品狀態與媒體發布狀態不一致；重新人工覆核。
- `queue.pending_jobs` 無法解析：不要直接清空，先保存 Script Property 原始值並查明原因。

`diagMediaReconcilePlan()` 只產生 `READ_ONLY_PLAN`，不修資料、不刪 Drive 檔案、不改分享權限。

## Catalog 標題不一致時的唯讀判讀

若 `diagPredeployAudit()` 回報 `catalog.headers: FAIL`，先執行
`diagCatalogContractPreview()`，不要先改 Sheet 第一列。這個函式只讀取 Catalog A:M，輸出
J:M 的公式／URL／狀態等結構計數；不回傳任何儲存格原文、URL、公式、藏品名稱或憑證。

依 `classification` 停在對應決策點：

- `STALE_LEGACY_HEADERS_CURRENT_POSITIONAL_DATA`：高機率只有標題過期；仍需 Craig 依 DD 核准
  header-only migration，診斷本身不會改寫。
- `LEGACY_HEADERS_LEGACY_POSITIONAL_DATA`：資料也仍在舊位置；需先建立可復原備份，再制定完整
  欄位遷移 DD，不可只改第一列。
- `AMBIGUOUS_LEGACY_HEADERS` 或 `UNKNOWN_HEADERS_OR_LAYOUT`：證據不足或混合格式；停止部署，
  再人工查看少量受限資料列。
- `CURRENT_CONTRACT`：Catalog 已符合凍結契約，可重新執行 `diagPredeployAudit()`。

請保留完整 `[AP Catalog Contract Preview]` JSON 執行紀錄供 migration go/no-go 判讀。

## v10.2 Queue 升級注意事項

- 貼新版程式前，先讓舊版 `pending_jobs` 消費至 0。舊 job payload 只有 Cache，無法安全枚舉並
  自動搬入 Script Properties；若 preflight 顯示 pending job 缺少 durable payload，停止部署。
- 新訊息的 job payload 同時放入 6 小時 Cache 與 Script Properties；成功完成後才清除 durable copy。
- 只有在 Drive／Sheet 寫入尚未開始前，429、HTTP 5xx、timeout 等暫時性錯誤才會自動重試，
  最多共 3 次。寫入開始後不自動重跑，以免建立重複藏品或圖片。
- 無法安全重試的任務會寫入 `job_dead_<jobId>`；payload 保留供人工復原。執行
  `diagQueueHealth()` 可查看 pending／dead-letter／orphan 數量與錯誤摘要，不會輸出 CDN URL 或 payload。
- 只有確認失敗發生在寫入前，才可從 Apps Script 手動執行 `safeEnqueue("<jobId>")`；它會重新從
  attempt 1 排入。標為 `PERSISTENCE_MAY_HAVE_STARTED` 或來源不明的 orphan payload 會拒絕重跑，
  必須先用 Catalog／AP_MEDIA reconcile 檢查是否已有部分資料。
- Discord `queue_status` 可讀取計數；`reset_queue` 已停用。`resetBot()` 只有在 pending、payload、
  dead-letter 全部為 0 時才允許執行。

## 部署後：零 Gemini 額度 canary

1. 建立新的 Apps Script deployment version；不要直接刪除上一版 deployment。
2. 執行 `diagPostdeployCanary()`。它會檢查：
   - preflight 仍為 `PASS`；
   - 唯一 `mainTick` trigger；
   - Discord bot identity 與目標 channel 可讀；
   - 由 `ScriptApp.getService().getUrl()` 取得**正式部署網址**並實際 GET，而非只呼叫編輯器內的
     `doGet()`；回傳筆數必須等於 Catalog 的 `完成` 筆數，且每筆保留 `imageUrl` 並含 `images[]`。
3. report 必須顯示 `status: PASS` 與 `geminiCalls: 0`。
4. 若要驗證模型可用性，再**另外且只執行一次** `diagTestGeminiFallbackCanary()`。這一步會消耗
   Gemini 免費額度；receipt 應列出實際成功模型與前序 fallback attempts。

## 真實 Discord smoke test

零額度 canary 通過後，再於 Intake channel 上傳一件非敏感測試藏品的 3–5 張不同角度照片，
放在**同一則 Discord 訊息**。建議優先順序：正面、背面／側面、底部、款識、局部狀況；通常
5 張足以兼顧辨識資訊與配額，硬上限仍為 8 張。

確認：

1. Discord 訊息只產生一筆藏品結果，不因相近時間合併其他訊息。
2. Catalog 新增一個 UUID，狀態為 `待人工覆核`。
3. `AP_MEDIA` 有 3–5 列使用同一 `artifactUuid`，且恰有一列 `isPrimary=true`。
4. 原圖維持私人，公開 `doGet()` 尚未回傳該藏品。
5. 在 Review Desk 調整順序／封面並執行 `保留並上架` 後，媒體全部成為 `approved`，公開 API
   才出現該藏品與多張 `images[]`。

## Review Desk

Review Desk 必須部署成另一個 owner-only Apps Script 專案。依
[`review_desk/README.md`](review_desk/README.md) 設定 `AP_SHEET_ID` 與
`AP_REVIEW_OWNER_EMAIL`，先跑 `setupReviewDesk()`，再以 `diagReviewDeskPreflight()` 的
`PASS` 作為發布門檻。若無法限制為「僅自己」，停止部署。

## 回復

程式異常時，將 Apps Script deployment 切回上一個已知正常 version；不要刪除 Sheet 列或 Drive
原圖。若 trigger 本身異常，可在舊版程式執行 `setupTrigger()` 重建唯一 `mainTick`。資料契約或
媒體權限異常則保持自動處理暫停，先保存 preflight／reconcile report 再處理。
