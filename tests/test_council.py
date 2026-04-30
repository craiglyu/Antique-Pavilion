"""Council 3-state pilot: state machine + persistence + dispatcher."""

from __future__ import annotations

import json

import pytest

from ap_org_bot.council.persistence import (
    list_active_topics,
    list_topics,
    load_topic,
    make_topic_id,
    save_topic,
)
from ap_org_bot.council.state_machine import (
    IllegalTransitionError,
    State,
    Topic,
    can_transition,
    transition,
)


# ── State machine ─────────────────────────────────────────────────────


def test_default_state_is_new():
    t = Topic(topic_id="x")
    assert t.state == State.NEW


def test_pilot_path_allowed():
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="test")
    transition(t, State.AWAITING_SIGNOFF, actor="test")
    transition(t, State.SIGNED_OFF, actor="craig")
    transition(t, State.ARCHIVED, actor="cli")
    assert t.state == State.ARCHIVED


def test_illegal_skip_raises():
    t = Topic(topic_id="x")
    with pytest.raises(IllegalTransitionError):
        transition(t, State.AWAITING_SIGNOFF, actor="test")


def test_idempotent_same_state_is_noop():
    t = Topic(topic_id="x", state=State.NEW)
    before = len(t.audit_log)
    transition(t, State.NEW, actor="test")  # no-op
    assert len(t.audit_log) == before
    assert t.state == State.NEW


def test_phase_states_unreachable_under_pilot():
    """Sprint 3 will lift this; for now blueprint phases are stubs."""
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="test")
    assert not can_transition(State.STRUCTURED, State.PHASE1_INDEPENDENT)


def test_audit_log_grows_per_transition():
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="pm")
    transition(t, State.AWAITING_SIGNOFF, actor="pm")
    assert len(t.audit_log) == 2
    assert t.audit_log[0]["from"] == "NEW"
    assert t.audit_log[0]["to"] == "STRUCTURED"
    assert t.audit_log[0]["actor"] == "pm"


def test_reject_path_to_reopened():
    t = Topic(topic_id="x")
    transition(t, State.STRUCTURED, actor="pm")
    transition(t, State.REJECTED, actor="craig")
    transition(t, State.REOPENED, actor="craig")
    transition(t, State.NEW, actor="craig")
    assert t.state == State.NEW


# ── Persistence ───────────────────────────────────────────────────────


def test_save_and_load_roundtrip(isolated_memory_dir):
    t = Topic(
        topic_id="ap-test-001",
        raw_input="testing",
        topic_type="視覺微調",
        convened=["Design", "Frontend"],
    )
    transition(t, State.STRUCTURED, actor="pm")
    save_topic(t)

    loaded = load_topic("ap-test-001")
    assert loaded is not None
    assert loaded.topic_id == "ap-test-001"
    assert loaded.state == State.STRUCTURED
    assert loaded.raw_input == "testing"
    assert loaded.convened == ["Design", "Frontend"]
    assert len(loaded.audit_log) == 1


def test_load_missing_returns_none(isolated_memory_dir):
    assert load_topic("does-not-exist") is None


def test_make_topic_id_unique(isolated_memory_dir):
    """Two consecutive make_topic_id() calls produce distinct IDs even within the same second."""
    a = make_topic_id()
    save_topic(Topic(topic_id=a))
    b = make_topic_id()
    assert a != b


def test_list_active_excludes_archived(isolated_memory_dir):
    t1 = Topic(topic_id="ap-active")
    t2 = Topic(topic_id="ap-done", state=State.ARCHIVED)
    save_topic(t1)
    save_topic(t2)

    actives = list_active_topics()
    ids = [t.topic_id for t in actives]
    assert "ap-active" in ids
    assert "ap-done" not in ids
    # Both still listed by list_topics()
    all_ids = [t.topic_id for t in list_topics()]
    assert {"ap-active", "ap-done"}.issubset(set(all_ids))


def test_save_is_atomic_no_dotted_files(isolated_memory_dir):
    t = Topic(topic_id="ap-atomic")
    save_topic(t)
    # No leftover .json.tmp
    leftover = list(isolated_memory_dir.glob("ap_council_state/*.tmp"))
    assert leftover == []


def test_corrupt_topic_file_skipped(isolated_memory_dir):
    bad = isolated_memory_dir / "ap_council_state" / "corrupt.json"
    bad.write_text("{not-valid-json", encoding="utf-8")
    # Should not raise
    topics = list_topics()
    assert all(t.topic_id != "corrupt" for t in topics)


def test_schema_version_round_trips(isolated_memory_dir):
    t = Topic(topic_id="ap-sv", schema_version=1)
    save_topic(t)
    raw = json.loads((isolated_memory_dir / "ap_council_state" / "ap-sv.json")
                     .read_text(encoding="utf-8"))
    assert raw["schema_version"] == 1
