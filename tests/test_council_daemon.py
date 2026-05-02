"""CouncilDaemon — auto-trigger Phase 1/2/3 tests.

All tests use FakeAgentInvoker so no live LLM calls are made.
Council state is isolated via isolated_memory_dir fixture (from conftest.py).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

import pytest

from ap_org_bot.council.persistence import load_topic, save_topic
from ap_org_bot.council.state_machine import (
    State,
    Topic,
    transition,
)
from ap_org_bot.council.daemon import (
    AgentInvoker,
    CouncilDaemon,
    DaemonRun,
    _detect_divergence,
    parse_stance,
    _parse_phase3_response,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _run(coro):
    return asyncio.run(coro)


def _make_topic(
    state: State = State.NEW,
    convened: Optional[list] = None,
    topic_id: str = "ap-2026-05-02-000000-001",
) -> Topic:
    t = Topic(topic_id=topic_id)
    t.raw_input = "測試議題"
    t.topic_type = "視覺微調"
    t.convened = convened or []
    now = datetime.now(timezone.utc).isoformat()
    t.created_at = now
    t.updated_at = now
    t.state = state
    return t


class FakeAgentInvoker(AgentInvoker):
    """Returns canned responses; records call history for assertions."""

    def __init__(self, stance: str = "支持", reasoning: str = "測試理由"):
        self.calls: list[dict] = []
        self._stance = stance
        self._reasoning = reasoning

    async def invoke(self, agent_name: str, prompt: str) -> str:
        self.calls.append({"agent": agent_name, "prompt_len": len(prompt)})
        if "Phase 3" in prompt or "整合提案" in prompt:
            return (
                f"TLDR: 整合完成\n"
                f"建議方向: 採納多數意見\n"
                f"理由: 各代理人討論後達成共識\n"
                f"後續任務:\n- 更新設計稿\n- PM 通知 Craig"
            )
        if "Phase 2" in prompt or "辯論" in prompt:
            return (
                f"核心分歧: 兩派意見不同\n"
                f"折衷方向: 採折衷方案\n"
                f"收斂狀態: 已收斂"
            )
        return f"立場: {self._stance}\n理由: {self._reasoning}"


class FakeErrorInvoker(AgentInvoker):
    """Always raises an exception."""

    async def invoke(self, agent_name: str, prompt: str) -> str:
        raise ConnectionError("LLM unreachable")


# ── parse_stance ─────────────────────────────────────────────────────


def test_parse_stance_explicit_label():
    assert parse_stance("立場: 支持\n理由: 設計良好") == "支持"


def test_parse_stance_fullwidth_colon():
    assert parse_stance("立場：反對\n因為預算不足") == "反對"


def test_parse_stance_modify():
    assert parse_stance("立場: 修改建議\n建議改小字") == "修改建議"


def test_parse_stance_neutral():
    assert parse_stance("立場: 中立\n目前無意見") == "中立"


def test_parse_stance_keyword_fallback():
    # No explicit 立場: line — falls back to keyword scan
    assert parse_stance("我個人贊成這個方向") == "支持"


def test_parse_stance_oppose_keyword():
    assert parse_stance("整體而言我持否決態度") == "反對"


def test_parse_stance_unknown():
    assert parse_stance("嗯…不確定") == "未知"


# ── _detect_divergence ───────────────────────────────────────────────


def test_no_divergence_all_agree():
    responses = {
        "Design": {"stance": "支持", "reasoning": ""},
        "Frontend": {"stance": "支持", "reasoning": ""},
    }
    assert _detect_divergence(responses) == []


def test_divergence_detected():
    responses = {
        "Design": {"stance": "支持", "reasoning": "好"},
        "Frontend": {"stance": "反對", "reasoning": "不好"},
    }
    divs = _detect_divergence(responses)
    assert len(divs) == 1
    assert "Design" in divs[0]
    assert "Frontend" in divs[0]


def test_neutral_does_not_cause_divergence():
    responses = {
        "Design": {"stance": "支持", "reasoning": ""},
        "SEO": {"stance": "中立", "reasoning": ""},
    }
    assert _detect_divergence(responses) == []


def test_three_way_divergence():
    responses = {
        "A": {"stance": "支持", "reasoning": ""},
        "B": {"stance": "反對", "reasoning": ""},
        "C": {"stance": "修改建議", "reasoning": ""},
    }
    divs = _detect_divergence(responses)
    assert len(divs) == 3  # 3 pairs from 3 distinct stances


def test_all_unknown_no_divergence():
    responses = {
        "A": {"stance": "未知", "reasoning": ""},
        "B": {"stance": "未知", "reasoning": ""},
    }
    assert _detect_divergence(responses) == []


# ── _parse_phase3_response ───────────────────────────────────────────


def test_parse_phase3_basic():
    text = "TLDR: 一句話\n建議方向: 採折衷\n理由: 各方同意\n後續任務:\n- 更新文件"
    parsed = _parse_phase3_response(text)
    assert parsed["tldr"] == "一句話"
    assert "折衷" in parsed["recommended"]
    assert len(parsed["follow_up_tasks"]) == 1
    assert parsed["follow_up_tasks"][0]["task"] == "更新文件"


def test_parse_phase3_empty_text_uses_fallback():
    parsed = _parse_phase3_response("")
    assert "tldr" in parsed
    assert isinstance(parsed["follow_up_tasks"], list)


def test_parse_phase3_multiple_tasks():
    text = "TLDR: 完成\n建議方向: x\n理由: y\n後續任務:\n- 任務A\n- 任務B\n- 任務C"
    parsed = _parse_phase3_response(text)
    assert len(parsed["follow_up_tasks"]) == 3


# ── DaemonRun dataclass ──────────────────────────────────────────────


def test_daemon_run_defaults():
    r = DaemonRun()
    assert r.topics_polled == 0
    assert r.topics_advanced == 0
    assert r.phases_executed == []
    assert r.errors == []


def test_daemon_run_to_dict():
    r = DaemonRun(topics_polled=3, topics_advanced=1, phases_executed=["x:phase1"])
    d = r.to_dict()
    assert d["topics_polled"] == 3
    assert d["phases_executed"] == ["x:phase1"]


# ── CouncilDaemon.poll_and_advance — no invoker (dry-run) ────────────


def test_daemon_no_invoker_skips_without_error(isolated_memory_dir):
    daemon = CouncilDaemon(invoker=None)
    run = _run(daemon.poll_and_advance())
    assert run.topics_polled == 0  # no topics on disk


def test_daemon_no_invoker_structured_topic_skips(isolated_memory_dir, monkeypatch):
    topic = _make_topic(state=State.STRUCTURED, convened=["Design", "Frontend"])
    monkeypatch.setattr(
        "ap_org_bot.council.daemon.list_active_topics",
        lambda: [topic],
    )
    daemon = CouncilDaemon(invoker=None)
    run = _run(daemon.poll_and_advance())
    assert run.topics_advanced == 0
    assert run.phases_executed == []


# ── Phase 1 flow ─────────────────────────────────────────────────────


def test_daemon_runs_phase1_for_structured_topic(isolated_memory_dir):
    invoker = FakeAgentInvoker(stance="支持")
    daemon = CouncilDaemon(invoker=invoker)

    topic = _make_topic(state=State.STRUCTURED, convened=["Design", "Frontend"])
    save_topic(topic)

    run = _run(daemon.poll_and_advance())
    assert run.topics_advanced == 1
    assert any("phase1" in p for p in run.phases_executed)
    assert len(invoker.calls) == 2  # one per agent

    saved = load_topic(topic.topic_id)
    assert saved is not None
    assert saved.state == State.PHASE1_INDEPENDENT
    assert "Design" in saved.phase1_responses
    assert "Frontend" in saved.phase1_responses
    assert saved.phase1_responses["Design"]["stance"] == "支持"


def test_daemon_phase1_error_agent_marked_neutral(isolated_memory_dir):
    daemon = CouncilDaemon(invoker=FakeErrorInvoker())

    topic = _make_topic(state=State.STRUCTURED, convened=["Design"])
    save_topic(topic)

    run = _run(daemon.poll_and_advance())
    saved = load_topic(topic.topic_id)
    assert saved is not None
    assert saved.phase1_responses["Design"]["stance"] == "中立"


# ── Phase 1 close — no divergence ────────────────────────────────────


def test_daemon_closes_phase1_no_divergence(isolated_memory_dir):
    invoker = FakeAgentInvoker(stance="支持")
    daemon = CouncilDaemon(invoker=invoker)

    # Topic already in PHASE1_INDEPENDENT with all agents responded
    topic = _make_topic(state=State.PHASE1_INDEPENDENT, convened=["Design", "Frontend"])
    topic.phase1_responses = {
        "Design": {"stance": "支持", "reasoning": "好"},
        "Frontend": {"stance": "支持", "reasoning": "贊成"},
    }
    save_topic(topic)

    run = _run(daemon.poll_and_advance())
    assert run.topics_advanced == 1

    saved = load_topic(topic.topic_id)
    assert saved is not None
    # Should skip Phase 2 and go through Phase 3 → AWAITING_SIGNOFF
    assert saved.state == State.AWAITING_SIGNOFF
    assert saved.phase3_proposal != {}


# ── Phase 1 close — with divergence ──────────────────────────────────


def test_daemon_runs_phase2_on_divergence(isolated_memory_dir):
    invoker = FakeAgentInvoker()
    daemon = CouncilDaemon(invoker=invoker)

    topic = _make_topic(state=State.PHASE1_INDEPENDENT, convened=["Design", "Frontend"])
    topic.phase1_responses = {
        "Design": {"stance": "支持", "reasoning": "好"},
        "Frontend": {"stance": "反對", "reasoning": "不好"},
    }
    save_topic(topic)

    run = _run(daemon.poll_and_advance())
    saved = load_topic(topic.topic_id)
    assert saved is not None
    assert saved.state == State.AWAITING_SIGNOFF
    assert len(saved.phase2_debate) >= 1
    phase_ids = " ".join(run.phases_executed)
    assert "phase2" in phase_ids
    assert "phase3" in phase_ids


def test_daemon_awaits_missing_phase1_responses(isolated_memory_dir):
    invoker = FakeAgentInvoker()
    daemon = CouncilDaemon(invoker=invoker)

    topic = _make_topic(state=State.PHASE1_INDEPENDENT, convened=["Design", "Frontend"])
    # Only Design responded — Frontend still pending
    topic.phase1_responses = {
        "Design": {"stance": "支持", "reasoning": "好"},
    }
    save_topic(topic)

    run = _run(daemon.poll_and_advance())
    # Should NOT advance — waiting for Frontend
    saved = load_topic(topic.topic_id)
    assert saved is not None
    assert saved.state == State.PHASE1_INDEPENDENT
    assert run.topics_advanced == 0


# ── Phase 3 standalone ────────────────────────────────────────────────


def test_daemon_runs_phase3_for_integration_state(isolated_memory_dir):
    invoker = FakeAgentInvoker()
    daemon = CouncilDaemon(invoker=invoker)

    topic = _make_topic(state=State.PHASE3_INTEGRATION, convened=["Design"])
    topic.phase1_responses = {"Design": {"stance": "支持", "reasoning": "好"}}
    save_topic(topic)

    run = _run(daemon.poll_and_advance())
    saved = load_topic(topic.topic_id)
    assert saved is not None
    assert saved.state == State.AWAITING_SIGNOFF
    assert "整合完成" in saved.phase3_proposal.get("tldr", "")


# ── Error handling ────────────────────────────────────────────────────


def test_daemon_records_error_on_unexpected_exception(isolated_memory_dir, monkeypatch):
    async def bad_advance(topic, run):
        raise RuntimeError("unexpected!")

    daemon = CouncilDaemon(invoker=FakeAgentInvoker())
    monkeypatch.setattr(daemon, "_advance_topic", bad_advance)

    topic = _make_topic(state=State.STRUCTURED, convened=["Design"])
    save_topic(topic)

    run = _run(daemon.poll_and_advance())
    assert len(run.errors) == 1
    assert "unexpected" in run.errors[0]
    assert run.topics_advanced == 0
