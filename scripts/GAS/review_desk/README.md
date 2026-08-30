# 吉寶軒 Curator Review Desk

內部藏品人工覆核 Web App。它和公開型錄 API 是兩個獨立的 Apps Script 專案：公開站只有讀取權；Review Desk 只供 Craig 使用，透過 Google 帳號授權寫回既有 Google Sheet。

## MVP 能做什麼

- 把 2026-08-23 已確認的 12 組／25 筆重複候選並排呈現。
- `全部藏品` 模式讀取完整收藏品工作表，可依文字、狀態與分類搜尋。
- 放大檢視 Google Drive 圖片，比較品名、年代、分類、參考資料、標籤與目前狀態。
- 對單筆藏品執行：
  - `保留並上架` → Sheet 狀態 `完成`
  - `暫留覆核` → Sheet 狀態 `待人工覆核`
  - `下架封存` → Sheet 狀態 `已下架`
  - `退件保留紀錄` → Sheet 狀態 `已退件`
  - 編輯既有原始描述、品名、分類、年代、故事、參考資料、Drive 圖片 URL、標籤與展示建議
- 每次寫入都在獨立的 `Review Audit` 工作表記錄操作者、前後狀態、變更欄位與備註。
- 可在完整型錄中選取 2–6 件藏品，建立 Craig 自訂的人工比對群組。

MVP 不提供永久刪除。公開 GAS API 仍只傳回 `完成`，所以其他三種狀態都不會出現在展示頁。

## 日常使用方式

### 判斷與處理重複藏品

1. 進入 `重複覆核`，選擇左側 D-XX 或 M-XX 群組。
2. 放大圖片，比較年代、分類、參考資料與標籤。
3. 對保留者按 `保留並上架`。
4. 對重複者按 `下架封存`。這是可復原的安全刪除；資料、圖片與 audit log 都保留。
5. 若尚不能判斷，按 `暫留覆核`，不要勉強選擇保留者。

### 管理全部藏品與 unavailable 狀態

1. 進入 `全部藏品`，搜尋品名或以狀態／分類篩選。
2. `完整編輯` 可修改原始描述、品名、分類、年代、故事、拍賣參考、價格、Drive 圖片 URL、標籤與展示建議。
   UUID 與入庫時間維持唯讀，作為稽核與還原依據；上架狀態由卡片上的動作按鈕管理。
3. 已售、借展、暫不可供觀賞或其他 unavailable 情況，按 `下架`；日後可按 `上架` 恢復。
4. 發現畫面相似者，分別按 `加入人工比對`，選滿 2–6 件後建立比對群組。

`下架封存` 不等於刪除 Drive 圖片，也不會刪除 Sheet 列。永久刪除若日後啟用，必須先建立回收站、二次確認與還原機制。

## 檔案

- `Code.gs`：權限檢查、Sheet 讀寫、審核佇列、狀態轉換與 audit log。
- `Index.html`：純 HTML/CSS/vanilla JS 的響應式審核 GUI；沒有框架或 build step。
- `appsscript.json`：V8 runtime、Taipei 時區與最小 OAuth scopes。

## 安全部署程序

1. 新建一個獨立 Apps Script 專案，例如 `AP Curator Review Desk`。不要覆蓋目前公開型錄 API 的專案。
2. 將本資料夾的 `Code.gs`、`Index.html`、`appsscript.json` 複製到新專案。
3. 在 Apps Script「專案設定 → 指令碼屬性」加入：
   - `AP_SHEET_ID`：收藏品 Google Sheet ID。
   - `AP_REVIEW_OWNER_EMAIL`：Craig 用來審核的 Google 帳號。
4. 在 Apps Script 編輯器執行一次 `setupReviewDesk()`，完成授權。此函式只新增／確認 `Review Queue`、`Review Audit` 兩個工作表並匯入 12 組審核佇列，不改收藏品工作表欄位。
5. 回到 Google Sheet，確認新工作表共有 25 筆 queue records，且 `Review Audit` 只有標題列。
6. 「部署 → 新部署 → 網頁應用程式」：
   - 執行身分：Craig／專案擁有者。
   - 存取權：僅自己。不要選擇匿名或所有人。
7. 開啟部署網址，先用一筆候選重複執行 `暫留覆核`，確認：
   - 原收藏品工作表該筆狀態成為 `待人工覆核`。
   - `Review Queue` 留下決定與備註。
   - `Review Audit` 新增一筆 before/after 紀錄。
   - 公開型錄重新載入後不再顯示該筆。

如果部署選單無法限制成「僅自己」，先停止部署，不要把寫入介面公開。

## 資料契約與防護

- 收藏品欄位維持既有 A:M，沒有新增、刪除或改名。
- 以 UUID 尋找即時列位置，不依賴可能因排序而改變的 row number。
- 年代編輯限既有九項 enum；上架前強制檢查品名、分類、年代。
- UUID 與入庫時間不允許從 GUI 修改；原始描述與 Drive 圖片 URL 可編輯並留下 audit log。
- 影像判讀只作編目線索，不作真偽、斷代或來源證明。
- Script Properties 必須設定；前端不包含 Sheet ID、API key 或 Bot token。

## 本地示範

直接由本機 HTTP server 開啟 `Index.html` 時，介面會載入本地重複候選與最新匯出的完整型錄資料。所有操作只改瀏覽器記憶體，不會寫入 Google Sheet。

### Chrome 快速啟動

直接雙擊 `Start_Review_Desk.cmd`。啟動器會：

1. 檢查本機 `127.0.0.1:8765` 是否已經有 Review Desk。
2. 必要時在背景啟動唯讀預覽服務。
3. 用 Chrome 開啟 Review Desk；找不到 Chrome 時才改用 Windows 預設瀏覽器。

電腦重新啟動後，需要再雙擊一次。這個本地預覽仍是示範模式；正式連接 Google Sheet 必須部署 owner-only GAS Web App。

### 手動啟動

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

再開啟：

`http://127.0.0.1:8765/scripts/GAS/review_desk/Index.html`

## 下一階段

- 把 AP_ORG Curator 的 exact fingerprint 衝突結果自動寫入 `Review Queue`。
- 增加群組層級「確認保留一件，其餘批次下架」操作，但仍逐筆寫 audit log。
- 增加安全的下架恢復清單與變更歷史檢視。
- 待 Craig 另行核准後，再評估帶二次確認與備份的永久刪除流程。
