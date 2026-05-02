"""RealDiscordFetcher tests — mocks discord.py, zero real Discord API calls.

discord.py is imported lazily inside fetch_after(), so patching sys.modules
before the coroutine runs is sufficient. No real bot process is needed.
"""

from __future__ import annotations

import asyncio
import sys
import types
import unittest.mock as mock

import pytest

# ── Shared fixtures / helpers ─────────────────────────────────────────────────


def _make_discord_mock() -> types.ModuleType:
    """Return a minimal fake 'discord' module that satisfies RealDiscordFetcher."""
    dm = types.ModuleType("discord")
    dm.Object = mock.MagicMock(side_effect=lambda id: mock.MagicMock(id=id))  # type: ignore[attr-defined]
    return dm


async def _aiter(items):
    """Async generator that yields from a plain list."""
    for item in items:
        yield item


def _make_msg(
    msg_id: int,
    content: str = "hello",
    attachment_count: int = 0,
) -> mock.MagicMock:
    """Build a minimal mock discord.Message."""
    msg = mock.MagicMock()
    msg.id = msg_id
    msg.author.id = 99999
    msg.content = content
    msg.created_at.isoformat.return_value = "2026-05-02T10:00:00+00:00"
    atts = []
    for i in range(attachment_count):
        a = mock.MagicMock()
        a.id = 1000 + i
        a.url = f"https://cdn.discordapp.com/attachments/{msg_id}/{i}/img.jpg"
        a.filename = f"img_{i}.jpg"
        atts.append(a)
    msg.attachments = atts
    return msg


def _make_channel(messages: list) -> mock.MagicMock:
    ch = mock.MagicMock()
    ch.history.return_value = _aiter(messages)
    return ch


def _make_bot(channel=None) -> mock.MagicMock:
    bot = mock.MagicMock()
    bot.get_channel.return_value = channel
    return bot


def _run_with_mock_discord(coro):
    """Execute ``coro`` with a fresh mock discord module in sys.modules."""
    dm = _make_discord_mock()
    with mock.patch.dict(sys.modules, {"discord": dm}):
        return asyncio.run(coro)


# Import the module under test after helpers (no top-level discord import in it).
from ap_org_bot.handlers.discord_fetcher_real import RealDiscordFetcher  # noqa: E402
from ap_org_bot.handlers.catchup_protocol import DiscordFetcher  # noqa: E402


# ── Test 1: empty channel ─────────────────────────────────────────────────────


def test_fetch_after_empty_channel_returns_empty_list():
    ch = _make_channel([])
    bot = _make_bot(channel=ch)
    fetcher = RealDiscordFetcher(bot)

    result = _run_with_mock_discord(fetcher.fetch_after("123456", None))

    assert result == []
    ch.history.assert_called_once()


# ── Test 2: messages with attachments ─────────────────────────────────────────


def test_fetch_after_returns_correct_dict_structure_with_attachments():
    msg_with_att = _make_msg(1001, "photo upload", attachment_count=2)
    msg_plain = _make_msg(1002, "plain text", attachment_count=0)
    ch = _make_channel([msg_with_att, msg_plain])
    bot = _make_bot(channel=ch)
    fetcher = RealDiscordFetcher(bot)

    result = _run_with_mock_discord(fetcher.fetch_after("777", "1000"))

    assert len(result) == 2

    first = result[0]
    assert first["id"] == "1001"
    assert first["content"] == "photo upload"
    assert len(first["attachments"]) == 2
    assert first["attachments"][0]["filename"] == "img_0.jpg"
    assert "url" in first["attachments"][0]

    second = result[1]
    assert second["id"] == "1002"
    assert second["attachments"] == []

    # Every dict must have the minimum contract keys
    for row in result:
        assert "id" in row
        assert "attachments" in row


# ── Test 3: pagination — limit and oldest_first forwarded ─────────────────────


def test_fetch_after_passes_limit_and_after_id_to_history():
    ch = _make_channel([_make_msg(i) for i in range(3)])
    bot = _make_bot(channel=ch)
    fetcher = RealDiscordFetcher(bot)

    result = _run_with_mock_discord(fetcher.fetch_after("555", "9000", limit=25))

    assert len(result) == 3

    # Verify discord.py history() received the right keyword args
    _, kwargs = ch.history.call_args
    assert kwargs.get("limit") == 25
    assert kwargs.get("oldest_first") is True

    # after= should be a discord.Object constructed from int(after_message_id)
    after_arg = kwargs.get("after")
    assert after_arg is not None
    assert after_arg.id == 9000


# ── Test 4: channel not in bot cache ─────────────────────────────────────────


def test_fetch_after_channel_not_in_cache_returns_empty_list():
    bot = _make_bot(channel=None)  # get_channel returns None
    fetcher = RealDiscordFetcher(bot)

    result = _run_with_mock_discord(fetcher.fetch_after("999999", None))

    assert result == []
    bot.get_channel.assert_called_once_with(999999)


# ── Test 5: discord API error propagates ─────────────────────────────────────


def test_fetch_after_discord_error_propagates():
    """History iteration errors must not be silently swallowed."""

    async def _error_gen(*args, **kwargs):
        raise RuntimeError("Discord API 503")
        yield  # make this an async generator; line never reached

    ch = mock.MagicMock()
    ch.history.return_value = _error_gen()
    bot = _make_bot(channel=ch)
    fetcher = RealDiscordFetcher(bot)

    with pytest.raises(RuntimeError, match="Discord API 503"):
        _run_with_mock_discord(fetcher.fetch_after("123", None))


# ── Test 6: after_message_id=None means no `after` kwarg passed ─────────────


def test_fetch_after_none_after_id_means_fetch_from_beginning():
    ch = _make_channel([_make_msg(1)])
    bot = _make_bot(channel=ch)
    fetcher = RealDiscordFetcher(bot)

    _run_with_mock_discord(fetcher.fetch_after("777", None))

    _, kwargs = ch.history.call_args
    assert kwargs.get("after") is None


# ── Bonus: protocol conformance against Sprint 3 base class ────────────────


def test_real_discord_fetcher_satisfies_catchup_protocol_contract():
    bot = _make_bot()
    fetcher = RealDiscordFetcher(bot)
    assert isinstance(fetcher, DiscordFetcher)
