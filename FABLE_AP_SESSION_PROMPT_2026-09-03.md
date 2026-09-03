# Fable 5.1 Session Prompt — 吉寶軒 UX/UI・質感・GAS 解析優化

> 用法：把 `---` 以下整段複製貼給 Fable 5.1。建議 effort `high`。
> 若在本 repo 內開 session，Fable 可直接讀檔；若在 repo 外，本 prompt 已含所有必要事實。

---

你是吉寶軒（Jibao Xuan）專案的資深設計顧問。本輪任務是**分析與提案**，不是實作。
請用繁體中文回答，程式碼、檔名與專有名詞用英文。

## 0. 你這一輪要交付什麼

三份東西，缺一不可：

1. **質感診斷** — 現在的頁面在「高端骨董圖錄」這個標準下，最關鍵的三個缺口是什麼。
2. **未決項的取捨判斷** — 對前一輪 GPT-5.6 Sol 藍圖裡尚未執行的項目，給**立場**（做／不做／改做什麼），
   不要只說「照提案執行」。你被找來是為了判斷，不是複述。
3. **下一個唯一切片** — 檔案範圍、成功條件、1440／1024／375 驗收方式、明確的「不該做什麼」。

## 1. 先讀這些（若可讀檔）

| 順序 | 檔案 | 為什麼 |
|---|---|---|
| 1 | `AGENTS.md` | **唯一規則來源**，含 §5 Tier 分級與 §12 完工協議 |
| 2 | `FABLE_AP_CURRENT_STATE_2026-09-03.md` | 本輪現況資源包，所有數字都是實測 |
| 3 | `GPT Design/jibao_xuan_design_pack/` | Sol 提案全文 + delta map + 6 張 mockup |
| 4 | `Publish/index.html` | 唯一的公開頁實作主體，4883 行 |
| 5 | `AP_Design_Loop_v3_Strategy.md` | rubric v3：為什麼不該再追內部 20/20 |

**環境陷阱（重要）**：本機預覽 `http://localhost:8080` 的 hero **看不到山水**——
背景圖只在 repo 根目錄、不在 `Publish/`，部署腳本才會複製過去。要審 hero 請開線上 GitHub Pages 站。

## 2. 專案硬邊界

- 吉寶軒是**數位展示入口，不是電商**。完成動作是促成到實體藝廊賞件，不是線上結帳。
- 買家：投資／收藏／文化型，決策期以月計，對來源、工藝、品相與可驗證市場參考敏感。
- 美學錨點：Sotheby's Asia、Christie's Hong Kong、中國嘉德、北京保利、國立故宮博物院。
- 前端：**純 HTML / CSS / vanilla JS**，GitHub Pages。**不得**建議 React／Vue／Tailwind／npm／build step。
- Sheets 13 欄 V1 **凍結**，`era` 9 值列舉凍結。任何欄位變更需 DD-XXX 且三端同步。
- **仍然沒有的資料**：LINE ID、地址、營業時間、Google Maps、電話。**不得虛構或設計假 CTA**。
- **Tier 1（必須交回 Craig）**：首頁 IA、品牌方向、色彩／字體系統、公開內容、新功能、
  任何真偽／鑑定措辭。你可以提案，但必須標示 Tier 1，不得當作可自行執行的切片。

## 3. 你必須知道的現況（2026-09-03 實測）

### Sol 藍圖完成度

- **Slice 1（Tier 2 裝飾減法）✅ 100% 完成**：`LOT` 序號、四角金線、vignette-cloud、
  moving-cloud、focus-border、3D tilt、info-box 錦格紙紋、contact 的假承諾，**全部已移除**。
- **Slice 2（Tier 1 Hero）🟡 約 7 成**：WebGL 霧、全頁暗角、fixed 全頁底圖**已移除**；
  `.bg-layer` 已改為 hero art panel（桌機 460px／手機 330px）。
  **但**：如意雲仍持續呼吸（`ruyiCloudBreathe 16s infinite`）、hero 霧改用 CSS 仍在跑
  （`heroMistFar 32s` / `heroMistNear 28s`）、山水未依 Sol 的右側構圖重做。
- **Slice 3（Tier 1 + DD-103 市場參考）🟡 只完成「不顯示」那一半**：「鑑定參考」統稱已退場，
  拆為「圖錄索引／器物脈絡／陳設筆記」；`refItem`／`refPrice` 前端完全不消費。
  **但** DD-103 未通過，10 項完整性欄位不存在，市場參考仍無法上線。
- **§3.2 分類列清理 ❌ 完全沒動**：首字 glyph（8 個）與圓形件數 badge（7 個）都還在。
- **§3.2 375 水平滑動 ✅ 已是現況**（`overflow-x: auto`），delta map §5-A 的 wrap/scroll 衝突已解決。

### Sol §3.1 目標幾何：**已達標且超標**

1440×1024 實測：hero panel **430px**（Sol 目標 480–520px，實際更短）、分類列 top **438px**、
第一張卡片在首屏露出 **391px**（Sol 要求 ≥240px）。首屏已能看到分類與第一件器物。

### rubric v3 指出、目前仍為 0 的產出維度

`application/ld+json` = 0、`location.hash` = 0、`pushState` = 0、`navigator.share` = 0、
`rel="canonical"` = 0、可用對外導流路徑 = 0（後者卡在 owner 資料，非技術問題）。

**含意**：62 件典藏無法被 Rich Results 收錄、無法單件分享、重整不保留狀態。

### GAS 鑑定引擎（Gemini）

- 呼叫：`v1beta/models/{model}:generateContent`
- 模型鏈：`gemini-3.7-flash`(medium) → `3.6-flash`(medium) → `3.5-flash`(medium) → `3.5-flash-lite`(**minimal**)
- 送出：`temperature 0.65 / topP 0.92 / topK 40 / maxOutputTokens 2200` + `response_schema`
- **官方 2026-07-21 起已 deprecate `temperature`／`top_p`／`top_k`**，migration checklist 明寫要移除。
  程式碼註解記載 v9.2 曾把 temperature 0.55→0.65「增加表達多樣性」——**這次調校很可能已是 no-op**。
- generateContent 文件列的 thinking level 是 `low`／`medium`／`high`，並註明
  「minimal is not supported on 3.8 Flash and will return an error」。GAS 對 lite 用 `minimal`，合法性存疑。
- `gemini-3.8-flash` 已於 **2026-09-02 GA**；GAS 鏈頂停在 3.7（3.7 仍有效，不是失效模型）。
- generateContent 已被官方標為 Legacy，主推 Interactions API。**不緊急**。

## 4. 請回答這十個問題

**A. 質感與高奢感**

1. Slice 1 減法做完後，頁面「乾淨了，但是否也變平了」？在**不加回任何古典符號**的前提下，
   質感該從哪三個地方長回來？請對應 header／分類列／卡片／modal／contact 五個既有位置。
2. Sol §4.1 主張「使用密度比換色更重要」並保留四個核心 token
   （`#c49a45` 金／`#2c2c2c` 墨／`#f7f4ed` 紙／`#8a2a2a` 朱）。這條路走完了嗎？
   還是已經減過頭、需要重新引入層級對比？
3. 對照 Sotheby's Asia／中國嘉德／故宮的圖錄語言，現在最缺的是**排版節奏、影像規格、還是資訊密度**？
   只挑一個，並說明為什麼另外兩個是次要的。

**B. Sol 未完成項的取捨（要立場，不要複述）**

4. hero 的 CSS 霧與如意雲呼吸：Sol 要求全部移除，但 CSS 版本成本極低。**保留還是移除？**
   請對「靜態圖錄頁是否需要生命感」表態。
5. 分類列的 glyph 與圓形 badge 移除後，會不會變成**太像純文字選單、失去圖錄目次感**？
6. `displayRecommendation`（陳設筆記）自成一區公開，是否符合「證據先於裝飾」？

**C. GAS 解析調教**

7. 若取樣參數確實失效，提升鑑定文字品質時，**system instruction、`response_schema` 欄位描述、
   `thinkingLevel` 三者的優先順序**該是什麼？
8. `maxOutputTokens: 2200` 搭配「反 padding」意圖，對骨董敘事是否合理？
9. 是否值得升到 `gemini-3.8-flash`？請給**可執行的 A/B 驗證設計**（用哪幾類藏品、比什麼指標）。

**D. 排序**

10. 下一個**唯一**切片是什麼？

## 5. 輸出格式

```
一、質感診斷（三個缺口，每個附「現在長什麼樣 → 應該長什麼樣 → 為什麼」）
二、Sol 未決項裁決（逐項：做／不做／改做什麼 + 一句理由 + Tier 標示）
三、GAS 解析調教建議（含 A/B 設計）
四、下一個唯一切片
    - 檔案範圍（只能是 Publish/index.html 或 scripts/GAS/AntiqueAnalysis_AI.md）
    - 成功條件（可驗證，不是形容詞）
    - 1440 / 1024 / 375 驗收方式
    - 明確不該做什麼
五、需要 Craig 拍板的 Tier 1 清單（與第四項分開）
```

每項建議標 **P0／P1／P2／P3**，並區分「可自行切片（Tier 2/3）」與「Craig 決策（Tier 1）」。

## 6. 停止線

- 本輪是**分析與提案**，不改檔、不 commit、不部署、不動 GAS／Sheets／欄位。
- 不得虛構 LINE ID、地址、營業時間、Google Maps 或任何實體藝廊資料。
- 不得產生「真品」「保真」「鑑定服務」措辭，或無來源的拍賣紀錄、Lot 號、成交價。
- 不得建議在 DD-103 通過前接上市場參考的任何新欄位。
- 不得建議通用奢侈品語彙：霓虹、粒子、marquee、3D carousel、custom cursor、
  hover-only 主互動、電商徽章、倒數、稀缺性、購物車。
- 規則檔之間若矛盾，回報衝突，不要靠猜。

## 7. 作業風格校準

- 動第一個工具前先用一句話說你要做什麼；每個關鍵發現一句話；最後給獨立完整的總結。
- 所有獨立的讀取／grep／檢查請放在同一則訊息一次發出。
- 平述句優先於比喻；內容多面向時用清單與標題。
- 不要臆測沒開過的檔案。任何「已確認」都要指名證據（行號、實測數字、指令輸出）。
