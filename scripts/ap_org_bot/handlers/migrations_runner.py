"""migrations_runner.py — startup Notion schema audit (Sprint 4).

Safe-by-default: read-only drift audit unless AP_MIGRATIONS_AUTO_APPLY=1 is set.
Reuses ap_org_bot.reconciler (compute_db_diff, load_desired_state) — no subprocess.
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from typing import Optional

from ap_org_bot.reconciler import compute_db_diff, load_desired_state

log = logging.getLogger(__name__)

_NOTION_API_BASE_DEFAULT = "https://api.notion.com/v1"
_NOTION_VERSION_DEFAULT = "2022-06-28"


def _notion_api_key() -> Optional[str]:
    val = os.environ.get("NOTION_API_KEY")
    if val:
        return val
    try:
        from notion_writer import NOTION_API_KEY  # type: ignore
        return NOTION_API_KEY or None
    except Exception:
        return None


def _notion_consts() -> tuple[str, str]:
    try:
        from notion_writer import NOTION_API_BASE, NOTION_VERSION  # type: ignore
        return NOTION_API_BASE, NOTION_VERSION
    except Exception:
        return _NOTION_API_BASE_DEFAULT, _NOTION_VERSION_DEFAULT


def _resolve_db_id(env_var: str) -> Optional[str]:
    val = os.environ.get(env_var)
    if val:
        return val
    try:
        from notion_writer import _ENV  # type: ignore
        return _ENV.get(env_var) or None
    except Exception:
        return None


def _fetch_actual(db_id: str) -> Optional[dict]:
    api_key = _notion_api_key()
    if not api_key or not db_id:
        return None
    base, version = _notion_consts()
    url = f"{base}/databases/{db_id}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Notion-Version", version)
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        log.warning("[migrations] fetch DB %s HTTP %d", db_id[:8], e.code)
        return None
    except Exception as e:
        log.warning("[migrations] fetch DB %s failed: %s", db_id[:8], e)
        return None


def _desired_spec_to_notion_body(spec: dict) -> Optional[dict]:
    ptype = spec.get("type")
    if ptype == "title":
        return {"title": {}}
    if ptype == "rich_text":
        return {"rich_text": {}}
    if ptype == "number":
        return {"number": {"format": spec.get("format", "number")}}
    if ptype == "select":
        return {"select": {"options": [
            {"name": o["name"], "color": o.get("color", "default")}
            for o in (spec.get("options") or [])
        ]}}
    if ptype == "multi_select":
        return {"multi_select": {"options": [
            {"name": o["name"], "color": o.get("color", "default")}
            for o in (spec.get("options") or [])
        ]}}
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


def _patch_add_properties(db_id: str, props: dict) -> Optional[dict]:
    api_key = _notion_api_key()
    if not api_key or not db_id:
        return None
    base, version = _notion_consts()
    url = f"{base}/databases/{db_id}"
    data = json.dumps({"properties": props}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PATCH")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Notion-Version", version)
    req.add_header("Content-Type", "application/json")
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        log.warning("[migrations] PATCH DB %s HTTP %d", db_id[:8], e.code)
        return None
    except Exception as e:
        log.warning("[migrations] PATCH DB %s failed: %s", db_id[:8], e)
        return None


class MigrationsRunner:
    """At bot startup, check Notion schema drift and optionally enforce.

    Safe-by-default: read-only audit unless AP_MIGRATIONS_AUTO_APPLY=1
    env var is set. Production bot should run audit-only by default;
    Craig manually flips the env var when he wants auto-apply.
    """

    def __init__(self, *, auto_apply: bool = False, dry_run: bool = True):
        self.auto_apply = auto_apply
        self.dry_run = dry_run

    def run_at_startup(self) -> dict:
        """Returns {drift_found: int, applied: int, errors: list, skipped_reason: str}.

        Logic:
        1. Read config/notion_desired_state.yaml for all desired DB schemas.
        2. For each DB call compute_db_diff (no subprocess).
        3. If auto_apply=True and dry_run=False: PATCH missing properties.
        4. Otherwise log warnings listing drift per DB.
        5. Return summary dict.
        """
        result: dict = {
            "drift_found": 0,
            "applied": 0,
            "errors": [],
            "skipped_reason": "",
        }

        if not _notion_api_key():
            result["skipped_reason"] = "NOTION_API_KEY not set"
            log.info("[migrations] skipping startup audit — NOTION_API_KEY not set")
            return result

        desired = load_desired_state()
        dbs = desired.get("databases") or {}
        if not dbs:
            result["skipped_reason"] = "no databases in notion_desired_state.yaml"
            return result

        for db_name, spec in dbs.items():
            env_var = spec.get("db_id_env")
            db_id = _resolve_db_id(env_var) if env_var else None
            if not db_id:
                log.debug("[migrations] %s skipped — env %s not set", db_name, env_var)
                continue

            try:
                actual = _fetch_actual(db_id)
                diff = compute_db_diff(db_name, spec, actual)
            except Exception as e:
                log.warning("[migrations] %s diff failed: %s", db_name, e)
                result["errors"].append(f"{db_name}: {e}")
                continue

            missing = [p for p in diff.properties if p.kind == "missing"]
            non_additive = [p for p in diff.properties if p.kind != "missing"]

            if missing:
                result["drift_found"] += len(missing)
                log.warning(
                    "[migrations] %s: %d missing propert(ies): %s",
                    db_name, len(missing), [p.name for p in missing],
                )
            if non_additive:
                log.warning(
                    "[migrations] %s: %d non-additive drift(s) require human review: %s",
                    db_name, len(non_additive), [p.name for p in non_additive],
                )

            if not missing or self.dry_run or not self.auto_apply:
                continue

            props_to_add: dict[str, dict] = {}
            for pd in missing:
                body = _desired_spec_to_notion_body(pd.desired or {})
                if body is None:
                    log.warning(
                        "[migrations] %s.%s: unsupported type — skipped",
                        db_name, pd.name,
                    )
                    continue
                props_to_add[pd.name] = body

            if not props_to_add:
                continue

            try:
                patch_result = _patch_add_properties(db_id, props_to_add)
                if patch_result is None:
                    result["errors"].append(f"{db_name}: PATCH returned None")
                else:
                    result["applied"] += len(props_to_add)
                    log.info(
                        "[migrations] %s: applied %d propert(ies): %s",
                        db_name, len(props_to_add), list(props_to_add),
                    )
            except Exception as e:
                log.warning("[migrations] %s: PATCH failed: %s", db_name, e)
                result["errors"].append(f"{db_name}: {e}")

        return result
