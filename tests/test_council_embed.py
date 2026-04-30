"""council_embed: Topic → Discord Embed, footer carries topic_id, extract_topic_id is inverse."""

from __future__ import annotations

from types import SimpleNamespace

import discord
import pytest

from ap_org_bot.council.state_machine import State, Topic
from ap_org_bot.discord_io.council_embed import (
    COUNCIL_EMBED_COLORS,
    DEFAULT_COLOR,
    FOOTER_TOPIC_PREFIX,
    build_council_embed,
    extract_topic_id,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _topic(**overrides) -> Topic:
    base = Topic(
        topic_id=overrides.pop("topic_id", "ap-2026-04-30-test-001"),
        state=overrides.pop("state", State.AWAITING_SIGNOFF),
        raw_input=overrides.pop("raw_input", "Sprint 1 第一個 Phase 1 Agent 應該選哪個"),
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


# ── build_council_embed: structure & content ────────────────────────


def test_embed_title_uses_raw_input():
    embed = build_council_embed(_topic(raw_input="如何讓 #ap-feedback 不要 watermark 卡住？"))
    assert "如何讓" in embed.title


def test_embed_footer_contains_topic_id():
    embed = build_council_embed(_topic(topic_id="ap-test-001"))
    assert FOOTER_TOPIC_PREFIX in embed.footer.text
    assert "ap-test-001" in embed.footer.text


def test_embed_footer_contains_state():
    for state in [State.NEW, State.AWAITING_SIGNOFF, State.SIGNED_OFF, State.REJECTED]:
        embed = build_council_embed(_topic(state=state))
        assert state.value in embed.footer.text


def test_embed_color_for_awaiting_signoff_is_gold():
    embed = build_council_embed(_topic(state=State.AWAITING_SIGNOFF))
    assert embed.color.value == COUNCIL_EMBED_COLORS[State.AWAITING_SIGNOFF]


def test_embed_color_for_signed_off_is_green():
    embed = build_council_embed(_topic(state=State.SIGNED_OFF))
    assert embed.color.value == COUNCIL_EMBED_COLORS[State.SIGNED_OFF]


def test_embed_color_for_rejected_is_red():
    embed = build_council_embed(_topic(state=State.REJECTED))
    assert embed.color.value == COUNCIL_EMBED_COLORS[State.REJECTED]


def test_structured_fields_render_when_present():
    t = _topic(structured={
        "problem": "PROBLEM_STR",
        "goal": "GOAL_STR",
        "constraints": "CONSTRAINTS_STR",
    })
    embed = build_council_embed(t)
    field_names = [f.name for f in embed.fields]
    assert any("問題" in n for n in field_names)
    assert any("目標" in n for n in field_names)
    assert any("限制" in n for n in field_names)


def test_no_structured_fields_when_topic_unstructured():
    t = _topic(structured={})
    embed = build_council_embed(t)
    field_names = [f.name for f in embed.fields]
    # State + topic_id always render; problem/goal/constraints should not
    for unwanted in ("🔍 問題", "🎯 目標", "⚖️ 限制"):
        assert unwanted not in field_names


def test_pilot_proposal_tldr_renders():
    t = _topic(pilot_proposal={"tldr": "選 Curator", "recommended": "Curator"})
    embed = build_council_embed(t)
    field_values = [f.value for f in embed.fields]
    assert any("選 Curator" in v for v in field_values)


def test_pilot_proposal_recommended_with_reasoning_renders():
    t = _topic(pilot_proposal={
        "recommended": "Curator",
        "reasoning": "三維度全部對齊",
    })
    embed = build_council_embed(t)
    field_values = [f.value for f in embed.fields]
    combined = " ".join(field_values)
    assert "Curator" in combined
    assert "三維度" in combined


def test_follow_up_tasks_render_with_truncation():
    tasks = [
        {"task_id": f"T-{i:03d}", "agent": "PM", "description": f"task {i}"}
        for i in range(8)
    ]
    t = _topic(pilot_proposal={"follow_up_tasks": tasks})
    embed = build_council_embed(t)
    follow_up_field = next(f for f in embed.fields if "後續任務" in f.name)
    # Only first 5 listed
    assert "T-000" in follow_up_field.value
    assert "T-004" in follow_up_field.value
    assert "T-005" not in follow_up_field.value
    assert "共 8 項" in follow_up_field.value


def test_convened_agents_render():
    t = _topic(convened=["PM", "Designer", "Frontend"])
    embed = build_council_embed(t)
    convened_field = next(f for f in embed.fields if "召集" in f.name)
    assert "PM" in convened_field.value
    assert "Designer" in convened_field.value


def test_signoff_guidance_only_when_awaiting():
    waiting = build_council_embed(_topic(state=State.AWAITING_SIGNOFF))
    assert any("簽核" in f.name for f in waiting.fields)

    structured = build_council_embed(_topic(state=State.STRUCTURED))
    assert not any("簽核" in f.name for f in structured.fields)


def test_signoff_metadata_renders_when_signed_off():
    t = _topic(state=State.SIGNED_OFF, signoff={
        "decision": "approve",
        "decided_by": "craig:566565645483769863",
        "decided_at": "2026-04-30T18:00:00Z",
        "reaction": "✅",
    })
    embed = build_council_embed(t)
    field_values = " ".join(f.value for f in embed.fields)
    assert "566565645483769863" in field_values


def test_dispatched_tasks_count_renders_when_signed_off():
    t = _topic(
        state=State.SIGNED_OFF,
        dispatched_tasks=[{"task_id": "T1"}, {"task_id": "T2"}],
        signoff={"decided_by": "craig:1", "decided_at": "x"},
    )
    embed = build_council_embed(t)
    field_values = " ".join(f.value for f in embed.fields)
    assert "2 個" in field_values


# ── extract_topic_id: round-trip ───────────────────────────────────


def _fake_message_with_embed(embed: discord.Embed) -> SimpleNamespace:
    return SimpleNamespace(embeds=[embed])


def test_extract_round_trip():
    t = _topic(topic_id="ap-2026-05-01-090000-001")
    embed = build_council_embed(t)
    msg = _fake_message_with_embed(embed)
    assert extract_topic_id(msg) == "ap-2026-05-01-090000-001"


def test_extract_returns_none_when_no_embed():
    msg = SimpleNamespace(embeds=[])
    assert extract_topic_id(msg) is None


def test_extract_returns_none_when_footer_has_no_marker():
    e = discord.Embed(title="x")
    e.set_footer(text="some other text")
    msg = _fake_message_with_embed(e)
    assert extract_topic_id(msg) is None


def test_extract_handles_multiple_embeds():
    """Returns first match across embeds."""
    t = _topic(topic_id="ap-multi-001")
    e_target = build_council_embed(t)
    e_other = discord.Embed(title="unrelated")
    msg = SimpleNamespace(embeds=[e_other, e_target])
    assert extract_topic_id(msg) == "ap-multi-001"


def test_truncation_is_applied():
    """Embed field value cap is 1024; we feed 5000 chars and confirm truncation."""
    long_problem = "問題" * 2000  # > 1024 chars
    t = _topic(structured={"problem": long_problem})
    embed = build_council_embed(t)
    problem_field = next(f for f in embed.fields if "問題" in f.name)
    assert len(problem_field.value) <= 1024
