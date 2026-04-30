"""Compute the diff between config/notion_desired_state.yaml and live Notion schema.

Pure functions — no I/O. The CLI (scripts/ap_notion_reconciler.py) reads
yaml + Notion API and feeds shaped dicts here.

Diff categories per DB:
- missing_properties:  in desired but NOT in actual → would be CREATEd
- extra_properties:    in actual but NOT in desired → potential drift
                       (we don't recommend deleting; just flag)
- type_mismatches:     name matches but type differs → MIGRATION needed
- option_diffs:        select/multi_select option set differs
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from ap_org_bot.infra.paths import CONFIG_DIR


DESIRED_STATE_PATH = CONFIG_DIR / "notion_desired_state.yaml"


@dataclass(frozen=True)
class PropertyDiff:
    """Diff for a single property name."""

    name: str
    kind: str   # "missing" | "extra" | "type_mismatch" | "option_diff"
    desired: Optional[dict] = None
    actual: Optional[dict] = None
    detail: str = ""


@dataclass
class DBDiff:
    """Diff for one Notion database."""

    db_name: str
    db_id: str = ""
    desired_present: bool = True
    actual_present: bool = True
    properties: list[PropertyDiff] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return (
            self.desired_present
            and self.actual_present
            and len(self.properties) == 0
        )

    def to_dict(self) -> dict:
        return {
            "db_name": self.db_name,
            "db_id": self.db_id,
            "desired_present": self.desired_present,
            "actual_present": self.actual_present,
            "is_clean": self.is_clean,
            "properties": [
                {
                    "name": p.name,
                    "kind": p.kind,
                    "desired": p.desired,
                    "actual": p.actual,
                    "detail": p.detail,
                }
                for p in self.properties
            ],
        }


def load_desired_state(path: Optional[Path] = None) -> dict:
    """Read config/notion_desired_state.yaml. Returns the parsed dict, or empty."""
    p = path or DESIRED_STATE_PATH
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _normalise_actual_property(actual: dict) -> dict:
    """Reduce a Notion API property block to the comparable shape used in yaml.

    Notion's GET /databases/{id} returns properties like:
        {"type": "select", "select": {"options": [{name, color, id}, ...]}}
    We convert this to:
        {"type": "select", "options": [{name, color}, ...]}
    so the yaml shape (no `id`s) compares cleanly.
    """
    ptype = actual.get("type")
    out: dict = {"type": ptype}
    if ptype in ("select", "multi_select"):
        opts = (actual.get(ptype) or {}).get("options") or []
        out["options"] = [
            {"name": o.get("name"), "color": o.get("color", "default")}
            for o in opts
        ]
    return out


def _options_match(desired_opts: list[dict], actual_opts: list[dict]) -> tuple[bool, str]:
    """Compare option sets by name (color is informational)."""
    desired_names = {o["name"] for o in desired_opts if "name" in o}
    actual_names = {o["name"] for o in actual_opts if "name" in o}

    missing = desired_names - actual_names
    extra = actual_names - desired_names
    if not missing and not extra:
        return True, ""

    parts = []
    if missing:
        parts.append(f"missing={sorted(missing)}")
    if extra:
        parts.append(f"extra={sorted(extra)}")
    return False, " ".join(parts)


def compute_db_diff(
    db_name: str,
    desired: dict,
    actual: Optional[dict],
) -> DBDiff:
    """Compute diff for one DB.

    Args:
        db_name: logical name (matches a key under `databases:` in yaml).
        desired: desired-state yaml subtree, e.g.
            {"db_id_env": "NOTION_TOPICS_DB",
             "properties": {"議題": {"type": "title"}, ...}}
        actual: Notion API GET /databases/{id} response, or None if DB doesn't exist.

    Returns:
        DBDiff describing the gap.
    """
    diff = DBDiff(db_name=db_name)
    desired_props: dict = (desired or {}).get("properties") or {}

    if actual is None:
        diff.actual_present = False
        # All desired properties are "missing" by definition.
        for name, spec in desired_props.items():
            diff.properties.append(PropertyDiff(
                name=name,
                kind="missing",
                desired=spec,
                detail="DB does not exist on Notion",
            ))
        return diff

    diff.db_id = actual.get("id", "") or ""
    actual_props: dict = actual.get("properties") or {}

    # missing + type_mismatch + option_diff
    for name, desired_spec in desired_props.items():
        if name not in actual_props:
            diff.properties.append(PropertyDiff(
                name=name, kind="missing",
                desired=desired_spec,
                detail="property not present on Notion",
            ))
            continue

        actual_norm = _normalise_actual_property(actual_props[name])
        desired_type = desired_spec.get("type")
        if desired_type != actual_norm["type"]:
            diff.properties.append(PropertyDiff(
                name=name, kind="type_mismatch",
                desired=desired_spec,
                actual=actual_norm,
                detail=f"desired={desired_type}, actual={actual_norm['type']}",
            ))
            continue

        # If select/multi_select, check options
        if desired_type in ("select", "multi_select"):
            d_opts = desired_spec.get("options") or []
            a_opts = actual_norm.get("options") or []
            ok, detail = _options_match(d_opts, a_opts)
            if not ok:
                diff.properties.append(PropertyDiff(
                    name=name, kind="option_diff",
                    desired={"options": d_opts},
                    actual={"options": a_opts},
                    detail=detail,
                ))

    # extra
    for name, actual_spec in actual_props.items():
        if name not in desired_props:
            diff.properties.append(PropertyDiff(
                name=name, kind="extra",
                actual=_normalise_actual_property(actual_spec),
                detail="property exists on Notion but not in desired_state.yaml",
            ))

    return diff
