# 吉寶軒 Sol 設計提案 → `Publish` Delta Map

> 日期：2026-08-21  
> 模式：read-only planning／不構成實作、部署、資料欄位或 Tier 1 核准  
> 比對對象：`GPT Design/jibao_xuan_design_pack/jibao_xuan_private_viewing_catalogue_visual_proposal_v1_2026-08-21.md` 與目前 `Publish/index.html`  
> Git snapshot：`main`；工作樹已有使用者的未提交修改。本文件不要求 revert、重建或吸收那些修改。

## 1. 結論先行

Sol 提案的核心方向可作為後續設計基線：**器物與可核對的研究資訊優先於中式裝飾；市場資料與鑑定語意分開；實體賞件資料未齊時不做假導流。**

但它不是可直接套用的 patch。提案的 design subject 是另一份較新的 `index.html`，而公開頁的唯一實作 subject 是 `Publish/index.html`。現行頁面已有 R5–R8 的 accessibility、responsive image 與 category-rail 修正，不能依提案行號或 mockup 反向覆蓋。

本輪最安全的下一個 implementation candidate 是「**卡片純減法**」：只移除不承載狀態或內容的四角裝飾、卡片雲霧與 3D tilt，保留既有卡片資料順序、分類篩選、modal、圖片 lazy load 和所有 R5–R8 行為。`LOT` 移除應在 Craig 以專案 authority 再次確認「不設公開典藏編號」後，才與此切片合併。

## 2. 評估範圍與非授權事項

此評估使用 AP luxury design review 的靜態程式／mockup 對照，並非新的 1440／1024／375 瀏覽器驗收。前次 R8 驗收結果不在此重跑或改寫。

- 只將 Sol 文件與六張圖片當作設計參考，**不**把其中「Craig 回覆」欄位視作本文件的執行授權。
- 不修改 `Publish/index.html`、GAS、Google Sheet、metadata 或 contact 文案。
- 不處理實體藝廊資訊（LINE、地址、時間、Google Maps）；此項仍等待 owner 資訊。
- 不將市場參考、condition、provenance、真偽或估值資料從 AI／單張圖片推定出來。

## 3. 現況品質快照（靜態比對，13/20）

| 面向 | 分數 | 根據 |
|---|---:|---|
| Accessibility | 3/4 | Category rail 有 tablist、roving tabindex、`aria-selected` 與 live region；modal 有既有 keyboard interaction。仍有 disabled LINE placeholder 與不完整實體導流內容。 |
| Performance | 3/4 | R8 已以 lazy `srcset`／`sizes` 載入器物圖；WebGL 對低階裝置與 reduced-motion 已設 gate，但仍是非必要的持續視覺層。 |
| Responsive | 3/4 | 既有 375px card stack 與折疊後 category wrap；與 Sol 的水平滑動稿存在決策衝突，不能在未驗收下替換。 |
| Brand / theming | 2/4 | 現有 palette 可用，但同一卡片同時有錦格、金角、印記、LOT、雲霧、focus border、zoom 與 tilt，器物的閱讀優先度不足。 |
| Anti-patterns / code | 2/4 | 資料欄位未可支持可驗證的市場參考；卡片的裝飾層與 DOM/JS 綁定耦合，且 contact 仍有 placeholder 承諾。 |

分數用於排序，不代表已完成 visual/browser QA；任何 layout 或 interaction patch 仍須在真實資料量下驗證 1440、1024、375。

## 4. 逐區域 Delta Map

| 區域 | Sol 提案意圖 | 現行 `Publish` 證據 | 差異與處置 | Tier / gate |
|---|---|---|---|---|
| Hero | 山水只作 Hero art panel；移除 fixed wallpaper、暗角與 WebGL 霧；縮短首屏使首件器物早出現 | `Publish/index.html:150` `.bg-layer`、`:177` `#glCanvas`、`:185` `.ink-vignette`、`:202` fixed `header`、`:2574` `syncHeroSpacing()`、`:3313` `initWebGLFog()` | 這是 Hero 結構、視覺語言與首屏資訊密度的重做；不能以「移除 WebGL」名義繞過 Hero decision。 | **Tier 1 — Craig** |
| Category rail | 完整分類名＋小件數＋微小英文；取消 glyph/badge；375 水平滑動 | `:431` rail、`:440` button、`:455` count、`:484` glyph；`:1886` 折疊後 wrap；`:2787–2810` 動態產生 badge/glyph | 375 水平滑動與已驗證的 R4「折行、所有分頁一次可見」相衝。先保留 R4；glyph／count 的去留應獨立審核，不能與 scroll 行為綁在一起。 | **Decision required**；視覺微調本身可評估 Tier 2，但 mobile rule 先定 |
| Card ornament | 器物圖版＋乾淨資料欄；移除四角、雲霧、focus border、卡片 tilt；只保留必要分類訊號 | `:609` `.card::before/::after`、`:659` vignette、`:673` moving cloud、`:691` focus border、`:3679` `initCardTilt()`；template `:3596–3612` | 與現況直接對應，且不改資料、IA、文案或卡片比例即可完成。保留圖片 lazy load、existing seal、metadata、modal trigger。 | **Tier 2 candidate** |
| Public `LOT` | 不設虛構序號，且不以 UUID／index 替代 | `.lot-number` `:829`；feature positioning `:815`；template uses `index + 1` at `:3612` | 本質是公開內容／識別語意，不是純 CSS。Sol 文件記載為 Craig 決策，但該文件本身是 proposal-only；需得到專案 authority 的直接確認才移除。 | **Conditional Tier 2** — Craig confirmation |
| Card information order | 類別／年代 → 品名 → metadata／摘要 → 進 modal | template currently renders category/era, title, metadata and story around `:3612` | 卡片結構與文案調序會影響現有 R6 story fitting，需先以實際 data 做內容測試。不是「裝飾純減法」的一部分。 | Defer; Tier 2 only with a separate verified slice |
| Modal / market reference | 改名「市場參考」；僅完整一手來源＋人工覆核才顯示；不以 `displayRecommendation` 補位 | markup `:2297–2303`; `openModal()` populates `refItem`／`refPrice`／`displayRecommendation` at `:3237–3242` | 現行邏輯為任一值存在就顯示「鑑定參考」，與 fail-closed 規則相反。所需欄位不在 frozen V1 public contract。 | **Tier 1 + DD-103** |
| Contact / physical viewing | 資訊齊全才提供 LINE、地址、時間與 Maps；不放 disabled CTA 或回覆承諾 | contact section `:2203`; `24 小時` at `:2224`; LINE placeholder at `:2227–2237` | Sol 的判斷正確，但 F1 實體藝廊資訊已暫緩。不得藉視覺整理修改該區。 | **Blocked — owner data / F1** |
| Motion | 保留 modal、filter、image inspect；去除持續霧、moving cloud、tilt 等純氣氛動態 | WebGL gating `:3313–3509`; card motion at `:659–704`, `:3655`, `:3679` | Card motion可與 card ornament slice 一起處理；Hero fog 依舊與 Tier 1 Hero 視覺決策綁定。 | Split: card Tier 2; Hero Tier 1 |

## 5. 待解的明確衝突

### A. 375px 分類列：horizontal scroll vs. verified wrap

Sol mockup 保留橫向捲動；現行程式在分類折疊後刻意改為 `flex-wrap: wrap`，理由是避免超過一半的分類在小螢幕看不見。兩者都可成立，但不能同時成立。

**預設保留現行 wrap。** 若 Craig 希望目次感更強，後續應先用實際最多分類數做一次 375px screenshot／touch target 審查，再決定是否回到 scroll。

### B. `LOT` 是內容決策，不是裝飾決策

自動以 `index + 1` 產生的 `LOT 001` 確實不能代表穩定典藏編號，也容易造成拍賣語意混淆。然而刪除它會改變公開資訊，不應只依設計檔內的歷史敘述自動執行。

**所需確認句：**「吉寶軒公開頁不顯示 `LOT` 或任何替代序號。」確認後才納入下一個 Tier 2 patch。

### C. 「市場參考公開」必須先有資料契約

Sol 所列拍賣行、專場、日期、Lot、價格類型、幣別、URL、比較理由、reviewer、reviewedAt、verified 均不是現有 V1 public API 的已核准欄位。前端只要出現其中一欄，就必須同步由 `writeToSheet()`、`doGet()` 與 frontend parser 實作；這需要 DD，並不是 modal rename。

### D. Hero mockup 是方向，不是既定 UI

三個 breakpoint mockup 的山水裁切與 card reveal 很有價值，但它們同時改動 Hero、header、卡片比例與資訊層級。不可切取單張畫面的文字、導航或假藏品資料直接進入公開頁。

## 6. 建議的下一個唯一 implementation slice

### `P2-OBJECT-FIRST-CARD-REDUCTION`

**目標**：讓器物照片與既有 metadata 成為卡片唯一視覺重點，而不改 Hero、資料、CTA、分類規則或 card IA。

**精確允許範圍（僅 `Publish/index.html`）**

- 刪除 card template 中 `.vignette-cloud`、`.moving-cloud`、`.focus-border` 三個純裝飾節點。
- 移除它們的 CSS 與 `.card::before`／`.card::after` 四角裝飾。
- 移除 `initCardTilt()` 的呼叫與函式；清除只服務於 tilt 的 CSS／listener。
- 將 card hover 收斂至既有 border／1–2px 位移內；手機不新增 hover 依賴。

**明確不做**

- 不移除 `LOT`（除非先取得 §5-B 確認）。
- 不改 `.info-box` 背景、seal 尺寸、card 比例、資料順序、摘要文案或圖片 crop。
- 不動 category rail、Hero／WebGL、modal、contact、GAS、Sheet schema、metadata。
- 不 git add、commit、push、建 branch 或開 PR。

**驗收**

1. 帶有實際 GAS 典藏資料時，1440／1024／375：無 horizontal overflow、器物照片未變形、各 card 仍可開 modal。
2. Mouse／touch：無 tilt、無移動雲、沒有被移除 decoration 遺留的空白或 click target。
3. Keyboard：category tablist、開啟／關閉 modal、Esc、左右導覽與 back-to-top 均保持工作。
4. `prefers-reduced-motion`：卡片載入與 modal 狀態正確；不新增持續動畫。
5. `git diff --check -- Publish/index.html` 通過；只報告該檔案的本輪 diff，不碰工作樹既有修改。

## 7. Craig 決策佇列（不在下一個切片內）

| 決策 | 為何需要 Craig | 決定後才能開始的工作 |
|---|---|---|
| Hero art panel、山水 crop、取消 full-page ink/WebGL | Hero／brand direction／first-screen narrative | Tier 1 Hero slice |
| 375 rail 要 wrap 或 horizontal scroll | 影響小螢幕 discovery pattern；與已驗證 R4 相衝 | Category rail refinement |
| 公開頁是否永久移除 `LOT` | 公開內容與 catalog identity language | 將 `LOT` 合併至 Tier 2 card slice，或另作極小 patch |
| DD-103 市場參考資料契約 | Frozen Sheet V1 與真實性／責任邊界 | Modal dossier + GAS/Sheet/frontend three-way implementation |
| LINE、地址、開放時間、Maps | 對外承諾必須是真實 owner 資料 | Physical-viewing conversion module |

## 8. Design reference 的可保留部分

- 以暖白、墨色、朱紅細線與少量古金建立層級，而不是新增色票。
- Hero 只保留一個文化焦點；卡片避免重複山水、雲、錦格與印章。
- modal 作為「圖錄 lightbox／dossier」，讓照片檢視與資料閱讀並列。
- 高端感來自可查核性、節制與留白，不來自更多古典符號或價格暗示。

---

## Stop line

本文件只定義差異與順序。未取得相應 Tier／DD／owner 資料前，不實作 Hero、market-reference、contact、欄位或公開文案變更；未取得 §5-B 確認前，不移除 `LOT`。
