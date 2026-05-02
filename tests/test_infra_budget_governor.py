"""BudgetGovernor: per-call USD ledger + daily/weekly/monthly caps + Council attribution.

All tests use isolated_memory_dir so production memory/ is never touched.
"""

from __future__ import annotations

import sqlite3

import pytest


# ---------------------------------------------------------------------------
# Shared fixture — single BudgetGovernor instance per test, isolated DB.
# ---------------------------------------------------------------------------

@pytest.fixture
def gov(isolated_memory_dir):
    from ap_org_bot.infra.budget_governor import BudgetGovernor
    return BudgetGovernor()


# ---------------------------------------------------------------------------
# 1. Default cost estimate is applied when cost_usd is omitted.
# ---------------------------------------------------------------------------

def test_record_call_uses_default_cost_estimate(gov):
    from ap_org_bot.infra.budget_governor import BudgetGovernor
    result = gov.record_call(provider="gemini", agent="curator")
    expected = BudgetGovernor.PROVIDER_COST_PER_CALL_USD["gemini"]
    assert result["monthly_used"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# 2. Explicit cost_usd overrides the estimate.
# ---------------------------------------------------------------------------

def test_record_call_with_explicit_cost_overrides_estimate(gov):
    result = gov.record_call(provider="gemini", agent="curator", cost_usd=0.99)
    assert result["monthly_used"] == pytest.approx(0.99)


# ---------------------------------------------------------------------------
# 3. record_call also bumps the legacy budget_gate call counter.
# ---------------------------------------------------------------------------

def test_record_call_bumps_legacy_call_counter(gov, isolated_memory_dir):
    from ap_org_bot.infra import budget_gate as bg

    before = bg.get_monthly_count("gemini")
    gov.record_call(provider="gemini", agent="curator")
    assert bg.get_monthly_count("gemini") == before + 1


# ---------------------------------------------------------------------------
# 4–6. USD cap enforcement for each time window.
# ---------------------------------------------------------------------------

def test_daily_cap_exceeded_raises_BudgetExceeded(gov, monkeypatch):
    from ap_org_bot.infra.budget_gate import BudgetExceeded
    from ap_org_bot.infra.budget_governor import BudgetGovernor

    monkeypatch.setattr(BudgetGovernor, "DAILY_CAPS_USD", {"gemini": 0.10})
    gov.record_call(provider="gemini", agent="curator", cost_usd=0.06)
    with pytest.raises(BudgetExceeded):
        gov.record_call(provider="gemini", agent="curator", cost_usd=0.06)


def test_weekly_cap_exceeded_raises_BudgetExceeded(gov, monkeypatch):
    from ap_org_bot.infra.budget_gate import BudgetExceeded
    from ap_org_bot.infra.budget_governor import BudgetGovernor

    monkeypatch.setattr(BudgetGovernor, "WEEKLY_CAPS_USD", {"gemini": 0.10})
    gov.record_call(provider="gemini", agent="curator", cost_usd=0.06)
    with pytest.raises(BudgetExceeded):
        gov.record_call(provider="gemini", agent="curator", cost_usd=0.06)


def test_monthly_cap_exceeded_raises_BudgetExceeded(gov, monkeypatch):
    from ap_org_bot.infra.budget_gate import BudgetExceeded
    from ap_org_bot.infra.budget_governor import BudgetGovernor

    monkeypatch.setattr(BudgetGovernor, "MONTHLY_CAPS_USD", {"gemini": 0.10})
    gov.record_call(provider="gemini", agent="curator", cost_usd=0.06)
    with pytest.raises(BudgetExceeded):
        gov.record_call(provider="gemini", agent="curator", cost_usd=0.06)


# ---------------------------------------------------------------------------
# 7. usage_summary_usd returns correct pct for all three windows.
# ---------------------------------------------------------------------------

def test_usage_summary_returns_pct_per_window(gov, monkeypatch):
    from ap_org_bot.infra.budget_governor import BudgetGovernor

    monkeypatch.setattr(BudgetGovernor, "DAILY_CAPS_USD",   {"gemini": 1.0, "opus_api": 2.0})
    monkeypatch.setattr(BudgetGovernor, "WEEKLY_CAPS_USD",  {"gemini": 5.0, "opus_api": 5.0})
    monkeypatch.setattr(BudgetGovernor, "MONTHLY_CAPS_USD", {"gemini": 10.0, "opus_api": 15.0})

    gov.record_call(provider="gemini", agent="curator", cost_usd=0.50)
    summary = gov.usage_summary_usd()

    assert "gemini" in summary
    assert summary["gemini"]["daily"]       == pytest.approx(0.50)
    assert summary["gemini"]["weekly"]      == pytest.approx(0.50)
    assert summary["gemini"]["monthly"]     == pytest.approx(0.50)
    assert summary["gemini"]["daily_pct"]   == pytest.approx(50.0)
    assert summary["gemini"]["weekly_pct"]  == pytest.approx(10.0)
    assert summary["gemini"]["monthly_pct"] == pytest.approx(5.0)
    # Unused provider should show zeroes.
    assert summary["opus_api"]["monthly"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 8. attribution_by_topic aggregates correctly across providers.
# ---------------------------------------------------------------------------

def test_attribution_by_topic_aggregates_correctly(gov):
    gov.record_call(provider="gemini",   agent="pm",      cost_usd=0.10, topic_id="topic-123")
    gov.record_call(provider="gemini",   agent="curator", cost_usd=0.20, topic_id="topic-123")
    gov.record_call(provider="opus_api", agent="pm",      cost_usd=0.15, topic_id="topic-123")
    # different topic — must not bleed in
    gov.record_call(provider="gemini",   agent="pm",      cost_usd=0.50, topic_id="topic-other")

    attr = gov.attribution_by_topic("topic-123")
    assert attr["gemini"]   == pytest.approx(0.30)
    assert attr["opus_api"] == pytest.approx(0.15)
    assert "topic-other" not in attr


# ---------------------------------------------------------------------------
# 9. Unknown topic_id returns empty dict.
# ---------------------------------------------------------------------------

def test_attribution_returns_empty_dict_for_unknown_topic(gov):
    gov.record_call(provider="gemini", agent="pm", cost_usd=0.10, topic_id="real-topic")
    assert gov.attribution_by_topic("nonexistent-topic") == {}


# ---------------------------------------------------------------------------
# 10. Providers with no USD cap never raise BudgetExceeded.
# ---------------------------------------------------------------------------

def test_provider_with_no_cap_does_not_raise(gov):
    from ap_org_bot.infra.budget_gate import BudgetExceeded

    # claude_cli has no entry in any USD cap dict — should never raise.
    for _ in range(10):
        result = gov.record_call(provider="claude_cli", agent="pm")

    assert result["monthly_used"] == pytest.approx(0.0)  # cost_usd=0.0


# ---------------------------------------------------------------------------
# 11. Sequential records all persist (atomicity / commit check).
# ---------------------------------------------------------------------------

def test_concurrent_records_persist_atomically(gov):
    costs = [0.01 * (i + 1) for i in range(5)]  # 0.01, 0.02, 0.03, 0.04, 0.05
    for cost in costs:
        gov.record_call(provider="gemini", agent="pm", cost_usd=cost, topic_id="t-atomic")

    attr = gov.attribution_by_topic("t-atomic")
    assert attr["gemini"] == pytest.approx(sum(costs))  # 0.15


# ---------------------------------------------------------------------------
# 12. budget_calls_v2 table is created on first use.
# ---------------------------------------------------------------------------

def test_db_table_created_on_first_use(gov, isolated_memory_dir):
    from ap_org_bot.infra.paths import BUDGET_STATE_FILE

    gov.record_call(provider="notion", agent="librarian")

    conn = sqlite3.connect(BUDGET_STATE_FILE)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()

    assert "budget_calls_v2" in tables
