<!-- CHANGE GAS-PREFLIGHT: AP GAS deployment gate and zero-cost canary runbook. -->
<!-- CHANGE GAS-QUEUE-SAFETY: v10.2 locked queue, durable payload, retry and dead-letter runbook. -->
<!-- CHANGE GAS-CATALOG-PREVIEW: read-only redacted Catalog contract diagnosis before migration. -->
<!-- CHANGE GAS-DD105-HEADERS: Craig-approved guarded A1:M1 header-only migration. -->
<!-- CHANGE GAS-LOCAL-BRIDGE: Discord I/O stays local; GAS exposes an idempotent secret-protected intake. -->
<!-- CHANGE GAS-DURABLE-ASYNC: DD-108 durable submit/status/worker deployment and duplicate quarantine. -->
<!-- CHANGE GAS-CANARY-EXEC-URL: canary tests the explicit formal /exec Script Property. -->

# AP GAS v10.4.1 部署與驗收手冊

這份手冊適用於 `AntiqueAnalysis_AI.md` 主資料管線與 `review_desk/` 人工覆核台。
所有診斷預設唯讀；本地提交不代表線上已部署。

## 部署前：主 AP GAS

1. 在 Apps Script「專案設定 → 指令碼屬性」確認：
   - `GEMINI_API_KEY`：必要。
   - `AP_INGEST_SECRET`：必要，至少 24 字元；本地 Intake 必須使用同一值。
   - `AP_WEBAPP_EXEC_URL`：必要，填正式 `https://script.google.com/macros/s/.../exec`；不可填 `/dev`。
   - `DISCORD_BOT_TOKEN`：GAS 不需要；舊值可在本地 bridge 驗收後移除。
2. 貼上新版 `AntiqueAnalysis_AI.md` 後先儲存。不要執行 `mainTick` 或任何舊 Discord 診斷函式。
3. 在編輯器執行 `diagPredeployAudit()`。這個函式不呼叫 Gemini，也不修改 Sheet、Drive、
   trigger 或 queue；report 不含任何 secret 值。
4. 原則上只有 `status: PASS` 才繼續。部署 v10.4 前尚未有 worker 時，允許預期的
   `trigger.durable_bridge: FAIL`（`processBridgeQueue=0`）；若同時只有 `media.sheet` 找不到
   `AP_MEDIA`，而 Catalog、Drive、Properties、queue 與 bridge state 均通過，也可由受控 setup
   建立。其餘 `FAIL` 必須先處理。
5. 執行 `setupAntiquePipeline()`。它會在缺少時建立 `AP_MEDIA`、驗證凍結契約，移除舊
   `mainTick`／`processJobAsync`，並重建唯一 `processBridgeQueue` 每分鐘 trigger。
6. 再跑一次 `diagPredeployAudit()`，確認 `trigger.durable_bridge` 為 `PASS`、
   `processBridgeQueue=1`、`mainTick=0`、legacy `processJobAsync=0`。

## 必須停手的 FAIL

- `catalog.headers`：Catalog A:M 不等於凍結契約。不要直接改欄名、移欄或讓程式自動遷移；
  先比對 DD-XXX 與前端 parser，再交 Craig 決定。
- `media.headers`：既有 `AP_MEDIA` 不符合 DD-104。不要覆寫標題列。
- `CATALOG_UUID_*`、`MEDIA_ORPHAN`、`MEDIA_ID_DUPLICATE`：可能是部分寫入或歷史重複；
  先執行 `diagMediaReconcilePlan()` 取得唯讀問題清單，不可自動刪列。
- `MEDIA_PRIVACY_STATE_MISMATCH`：未上架藏品卻有 `approved` 媒體；先用 Review Desk 撤回。
- `PUBLISHED_WITHOUT_APPROVED_MEDIA`：新多圖藏品狀態與媒體發布狀態不一致；重新人工覆核。
- `queue.pending_jobs` 無法解析：不要直接清空，先保存 Script Property 原始值並查明原因。
- `PARTIAL_INGEST_REQUIRES_RECONCILE`：同一 `messageId` 可能已有部分 Drive／Sheet 寫入；
  執行 `diagBridgeReconcilePlan()`，不可移除 reaction 後直接重送。
- `bridge.durable_state` 的 `reconcile>0`：staging 或 persistence 結果不明；停止 Intake，先保留
  staging 與 state，再執行 `diagBridgeReconcilePlan()`。
- `bridge.durable_state` 的 `corrupt>0`：Script Property JSON 損壞；保存原始 property 後人工修復，
  worker 與相同 messageId submit 都會 fail closed。完成 state 只保留 90 天，之後 replay 由
  Catalog + AP_MEDIA 重建，不代表資料遺失。

`diagMediaReconcilePlan()` 只產生 `READ_ONLY_PLAN`，不修資料、不刪 Drive 檔案、不改分享權限。
`diagBridgeReconcilePlan()` 只列出 partial marker／`RECONCILE_REQUIRED` state 對應的
`artifactUuid` 與 Catalog／AP_MEDIA 筆數；它同樣不修資料，也不會清除 marker。

## DD-108 已知測試重複的受控隔離

先執行 `diagBridgeMessageDuplicates()`。2026-08-31 已核准證據應只包含
`sourceMessageId=1543912512204967967` 的兩個 UUID。診斷只輸出 ID、列數與狀態，不回傳藏品內容、
URL 或公式。

只有該群組仍精確符合 keeper `9a3705a2-fa29-420b-8047-6b56c524a0a5`、duplicate
`06b0648a-3e4a-4ffe-a330-4e0523b53bba`，且兩者 attachment／sortOrder 完全一致時，才執行一次
`applyDd108KnownTestDuplicateQuarantine()`。成功 receipt 必須為 `APPLIED`（重跑為
`ALREADY_APPLIED`）、`catalogRowsTouched=1`、`mediaRowsTouched=2`、`filesDeleted=0`。此函式不刪列、
不刪 Drive 檔、不改 keeper，只把 duplicate Catalog 設為 `已退件`、媒體設為 `rejected`。

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

### DD-105 已核准的 header-only migration

Craig 於 2026-08-31 核准 DD-105。只有 preview 同時回傳以下四個條件時，才可在 Apps Script
手動執行一次 `applyDd105CatalogHeaderMigration()`：

- `classification = STALE_LEGACY_HEADERS_CURRENT_POSITIONAL_DATA`
- `confidence = high`
- `currentPosition = currentMaximum`
- `legacyPosition = 0`

函式會取得 Script Lock，確認 A1:M1 仍是精確舊標題，只把該標題列改為凍結契約；第 2 列
以後不會寫入。成功 receipt 必須為 `status: APPLIED`、`range: A1:M1`、
`headerRowsTouched: 1`、`dataRowsTouched: 0`。如果已套用，回傳 `ALREADY_APPLIED` 且不再寫入；
若寫入後驗證失敗，函式會嘗試回復舊標題並以 `FAILED` 結束。

執行後先貼回完整 `[AP DD-105 Migration]` receipt，接著只重跑 `diagPredeployAudit()`。
此階段仍不要執行 `setupAntiquePipeline()`、不要更新 deployment。

## 舊 v10.2 Queue 的退場注意事項

- 貼新版程式前，先讓舊版 `pending_jobs` 消費至 0。舊 job payload 只有 Cache，無法安全枚舉並
  自動搬入 Script Properties；若 preflight 顯示 pending job 缺少 durable payload，停止部署。
- v10.4 不再建立或消費 GAS Discord queue；若仍有 pending／dead-letter／orphan，先保存並
  人工釐清，不能靠重啟 trigger 消費。
- 無法安全重試的任務會寫入 `job_dead_<jobId>`；payload 保留供人工復原。執行
  `diagQueueHealth()` 可查看 pending／dead-letter／orphan 數量與錯誤摘要，不會輸出 CDN URL 或 payload。
- 只有確認失敗發生在寫入前，才可從 Apps Script 手動執行 `safeEnqueue("<jobId>")`；它會重新從
  attempt 1 排入。標為 `PERSISTENCE_MAY_HAVE_STARTED` 或來源不明的 orphan payload 會拒絕重跑，
  必須先用 Catalog／AP_MEDIA reconcile 檢查是否已有部分資料。
- `resetBot()` 只有在 pending、payload、dead-letter 全部為 0 時才允許執行；它清除舊 lastId、
  移除 legacy trigger，並重建唯一 `processBridgeQueue`，不會建立 `mainTick`。

## 正式 Web App 與本地 Intake 設定

1. 將 GAS 建立為新的 Web App version，執行身分選「我」，存取權選可匿名存取；保留上一版
   deployment 供回復。公開 GET 只會輸出已核准藏品，POST 另由 `AP_INGEST_SECRET` fail closed。
2. 複製正式 `https://script.google.com/macros/s/.../exec` URL；不可使用 `/dev`。
3. 在 gitignored 的本地 `.env.antique` 設定：

   ```text
   DISCORD_BOT_TOKEN=<raw token，不含 Bot 前綴>
   AP_GAS_DOPOST_URL=https://script.google.com/macros/s/<deployment-id>/exec
   AP_INGEST_SECRET=<與 GAS 完全相同、至少 24 字元>
   AP_ENTERPRISE_SSL_BYPASS=0
   ```

4. 依 `requirements-ap-intake.txt` 安裝依賴，再從 WSL2 執行 `python3 -u ap_discord_bot.py`。
   只有公司代理憑證確實造成 TLS 失敗時，才把 `AP_ENTERPRISE_SSL_BYPASS` 設為 `1`。

## 部署後：零 Gemini 額度 canary

1. 建立新的 Apps Script deployment version；不要直接刪除上一版 deployment。
2. 執行 `diagPostdeployCanary()`。它會檢查：
   - preflight 仍為 `PASS`；
   - `processBridgeQueue=1`、`mainTick=0`、legacy `processJobAsync=0`；
   - local bridge mode 與 `AP_INGEST_SECRET` 已就緒，GAS Discord egress calls 固定為 0；
   - 由 Script Property `AP_WEBAPP_EXEC_URL` 取得明確的**正式 `/exec` 網址**並實際 GET，而非
     使用可能命中 `/dev`／其他 deployment 的自動網址；回傳筆數必須等於 Catalog 的 `完成`
     筆數，且每筆保留 `imageUrl` 並含 `images[]`。
3. report 必須顯示 `status: PASS` 與 `geminiCalls: 0`。
4. 若要驗證模型可用性，再**另外且只執行一次** `diagTestGeminiFallbackCanary()`。這一步會消耗
   Gemini 免費額度；receipt 應列出實際成功模型與前序 fallback attempts。

## 真實 Discord smoke test

零額度 canary 通過且本地 `ap_discord_bot.py` 已啟動後，再於 Intake channel 上傳一件非敏感
測試藏品的 3–5 張不同角度照片，
放在**同一則 Discord 訊息**。建議優先順序：正面、背面／側面、底部、款識、局部狀況；通常
5 張足以兼顧辨識資訊與配額，硬上限仍為 8 張。

確認：

1. Discord log 先出現 durable `QUEUED`／`RUNNING`，同一訊息最後只產生一筆藏品結果，
   不因相近時間合併其他訊息。
2. Catalog 新增一個 UUID，狀態為 `待人工覆核`。
3. `AP_MEDIA` 有 3–5 列使用同一 `artifactUuid`，且恰有一列 `isPrimary=true`。
4. 原圖維持私人，公開 `doGet()` 尚未回傳該藏品。
5. 在 Review Desk 調整順序／封面並執行 `保留並上架` 後，媒體全部成為 `approved`，公開 API
   才出現該藏品與多張 `images[]`。
6. 以相同 `messageId` 重送時 receipt 為 `duplicate: true`，Catalog／AP_MEDIA 筆數不增加。

## Review Desk

Review Desk 必須部署成另一個 owner-only Apps Script 專案。依
[`review_desk/README.md`](review_desk/README.md) 設定 `AP_SHEET_ID` 與
`AP_REVIEW_OWNER_EMAIL`，先跑 `setupReviewDesk()`，再以 `diagReviewDeskPreflight()` 的
`PASS` 作為發布門檻。若無法限制為「僅自己」，停止部署。

## 回復

程式異常時，停止本地 Intake Bot，將 Apps Script deployment 切回上一個已知正常 version；
不要刪除 Sheet 列、partial marker 或 Drive 原圖。資料契約、媒體權限或 partial write 異常時，
保持自動處理暫停，先保存 preflight／reconcile report 再處理。任何回復都不得重新建立 GAS
Discord polling trigger。
