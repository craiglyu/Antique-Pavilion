# 吉寶軒 Design Brief — Epic D：輔助科技與真機韌性（A11y & Real-Device Resilience）

> 由 Claude Code 依 AP_Design_Loop_v3_Strategy.md §3 產生 · 2026-07-08
> 性質：**最純粹的 loop 自主主戰場** — D1–D6 全自動、無需真實資料、無 Tier 1。
> branch：`design/epic-a11y` · Epic metric：axe a11y 分數、報讀器標題數==卡片數、
> reduced-motion 下 fog rAF 未啟動、斷點重疊/溢出測試通過數。

> ⚠️ **與暖身輪的重疊**：若已先跑 `DESIGN_BRIEF_QuickWins.md`，則 QW2/QW3 已完成
> 本 epic 的 **D1（aria-live）、D2（modal 焦點）、D3（裝飾層 aria-hidden + fog 減動）**。
> 這種情況下 **Epic D 從 D4 起跑**（下方 prompt 已把 D1–D3 標為「若暖身輪已完成則略過」）。

---

## 📋 複製以下全文，貼入 Claude Design text window

```
你是吉寶軒（Jibao Xuan）的首席設計師，正在為一個高奢中式古董展覽網站補完
「輔助科技 + 真機韌性」——讓報讀器、純鍵盤、真實手機使用者拿到與視覺打磨等值的體驗。
品牌定位等同 Sotheby's Asia、Christie's Hong Kong、中國嘉德。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【設計系統】（必須嚴格遵守，違反則整輪作廢）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
色彩（僅此四色 + scale）：
  ink #2c2c2c | paper #f7f4ed | gold #c49a45 | seal-red #8a2a2a
  → 無 blue / teal / purple / aurora gradient
四層字型（font-weight: 400 only）：
  Plaque：Ma Shan Zheng → 標楷體   Display：標楷體 → DFKai-SB
  Body：LXGW WenKai TC → 標楷體    Latin：Cormorant Garamond（僅 Latin 字元）
動畫（Emil）：只 animate transform/opacity/filter；exit 2× enter；
  will-change 在 animationend 後清除；prefers-reduced-motion 覆蓋所有動畫
佈局：單欄交錯卡片（奇右偶左）；絕不用 3-column grid；8px grid；觸控 ≥ 44×44px
技術：純 HTML/CSS/vanilla JS；所有改動在 Publish/index.html 一個檔案內完成

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【本輪 Epic 目標】輔助科技與真機韌性
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
維持既有 5 維美學 20/20 不得回歸。本 epic 追以下量測目標：
  axe a11y 100 · 報讀器標題數 == 可見卡片數 · reduced-motion 下 fog rAF 未啟動 ·
  320/360/375/768/1024+橫向皆無重疊/溢出。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【本輪任務】（一次做 D4–D6；D1–D3 若暖身輪 QW2/QW3 已完成則略過，
             否則先補做——見每項的「前置」註記）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

D1（前置｜暖身輪 QW3(b) 已做則略過）｜aria-live 狀態播報
  新增 sr-only role="status" aria-live="polite"，於 fetch 完成 / 每次篩選 / 空狀態
  更新 textContent（如「青銅專場・共 8 件典藏」）。
  驗收：逐一切分類皆播報且文字與可見卡片數一致。

D2（前置｜暖身輪 QW3(c) 已做則略過）｜modal 焦點一次到位
  .modal-content 加 tabindex="-1"，轉場結束後只 focus 容器一次、移除所有 setTimeout 補焦；
  navigateModal 後把新品名寫入 aria-live（讓切上/下件被報讀）。
  驗收：開啟後 activeElement === .modal-content 且僅一次；Tab/Shift+Tab 焦點不逸出；
        切上/下件報讀新品名。

D3（前置｜暖身輪 QW2+QW3(a) 已做則略過）｜裝飾層與鍵盤放大
  #glCanvas/.bg-layer/.ink-vignette 補 aria-hidden；modal 放大圖改 role="button"+tabindex，
  Enter/Space 切換 zoom、aria-pressed 反映狀態（目前放大僅滑鼠 onclick 可達）。
  驗收：a11y tree 不再出現三裝飾節點；純鍵盤可切換放大、aria-pressed 隨狀態更新。

D4｜卡片語意化
  卡片目前是 <div role="button">，把 h2 品名吞在按鈕內、報讀器 H 鍵列不出標題。
  改為 <article> + 內部一顆真 <button>/<a> 掛在品名 h2 上，保留大點擊區與鍵盤開啟。
  驗收：報讀器 H 鍵標題清單列出每件品名、數量 == 可見卡片數；Enter/Space 仍能開 modal，無回歸。

D5｜動態 header 高度 + 標題響應（除掉 300px magic number）
  現況：category-rail-wrap 用 margin-top: 300px 硬編碼避開固定 hero，一換裝置/字級就疊字或留大洞。
  任務：JS 於載入/resize 量測 header 實際高度，動態設 rail margin-top（取代 300px）；
        brand-title 加 clamp() 降級字級/字距，避免窄屏溢出。
  驗收：320/360/375/768/1024+橫向下 rail 頂緣恆在 hero 底緣下、間距誤差 <8px；
        brand-title scrollWidth ≤ 容器、左右 ≥24px 呼吸。

D6｜觸控手勢 + 安全區
  modal 綁 touchstart/touchend：水平位移 >40px 且垂直 <30px 時切換藏品（取代只能點 ‹/› 按鈕）；
  放大態加拖曳平移可達四角；<meta viewport> 加 viewport-fit=cover，固定 UI bottom 改
  calc(基準 + env(safe-area-inset-bottom))。
  ⚠️ 注意右下已擁擠的固定層（backToTop right:16/bottom:24、scroll-progress-wrap、scroll-seal）——
     手機窄屏務必處理 bottom-right 碰撞與 safe-area 疊加，勿互相遮蓋。
  驗收：合成 TouchEvent 左右滑正確變 index 不越界、垂直不誤觸；放大拖曳 translate 隨手勢達四角；
        瀏海模擬下背景延伸到邊緣、backToTop 底緣距窗底 ≥34px + 基準。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【輸出要求】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 從 GitHub repo 讀取 branch design/epic-a11y（無則自 main 開）的 Publish/index.html。
2. 完成後開 Pull Request：
   - base: main   head: design/epic-a11y
   - title: design(epic-a11y): D4–D6 卡片語意化 + 動態 header + 觸控手勢/安全區
   - 只修改 Publish/index.html
3. 每個改動處加上 /* CHANGE [D1..D6]: 說明 */ 註解。
4. 確保現有功能全部保持運作：modal 前後導覽 + focus trap、category filter、
   WebGL fog、scroll-seal、card tilt、lazy image、back-to-top。
5. ⚠️ 不得改動：四色/四層字型系統、Sheet 欄位、任何真實藝廊資料、provenance 欄位；
   不得新增對外首頁區塊（那屬 Tier 1，需 Craig 簽核）。
```

---

### Craig 執行備註

- 全 6 輪皆自主軌 Tier 2/3。Sprint 5 前 PR 需你手動 review 併入。
- 併入前跑 Phase B' harness：axe a11y、a11y tree 標題數、reduced-motion fog 停、
  320–1024 斷點截圖無破版、合成 TouchEvent 切件正確。
- D4 卡片語意化改動最大（影響 openModal 觸發與鍵盤路徑），回歸測試務必涵蓋鍵盤開/關 modal。
- 若尚未跑暖身輪，可把 D1–D3 一起做（prompt 已含）；若已跑，Claude Design 會依「前置略過」註記只做 D4–D6。
