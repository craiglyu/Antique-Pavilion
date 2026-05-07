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


def _patch_add_properties(db_id: str, props: dict) -> Optional[dict]:
    """PATCH /databases/{id} to add missing properties.

    `props` is a dict of {property_name: notion_property_body}.
    Returns the Notion API response on success, or None on failure.
    """
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
    payload = {"properties": props}
    data = _json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PATCH")
    req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return _json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        print(f"   ❌ PATCH HTTP {e.code} on {db_id[:8]}…: {body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"   ❌ PATCH failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _desired_spec_to_notion_body(spec: dict) -> Optional[dict]:
    """Convert a desired-state yaml property spec to the Notion API property body.

    Returns None if the type is unsupported (caller should skip that property).
    """
    ptype = spec.get("type")
    if ptype == "title":
        return {"title": {}}
    if ptype == "rich_text":
        return {"rich_text": {}}
    if ptype == "number":
        return {"number": {"format": spec.get("format", "number")}}
    if ptype == "select":
        return {
            "select": {
                "options": [
                    {"name": o["name"], "color": o.get("color", "default")}
                    for o in (spec.get("options") or [])
                ]
            }
        }
    if ptype == "multi_select":
        return {
            "multi_select": {
                "options": [
                    {"name": o["name"], "color": o.get("color", "default")}
                    for o in (spec.get("options") or [])
                ]
            }
        }
    if ptype == "checkbox":
        return {"checkbox": {}}
    if ptype == "url":
        return {"url": {}}
    if ptype == "date":
        return {"date": {}}
    if ptype == "email":
        return {"email": {}}
    if ptype == "files":
        return {"files": {}}
    return None


def cmd_enforce(args: argparse.Namespace) -> int:
    """Enforce mode: PATCH Notion DBs to add missing properties (additive only).

    Safety rules:
    - Only fixes `missing` diffs (additive) — never deletes or type-changes
    - `type_mismatch` and `extra` are flagged but NOT auto-fixed (human review)
    - Requires --confirm flag
    """
    if not args.confirm:
        print("❌ enforce requires --confirm flag (safety guard).", file=sys.stderr)
        print("   Re-run with: enforce --confirm", file=sys.stderr)
        return 4

    desired = load_desired_state()
    dbs = desired.get("databases") or {}
    if not dbs:
        print("❌ No databases in config/notion_desired_state.yaml", file=sys.stderr)
        return 2

    if args.db:
        if args.db not in dbs:
            print(f"❌ DB '{args.db}' not found. Available: {list(dbs.keys())}",
                  file=sys.stderr)
            return 2
        dbs = {args.db: dbs[args.db]}

    print(f"🔧 Enforce mode — checking {len(dbs)} DB(s)...\n")

    total_added = 0
    total_skipped = 0
    needs_human: list[str] = []

    for db_name, spec in dbs.items():
        env_var = spec.get("db_id_env")
        db_id = _resolve_db_id(env_var) if env_var else None
        if not db_id:
            print(f"  ⏭️  {db_name:<22} skipped — env {env_var} not set")
            continue

        actual = _fetch_actual(db_id)
        diff = compute_db_diff(db_name, spec, actual)

        missing = [p for p in diff.properties if p.kind == "missing"]
        type_mis = [p for p in diff.properties if p.kind == "type_mismatch"]
        option_d = [p for p in diff.properties if p.kind == "option_diff"]

        if not diff.actual_present:
            print(f"  ⚠️  {db_name:<22} DB not found on Notion — skipping")
            continue

        if type_mis:
            for p in type_mis:
                needs_human.append(f"{db_name}.{p.name}: {p.detail}")

        if option_d:
            for p in option_d:
                needs_human.append(f"{db_name}.{p.name}: option_diff — {p.detail}")

        if not missing:
            print(f"  ✅ {db_name:<22} nothing to add")
            continue

        props_to_add: dict[str, dict] = {}
        for pd in missing:
            desired_spec = pd.desired or {}
            body = _desired_spec_to_notion_body(desired_spec)
            if body is None:
                print(f"       ⚠️  {pd.name}: unsupported type {desired_spec.get('type')} — skipped")
                total_skipped += 1
                continue
            props_to_add[pd.name] = body

        if not props_to_add:
            continue

        print(f"  🔧 {db_name:<22} PATCH adding {len(props_to_add)} propert(ies)...")
        result = _patch_add_properties(db_id, props_to_add)
        if result is None:
            print(f"       ❌ PATCH failed — check credentials / permissions")
            continue

        for name in props_to_add:
            print(f"       ✓ added: {name}")
        total_added += len(props_to_add)

    print()
    print(f"=== enforce summary ===")
    print(f"  {total_added} propert(ies) added")
    if total_skipped:
        print(f"  {total_skipped} propert(ies) skipped (unsupported type)")
    if needs_human:
        print(f"\n⚠️  {len(needs_human)} issue(s) require human review:")
        for issue in needs_human:
            print(f"     • {issue}")
        print("   type_mismatch and option_diff are NOT auto-fixed.")
    return 0


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

    p_enforce = sub.add_parser(
        "enforce",
        help="PATCH Notion DBs to add missing properties (additive only, requires --confirm)",
    )
    p_enforce.add_argument("--db", help="only this DB (default: all)")
    p_enforce.add_argument("--confirm", action="store_true",
                           help="REQUIRED — explicit safety acknowledgement")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "inspect-desired": cmd_inspect_desired,
        "drift": cmd_drift,
        "enforce": cmd_enforce,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
