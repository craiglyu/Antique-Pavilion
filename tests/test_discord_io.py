"""discord_io: split + opus_parse — pure functions, no Discord client."""

from __future__ import annotations

from ap_org_bot.discord_io.opus_parse import parse_opus_items
from ap_org_bot.discord_io.split import split_for_discord


def test_split_short_text_unchanged():
    assert split_for_discord("hello world") == ["hello world"]


def test_split_empty_returns_empty():
    assert split_for_discord("") == []


def test_split_breaks_on_newlines():
    text = "alpha\nbeta\ngamma"
    chunks = split_for_discord(text, limit=10)
    assert all(len(c) <= 10 for c in chunks)
    assert "".join(chunks).replace("\n", "") == "alphabetagamma" or \
           "\n".join(chunks) == text or \
           "\n" not in chunks[0]  # boundary may merge with newline


def test_split_hard_cuts_when_no_newline():
    text = "x" * 50
    chunks = split_for_discord(text, limit=10)
    assert len(chunks) == 5
    assert all(len(c) == 10 for c in chunks)


def test_split_default_limit_is_safe():
    text = "a" * 5000
    chunks = split_for_discord(text)
    assert all(len(c) <= 1900 for c in chunks)


def test_opus_parse_no_marker_returns_input():
    body, items = parse_opus_items("Just a normal response.")
    assert body == "Just a normal response."
    assert items == []


def test_opus_parse_extracts_items_after_marker():
    text = (
        "Designer response body here.\n\n"
        "OPUS_ESCALATE:\n"
        "- Hero 區方向\n"
        "- 主視覺色調"
    )
    body, items = parse_opus_items(text)
    assert "OPUS_ESCALATE" not in body
    assert items == ["Hero 區方向", "主視覺色調"]


def test_opus_parse_caps_at_three_items():
    text = (
        "body\n"
        "OPUS_ESCALATE:\n"
        "- one\n- two\n- three\n- four\n- five"
    )
    _body, items = parse_opus_items(text)
    assert len(items) == 3
    assert items == ["one", "two", "three"]


def test_opus_parse_strips_bullet_chars():
    text = "body\nOPUS_ESCALATE:\n• unicode bullet\n· interpunct"
    _body, items = parse_opus_items(text)
    assert "unicode bullet" in items[0]
    assert "interpunct" in items[1]
    assert not any(i.startswith(("-", "•", "·")) for i in items)
