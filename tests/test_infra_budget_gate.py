"""budget_gate: counters increment per call, hard caps raise BudgetExceeded."""

from __future__ import annotations

import pytest


def test_first_call_passes(isolated_memory_dir):
    from ap_org_bot.infra import budget_gate as bg
    assert bg.check_call_allowed("claude_cli") is True
    bg.record_call_attempt(provider="claude_cli", agent="pm")
    assert bg.get_monthly_count("claude_cli") == 1


def test_record_increments_count(isolated_memory_dir):
    from ap_org_bot.infra import budget_gate as bg
    for _ in range(5):
        bg.record_call_attempt(provider="claude_cli", agent="designer")
    assert bg.get_monthly_count("claude_cli") == 5


def test_unknown_provider_allowed_with_warning(isolated_memory_dir):
    from ap_org_bot.infra import budget_gate as bg
    # No raise, returns True for unknown provider
    assert bg.check_call_allowed("unknown_x") is True


def test_check_does_not_modify_counter(isolated_memory_dir):
    from ap_org_bot.infra import budget_gate as bg
    bg.check_call_allowed("claude_cli")
    bg.check_call_allowed("claude_cli")
    bg.check_call_allowed("claude_cli")
    assert bg.get_monthly_count("claude_cli") == 0


def test_cap_exceeded_raises(isolated_memory_dir, monkeypatch):
    from ap_org_bot.infra import budget_gate as bg
    monkeypatch.setitem(bg.MONTHLY_CAPS, "claude_cli", 3)
    for _ in range(3):
        bg.record_call_attempt(provider="claude_cli", agent="pm")
    with pytest.raises(bg.BudgetExceeded) as exc:
        bg.record_call_attempt(provider="claude_cli", agent="pm")
    assert exc.value.provider == "claude_cli"
    assert exc.value.current == 3
    assert exc.value.cap == 3


def test_check_can_return_false_instead_of_raising(isolated_memory_dir, monkeypatch):
    from ap_org_bot.infra import budget_gate as bg
    monkeypatch.setitem(bg.MONTHLY_CAPS, "gemini", 2)
    bg.record_call_attempt(provider="gemini", agent="curator")
    bg.record_call_attempt(provider="gemini", agent="curator")
    assert bg.check_call_allowed("gemini", raise_on_exceed=False) is False


def test_summary_reports_pct(isolated_memory_dir, monkeypatch):
    from ap_org_bot.infra import budget_gate as bg
    monkeypatch.setitem(bg.MONTHLY_CAPS, "claude_cli", 10)
    for _ in range(7):
        bg.record_call_attempt(provider="claude_cli", agent="pm")
    summary = bg.usage_summary()
    assert summary["claude_cli"]["used"] == 7
    assert summary["claude_cli"]["cap"] == 10
    assert summary["claude_cli"]["pct"] == 70.0


def test_idempotent_per_provider_isolation(isolated_memory_dir):
    from ap_org_bot.infra import budget_gate as bg
    bg.record_call_attempt(provider="claude_cli", agent="pm")
    bg.record_call_attempt(provider="gemini", agent="curator")
    assert bg.get_monthly_count("claude_cli") == 1
    assert bg.get_monthly_count("gemini") == 1
    assert bg.get_monthly_count("opus_api") == 0
