# GPT Polish Log

## GPT-R1 — 2026-06-11

### 本回合範圍
- P1 favicon 缺失。
- P1 meta description + OpenGraph / Twitter card 缺失。
- P1 卡片比例變體系統死碼，改用實際 Sheet 分類 + 固定節奏。
- P1 回到頂部按鈕。

### 完成項
- 在 `<head>` 補 description、OpenGraph、Twitter card、inline SVG favicon 與 apple-touch-icon。
- 將卡片比例映射改為實際分類：玉器、銅器、陶瓷、雜項、香爐、手爐、木器、金屬器、書畫、祭祀器、銅香爐；每第 7 張升級 feature，未知分類每第 4 張落 landscape，避免全數 portrait。
- 新增右下角印章式回頂按鈕：捲過 2 個 viewport 後顯示，48px touch target，aria-hidden/tabindex 狀態同步，reduced-motion 下取消位移。
- 驗證時發現既有 keyboard modal open 會讓 focus 留在 card；補最小 a11y 修正，改成 keyup 後延遲開啟並加 modal close focus fallback。

### 驗證結果
- `node --check` 等效 inline script parse：通過。
- `git diff --check -- Publish/index.html`：通過；僅提示 Git 會在下次 touch 時 LF→CRLF。
- GAS API：本環境無法連線，未實測真實 API 回應。
- Headless Chrome + Playwright（本機 Chrome executablePath，臨時 route 85 筆資料、11 分類；背景 webp 複製到 Temp 與 index.html 同層）：
  - 1440x900：85 cards、12 tabs、feature 13 / landscape 40 / portrait 32、console errors 0、page errors 0、無水平 overflow、modal open/focus trap/ESC、分類方向鍵、回頂通過。
  - 1024x768：同上，通過。
  - 375x812：同上，通過。

### 回退項與原因
- 無。

### 下回合計畫
- P1 URL hash 還原分類與 modal 狀態。
- P1 手機 modal 左右 swipe。
- 若 P1 剩餘項清完，再進 P2 sticky 分類列或前端搜尋框。

## GPT-R2 — 2026-06-11

### 本回合範圍
- P0 og:image / twitter:image 404：改到 `jibao-xuan-site` Pages URL，並補 `og:url`。
- P1 動畫 token 化第一段：新增 `--ease-out` / `--ease-exit` / `--ease-spring` / `--ease-material` 與 4 級 duration token，替換主要 entrance / exit / filter / modal / CTA 使用點。
- P1 card hover restraint pass：降低卡片 lift、圖片放大、focus-border、金色陰影與 tilt 角度。

### 完成項
- `og:image` 與 `twitter:image`：`https://craiglyu.github.io/Antique-Pavilion/...webp` → `https://craiglyu.github.io/jibao-xuan-site/...webp`。
- 新增 `<meta property="og:url" content="https://craiglyu.github.io/jibao-xuan-site/">`。
- Motion tokens：
  - `--ease-out: cubic-bezier(0.25, 1, 0.5, 1)`
  - `--ease-exit: cubic-bezier(0.4, 0, 1, 1)`
  - `--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1)`
  - `--ease-material: cubic-bezier(0.4, 0, 0.2, 1)`
  - `--dur-quick/base/slow/brand`
- Hover old → new：
  - card lift `translateY(-5px)` → `translateY(-3px)`
  - card hover shadow `0 20px 50px rgba(196,154,69,0.3)` → `0 14px 36px rgba(196,154,69,0.18)`
  - image scale `1.08` → `1.035`
  - hover image brightness `1.02` → `1`
  - focus border opacity `0.8` → `0.55`
  - mouse tilt `±3deg` → `±2deg`

### 驗證結果
- Inline script parse：通過。
- `git diff --check -- Publish/index.html`：通過；僅提示 Git 會在下次 touch 時 LF→CRLF。
- Public og:image HEAD：`200 image/webp`。
- Headless Chrome + Playwright（臨時目錄，route 85 筆資料、11 分類，背景 webp 與 index 同層）：
  - 1440x900：85 cards、12 tabs、feature 13 / landscape 40 / portrait 32、body height 47642、無水平 overflow、console/page errors 0。
  - 1024x768：85 cards、12 tabs、同樣 variant 分布、無水平 overflow、console/page errors 0。
  - 375x812：85 cards、12 tabs、同樣 variant 分布、body height 56447、無水平 overflow、console/page errors 0。
  - 鍵盤：分類列 ArrowRight 通過；modal Enter 開啟、focus 在 close button、ESC 關閉通過。
  - Hover computed：card translateY -3px、image scale 1.035、focus-border opacity 0.55、shadow alpha 0.18。
  - `prefers-reduced-motion: reduce`：matchMedia true；scroll invite animation none；back-to-top transition 近零時間。

### 回退項與原因
- 無。

### 下回合計畫
- P1 shadow language token 化。
- P1 modal 進場 interior cascade。
- P1 filter transition staged exit / enter polish。

## 待 Craig 決策
- 無新增。
