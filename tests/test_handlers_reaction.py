"""CouncilReactionHandler: ✅/❌ in #council-decisions → state machine transition.

Avoids pytest-asyncio dependency by wrapping each async call in asyncio.run().

Behaviours covered:
- Filter chain: only #council-decisions, only Craig, only ✅/❌, ignore self
- Idempotency: same reaction twice doesn't double-dispatch
- Cross-restart: handler picks up reactions on older messages (relies only on JSON state)
- Topic state: ✅ → SIGNED_OFF, ❌ → REJECTED
- Sign-off metadata recorded on topic.signoff
- 💬 reaction logged but does NOT transition (Sprint 2 reopens this)
- Graceful skip when channel_id == 0
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ap_org_bot.council.persistence import load_topic, save_topic
from ap_org_bot.council.state_machine import State, Topic, transition
from ap_org_bot.handlers.reaction import CouncilReactionHandler


# ── Helpers ─────────────────────────────────────────────────────────


def _run(coro):
    """Run an awaitable synchronously without pytest-asyncio."""
    return asyncio.run(coro)


CRAIG_ID = "566565645483769863"


def _make_topic(state=State.AWAITING_SIGNOFF, **overrides) -> Topic:
    t = Topic(
        topic_id=overrides.pop("topic_id", "ap-test-reaction-001"),
        state=State.NEW,
        raw_input=overrides.pop("raw_input", "test topic"),
        topic_type=overrides.pop("topic_type", "鑑定品質"),
    )
    t.pilot_proposal = overrides.pop("pilot_proposal", {
        "tldr": "test tldr",
        "recommended": "option A",
        "follow_up_tasks": [
            {"task_id": "T1", "agent": "PM", "description": "x"},
            {"task_id": "T2", "agent": "Dev", "description": "y"},
        ],
    })
    # Walk to target state through legal transitions
    if state in (State.STRUCTURED, State.AWAITING_SIGNOFF, State.SIGNED_OFF, State.REJECTED):
        transition(t, State.STRUCTURED, actor="test")
    if state in (State.AWAITING_SIGNOFF, State.SIGNED_OFF, State.REJECTED):
        transition(t, State.AWAITING_SIGNOFF, actor="test")
    save_topic(t)
    return t


def _make_payload(*, channel_id, message_id, user_id, emoji_str):
    """Build a fake RawReactionActionEvent."""
    class FakeEmoji:
        def __str__(self):
            return emoji_str

    return SimpleNamespace(
        channel_id=channel_id,
        message_id=message_id,
        user_id=user_id,
        emoji=FakeEmoji(),
    )


def _make_message_with_topic_footer(topic_id: str):
    from ap_org_bot.discord_io.council_embed import FOOTER_TOPIC_PREFIX

    class FakeFooter:
        text = f"{FOOTER_TOPIC_PREFIX} {topic_id} • AWAITING_SIGNOFF"

    fake_embed = SimpleNamespace(footer=FakeFooter())
    msg = MagicMock()
    msg.embeds = [fake_embed]
    msg.edit = AsyncMock()
    return msg


def _make_bot_mock(message):
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    bot = MagicMock()
    bot.user = SimpleNamespace(id=999_999)
    bot.get_channel = MagicMock(return_value=channel)
    bot.fetch_channel = AsyncMock(return_value=channel)
    return bot


def _is_craig(uid):
    return uid == CRAIG_ID


# ── Filter chain ────────────────────────────────────────────────────


def test_skip_when_channel_id_zero(isolated_memory_dir):
    t = _make_topic()
    handler = CouncilReactionHandler(
        bot=MagicMock(), council_decisions_channel_id=0, is_craig=_is_craig,
    )
    payload = _make_payload(
        channel_id=12345, message_id=1, user_id=int(CRAIG_ID), emoji_str="✅",
    )
    _run(handler.on_raw_reaction_add(payload))
    assert load_topic(t.topic_id).state == State.AWAITING_SIGNOFF


def test_skip_when_wrong_channel(isolated_memory_dir):
    t = _make_topic()
    handler = CouncilReactionHandler(
        bot=MagicMock(), council_decisions_channel_id=99999, is_craig=_is_craig,
    )
    payload = _make_payload(
        channel_id=12345, message_id=1, user_id=int(CRAIG_ID), emoji_str="✅",
    )
    _run(handler.on_raw_reaction_add(payload))
    assert load_topic(t.topic_id).state == State.AWAITING_SIGNOFF


def test_skip_when_non_craig_reacts(isolated_memory_dir):
    t = _make_topic()
    msg = _make_message_with_topic_footer(t.topic_id)
    bot = _make_bot_mock(msg)
    handler = CouncilReactionHandler(
        bot=bot, council_decisions_channel_id=12345, is_craig=_is_craig,
    )
    payload = _make_payload(
        channel_id=12345, message_id=1, user_id=999_888_777, emoji_str="✅",
    )
    _run(handler.on_raw_reaction_add(payload))
    assert load_topic(t.topic_id).state == State.AWAITING_SIGNOFF


def test_skip_when_bot_self_reacts(isolated_memory_dir):
    t = _make_topic()
    msg = _make_message_with_topic_footer(t.topic_id)
    bot = _make_bot_mock(msg)
    handler = CouncilReactionHandler(
        bot=bot, council_decisions_channel_id=12345, is_craig=_is_craig,
    )
    payload = _make_payload(
        channel_id=12345, message_id=1, user_id=999_999, emoji_str="✅",
    )
    _run(handler.on_raw_reaction_add(payload))
    assert load_topic(t.topic_id).state == State.AWAITING_SIGNOFF


def test_skip_unrecognised_emoji(isolated_memory_dir):
    t = _make_topic()
    msg = _make_message_with_topic_footer(t.topic_id)
    bot = _make_bot_mock(msg)
    handler = CouncilReactionHandler(
        bot=bot, council_decisions_channel_id=12345, is_craig=_is_craig,
    )
    payload = _make_payload(
        channel_id=12345, message_id=1, user_id=int(CRAIG_ID), emoji_str="🤔",
    )
    _run(handler.on_raw_reaction_add(payload))
    assert load_topic(t.topic_id).state == State.AWAITING_SIGNOFF


# ── Approve / reject paths ─────────────────────────────────────────


def test_check_reaction_signs_off(isolated_memory_dir):
    t = _make_topic()
    msg = _make_message_with_topic_footer(t.topic_id)
    bot = _make_bot_mock(msg)
    handler = CouncilReactionHandler(
        bot=bot, council_decisions_channel_id=12345, is_craig=_is_craig,
    )
    payload = _make_payload(
        channel_id=12345, message_id=42, user_id=int(CRAIG_ID), emoji_str="✅",
    )
    _run(handler.on_raw_reaction_add(payload))

    reloaded = load_topic(t.topic_id)
    assert reloaded.state == State.SIGNED_OFF
    assert reloaded.signoff["decision"] == "approve"
    assert reloaded.signoff["reaction"] == "✅"
    assert reloaded.signoff["discord_message_id"] == "42"
    # follow_up_tasks staged into dispatched_tasks
    assert len(reloaded.dispatched_tasks) == 2
    msg.edit.assert_awaited_once()


def test_x_reaction_rejects(isolated_memory_dir):
    t = _make_topic()
    msg = _make_message_with_topic_footer(t.topic_id)
    bot = _make_bot_mock(msg)
    handler = CouncilReactionHandler(
        bot=bot, council_decisions_channel_id=12345, is_craig=_is_craig,
    )
    payload = _make_payload(
        channel_id=12345, message_id=42, user_id=int(CRAIG_ID), emoji_str="❌",
    )
    _run(handler.on_raw_reaction_add(payload))

    reloaded = load_topic(t.topic_id)
    assert reloaded.state == State.REJECTED
    assert reloaded.signoff["decision"] == "reject"
    assert reloaded.signoff["reaction"] == "❌"
    assert len(reloaded.dispatched_tasks) == 0


def test_speech_balloon_does_not_transition(isolated_memory_dir):
    """💬 = "let's reopen / re-debate" — recorded but state machine NOT advanced.

    Sprint 2 will wire this to actual reopening.
    """
    t = _make_topic()
    msg = _make_message_with_topic_footer(t.topic_id)
    bot = _make_bot_mock(msg)
    handler = CouncilReactionHandler(
        bot=bot, council_decisions_channel_id=12345, is_craig=_is_craig,
    )
    payload = _make_payload(
        channel_id=12345, message_id=42, user_id=int(CRAIG_ID), emoji_str="💬",
    )
    _run(handler.on_raw_reaction_add(payload))
    assert load_topic(t.topic_id).state == State.AWAITING_SIGNOFF


# ── Idempotency + state guards ─────────────────────────────────────


def test_double_check_reaction_is_idempotent(isolated_memory_dir):
    """Reacting ✅ twice — second is no-op (already SIGNED_OFF)."""
    t = _make_topic()
    msg = _make_message_with_topic_footer(t.topic_id)
    bot = _make_bot_mock(msg)
    handler = CouncilReactionHandler(
        bot=bot, council_decisions_channel_id=12345, is_craig=_is_craig,
    )
    payload = _make_payload(
        channel_id=12345, message_id=42, user_id=int(CRAIG_ID), emoji_str="✅",
    )
    _run(handler.on_raw_reaction_add(payload))
    _run(handler.on_raw_reaction_add(payload))

    reloaded = load_topic(t.topic_id)
    assert reloaded.state == State.SIGNED_OFF
    # dispatched_tasks not duplicated (still 2)
    assert len(reloaded.dispatched_tasks) == 2


def test_skip_when_topic_not_in_awaiting_signoff(isolated_memory_dir):
    """Topic in NEW state — reaction shouldn't push it to SIGNED_OFF."""
    t = Topic(
        topic_id="ap-test-new-001", state=State.NEW, raw_input="test"
    )
    save_topic(t)

    msg = _make_message_with_topic_footer(t.topic_id)
    bot = _make_bot_mock(msg)
    handler = CouncilReactionHandler(
        bot=bot, council_decisions_channel_id=12345, is_craig=_is_craig,
    )
    payload = _make_payload(
        channel_id=12345, message_id=99, user_id=int(CRAIG_ID), emoji_str="✅",
    )
    _run(handler.on_raw_reaction_add(payload))

    assert load_topic(t.topic_id).state == State.NEW


def test_skip_when_message_has_no_topic_footer(isolated_memory_dir):
    """Random Discord message without topic_id footer — handler is a no-op."""
    msg = MagicMock()
    msg.embeds = []
    msg.edit = AsyncMock()
    bot = _make_bot_mock(msg)
    handler = CouncilReactionHandler(
        bot=bot, council_decisions_channel_id=12345, is_craig=_is_craig,
    )
    payload = _make_payload(
        channel_id=12345, message_id=999, user_id=int(CRAIG_ID), emoji_str="✅",
    )
    _run(handler.on_raw_reaction_add(payload))
    msg.edit.assert_not_awaited()
