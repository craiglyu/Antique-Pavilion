"""Council 9-state extension (Sprint 2): Phase 1/2/3 transitions + helpers.

Sprint 1 pilot path (NEW → STRUCTURED → AWAITING_SIGNOFF) tests live in
test_council.py. This file covers the Sprint 2 9-state path:
  STRUCTURED → PHASE1_INDEPENDENT → PHASE2_DEBATE → PHASE3_INTEGRATION
              → AWAITING_SIGNOFF
"""

from __future__ import annotations

import pytest

from ap_org_bot.council.state_machine import (
    PhaseStateError,
    State,
    Topic,
    add_phase1_response,
    add_phase2_debate_round,
    can_transition,
    proposal_for_embed,
    set_phase3_proposal,
    transition,
)


# ── Transition graph ────────────────────────────────────────────────


def test_pilot_path_still_works():
    """Sprint 1 short-circuit path is preserved."""
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="pm")
    transition(t, State.AWAITING_SIGNOFF, actor="pm")
    assert t.state == State.AWAITING_SIGNOFF


def test_full_9state_path_allowed():
    t = Topic(topic_id="x")
    for target in [State.STRUCTURED, State.PHASE1_INDEPENDENT,
                   State.PHASE2_DEBATE, State.PHASE3_INTEGRATION,
                   State.AWAITING_SIGNOFF, State.SIGNED_OFF, State.ARCHIVED]:
        transition(t, target, actor="test")
    assert t.state == State.ARCHIVED


def test_phase1_can_skip_phase2_when_no_divergence():
    """If Phase 1 stances all agree, PM may go directly to PHASE3_INTEGRATION."""
    t = Topic(topic_id="x", state=State.PHASE1_INDEPENDENT)
    assert can_transition(State.PHASE1_INDEPENDENT, State.PHASE3_INTEGRATION)


def test_phase1_can_short_circuit_to_awaiting():
    """If everyone agreed in Phase 1, PM may skip Phase 2/3 entirely."""
    assert can_transition(State.PHASE1_INDEPENDENT, State.AWAITING_SIGNOFF)


def test_phase2_cannot_skip_phase3():
    """Once we're in debate, must produce an integrated proposal before signoff."""
    assert not can_transition(State.PHASE2_DEBATE, State.AWAITING_SIGNOFF)


def test_any_phase_can_be_rejected():
    for state in [State.PHASE1_INDEPENDENT, State.PHASE2_DEBATE,
                  State.PHASE3_INTEGRATION]:
        assert can_transition(state, State.REJECTED)


# ── add_phase1_response ─────────────────────────────────────────────


def test_phase1_response_recorded():
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="pm")
    transition(t, State.PHASE1_INDEPENDENT, actor="pm")
    add_phase1_response(t, agent_name="UX", stance="輪播",
                        reasoning="信任路徑優先", model="haiku")
    assert "UX" in t.phase1_responses
    assert t.phase1_responses["UX"]["stance"] == "輪播"
    assert t.phase1_responses["UX"]["reasoning"] == "信任路徑優先"
    assert t.phase1_responses["UX"]["model"] == "haiku"
    assert t.phase1_responses["UX"]["timestamp"]


def test_phase1_multiple_agents():
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="pm")
    transition(t, State.PHASE1_INDEPENDENT, actor="pm")
    for agent, stance in [("UX", "輪播"), ("Design", "影片"), ("Frontend", "輪播")]:
        add_phase1_response(t, agent_name=agent, stance=stance)
    assert len(t.phase1_responses) == 3
    assert t.phase1_responses["Design"]["stance"] == "影片"


def test_phase1_overwrites_same_agent():
    """An agent updating their stance overwrites the prior recording."""
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="pm")
    transition(t, State.PHASE1_INDEPENDENT, actor="pm")
    add_phase1_response(t, agent_name="UX", stance="A")
    add_phase1_response(t, agent_name="UX", stance="B")
    assert t.phase1_responses["UX"]["stance"] == "B"
    assert len(t.phase1_responses) == 1


def test_phase1_outside_phase1_raises():
    t = Topic(topic_id="x")  # state=NEW
    with pytest.raises(PhaseStateError):
        add_phase1_response(t, agent_name="UX", stance="x")


# ── add_phase2_debate_round ─────────────────────────────────────────


def test_phase2_debate_recorded():
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="pm")
    transition(t, State.PHASE1_INDEPENDENT, actor="pm")
    transition(t, State.PHASE2_DEBATE, actor="pm")
    rounds = [
        {"agent": "UX", "position": "輪播", "response": "因 LCP 風險"},
        {"agent": "Design", "position": "影片", "response": "願意接受 LCP 影響換 brand"},
    ]
    add_phase2_debate_round(
        t,
        divergence_point="首屏 LCP 影響",
        rounds=rounds,
        convergence="輪播 LCP 1.8s vs 影片 3.2s, Frontend veto 影片",
    )
    assert len(t.phase2_debate) == 1
    assert t.phase2_debate[0]["divergence_point"] == "首屏 LCP 影響"
    assert len(t.phase2_debate[0]["rounds"]) == 2
    assert "Frontend veto" in t.phase2_debate[0]["convergence"]


def test_phase2_multiple_divergence_points():
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="pm")
    transition(t, State.PHASE1_INDEPENDENT, actor="pm")
    transition(t, State.PHASE2_DEBATE, actor="pm")
    add_phase2_debate_round(t, divergence_point="LCP", rounds=[], convergence="A")
    add_phase2_debate_round(t, divergence_point="brand", rounds=[], convergence="B")
    assert len(t.phase2_debate) == 2


def test_phase2_outside_phase2_raises():
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="pm")
    with pytest.raises(PhaseStateError):
        add_phase2_debate_round(t, divergence_point="x", rounds=[], convergence="y")


# ── set_phase3_proposal ─────────────────────────────────────────────


def test_phase3_proposal_set_and_mirrored_to_pilot():
    """phase3 proposal mirrors to pilot_proposal so existing embed/reaction works."""
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="pm")
    transition(t, State.PHASE1_INDEPENDENT, actor="pm")
    transition(t, State.PHASE2_DEBATE, actor="pm")
    transition(t, State.PHASE3_INTEGRATION, actor="pm")
    set_phase3_proposal(
        t,
        tldr="採輪播方案 + 第二屏放品牌短影片",
        recommended="輪播 + 第二屏影片",
        reasoning="LCP 風險 + brand 兼顧",
        follow_up_tasks=[
            {"task_id": "T1", "agent": "Frontend", "description": "輪播 LCP 優化"},
        ],
    )
    assert t.phase3_proposal["tldr"] == "採輪播方案 + 第二屏放品牌短影片"
    assert len(t.phase3_proposal["follow_up_tasks"]) == 1
    # Mirrored:
    assert t.pilot_proposal["tldr"] == "採輪播方案 + 第二屏放品牌短影片"
    assert len(t.pilot_proposal["follow_up_tasks"]) == 1
    assert "phase3_synced_at" in t.pilot_proposal


def test_phase3_outside_phase3_raises():
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="pm")
    with pytest.raises(PhaseStateError):
        set_phase3_proposal(t, tldr="x")


def test_phase3_proposal_default_lists_empty_not_none():
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="pm")
    transition(t, State.PHASE1_INDEPENDENT, actor="pm")
    transition(t, State.PHASE3_INTEGRATION, actor="pm")  # phase1→phase3 skip
    set_phase3_proposal(t, tldr="x")
    assert t.phase3_proposal["follow_up_tasks"] == []
    assert t.phase3_proposal["options_considered"] == []


# ── proposal_for_embed accessor ────────────────────────────────────


def test_proposal_for_embed_uses_phase3_when_set():
    t = Topic(topic_id="x")
    t.pilot_proposal = {"tldr": "PILOT"}
    t.phase3_proposal = {"tldr": "PHASE3"}
    assert proposal_for_embed(t)["tldr"] == "PHASE3"


def test_proposal_for_embed_falls_back_to_pilot_when_no_phase3():
    t = Topic(topic_id="x")
    t.pilot_proposal = {"tldr": "PILOT"}
    t.phase3_proposal = {}
    assert proposal_for_embed(t)["tldr"] == "PILOT"


# ── End-to-end: walk a topic through all phases + sign off ──────────


def test_full_9state_walk_with_phase_data():
    t = Topic(topic_id="ap-9state-walk", raw_input="end-to-end test")
    transition(t, State.STRUCTURED, actor="pm")
    transition(t, State.PHASE1_INDEPENDENT, actor="pm")
    add_phase1_response(t, agent_name="UX", stance="A", reasoning="...")
    add_phase1_response(t, agent_name="Design", stance="B", reasoning="...")
    transition(t, State.PHASE2_DEBATE, actor="pm")
    add_phase2_debate_round(
        t, divergence_point="A vs B",
        rounds=[{"agent": "UX", "position": "A"}, {"agent": "Design", "position": "B"}],
        convergence="採 A，Design 接受",
    )
    transition(t, State.PHASE3_INTEGRATION, actor="pm")
    set_phase3_proposal(t, tldr="採 A", recommended="A", reasoning="UX wins")
    transition(t, State.AWAITING_SIGNOFF, actor="pm")
    transition(t, State.SIGNED_OFF, actor="craig")

    assert t.state == State.SIGNED_OFF
    assert len(t.phase1_responses) == 2
    assert len(t.phase2_debate) == 1
    assert t.phase3_proposal["recommended"] == "A"
    assert t.pilot_proposal["recommended"] == "A"  # mirrored
    # Audit log captures every transition + (we hope) preserves order
    transitions = [(e["from"], e["to"]) for e in t.audit_log]
    assert transitions == [
        ("NEW", "STRUCTURED"),
        ("STRUCTURED", "PHASE1_INDEPENDENT"),
        ("PHASE1_INDEPENDENT", "PHASE2_DEBATE"),
        ("PHASE2_DEBATE", "PHASE3_INTEGRATION"),
        ("PHASE3_INTEGRATION", "AWAITING_SIGNOFF"),
        ("AWAITING_SIGNOFF", "SIGNED_OFF"),
    ]
