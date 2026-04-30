#!/usr/bin/env python3
"""ap_notion_reconciler.py — declarative diff between desired state yaml and live Notion (blueprint v1.1 §6.4).

Sprint 2: drift mode only (read-only). Sprint 3+ will add enforce mode that
auto-PATCHes live Notion to match desired state.

Run examples:

    # diff all 8 DBs
    python3 scripts/ap_notion_reconciler.py drift

    # diff only the topics DB
    python3 scripts/ap_notion_reconciler.py drift --db topics

    # write a JSON report
    python3 scripts/ap_notion_reconciler.py drift --json out.json

    # show what's in the desired state file (no Notion API call)
    python3 scripts/ap_notion_reconciler.py inspect-desired
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Allow running from any cwd.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from ap_org_bot.reconciler import (  # noqa: E402
    DBDiff,
    compute_db_diff,
    load_desired_state,
)


def _resolve_db_id(db_id_env: str) -> Optional[str]:
    """Look up env var (NOTION_TOPICS_DB, etc) — first os.environ, then notion_writer."""
    val = os.environ.get(db_id_env)
    if val:
        return val
    try:
        from notion_writer import _ENV  # type: ignore
        return _ENV.get(db_id_env) or None
    except Exception:
        return None


def _fetch_actual(db_id: str) -> Optional[dict]:
    """GET /databases/{id} via notion_writer's _post-style helper.

    Falls back to direct urllib if notion_writer isn't loadable.
    """
    if not db_id:
        return None
    try:
        from notion_writer import (  # type: ignore
            NOTION_API_BASE, NOTION_API_KEY, NOTION_VERSION,
        )
        if not NOTION_API_KEY:
            return None
    except Exception:
        return None

    import json as _json
    import ssl
    import urllib.error
    import urllib.request

    url = f"{NOTION_API_BASE}/databases/{db_id}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
    req.add_header("Notion-Version", NOTION_VERSION)
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            return _json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        print(f"   ⚠️  HTTP {e.code} on {db_id[:8]}…: {body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"   ⚠️  fetch failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _print_db_diff(diff: DBDiff) -> None:
    if diff.is_clean:
        print(f"  ✅ {diff.db_name:<22} clean")
        return

    if not diff.actual_present:
        print(f"  ⚠️  {diff.db_name:<22} desired-state defined, "
              f"actual DB NOT FOUND")
        return

    icons = {
        "missing": "➕",
        "extra": "❓",
        "type_mismatch": "⚠️",
        "option_diff": "🔄",
    }
    print(f"  ⚠️  {diff.db_name:<22} {len(diff.properties)} drift(s)")
    for p in diff.properties:
        icon = icons.get(p.kind, "·")
        print(f"        {icon} [{p.kind:<14}] {p.name} — {p.detail}")


def cmd_inspect_desired(_args: argparse.Namespace) -> int:
    desired = load_desired_state()
    dbs = desired.get("databases") or {}
    print(f"📋 Desired state: {len(dbs)} database(s) declared\n")
    for db_name, spec in dbs.items():
        n_props = len(spec.get("properties") or {})
        env_var = spec.get("db_id_env", "?")
        print(f"  {db_name:<22} {n_props} properties  (id env: {env_var})")
    return 0


def cmd_drift(args: argparse.Namespace) -> int:
    desired = load_desired_state()
    dbs = desired.get("databases") or {}
    if not dbs:
        print("❌ No databases declared in config/notion_desired_state.yaml",
              file=sys.stderr)
        return 2

    if args.db:
        if args.db not in dbs:
            print(f"❌ DB '{args.db}' not in desired state. Available: "
                  f"{list(dbs.keys())}",
                  file=sys.stderr)
            return 2
        dbs = {args.db: dbs[args.db]}

    print(f"🔍 Computing drift for {len(dbs)} DB(s)...\n")

    all_diffs: list[DBDiff] = []
    for db_name, spec in dbs.items():
        env_var = spec.get("db_id_env")
        db_id = _resolve_db_id(env_var) if env_var else None
        if not db_id:
            print(f"  ⏭️  {db_name:<22} skipped — env {env_var} not set")
            continue

        actual = _fetch_actual(db_id)
        diff = compute_db_diff(db_name, spec, actual)
        all_diffs.append(diff)
        _print_db_diff(diff)

    print()
    n_clean = sum(1 for d in all_diffs if d.is_clean)
    n_drift = len(all_diffs) - n_clean
    print(f"=== summary ===")
    print(f"  {n_clean} / {len(all_diffs)} DB(s) clean")
    if n_drift:
        print(f"  {n_drift} DB(s) have drift — Sprint 3 enforce mode will auto-fix")
        print(f"  (Sprint 2: drift mode is read-only)")

    if args.json:
        report = {
            "summary": {
                "total": len(all_diffs),
                "clean": n_clean,
                "drift": n_drift,
            },
            "diffs": [d.to_dict() for d in all_diffs],
        }
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n📄 Full report → {args.json}")

    return 0 if n_drift == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ap_notion_reconciler",
        description="Declarative diff between notion_desired_state.yaml and live Notion DBs",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("inspect-desired",
                   help="print declared DBs in desired_state.yaml (no API call)")

    p_drift = sub.add_parser("drift",
                             help="compute diff between desired state and live Notion (read-only)")
    p_drift.add_argument("--db", help="only this DB (default: all)")
    p_drift.add_argument("--json", help="write JSON report to this path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "inspect-desired": cmd_inspect_desired,
        "drift": cmd_drift,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
