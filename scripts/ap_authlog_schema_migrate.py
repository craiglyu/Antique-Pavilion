#!/usr/bin/env python3
"""ap_authlog_schema_migrate.py — Notion Auth Log DB schema migration CLI.

Reads a migration yaml under config/migrations/ and applies it to the Notion
Authentication Log DB via PATCH /v1/databases/{id}.

Sprint 2 scope:
- `inspect`     — print current DB schema (read-only)
- `dry-run`     — print the diff between current schema and target migration
- `apply`       — PATCH the DB (REQUIRES NOTION_API_KEY + Craig confirmation)

Sprint 3 scope (deferred):
- backfill      — fill historical entries' era/category by re-asking Gemini

Run examples:

    python3 scripts/ap_authlog_schema_migrate.py inspect
    python3 scripts/ap_authlog_schema_migrate.py dry-run config/migrations/2026-04-30_auth_log_v1_to_v2.yaml
    python3 scripts/ap_authlog_schema_migrate.py apply  config/migrations/2026-04-30_auth_log_v1_to_v2.yaml --confirm
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

# Allow running from any cwd.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import yaml  # noqa: E402

from ap_org_bot.infra.paths import MIGRATIONS_DIR  # noqa: E402

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


# ── Lazy imports of Notion config (after sys.path is set up) ────────


def _load_notion_credentials() -> tuple[Optional[str], Optional[str]]:
    """Returns (api_key, db_id) or (None, None) if not configured."""
    try:
        from notion_writer import DB_AUTH_LOG, NOTION_API_KEY  # type: ignore
        return NOTION_API_KEY, DB_AUTH_LOG
    except Exception:
        return None, None


# ── HTTP helpers (independent of notion_writer to keep this script self-contained) ─


def _http(method: str, path: str, payload: Optional[dict] = None) -> Optional[dict]:
    api_key, _ = _load_notion_credentials()
    if not api_key:
        return None
    url = f"{NOTION_API_BASE}{path}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Notion-Version", NOTION_VERSION)
    if payload:
        req.add_header("Content-Type", "application/json")
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        print(f"❌ Notion HTTP {e.code} on {method} {path}", file=sys.stderr)
        print(f"   {body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"❌ Notion request error: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _get_current_schema(db_id: str) -> Optional[dict]:
    return _http("GET", f"/databases/{db_id}")


# ── Migration loader + diff ─────────────────────────────────────────


def _load_migration_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"migration yaml not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _diff_schemas(current: dict, target: dict) -> dict:
    """Compute additive / rename / remove diff between current Notion schema
    and target migration's `add_properties` block."""
    current_props = (current or {}).get("properties", {}) or {}
    target_add = target.get("add_properties", {}) or {}
    target_remove = target.get("remove_properties", []) or []
    target_rename = target.get("rename_properties", {}) or {}

    to_add: dict[str, dict] = {}
    already_present: list[str] = []
    for name, spec in target_add.items():
        if name in current_props:
            already_present.append(name)
        else:
            to_add[name] = spec

    return {
        "to_add": to_add,
        "already_present": already_present,
        "to_remove": target_remove,
        "to_rename": target_rename,
    }


def _spec_to_notion_property(spec: dict) -> dict:
    """Convert migration yaml's property spec to Notion API property body."""
    ptype = spec["type"]
    if ptype == "select":
        return {
            "select": {
                "options": [
                    {"name": opt["name"], "color": opt.get("color", "default")}
                    for opt in spec.get("options", [])
                ]
            }
        }
    if ptype == "multi_select":
        return {
            "multi_select": {
                "options": [
                    {"name": opt["name"], "color": opt.get("color", "default")}
                    for opt in spec.get("options", [])
                ]
            }
        }
    if ptype == "checkbox":
        return {"checkbox": {}}
    if ptype == "rich_text":
        return {"rich_text": {}}
    if ptype == "number":
        return {"number": {"format": spec.get("format", "number")}}
    if ptype == "url":
        return {"url": {}}
    if ptype == "date":
        return {"date": {}}
    raise ValueError(f"unsupported property type: {ptype}")


# ── Subcommands ─────────────────────────────────────────────────────


def cmd_inspect(_args: argparse.Namespace) -> int:
    api_key, db_id = _load_notion_credentials()
    if not api_key:
        print("❌ NOTION_API_KEY 未設 (.env.antique)。", file=sys.stderr)
        return 2
    if not db_id:
        print("❌ NOTION_AUTH_LOG_DB 未設。", file=sys.stderr)
        return 2

    schema = _get_current_schema(db_id)
    if schema is None:
        return 3

    print(f"📋 Authentication Log DB ({db_id[:8]}…)")
    title_block = schema.get("title", [])
    if title_block:
        print(f"   Title: {''.join(t.get('plain_text', '') for t in title_block)}")
    print()
    print(f"   Current properties ({len(schema.get('properties', {}))}):")
    for name, prop in (schema.get("properties") or {}).items():
        ptype = prop.get("type", "?")
        extra = ""
        if ptype == "select":
            opts = (prop.get("select") or {}).get("options") or []
            extra = f" — {len(opts)} options"
        print(f"      • {name:<25} ({ptype}){extra}")
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    migration = _load_migration_yaml(Path(args.migration_file))
    api_key, db_id = _load_notion_credentials()
    if not api_key or not db_id:
        # We can still print the migration body without Notion access.
        print(f"⚠️  Notion credentials missing — printing migration intent only.\n")
        print(json.dumps(migration, ensure_ascii=False, indent=2))
        return 0

    schema = _get_current_schema(db_id)
    if schema is None:
        return 3

    diff = _diff_schemas(schema, migration)

    print(f"📋 Migration: {migration.get('migration_id', 'unnamed')}")
    print(f"   {migration.get('description', '')}")
    print(f"   Target DB: {db_id[:8]}…")
    print(f"   Version: {migration.get('from_version')} → {migration.get('to_version')}\n")

    print(f"✅ {len(diff['already_present'])} property(ies) already present:")
    for name in diff["already_present"]:
        print(f"      ✓ {name}")
    print()

    print(f"➕ {len(diff['to_add'])} property(ies) WILL be added:")
    for name, spec in diff["to_add"].items():
        ptype = spec["type"]
        if ptype in ("select", "multi_select"):
            n_opts = len(spec.get("options", []))
            print(f"      + {name:<20} ({ptype}, {n_opts} options)")
        else:
            print(f"      + {name:<20} ({ptype})")
    print()

    if diff["to_remove"]:
        print(f"⚠️  {len(diff['to_remove'])} property(ies) WILL be removed:")
        for name in diff["to_remove"]:
            print(f"      - {name}")
        print()

    backfill = migration.get("backfill", "noop")
    print(f"📦 Backfill: {backfill}")
    if backfill != "noop":
        print(f"   ⚠️  Existing entries WILL be modified — review carefully")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    if not args.confirm:
        print("❌ apply requires --confirm flag (safety guard).", file=sys.stderr)
        print("   Re-run with: --confirm", file=sys.stderr)
        return 4

    migration = _load_migration_yaml(Path(args.migration_file))
    api_key, db_id = _load_notion_credentials()
    if not api_key:
        print("❌ NOTION_API_KEY 未設.", file=sys.stderr)
        return 2
    if not db_id:
        print("❌ NOTION_AUTH_LOG_DB 未設.", file=sys.stderr)
        return 2

    schema = _get_current_schema(db_id)
    if schema is None:
        return 3
    diff = _diff_schemas(schema, migration)

    if not diff["to_add"]:
        print("✨ Nothing to add — schema already matches target.")
        return 0

    properties_payload: dict[str, Any] = {}
    for name, spec in diff["to_add"].items():
        try:
            properties_payload[name] = _spec_to_notion_property(spec)
        except ValueError as e:
            print(f"❌ {e} (property {name})", file=sys.stderr)
            return 5

    print(f"🔧 PATCH /databases/{db_id[:8]}… "
          f"adding {len(properties_payload)} properties...")
    result = _http("PATCH", f"/databases/{db_id}",
                   {"properties": properties_payload})
    if result is None:
        return 3

    # Verify
    after = _get_current_schema(db_id)
    if after is None:
        print("⚠️  apply succeeded but post-verify failed.")
        return 0
    after_props = set((after.get("properties") or {}).keys())
    added = [n for n in properties_payload if n in after_props]
    print(f"✅ Added {len(added)}/{len(properties_payload)} properties.")
    for name in added:
        print(f"      ✓ {name}")

    print()
    print("📝 Next: reverse-fill is intentionally noop. New entries will start "
          "populating era/category once GAS analyzeWithGemini() is updated to "
          "emit them (already in v9.1 schema; verify deploy).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ap_authlog_schema_migrate",
        description="Notion Auth Log DB schema migration CLI",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("inspect", help="print current Notion DB schema")

    p_dry = sub.add_parser("dry-run", help="print the diff (no writes)")
    p_dry.add_argument(
        "migration_file",
        nargs="?",
        default=str(MIGRATIONS_DIR / "2026-04-30_auth_log_v1_to_v2.yaml"),
        help="migration yaml path (default: latest)",
    )

    p_a = sub.add_parser("apply", help="PATCH the DB with the migration")
    p_a.add_argument("migration_file")
    p_a.add_argument("--confirm", action="store_true",
                     help="REQUIRED — explicit safety acknowledgement")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "inspect": cmd_inspect,
        "dry-run": cmd_dry_run,
        "apply": cmd_apply,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
