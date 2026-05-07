"""catchup_protocol: WatermarkStore CRUD + CatchupCoordinator on_bot_startup audit + active replay."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from ap_org_bot.council.persistence import save_topic
from ap_org_bot.council.state_machine import State, Topic, transition
from ap_org_bot.handlers.catchup_protocol import (
    SCHEMA_VERSION,
    STALE_WATERMARK_AGE_HOURS,
    CatchupCoordinator,
    DiscordFetcher,
    ReplayResult,
    SourceType,
    Watermark,
    WatermarkStore,
)


@pytest.fixture
def store(isolated_memory_dir, monkeypatch):
    catchup_dir = isolated_memory_dir / "ap_catchup"
    catchup_dir.mkdir()
    return WatermarkStore(base_dir=catchup_dir)


# ── SourceType enum ─────────────────────────────────────────────────


def test_five_source_types_defined():
    assert {s.value for s in SourceType} == {
        "discord_feedback", "gemini_calls", "notion_writes",
        "council_state", "bot_heartbeat",
    }


# ── Watermark dataclass ─────────────────────────────────────────────


def test_watermark_round_trip():
    wm = Watermark(
        source=SourceType.DISCORD_FEEDBACK,
        value="msg-12345",
        updated_at="2026-04-30T20:00:00+00:00",
        extra={"channel": "ap-feedback"},
    )
    d = wm.to_dict()
    restored = Watermark.from_dict(d)
    assert restored == wm


def test_age_hours_for_recent_value():
    wm = Watermark(
        source=SourceType.BOT_HEARTBEAT,
        value="x",
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    age = wm.age_hours()
    assert age is not None
    assert age < 0.1


def test_age_hours_for_naive_iso_treated_as_utc():
    wm = Watermark(
        source=SourceType.BOT_HEARTBEAT,
        value="x",
        updated_at="2020-01-01T00:00:00",  # naive
    )
    age = wm.age_hours()
    assert age is not None
    assert age > 24 * 365  # > 1 year ago


def test_age_hours_for_invalid_returns_none():
    wm = Watermark(source=SourceType.BOT_HEARTBEAT, value="x", updated_at="not-a-date")
    assert wm.age_hours() is None


# ── WatermarkStore CRUD ─────────────────────────────────────────────


def test_get_missing_returns_none(store):
    assert store.get(SourceType.DISCORD_FEEDBACK) is None


def test_set_then_get(store):
    store.set(SourceType.DISCORD_FEEDBACK, "msg-1234")
    wm = store.get(SourceType.DISCORD_FEEDBACK)
    assert wm is not None
    assert wm.source == SourceType.DISCORD_FEEDBACK
    assert wm.value == "msg-1234"
    assert wm.schema_version == SCHEMA_VERSION


def test_set_overrides_previous_value(store):
    store.set(SourceType.GEMINI_CALLS, "first")
    store.set(SourceType.GEMINI_CALLS, "second")
    assert store.get(SourceType.GEMINI_CALLS).value == "second"


def test_set_persists_extra_metadata(store):
    store.set(
        SourceType.DISCORD_FEEDBACK, "msg-1",
        extra={"channel_id": "1497066777677398026", "author": "Craig"},
    )
    wm = store.get(SourceType.DISCORD_FEEDBACK)
    assert wm.extra == {"channel_id": "1497066777677398026", "author": "Craig"}


def test_atomic_write_no_dotted_files(store, isolated_memory_dir):
    store.set(SourceType.BOT_HEARTBEAT, "x")
    leftover = list((isolated_memory_dir / "ap_catchup").glob("*.tmp"))
    assert leftover == []


def test_list_all_returns_only_existing(store):
    store.set(SourceType.DISCORD_FEEDBACK, "msg-1")
    store.set(SourceType.GEMINI_CALLS, "ts-1")
    watermarks = store.list_all()
    sources = {w.source for w in watermarks}
    assert sources == {SourceType.DISCORD_FEEDBACK, SourceType.GEMINI_CALLS}


def test_clear_existing_returns_true(store):
    store.set(SourceType.NOTION_WRITES, "page-1")
    assert store.clear(SourceType.NOTION_WRITES) is True
    assert store.get(SourceType.NOTION_WRITES) is None


def test_clear_missing_returns_false(store):
    assert store.clear(SourceType.NOTION_WRITES) is False


def test_corrupt_file_yields_none(store, isolated_memory_dir):
    bad = isolated_memory_dir / "ap_catchup" / "discord_feedback.json"
    bad.write_text("{not-valid", encoding="utf-8")
    assert store.get(SourceType.DISCORD_FEEDBACK) is None


# ── CatchupCoordinator ──────────────────────────────────────────────


def test_startup_audit_with_no_watermarks_or_topics(store):
    coord = CatchupCoordinator(store=store)
    report = coord.on_bot_startup()

    assert report["active_topic_count"] == 0
    assert report["fresh_watermarks"] == []
    assert report["stale_watermarks"] == []
    # All 5 sources missing
    assert set(report["missing_watermarks"]) == {s.value for s in SourceType}


def test_startup_audit_classifies_fresh_watermark(store):
    store.set(SourceType.BOT_HEARTBEAT, "now")
    coord = CatchupCoordinator(store=store)
    report = coord.on_bot_startup()
    assert "bot_heartbeat" in report["fresh_watermarks"]
    assert "bot_heartbeat" not in report["stale_watermarks"]


def test_startup_audit_classifies_stale_watermark(store, isolated_memory_dir):
    """Manually plant an old watermark file (older than threshold)."""
    import json as _json
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=STALE_WATERMARK_AGE_HOURS + 5)).isoformat()
    path = isolated_memory_dir / "ap_catchup" / "gemini_calls.json"
    path.write_text(_json.dumps({
        "source": "gemini_calls",
        "value": "old",
        "updated_at": old_ts,
        "schema_version": SCHEMA_VERSION,
        "extra": {},
    }), encoding="utf-8")
    coord = CatchupCoordinator(store=store)
    report = coord.on_bot_startup()
    assert "gemini_calls" in report["stale_watermarks"]
    assert "gemini_calls" not in report["fresh_watermarks"]


def test_startup_audit_lists_active_council_topics(store, isolated_memory_dir):
    t = Topic(topic_id="ap-test-active-001", raw_input="active")
    transition(t, State.STRUCTURED, actor="test")
    save_topic(t)

    coord = CatchupCoordinator(store=store)
    report = coord.on_bot_startup()
    assert "ap-test-active-001" in report["active_council_topics"]
    assert report["active_topic_count"] == 1


def test_startup_audit_excludes_archived_topics(store, isolated_memory_dir):
    t = Topic(topic_id="ap-test-archived-001", state=State.ARCHIVED, raw_input="done")
    save_topic(t)

    coord = CatchupCoordinator(store=store)
    report = coord.on_bot_startup()
    assert "ap-test-archived-001" not in report["active_council_topics"]


def test_heartbeat_bumps_watermark(store):
    coord = CatchupCoordinator(store=store)
    wm1 = coord.heartbeat()
    wm2 = coord.heartbeat()
    assert wm1.source == SourceType.BOT_HEARTBEAT
    # second heartbeat should be later (or equal in low-resolution clocks)
    assert wm2.updated_at >= wm1.updated_at


# ── ReplayResult dataclass ──────────────────────────────────────────


def test_replay_result_not_skipped_by_default():
    r = ReplayResult(
        source=SourceType.DISCORD_FEEDBACK,
        messages_scanned=5,
        messages_with_attachments=2,
        new_watermark="msg-99",
    )
    assert not r.skipped
    assert r.to_dict()["messages_scanned"] == 5


def test_replay_result_skipped_when_reason_set():
    r = ReplayResult(
        source=SourceType.DISCORD_FEEDBACK,
        messages_scanned=0,
        messages_with_attachments=0,
        new_watermark=None,
        skipped_reason="no fetcher",
    )
    assert r.skipped
    assert r.to_dict()["skipped_reason"] == "no fetcher"


# ── replay_feedback_channel — fake fetcher ──────────────────────────


class FakeDiscordFetcher(DiscordFetcher):
    """Injected in tests to avoid live Discord calls."""

    def __init__(self, messages: list[dict]):
        self._messages = messages
        self.calls: list[dict] = []

    async def fetch_after(
        self,
        channel_id: str,
        after_message_id: Optional[str],
        limit: int = 200,
    ) -> list[dict]:
        self.calls.append({"channel_id": channel_id, "after": after_message_id})
        return list(self._messages)


def _run(coro):
    return asyncio.run(coro)


def test_replay_no_fetcher_returns_skipped(store):
    coord = CatchupCoordinator(store=store, fetcher=None)
    result = _run(coord.replay_feedback_channel("ch-001"))
    assert result.skipped
    assert "no DiscordFetcher" in result.skipped_reason


def test_replay_no_new_messages(store):
    fetcher = FakeDiscordFetcher(messages=[])
    coord = CatchupCoordinator(store=store, fetcher=fetcher)
    result = _run(coord.replay_feedback_channel("ch-001"))
    assert result.messages_scanned == 0
    assert result.new_watermark is None


def test_replay_messages_without_attachments(store):
    msgs = [
        {"id": "100", "attachments": []},
        {"id": "101", "attachments": []},
    ]
    fetcher = FakeDiscordFetcher(messages=msgs)
    coord = CatchupCoordinator(store=store, fetcher=fetcher)
    result = _run(coord.replay_feedback_channel("ch-001"))
    assert result.messages_scanned == 2
    assert result.messages_with_attachments == 0
    assert result.new_watermark == "101"


def test_replay_messages_with_attachments(store):
    msgs = [
        {"id": "200", "attachments": [{"url": "img.jpg"}]},
        {"id": "201", "attachments": []},
        {"id": "202", "attachments": [{"url": "img2.jpg"}]},
    ]
    fetcher = FakeDiscordFetcher(messages=msgs)
    coord = CatchupCoordinator(store=store, fetcher=fetcher)
    result = _run(coord.replay_feedback_channel("ch-feedback"))
    assert result.messages_scanned == 3
    assert result.messages_with_attachments == 2
    assert result.new_watermark == "202"


def test_replay_advances_watermark(store):
    msgs = [{"id": "300", "attachments": []}]
    fetcher = FakeDiscordFetcher(messages=msgs)
    coord = CatchupCoordinator(store=store, fetcher=fetcher)
    _run(coord.replay_feedback_channel("ch-001"))
    wm = store.get(SourceType.DISCORD_FEEDBACK)
    assert wm is not None
    assert wm.value == "300"


def test_replay_uses_existing_watermark_as_after(store):
    store.set(SourceType.DISCORD_FEEDBACK, "prev-999")
    msgs = [{"id": "1000", "attachments": []}]
    fetcher = FakeDiscordFetcher(messages=msgs)
    coord = CatchupCoordinator(store=store, fetcher=fetcher)
    _run(coord.replay_feedback_channel("ch-001"))
    assert fetcher.calls[0]["after"] == "prev-999"


def test_replay_fetch_error_returns_skipped(store):
    class ErrorFetcher(DiscordFetcher):
        async def fetch_after(self, channel_id, after_message_id, limit=200):
            raise ConnectionError("Discord down")

    coord = CatchupCoordinator(store=store, fetcher=ErrorFetcher())
    result = _run(coord.replay_feedback_channel("ch-001"))
    assert result.skipped
    assert "fetch error" in result.skipped_reason


# ── reconcile_gemini_quota ──────────────────────────────────────────


def test_reconcile_gemini_quota_returns_dict(store, monkeypatch):
    def fake_usage_summary():
        return {"providers": [{"provider": "gemini", "current": 5, "cap": 30}]}

    monkeypatch.setattr(
        "ap_org_bot.infra.budget_gate.usage_summary",
        fake_usage_summary,
    )
    coord = CatchupCoordinator(store=store)
    result = coord.reconcile_gemini_quota()
    assert "gemini_usage" in result
    assert result["alert"] is False  # 5/30 = 16% — below 80%


def test_reconcile_gemini_quota_alerts_at_80pct(store, monkeypatch):
    def fake_usage_summary():
        return {"providers": [{"provider": "gemini", "current": 25, "cap": 30}]}

    monkeypatch.setattr(
        "ap_org_bot.infra.budget_gate.usage_summary",
        fake_usage_summary,
    )
    coord = CatchupCoordinator(store=store)
    result = coord.reconcile_gemini_quota()
    assert result["alert"] is True
    assert "80%" in result.get("alert_reason", "") or "83%" in result.get("alert_reason", "")
