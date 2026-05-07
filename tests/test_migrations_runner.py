"""Unit tests for MigrationsRunner — all Notion API calls mocked."""

from unittest.mock import patch

import pytest

from ap_org_bot.handlers.migrations_runner import MigrationsRunner
from ap_org_bot.reconciler import DBDiff, PropertyDiff

MODULE = "ap_org_bot.handlers.migrations_runner"

_DESIRED = {
    "databases": {
        "topics": {
            "db_id_env": "NOTION_TOPICS_DB",
            "properties": {
                "議題": {"type": "title"},
                "狀態": {
                    "type": "select",
                    "options": [{"name": "待結構化"}],
                },
            },
        }
    }
}


def _diff_clean() -> DBDiff:
    return DBDiff(db_name="topics", db_id="abc", actual_present=True, properties=[])


def _diff_missing() -> DBDiff:
    return DBDiff(
        db_name="topics",
        db_id="abc",
        actual_present=True,
        properties=[
            PropertyDiff(
                name="狀態",
                kind="missing",
                desired={"type": "select", "options": [{"name": "待結構化"}]},
                detail="property not present on Notion",
            )
        ],
    )


# ── 1. dry-run audit with no drift ────────────────────────────────────────────

@patch(f"{MODULE}._notion_api_key", return_value="fake-key")
@patch(f"{MODULE}._resolve_db_id", return_value="db-id-123")
@patch(f"{MODULE}._fetch_actual", return_value={"id": "abc", "properties": {}})
@patch(f"{MODULE}.compute_db_diff")
@patch(f"{MODULE}.load_desired_state", return_value=_DESIRED)
def test_runner_dry_run_audit_no_changes(mock_load, mock_diff, mock_fetch, mock_resolve, mock_key):
    mock_diff.return_value = _diff_clean()
    runner = MigrationsRunner(auto_apply=False, dry_run=True)
    result = runner.run_at_startup()

    assert result["drift_found"] == 0
    assert result["applied"] == 0
    assert result["errors"] == []
    assert result["skipped_reason"] == ""


# ── 2. drift detected, dry-run → no PATCH ────────────────────────────────────

@patch(f"{MODULE}._notion_api_key", return_value="fake-key")
@patch(f"{MODULE}._resolve_db_id", return_value="db-id-123")
@patch(f"{MODULE}._fetch_actual", return_value={"id": "abc", "properties": {}})
@patch(f"{MODULE}.compute_db_diff")
@patch(f"{MODULE}._patch_add_properties")
@patch(f"{MODULE}.load_desired_state", return_value=_DESIRED)
def test_runner_drift_detected_dry_run_does_not_patch(
    mock_load, mock_patch, mock_diff, mock_fetch, mock_resolve, mock_key
):
    mock_diff.return_value = _diff_missing()
    runner = MigrationsRunner(auto_apply=False, dry_run=True)
    result = runner.run_at_startup()

    assert result["drift_found"] == 1
    assert result["applied"] == 0
    mock_patch.assert_not_called()


# ── 3. auto_apply=True → _patch_add_properties is called ─────────────────────

@patch(f"{MODULE}._notion_api_key", return_value="fake-key")
@patch(f"{MODULE}._resolve_db_id", return_value="db-id-123")
@patch(f"{MODULE}._fetch_actual", return_value={"id": "abc", "properties": {}})
@patch(f"{MODULE}.compute_db_diff")
@patch(f"{MODULE}._patch_add_properties", return_value={"id": "abc"})
@patch(f"{MODULE}.load_desired_state", return_value=_DESIRED)
def test_runner_auto_apply_calls_patch(
    mock_load, mock_patch, mock_diff, mock_fetch, mock_resolve, mock_key
):
    mock_diff.return_value = _diff_missing()
    runner = MigrationsRunner(auto_apply=True, dry_run=False)
    result = runner.run_at_startup()

    assert result["drift_found"] == 1
    assert result["applied"] == 1
    mock_patch.assert_called_once()


# ── 4. _patch_add_properties returns None → error recorded ───────────────────

@patch(f"{MODULE}._notion_api_key", return_value="fake-key")
@patch(f"{MODULE}._resolve_db_id", return_value="db-id-123")
@patch(f"{MODULE}._fetch_actual", return_value={"id": "abc", "properties": {}})
@patch(f"{MODULE}.compute_db_diff")
@patch(f"{MODULE}._patch_add_properties", return_value=None)
@patch(f"{MODULE}.load_desired_state", return_value=_DESIRED)
def test_runner_handles_notion_api_error(
    mock_load, mock_patch, mock_diff, mock_fetch, mock_resolve, mock_key
):
    mock_diff.return_value = _diff_missing()
    runner = MigrationsRunner(auto_apply=True, dry_run=False)
    result = runner.run_at_startup()

    assert len(result["errors"]) == 1
    assert result["applied"] == 0


# ── 5. no NOTION_API_KEY → skipped_reason set ────────────────────────────────

@patch(f"{MODULE}._notion_api_key", return_value=None)
def test_runner_skips_when_no_notion_api_key(mock_key):
    runner = MigrationsRunner(auto_apply=False, dry_run=True)
    result = runner.run_at_startup()

    assert result["skipped_reason"] != ""
    assert result["drift_found"] == 0
    assert result["applied"] == 0


# ── 6. return dict always has required keys ───────────────────────────────────

@patch(f"{MODULE}._notion_api_key", return_value=None)
def test_runner_returns_dict_with_required_keys(mock_key):
    runner = MigrationsRunner()
    result = runner.run_at_startup()

    for key in ("drift_found", "applied", "errors", "skipped_reason"):
        assert key in result, f"missing key: {key}"
