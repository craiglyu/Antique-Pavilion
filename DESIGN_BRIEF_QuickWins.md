# 吉寶軒 Design Brief — Quick-Win Sprint（立即暖身輪）

> 由 Claude Code 依 AP_Design_Loop_v3_Strategy.md 產生 · 2026-07-08
> 性質：**跨 epic 精選**，5 個最高 CP 的自主項（無 Tier 1、無需真實資料）。一輪拿下、順手驗證新 harness。
> branch：`design/quick-wins` · Tier 2/3（自主軌，Sprint 5 前停在 PR 由 Craig 併）

---

## 📋 複製以下全文，貼入 Claude Design text window

```
你是吉寶軒（Jibao Xuan）的首席設計師，正在優化一個高奢中式古董展覽網站。
品牌定位等同 Sotheby's Asia、Christie's Hong Kong、中國嘉德。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【設計系統】（必須嚴格遵守，違反則整輪作廢）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
色彩（僅此四色 + scale）：
  ink #2c2c2c 墨 | paper #f7f4ed 宣紙 | gold #c49a45 黃銅 | seal-red #8a2a2a 朱砂
  → 無任何 blue / teal / purple / aurora gradient
四層字型（font-weight: 400 only，絕不用 bold）：
  Plaque：Ma Shan Zheng → 標楷體      Display：標楷體 → DFKai-SB
  Body：LXGW WenKai TC → 標楷體        Latin：Cormorant Garamond（僅 Latin 字元）
動畫（Emil Kowalski）：
  只 animate transform / opacity / filter；exit 速度 2× enter；
  will-change 在 animationend 後清除；prefers-reduced-motion 必須覆蓋所有動畫
佈局：單欄交錯卡片（奇右偶左）；絕不用 3-column grid；8px grid；觸控 ≥ 44×44px
技術：純 HTML/CSS/vanilla JS；所有改動在 Publish/index.html 一個檔案內完成

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【本輪定位】跨 epic 暖身輪 — 補完「內部美學尺量不到、但真正影響體驗」的 5 個缺口
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
既有 5 維美學 audit 已滿分 20/20，本輪不碰像素微調，只補產出型缺口。
維持 20/20 不得回歸（可及性/視覺層次/品牌一致性/動畫品質/程式碼品質）。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【本輪任務】（5 項，每項附驗收標準）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QW1｜圖片韌性 onerror fallback
  現況：卡片(lazyImageObserver 設 img.src)與 modal 圖都走
        drive.google.com/thumbnail?id=…；該端點會限流/對非公開檔回 403，目前無 onerror
        → 一次限流就在奢華頁面顯示瀏覽器破圖 icon。品牌佔位 SVG 已存在於檔內
        （imageUrl 為 falsy 時的預設值），只差在「imageUrl 存在但載入失敗」時切回。
  任務：卡片與 modal 的 img 都加 onerror → 切換到品牌印章 SVG 佔位圖；
        並加 referrerpolicy="no-referrer"、decoding="async"。
  驗收：把某件 imageUrl 改成無效 Drive id / 封鎖 drive.google.com 後，
        全頁顯示品牌佔位圖而非破圖 icon；不影響正常圖片載入。

QW2｜WebGL 縹霧補 reduced-motion gate + 捲離 hero 暫停 rAF
  現況：initWebGLFog() 已有裝置閘（cores<=4 || memGB<4 時 return），但
        (a) 完全無視 OS 的 prefers-reduced-motion；(b) 捲過 hero 後仍全速 drawArrays 空耗 GPU
        （只在分頁隱藏時暫停）。這是整頁最大動態元素，卻是唯一忽略減動請求的。
  任務：(a) initWebGLFog() 開頭加 matchMedia('(prefers-reduced-motion: reduce)') 判斷，
            為真則隱藏 canvas 並 return；
        (b) 以 IntersectionObserver 監看 hero sentinel，捲離 hero 即 cancelAnimationFrame、
            回到 hero 再 requestAnimationFrame（沿用既有 startTime 補償邏輯，避免時間跳躍）。
  驗收：開 OS 減少動態後，未排程任何 rafId、兩幀 readPixels 一致（畫面靜止）；
        捲離 hero 後 GPU/Scripting 軌道歸零；捲回 hero 恢復且無時間跳躍。

QW3｜a11y 三件套
  (a) 裝飾層 aria-hidden：#glCanvas、.bg-layer、.ink-vignette 補 aria-hidden="true"
      （其餘裝飾層已標，這三個漏掉）。
  (b) 篩選 aria-live 播報：新增一個 sr-only role="status" aria-live="polite" 節點，
      於 fetch 完成 / 每次切分類 / 空狀態時更新 textContent（如「青銅專場・共 8 件典藏」）。
  (c) modal 焦點落在內容：.modal-content 加 tabindex="-1"，轉場結束後（transitionend）
      只 focus 容器一次，移除 openModal() 目前那組多重 setTimeout 補焦 hack，
      讓報讀器先唸品名而非「關閉」。
  驗收：a11y tree 不再出現三個裝飾節點；逐一切分類皆播報且文字與可見卡片數一致；
        開 modal 後 activeElement === .modal-content 且僅一次，Tab/Shift+Tab 焦點不逸出。

QW4｜modal 敘事順序倒置修正
  現況：modal-right 的 DOM 順序是 title→era→badges→鑑定參考(參考品/參考價)→故事→金句→tags→洽詢，
        「先價後事」把體驗定調成「標好價的資料庫」，與非電商、重敘事的品牌定位相悖。
  任務：改 DOM 順序（或 flex order）為 故事 → 金句 → 鑑定參考 → 洽詢。
        注意 JS 以 element id 寫 textContent，重排 DOM 節點不會破壞填值邏輯。
  驗收：DOM 中 modal-story 在 modal-appraisal 之前；各欄位填值同步、無空區塊殘留。

QW5｜邊緣三態品牌化
  現況：篩選無結果已品牌化（虛 glyph）；但「整體抓不到資料」與「連線失敗」兩態是裸文字，
        且 error 態把 GAS URL 與 e.message 洩漏給貴賓。
  任務：no-data 態與 error 態改為印章插圖 + 品牌字型文案 + 下一步引導（瀏覽其他專場 / 洽詢）；
        error 態移除 e.message 與 API_URL 字串（僅在 console 保留除錯資訊）。
  驗收：模擬 artifactsData=[] 與 fetch reject 時，畫面呈現品牌化插圖與得體文案、
        不出現任何技術字串（GAS URL / JS 例外）；符合四色與四層字型系統。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【輸出要求】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 從 GitHub repo 讀取最新的 Publish/index.html（main）。
2. 完成優化後開 Pull Request：
   - base: main   head: design/quick-wins
   - title: design(quick-wins): 圖片韌性 + WebGL 減動 + a11y 三件套 + modal 敘事 + 邊緣三態
   - 只修改 Publish/index.html
3. 每個改動處加上 /* CHANGE [QW1..QW5]: 說明 */ 註解。
4. 確保現有功能全部保持運作：modal、WebGL fog、category filter、scroll-seal、
   card tilt、lazy image、back-to-top、focus trap。
5. ⚠️ 不得改動：四色/四層字型系統、Sheet 欄位、任何真實藝廊資料、provenance 欄位。
```

---

### Craig 執行備註

- 完成後這是 Tier 2/3 自主軌產出——**Sprint 5 branch protection 上線前**，PR 需你手動 review 併入
  （merge 前跑一次 Phase B' harness：Lighthouse 不回歸、axe a11y 提升、reduced-motion 下 fog 停）。
- QW3(c) 若動到 modal 焦點時序，務必回歸測試鍵盤開 modal（Enter/Space on card）與 ESC 關閉。
- 跑 harness 前確認 `/usage-status` 未逼近 §6 上限。
