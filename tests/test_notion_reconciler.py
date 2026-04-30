"""notion_reconciler: pure-function diff between desired state and Notion API responses."""

from __future__ import annotations

import textwrap

import pytest

from ap_org_bot.reconciler.notion_diff import (
    DBDiff,
    PropertyDiff,
    compute_db_diff,
    load_desired_state,
)


# ── Fixtures ────────────────────────────────────────────────────────


def _desired_topics_db() -> dict:
    return {
        "db_id_env": "NOTION_TOPICS_DB",
        "properties": {
            "議題": {"type": "title"},
            "狀態": {
                "type": "select",
                "options": [
                    {"name": "待結構化", "color": "default"},
                    {"name": "通過",     "color": "green"},
                    {"name": "否決",     "color": "red"},
                ],
            },
        },
    }


def _actual_topics_db_clean() -> dict:
    """Notion GET response for a DB that matches desired state exactly."""
    return {
        "id": "abcdef-12345",
        "properties": {
            "議題": {"type": "title", "title": {}},
            "狀態": {
                "type": "select",
                "select": {
                    "options": [
                        {"id": "x1", "name": "待結構化", "color": "default"},
                        {"id": "x2", "name": "通過", "color": "green"},
                        {"id": "x3", "name": "否決", "color": "red"},
                    ],
                },
            },
        },
    }


# ── Clean cases ─────────────────────────────────────────────────────


def test_clean_db_no_drift():
    diff = compute_db_diff("topics", _desired_topics_db(),
                           _actual_topics_db_clean())
    assert diff.is_clean
    assert diff.db_id == "abcdef-12345"


# ── Missing property ────────────────────────────────────────────────


def test_missing_property_detected():
    actual = _actual_topics_db_clean()
    del actual["properties"]["狀態"]
    diff = compute_db_diff("topics", _desired_topics_db(), actual)
    assert not diff.is_clean
    assert len(diff.properties) == 1
    assert diff.properties[0].kind == "missing"
    assert diff.properties[0].name == "狀態"


def test_db_does_not_exist():
    """Whole DB missing — every desired property reported as missing."""
    diff = compute_db_diff("topics", _desired_topics_db(), None)
    assert not diff.actual_present
    assert len(diff.properties) == 2  # 議題 + 狀態
    assert all(p.kind == "missing" for p in diff.properties)


# ── Extra property ──────────────────────────────────────────────────


def test_extra_property_detected():
    actual = _actual_topics_db_clean()
    actual["properties"]["額外欄"] = {"type": "rich_text", "rich_text": {}}
    diff = compute_db_diff("topics", _desired_topics_db(), actual)
    assert not diff.is_clean
    extras = [p for p in diff.properties if p.kind == "extra"]
    assert len(extras) == 1
    assert extras[0].name == "額外欄"


# ── Type mismatch ───────────────────────────────────────────────────


def test_type_mismatch_detected():
    actual = _actual_topics_db_clean()
    # change 議題 from title to rich_text
    actual["properties"]["議題"] = {"type": "rich_text", "rich_text": {}}
    diff = compute_db_diff("topics", _desired_topics_db(), actual)
    assert not diff.is_clean
    mismatches = [p for p in diff.properties if p.kind == "type_mismatch"]
    assert len(mismatches) == 1
    assert mismatches[0].name == "議題"
    assert "title" in mismatches[0].detail
    assert "rich_text" in mismatches[0].detail


# ── Option diff (select / multi_select) ────────────────────────────


def test_option_missing():
    """Desired has 3 options; actual has 2 — option_diff."""
    actual = _actual_topics_db_clean()
    actual["properties"]["狀態"]["select"]["options"] = (
        actual["properties"]["狀態"]["select"]["options"][:2]
    )
    diff = compute_db_diff("topics", _desired_topics_db(), actual)
    opt_diffs = [p for p in diff.properties if p.kind == "option_diff"]
    assert len(opt_diffs) == 1
    assert "missing" in opt_diffs[0].detail
    assert "否決" in opt_diffs[0].detail


def test_option_extra():
    actual = _actual_topics_db_clean()
    actual["properties"]["狀態"]["select"]["options"].append(
        {"id": "x4", "name": "額外", "color": "yellow"}
    )
    diff = compute_db_diff("topics", _desired_topics_db(), actual)
    opt_diffs = [p for p in diff.properties if p.kind == "option_diff"]
    assert len(opt_diffs) == 1
    assert "extra" in opt_diffs[0].detail
    assert "額外" in opt_diffs[0].detail


def test_option_color_change_does_not_drift():
    """Color is informational; we compare by name only."""
    actual = _actual_topics_db_clean()
    actual["properties"]["狀態"]["select"]["options"][0]["color"] = "blue"  # was default
    diff = compute_db_diff("topics", _desired_topics_db(), actual)
    assert diff.is_clean


# ── load_desired_state ──────────────────────────────────────────────


def test_load_desired_state_reads_real_yaml(tmp_path):
    """Smoke — point at a tmp yaml so we don't depend on the prod file."""
    yaml_text = textwrap.dedent("""
        databases:
          topics:
            db_id_env: NOTION_TOPICS_DB
            properties:
              議題: {type: title}
    """).strip()
    p = tmp_path / "desired.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    state = load_desired_state(p)
    assert "databases" in state
    assert "topics" in state["databases"]


def test_load_missing_yaml_returns_empty(tmp_path):
    state = load_desired_state(tmp_path / "no-such-file.yaml")
    assert state == {}


# ── DBDiff serialisation ────────────────────────────────────────────


def test_db_diff_to_dict_shape():
    diff = compute_db_diff("topics", _desired_topics_db(),
                           _actual_topics_db_clean())
    d = diff.to_dict()
    assert d["is_clean"] is True
    assert d["db_name"] == "topics"
    assert d["db_id"] == "abcdef-12345"
    assert isinstance(d["properties"], list)
