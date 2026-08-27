# 吉寶軒 × GPT-5.6 Sol：設計討論現況卡

> 用途：提供 Chat 模式的 GPT-5.6 Sol 作為設計討論的唯一「目前狀態」摘要。
> 這是內部討論材料，不是實作授權，也不是對外文案。

## 產品與商業現實

- 吉寶軒是中國古文物的數位展示入口，不是電商；完成動作是促成藏家到實體藝廊賞件、預約或洽詢。
- 目標客群為投資型、收藏型與文化型買家；決策期以週到月計，對來源、工藝、品相與可驗證的市場參考敏感。
- 美學錨點：Sotheby's Asia、Christie's Hong Kong、中國嘉德、北京保利、國立故宮博物院。
- 專案現階段尚未具備地址、開放時間、LINE ID、Google Maps 等實體藝廊資料；不得為了改善導流而虛構、啟用或設計假 CTA。

## 技術與權限邊界

- 公開頁：`Publish/index.html`；純 HTML、CSS、vanilla JavaScript、GitHub Pages。
- 資料路徑：Discord 圖片 → GAS Gemini 分析 → Google Sheets／Drive → GAS `doGet()` → 展示頁。
- 任何新欄位、欄位改名或欄位順序異動均需要 DD-XXX，並同步 `writeToSheet()`、`doGet()`、前端 parser；不可只改其中一端。
- Tier 1，必須先由 Craig 決定：Hero／品牌、色彩或字體系統、IA／新頁面、公開品牌敘事、新功能、任何真偽或鑑定聲明。
- 此輪是「設計與資料契約提案」。Sol 不應直接實作、改檔或把提案視為核准。

## 已完成的前端基線

- P2-ZOOM／BOX／LIFE／RAIL 已完成：modal 細看提示、手機 box-sizing、關閉競態與 focus trap、分類列長尾收斂與手機折行。
- R5 已完成：資訊文字對比、語意 landmarks 與 heading hierarchy、超長 era 前端韌性。
- R6 已完成：故事只在完整句子截斷、全文提示、卡片 compositing hint 動態化。
- R7 已完成：Google Fonts 只請求實際使用的字重；手機 feature／portrait／landscape 圖高恢復差異。
- R8 已完成：卡片 Drive 縮圖以 lazy `srcset`／`sizes` 依圖框與 DPR 選取；三種空狀態印章字對輔助科技隱藏。

## 已證實的設計與資料問題

1. `refItem` 寫入 Sheet，但公開 `doGet()` 未傳出；modal 的「參考拍品」版位因此拿不到資料。
2. `highlightQuote` 已有 card／modal 版位，GAS 分析也生成它，但目前的持久化與公開 API 路徑未接上。
3. `features` 已由 AI 產生，卻未寫入 Sheet；可驗證的器物觀察無法成為日後圖錄、檢索或人工覆核的依據。
4. `condition` 與 `provenance` 不能由單張圖片冒充實物品相或來源；要先設計證據與人工覆核語意，才可入公開頁。
5. 中國古文物感不應靠龍紋貼圖、仿古濾鏡、金色堆砌或舞台式煙霧建立；應從器物、形制、研究脈絡、材質與安靜的賞件節奏形成。

## Sol 需要回答的設計問題

- 哪三個「中國古文物型錄」的視覺原則最能強化辨識，且不落入中式主題餐廳或電商感？請對應到既有的 header、category rail、card、modal、contact 五個位置。
- 首屏如何兼顧品牌儀式感、器物可信度與日後的實體賞件導流？請把需要 Craig Tier 1 決定的部分分開。
- 三種買家各需要什麼證據、閱讀順序與到店理由？請不要用折扣、倒數、購物車或催購。
- 在不新增未核准欄位的前提下，哪些既有資料最值得先接到前端？哪些欄位應永遠留在內部？
- 請提出 3 個可驗證的 Tier 2 小切片；每個都要有檔案範圍、成功條件、1440／1024／375 驗證，以及不該做什麼。

## 不能接受的方向

- React／Vue／Tailwind／npm build step，或取代現有純前端架構。
- 通用奢侈品網站語彙：霓虹、紫色／極光、粒子、marquee、3D carousel、custom cursor、hover-only 主互動、電商徽章。
- 任何「保真」「真品」「鑑定服務」等未核准聲明，或無來源的拍賣紀錄、Lot 號、成交價、來源故事。
- 沒有資料就假裝有的實體藝廊資訊或 CTA。

## 設計評估標準

以 20 分制回覆：Accessibility、Performance、Responsive、Brand/Theming、Anti-patterns/Code 各 4 分；
每項建議需標為 P0／P1／P2／P3，且區分「可自行切片」與「Craig Tier 1 決策」。
