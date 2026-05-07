#!/usr/bin/env python3
"""
ap_design_review.py — 吉寶軒 Claude Design Loop 自動 Review 腳本
由 git post-commit hook 自動呼叫，也可手動執行。

用途：
  1. 偵測最新 commit 是否包含 Publish/index.html
  2. 提取 diff 摘要
  3. 根據吉寶軒設計系統規則做靜態分析（無 AI，不耗 quota）
  4. 輸出下一輪 Claude Design brief 到 DESIGN_BRIEF_NEXT.md

執行方式：
  python3 scripts/ap_design_review.py            # 分析最新 commit
  python3 scripts/ap_design_review.py <hash>     # 分析指定 commit
"""

import subprocess
import sys
import os
import re
from datetime import datetime
from pathlib import Path

# Windows cp950 主控台 UTF-8 強制 (emoji / 繁中字元)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── 常數 ────────────────────────────────────────────────────────────────────
REPO_ROOT  = Path(__file__).parent.parent
TARGET     = "Publish/index.html"
BRIEF_OUT  = REPO_ROOT / "DESIGN_BRIEF_NEXT.md"
REVIEW_LOG = REPO_ROOT / "memory" / "design_review_log.md"

# 違規 pattern（靜態掃描，不需 AI）
VIOLATIONS = [
    # 硬編碼顏色（排除已知 fallback）
    (r'(?<!var\()#[0-9a-fA-F]{3,6}(?![\w])',
     "硬編碼 hex 色彩（應使用 CSS 變數）", "brand"),

    # 禁用 framework / npm
    (r'import\s+React|from\s+[\'"]react|from\s+[\'"]vue|tailwind',
     "使用了禁止的 JS framework", "tech"),

    # 禁止在中文字型用 bold
    (r'font-weight:\s*bold(?=.*(?:font-plaque|font-display|font-body|Ma Shan|標楷|LXGW))',
     "brush/kai 字型套用 font-weight: bold（破壞筆觸感）", "type"),

    # SVG presentation attr 用 CSS var
    (r'font-family="var\(',
     'SVG <text> 用 font-family="var(...)" presentation attr（vars 無法在此解析）', "tech"),

    # 禁用 animate width/height/top/left/margin/padding
    (r'(?:transition|animation)[^;{]*(?:\bwidth\b|\bheight\b|\btop\b|\bleft\b|\bmargin\b|\bpadding\b)',
     "動畫/過渡使用了非 compositor 屬性（width/height/top/left/margin）", "animation"),

    # 禁止出現 aurora / teal / purple 漸層
    (r'(?:linear-gradient|radial-gradient)[^;]*(?:teal|purple|#8b5cf6|#06b6d4|aurora)',
     "使用了品牌禁止的色彩（teal/purple/aurora）", "brand"),

    # 俗字檢查
    (r'商品|查看詳情|倉庫(?!目前)|No items found|Book now',
     "使用了品牌俗字（應替換為典藏詞彙）", "copy"),

    # 3-column grid
    (r'grid-template-columns[^;]*repeat\(\s*3',
     "使用了 3-column grid（品牌佈局只允許單欄交錯）", "layout"),
]

OPTIMISTIC_NOTES = [
    (r'prefers-reduced-motion', "✅ 有 prefers-reduced-motion 覆蓋"),
    (r'animation-play-state:\s*paused', "✅ moving-cloud 已暫停（B5）"),
    (r'will-change.*filter.*transform|will-change.*transform.*filter', "✅ will-change 已設定"),
    (r'font-variant-numeric:\s*tabular-nums', "✅ lot-number tabular 對齊"),
    (r'clip-path.*inset', "✅ modal 使用 clip-path 動畫"),
    (r'currentColor', "✅ SVG 使用 currentColor（不硬編碼色彩）"),
]

# ── Git 工具函數 ─────────────────────────────────────────────────────────────

def run(cmd: list[str]) -> str:
    result = subprocess.run(
        cmd, capture_output=True, cwd=REPO_ROOT,
        encoding='utf-8', errors='replace'   # Windows cp950 安全
    )
    return (result.stdout or '').strip()

def get_commit_hash(ref: str = "HEAD") -> str:
    return run(["git", "rev-parse", "--short", ref])

def get_commit_message(ref: str = "HEAD") -> str:
    return run(["git", "log", "-1", "--pretty=%s", ref])

def get_round_number() -> int:
    """根據 design_review_log.md 推算目前是第幾輪"""
    if not REVIEW_LOG.exists():
        return 1
    content = REVIEW_LOG.read_text(encoding="utf-8")
    rounds = re.findall(r"Round\s+(\d+)", content)
    return (max(int(r) for r in rounds) + 1) if rounds else 1

def target_in_commit(ref: str = "HEAD") -> bool:
    changed = run(["git", "diff", "--name-only", f"{ref}~1", ref])
    return TARGET in changed

def get_diff(ref: str = "HEAD") -> str:
    return run(["git", "diff", f"{ref}~1", ref, "--", TARGET])

def get_diff_stat(ref: str = "HEAD") -> str:
    return run(["git", "diff", "--stat", f"{ref}~1", ref, "--", TARGET])

def read_current_html() -> str:
    p = REPO_ROOT / TARGET
    return p.read_text(encoding="utf-8") if p.exists() else ""

# ── 靜態分析 ─────────────────────────────────────────────────────────────────

def analyze(html: str, diff: str) -> dict:
    violations, warnings, passes = [], [], []

    for pattern, desc, category in VIOLATIONS:
        # diff 中新增行（+ 開頭）才算
        new_lines = "\n".join(
            line[1:] for line in diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        if re.search(pattern, new_lines, re.IGNORECASE):
            violations.append(f"[{category.upper()}] {desc}")

    for pattern, desc in OPTIMISTIC_NOTES:
        if re.search(pattern, html, re.IGNORECASE):
            passes.append(desc)

    # 字型四層完整性
    if all(f in html for f in ["--font-plaque", "--font-display", "--font-body", "--font-latin"]):
        passes.append("✅ 四層字型系統完整")

    # modal nav
    if "modal-nav" in html or "modalPrev" in html:
        passes.append("✅ Modal 前後導覽已實作（B2）")

    # highlight-quote
    if "highlight-quote" in html or "highlightQuote" in html:
        passes.append("✅ highlightQuote 金句已渲染（B1）")

    # prefers-reduced-motion 覆蓋
    if ".ruyi-center" in html and "opacity: 1 !important" in html:
        passes.append("✅ prefers-reduced-motion 覆蓋 ruyi-center（D5）")

    return {"violations": violations, "warnings": warnings, "passes": passes}

def score(analysis: dict) -> dict:
    v_count = len(analysis["violations"])
    scores = {
        "品牌一致性": max(0, 4 - sum(1 for v in analysis["violations"] if "BRAND" in v)),
        "動畫品質":   max(0, 4 - sum(1 for v in analysis["violations"] if "ANIMATION" in v)),
        "排版正確性": max(0, 4 - sum(1 for v in analysis["violations"] if "TYPE" in v)),
        "可及性":     4 if any("prefers-reduced-motion" in p for p in analysis["passes"]) else 2,
        "程式碼品質": max(0, 4 - sum(1 for v in analysis["violations"] if "TECH" in v)),
    }
    scores["total"] = sum(scores.values())
    return scores

# ── Brief 生成 ────────────────────────────────────────────────────────────────

NEXT_TASKS = [
    "C1: 卡片 3D tilt 視差效果（±3° rotateXY，mousemove 驅動）",
    "C2: 捲軸印章隨滾動進度旋轉（rotate(progress × 15 - 7.5 deg)）",
    "C4: 分類篩選按鈕加上藏品數量 badge",
    "C5: 8px grid 間距微調（item-era / material-badges → 16px；ruyi-divider margin → 32px）",
    "B4: 聯絡區塊補入實際地址、電話、營業時間（Craig 提供資料後）",
]

def generate_brief(round_n: int, commit_hash: str, commit_msg: str,
                   analysis: dict, scores: dict, diff_stat: str) -> str:
    v_section  = "\n".join(f"  - ❌ {v}" for v in analysis["violations"]) or "  （無違規）"
    p_section  = "\n".join(f"  - {p}" for p in analysis["passes"])        or "  （無）"
    score_rows = "\n".join(f"| {k} | {v}/4 |" for k, v in scores.items() if k != "total")
    next_tasks = "\n".join(f"{i+1}. {t}" for i, t in enumerate(NEXT_TASKS[:3]))

    return f"""# 吉寶軒 Design Review — Round {round_n}

> 自動由 `scripts/ap_design_review.py` 生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}
> Commit: `{commit_hash}` — {commit_msg}

## Diff 摘要
```
{diff_stat or '（無 index.html 改動）'}
```

## 審查結果

### ✅ 通過
{p_section}

### ❌ 違規（必須修正）
{v_section}

## 評分
| 維度 | 分數 |
|---|---|
{score_rows}
| **總分** | **{scores['total']}/20** |

---

## 📋 Round {round_n + 1} — Claude Design Brief
> 複製以下全文貼入 Claude Design

---

你是吉寶軒（Jibao Xuan）的首席設計師，正在優化一個高奢中式古董展覽網站。
品牌定位等同 Sotheby's Asia、Christie's Hong Kong、中國嘉德。

**設計系統核心規則**（必須嚴格遵守）：
- 色彩：sumi ink (#2c2c2c) / rice paper (#f7f4ed) / aged brass (#c49a45) / cinnabar seal (#8a2a2a)
- 四層字型：
  - Plaque（品牌大字）：Ma Shan Zheng → 標楷體 → Noto Serif TC
  - Display（標題/印章）：標楷體 → DFKai-SB → Noto Serif TC
  - Body（故事文字）：LXGW WenKai TC → 標楷體 → Noto Serif TC
  - Latin（批號/年份）：Cormorant Garamond（僅用於 Latin 字元）
- 動畫：只 animate transform / opacity / filter；exit 速度 2× enter；必有 prefers-reduced-motion 覆蓋
- 佈局：單欄交錯卡片（奇右偶左）；絕不用 3-column grid；8px grid 系統
- 技術：純 HTML/CSS/vanilla JS；無 npm / framework；全部改動在 Publish/index.html 一個檔案

**上一輪完成的工作（Round {round_n}）**：
{commit_msg}

**本輪發現的問題**：
{v_section if analysis['violations'] else '  （上一輪無違規，品質良好）'}

**本輪任務（Round {round_n + 1}）**：
{next_tasks}

**輸出要求**：
- 直接輸出完整的 Publish/index.html
- 在修改處加上 `/* CHANGE [任務代號]: 說明 */` 註解
- 確保所有現有功能（modal、WebGL fog、category filter、scroll-seal）保持運作

---
"""

# ── 主流程 ───────────────────────────────────────────────────────────────────

def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"

    print("\n🔍 吉寶軒 Design Review 自動腳本")
    print("=" * 50)

    # 確認 index.html 有在這次 commit 裡
    if not target_in_commit(ref):
        # 找最近一次含 index.html 的 commit
        recent = run(["git", "log", "--oneline", "-1", "--", TARGET])
        if recent:
            ref = recent.split()[0]
            print(f"⚠️  HEAD 未包含 {TARGET}，改用最近 commit：{ref}")
        else:
            print(f"❌ 找不到任何包含 {TARGET} 的 commit，中止。")
            sys.exit(1)

    commit_hash = get_commit_hash(ref)
    commit_msg  = get_commit_message(ref)
    round_n     = get_round_number()
    diff        = get_diff(ref)
    diff_stat   = get_diff_stat(ref)
    html        = read_current_html()

    print(f"📦 Commit : {commit_hash} — {commit_msg}")
    print(f"🎨 Round  : {round_n}")
    print(f"📄 Diff   :\n{diff_stat}\n")

    analysis = analyze(html, diff)
    scores   = score(analysis)

    if analysis["violations"]:
        print("❌ 違規項目：")
        for v in analysis["violations"]:
            print(f"   {v}")
    else:
        print("✅ 無設計違規")

    print(f"\n📊 總分：{scores['total']}/20")

    brief = generate_brief(round_n, commit_hash, commit_msg, analysis, scores, diff_stat)
    BRIEF_OUT.write_text(brief, encoding="utf-8")

    # 附加到 review log
    REVIEW_LOG.parent.mkdir(exist_ok=True)
    with open(REVIEW_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n\n---\n{brief}")

    print(f"\n✅ Brief 已寫入 → {BRIEF_OUT.relative_to(REPO_ROOT)}")
    print("   複製其中內容貼入 Claude Design 開始下一輪優化\n")

if __name__ == "__main__":
    main()
