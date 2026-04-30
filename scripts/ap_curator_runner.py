#!/usr/bin/env python3
"""ap_curator_runner.py — CLI for Sprint 1 Curator agent.

Sprint 1 (this file):
- `classify` — classify a single entry from CLI args (smoke test)
- `review`   — classify a JSON file of N entries (`[{...}, {...}]`)
- `thresholds` — print current rule thresholds
- `eras`     — print the 9-enum

Sprint 1 added:
- `pull-pending` — query Notion Auth Log DB for curator_status='未審' (read-only,
  no write-back yet)

Sprint 2 (future):
- `pull-pending --apply` — write verdicts back to Notion (curator_status update)
- `cron`         — daemon mode with scheduled review passes
- `--llm-judge`  — invoke Sonnet for borderline cases (confidence ∈ [0.7, 0.85])
- Auth Log DB schema migration (add era / category select properties)

Run examples:

    # classify a single entry
    python3 scripts/ap_curator_runner.py classify \\
        --era 清朝 --confidence 0.85 --item-name "粉彩穿花鳳紋瓶" \\
        --category 瓷器

    # review a batch
    python3 scripts/ap_curator_runner.py review tests/fixtures/curator_sample.json

    # show current rules
    python3 scripts/ap_curator_runner.py thresholds
    python3 scripts/ap_curator_runner.py eras
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Force UTF-8 on stdout/stderr so emoji + 中文 render under Windows cp950 console.
# WSL2 / macOS / Linux already default to UTF-8, so this is a no-op there.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Allow running from any cwd.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ap_org_bot.agents._domain.ap.curator import (  # noqa: E402
    DEFAULT_CONFIDENCE_THRESHOLD,
    FORBIDDEN_AD_TONE_WORDS,
    REQUIRED_FIELDS,
    VAGUE_REFERENCE_MARKERS,
    VALID_ERAS,
    CuratorAgent,
    CuratorReview,
)


def _print_review(review: CuratorReview, verbose: bool = True) -> None:
    icon = {"通過": "✅", "待重審": "🟡", "衝突": "🟠", "退回": "❌"}[review.verdict.value]
    line = f"{icon} {review.verdict.value:<6} {review.auth_log_id}"
    print(line)
    if verbose:
        for reason in review.reasons:
            print(f"     ↳ {reason}")
        if review.recommended_action:
            print(f"     → {review.recommended_action}")
        if review.promote_to_kb:
            print(f"     ↗ promote to Knowledge Base")
        print()


def cmd_classify(args: argparse.Namespace) -> int:
    """Classify a single entry from CLI args."""
    entry: dict[str, Any] = {
        "auth_log_id": args.id or "<cli-anonymous>",
        "itemName": args.item_name or "",
        "category": args.category or "",
        "era": args.era or "",
        "confidence": args.confidence,
        "story": args.story or "",
        "refItem": args.ref_item or "",
        "refPrice": args.ref_price or "",
        "displayRecommendation": args.display_rec or "",
        "tags": args.tags or "",
        "userCaption": args.user_caption or "",
        "isValid": args.invalid is False if args.invalid is not None else True,
    }
    threshold = args.threshold or DEFAULT_CONFIDENCE_THRESHOLD
    agent = CuratorAgent(confidence_threshold=threshold)
    review = agent.classify(entry)
    _print_review(review)
    if args.json:
        print(json.dumps(review.to_dict(), ensure_ascii=False, indent=2))
    return 0 if review.verdict.value in ("通過", "待重審") else 1


def cmd_review(args: argparse.Namespace) -> int:
    """Classify a JSON batch."""
    path = Path(args.file)
    if not path.exists():
        print(f"❌ file not found: {path}", file=sys.stderr)
        return 2
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ invalid JSON: {e}", file=sys.stderr)
        return 2
    if not isinstance(entries, list):
        print("❌ JSON must be an array of entry objects", file=sys.stderr)
        return 2

    threshold = args.threshold or DEFAULT_CONFIDENCE_THRESHOLD
    agent = CuratorAgent(confidence_threshold=threshold)
    reviews = agent.review_batch(entries)
    summary = agent.summary(reviews)

    print(f"Reviewed {len(reviews)} entries (threshold={threshold}):\n")
    for r in reviews:
        _print_review(r, verbose=not args.brief)

    print("=== summary ===")
    for verdict, n in summary.items():
        if n > 0:
            print(f"  {verdict}: {n}")

    if args.json:
        out = [r.to_dict() for r in reviews]
        Path(args.json).write_text(
            json.dumps({"summary": summary, "reviews": out}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nfull JSON written to {args.json}")

    # Exit non-zero only if any 衝突 / 退回 — those need attention.
    return 0 if (summary["衝突"] == 0 and summary["退回"] == 0) else 1


def cmd_pull_pending(args: argparse.Namespace) -> int:
    """Sprint 1 read-only: query Notion Auth Log for curator_status='未審'."""
    # Local import keeps `classify`/`review` working when notion_writer is missing.
    from ap_org_bot.infra.notion_client import (
        DB_AUTH_LOG,
        extract_property_value,
        is_enabled,
        query_database,
    )

    if not is_enabled():
        print("❌ NOTION_API_KEY 未設定 (.env.antique)；無法 pull-pending。",
              file=sys.stderr)
        print("   Phase A 啟用步驟見 PHASE_A_SETUP.md。", file=sys.stderr)
        return 2
    if not DB_AUTH_LOG:
        print("❌ NOTION_AUTH_LOG_DB 未設定 (.env.antique)。", file=sys.stderr)
        return 2

    print(f"🔍 Querying Notion Auth Log DB (curator_status='未審', max {args.limit})...")
    try:
        pages = query_database(
            DB_AUTH_LOG,
            filter_={"property": "Curator 標註", "select": {"equals": "未審"}},
            sorts=[{"property": "上傳時間", "direction": "ascending"}],
            page_size=min(args.limit, 100),
        )
    except Exception as e:
        print(f"❌ Notion query failed: {e}", file=sys.stderr)
        return 3

    if not pages:
        print("✨ 無未審條目 — Curator gate 已淨。")
        return 0

    pages = pages[: args.limit]
    print(f"\n📋 找到 {len(pages)} 筆未審條目；開始 review...\n")

    # Map Notion page → Curator entry dict.
    # SCHEMA GAP NOTE: Auth Log DB schema does not currently include era /
    # category select properties (the only categorical fields are 'Curator 標註'
    # itself + 'Gemini 判讀' as rich_text). This means most pulled entries will
    # be flagged 待重審 with reason "missing required fields" — that's the
    # correct signal that Sprint 2 must add schema migration.
    entries: list[dict] = []
    for page in pages:
        entry: dict[str, Any] = {
            "auth_log_id": page.get("id", "<unknown>"),
            "itemName": extract_property_value(page, "鑑定") or "",
            "confidence": extract_property_value(page, "信心度") or 0.0,
            "category": "",  # SCHEMA GAP — not in current Auth Log DB
            "era": "",       # SCHEMA GAP
            "isValid": True,
        }
        entries.append(entry)

    threshold = args.threshold or DEFAULT_CONFIDENCE_THRESHOLD
    agent = CuratorAgent(confidence_threshold=threshold)
    reviews = agent.review_batch(entries)
    summary = agent.summary(reviews)

    for r in reviews:
        _print_review(r, verbose=not args.brief)

    print("=== summary ===")
    for verdict, n in summary.items():
        if n > 0:
            print(f"  {verdict}: {n}")

    # Diagnostic: if all PENDING_REVIEW, surface the schema gap to Craig.
    if entries and summary["待重審"] == len(entries):
        print()
        print("⚠️  全部 待重審 — 這是 Auth Log DB schema gap 訊號。")
        print("   原因：DB 內無 era / category select 欄位，Curator 規則 R3 觸發。")
        print("   Sprint 2 計畫補 schema migration（加 era / category 對應 9-enum + 8-class），")
        print("   現有條目反向回填，新鑑定也帶這 2 欄位入庫。")

    if args.apply:
        print()
        print("ℹ️  --apply 旗標 Sprint 1 尚未實作（write-back 到 Notion）。")
        print("    Sprint 2 將加：通過→curator_status='通過'，待重審→保留+ping Craig，")
        print("    衝突/退回→對應 select 值。")

    return 0 if summary["衝突"] == 0 and summary["退回"] == 0 else 1


def cmd_thresholds(_args: argparse.Namespace) -> int:
    print(f"confidence_threshold (default): {DEFAULT_CONFIDENCE_THRESHOLD}")
    print(f"required_fields:                {sorted(REQUIRED_FIELDS)}")
    print(f"forbidden_ad_tone_words:        {sorted(FORBIDDEN_AD_TONE_WORDS)}")
    print(f"vague_reference_markers:        {sorted(VAGUE_REFERENCE_MARKERS)}")
    return 0


def cmd_eras(_args: argparse.Namespace) -> int:
    for era in sorted(VALID_ERAS):
        print(era)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ap_curator_runner",
        description="AP Curator agent — Sprint 1 rule-based authentication-quality gate",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_c = sub.add_parser("classify", help="classify one entry from CLI args")
    p_c.add_argument("--id", help="auth_log_id (defaults to <cli-anonymous>)")
    p_c.add_argument("--era", required=False, help="era (must be in 9-enum)")
    p_c.add_argument("--confidence", type=float, default=0.0)
    p_c.add_argument("--item-name", help="品名")
    p_c.add_argument("--category", help="分類")
    p_c.add_argument("--story", help="故事")
    p_c.add_argument("--ref-item", help="拍賣參考品")
    p_c.add_argument("--ref-price", help="參考價格")
    p_c.add_argument("--display-rec", help="展示建議")
    p_c.add_argument("--tags", help="標籤 (string or comma-separated)")
    p_c.add_argument("--user-caption", help="用戶描述")
    p_c.add_argument("--invalid", action="store_true",
                     help="treat as Gemini.isValid=False (forces 退回)")
    p_c.add_argument("--threshold", type=float,
                     help=f"confidence threshold override (default {DEFAULT_CONFIDENCE_THRESHOLD})")
    p_c.add_argument("--json", action="store_true", help="also print JSON form")

    p_r = sub.add_parser("review", help="classify a JSON file of N entries")
    p_r.add_argument("file", help="path to JSON array of entries")
    p_r.add_argument("--threshold", type=float)
    p_r.add_argument("--brief", action="store_true", help="terse output (verdict only)")
    p_r.add_argument("--json", help="write full JSON output to this path")

    p_p = sub.add_parser(
        "pull-pending",
        help="query Notion Auth Log for curator_status='未審' and review (Sprint 1: read-only)",
    )
    p_p.add_argument("--limit", type=int, default=20,
                     help="max entries to fetch (default 20)")
    p_p.add_argument("--threshold", type=float)
    p_p.add_argument("--brief", action="store_true")
    p_p.add_argument("--apply", action="store_true",
                     help="(Sprint 2) write verdicts back to Notion")

    sub.add_parser("thresholds", help="print current rule thresholds")
    sub.add_parser("eras", help="print the 9 valid era values")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "classify": cmd_classify,
        "review": cmd_review,
        "pull-pending": cmd_pull_pending,
        "thresholds": cmd_thresholds,
        "eras": cmd_eras,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
