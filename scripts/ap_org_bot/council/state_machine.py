"""3-state Council pilot state machine.

Why this is restricted to 3 transitions instead of blueprint's 9:
- Phase 1 / Phase 2 / Phase 3 of the council protocol require multi-agent
  coordination logic (each agent posts independently, PM identifies divergences,
  rounds of debate). That's ~300 LoC + non-trivial tests.
- For Sprint 1, we want to prove out persistence + Discord roundtrip + dispatch
  with the smallest viable surface. PM (or Craig) writes the proposal manually
  in #council-meetings; this module just handles the state transitions and the
  signoff embed.
- Sprint 3 extends this without changing persistence shape: new states get added
  to State enum + new `transition_*` methods. Existing JSON state files
  forward-compatible.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

log = logging.getLogger("ap_org_bot.council.state_machine")


class State(str, Enum):
    NEW = "NEW"
    STRUCTURED = "STRUCTURED"
    AWAITING_SIGNOFF = "AWAITING_SIGNOFF"
    SIGNED_OFF = "SIGNED_OFF"
    REJECTED = "REJECTED"
    # Forward-compatibility placeholders (not yet driving any logic):
    PHASE1_INDEPENDENT = "PHASE1_INDEPENDENT"
    PHASE2_DEBATE = "PHASE2_DEBATE"
    PHASE3_INTEGRATION = "PHASE3_INTEGRATION"
    REOPENED = "REOPENED"
    ARCHIVED = "ARCHIVED"


# Sprint 2: 9-state path active. Sprint 1 "pilot short-circuit"
# (STRUCTURED → AWAITING_SIGNOFF) is preserved alongside full 9-state path,
# so PMs can pick simple-PM-integration vs full multi-agent debate per topic.
ALLOWED_TRANSITIONS: dict[State, set[State]] = {
    State.NEW: {State.STRUCTURED, State.REJECTED},

    State.STRUCTURED: {
        State.AWAITING_SIGNOFF,        # pilot path (PM directly integrates)
        State.PHASE1_INDEPENDENT,      # full 9-state path
        State.REJECTED,
    },

    State.PHASE1_INDEPENDENT: {
        State.PHASE2_DEBATE,           # standard — proceed to debate
        State.PHASE3_INTEGRATION,      # skip if no divergence
        State.AWAITING_SIGNOFF,        # PM short-circuit (e.g. all agents agreed)
        State.REJECTED,
    },

    State.PHASE2_DEBATE: {
        State.PHASE3_INTEGRATION,
        State.REJECTED,
    },

    State.PHASE3_INTEGRATION: {
        State.AWAITING_SIGNOFF,
        State.REJECTED,
    },

    State.AWAITING_SIGNOFF: {State.SIGNED_OFF, State.REJECTED},
    State.SIGNED_OFF: {State.ARCHIVED},
    State.REJECTED: {State.ARCHIVED, State.REOPENED},
    State.REOPENED: {State.NEW},
    State.ARCHIVED: set(),
}

TERMINAL_STATES = {State.ARCHIVED}


@dataclass
class Topic:
    """A Council topic — full state envelope serialized to JSON.

    Schema mirrors blueprint v1.1 §3.6.2 — fields not yet used (phase1_responses,
    phase2_debate) are left as empty containers so 9-state extension doesn't
    require migration of pilot-era files.
    """

    topic_id: str
    state: State = State.NEW
    schema_version: int = 1
    created_at: str = ""
    updated_at: str = ""

    # Topic content (filled by PM during NEW → STRUCTURED)
    raw_input: str = ""
    structured: dict[str, str] = field(default_factory=dict)
    topic_type: str = "其他"          # matches keys in council_routing.yaml
    convened: list[str] = field(default_factory=list)

    # Pilot proposal (filled during STRUCTURED → AWAITING_SIGNOFF)
    pilot_proposal: dict[str, Any] = field(default_factory=dict)

    # Forward-compat (Sprint 3 will populate)
    phase1_responses: dict[str, Any] = field(default_factory=dict)
    phase2_debate: list[dict] = field(default_factory=list)
    phase3_proposal: dict[str, Any] = field(default_factory=dict)

    # Sign-off
    signoff: dict[str, Any] = field(default_factory=lambda: {
        "decision": None,
        "decided_by": None,
        "decided_at": None,
        "reaction": None,
    })
    dispatched_tasks: list[dict] = field(default_factory=list)

    # Audit log of every transition
    audit_log: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "schema_version": self.schema_version,
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "topic": {
                "raw_input": self.raw_input,
                "structured": self.structured,
                "topic_type": self.topic_type,
            },
            "convened": self.convened,
            "pilot_proposal": self.pilot_proposal,
            "phase1_responses": self.phase1_responses,
            "phase2_debate": self.phase2_debate,
            "phase3_proposal": self.phase3_proposal,
            "signoff": self.signoff,
            "dispatched_tasks": self.dispatched_tasks,
            "audit_log": self.audit_log,
        }

    @classmethod
    def from_dict(cls, doc: dict) -> "Topic":
        topic_block = doc.get("topic", {})
        t = cls(
            topic_id=doc["topic_id"],
            schema_version=doc.get("schema_version", 1),
            state=State(doc.get("state", "NEW")),
            created_at=doc.get("created_at", ""),
            updated_at=doc.get("updated_at", ""),
            raw_input=topic_block.get("raw_input", ""),
            structured=topic_block.get("structured", {}) or {},
            topic_type=topic_block.get("topic_type", "其他"),
            convened=doc.get("convened", []) or [],
            pilot_proposal=doc.get("pilot_proposal", {}) or {},
            phase1_responses=doc.get("phase1_responses", {}) or {},
            phase2_debate=doc.get("phase2_debate", []) or [],
            phase3_proposal=doc.get("phase3_proposal", {}) or {},
            signoff=doc.get("signoff") or {},
            dispatched_tasks=doc.get("dispatched_tasks", []) or [],
            audit_log=doc.get("audit_log", []) or [],
        )
        return t


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def can_transition(current: State, target: State) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


class IdempotentTransitionError(RuntimeError):
    """Caller asked to transition into the state we're already in. Treated as no-op."""


class IllegalTransitionError(RuntimeError):
    """Target state not reachable from current state under pilot rules."""


def transition(
    topic: Topic,
    target: State,
    *,
    actor: str,
    payload: Optional[dict] = None,
) -> Topic:
    """Apply a state transition. Idempotent if already in target state.

    Raises:
        IllegalTransitionError if transition not in ALLOWED_TRANSITIONS.
    """
    if topic.state == target:
        # Idempotency: the same transition can be safely re-applied without
        # double-dispatching tasks or double-billing Gemini quota.
        log.info("[council] topic %s already in %s — no-op",
                 topic.topic_id, target.value)
        return topic

    if not can_transition(topic.state, target):
        raise IllegalTransitionError(
            f"{topic.topic_id}: cannot transition {topic.state.value} → {target.value}"
        )

    prev = topic.state
    topic.state = target
    topic.updated_at = _now_utc()
    if not topic.created_at:
        topic.created_at = topic.updated_at

    entry = {
        "ts": topic.updated_at,
        "from": prev.value,
        "to": target.value,
        "actor": actor,
    }
    if payload:
        entry["payload"] = payload
    topic.audit_log.append(entry)

    log.info("[council] topic %s %s → %s (by %s)",
             topic.topic_id, prev.value, target.value, actor)
    return topic


# ── Phase 1/2/3 helpers (Sprint 2 — 9-state path) ──────────────────


class PhaseStateError(RuntimeError):
    """Caller tried a phase op but the topic is in the wrong state."""


def add_phase1_response(
    topic: Topic,
    *,
    agent_name: str,
    stance: str,
    reasoning: str = "",
    model: str = "haiku",
) -> Topic:
    """Record one agent's independent stance during PHASE1_INDEPENDENT.

    Per blueprint v1.1 §3.2: Phase 1 = each agent posts in parallel without
    seeing others' replies. This helper just appends to phase1_responses dict;
    the actual parallelism happens at the agent invocation layer (Sprint 3).
    """
    if topic.state != State.PHASE1_INDEPENDENT:
        raise PhaseStateError(
            f"add_phase1_response requires PHASE1_INDEPENDENT, got {topic.state.value}"
        )
    topic.phase1_responses[agent_name] = {
        "timestamp": _now_utc(),
        "stance": stance,
        "reasoning": reasoning,
        "model": model,
    }
    topic.updated_at = _now_utc()
    log.info("[council] %s phase1 ← %s: %s", topic.topic_id, agent_name, stance[:40])
    return topic


def add_phase2_debate_round(
    topic: Topic,
    *,
    divergence_point: str,
    rounds: list[dict],
    convergence: str,
) -> Topic:
    """Append one debate round for one divergence point in PHASE2_DEBATE.

    `rounds` is a list of {agent, position, response} dicts (1-2 rounds typical).
    `convergence` is PM's summary of what got resolved (or "no convergence").
    """
    if topic.state != State.PHASE2_DEBATE:
        raise PhaseStateError(
            f"add_phase2_debate_round requires PHASE2_DEBATE, got {topic.state.value}"
        )
    topic.phase2_debate.append({
        "timestamp": _now_utc(),
        "divergence_point": divergence_point,
        "rounds": list(rounds),
        "convergence": convergence,
    })
    topic.updated_at = _now_utc()
    log.info(
        "[council] %s phase2 debate: %s (%d rounds) → %s",
        topic.topic_id, divergence_point[:40], len(rounds), convergence[:40],
    )
    return topic


def set_phase3_proposal(
    topic: Topic,
    *,
    tldr: str,
    recommended: str = "",
    reasoning: str = "",
    follow_up_tasks: Optional[list[dict]] = None,
    options_considered: Optional[list[dict]] = None,
    body: str = "",
    embed_message_id: Optional[str] = None,
    model: str = "sonnet",
) -> Topic:
    """Set the integrated proposal during PHASE3_INTEGRATION.

    Mirrors fields to `pilot_proposal` so the reaction handler / embed renderer
    don't have to branch on path. The 9-state path overwrites pilot_proposal
    with the integrated phase3 content; the Sprint 1 short-circuit path leaves
    pilot_proposal untouched.
    """
    if topic.state != State.PHASE3_INTEGRATION:
        raise PhaseStateError(
            f"set_phase3_proposal requires PHASE3_INTEGRATION, got {topic.state.value}"
        )
    timestamp = _now_utc()
    topic.phase3_proposal = {
        "timestamp": timestamp,
        "tldr": tldr,
        "recommended": recommended,
        "reasoning": reasoning,
        "follow_up_tasks": list(follow_up_tasks or []),
        "options_considered": list(options_considered or []),
        "body": body,
        "embed_message_id": embed_message_id,
        "model": model,
    }
    # Mirror to pilot_proposal so existing embed/reaction code works unchanged.
    topic.pilot_proposal = {
        **(topic.pilot_proposal or {}),
        "tldr": tldr,
        "recommended": recommended,
        "reasoning": reasoning,
        "follow_up_tasks": list(follow_up_tasks or []),
        "options_considered": list(options_considered or []),
        "phase3_synced_at": timestamp,
    }
    topic.updated_at = timestamp
    log.info("[council] %s phase3 proposal set: %s", topic.topic_id, tldr[:60])
    return topic


def proposal_for_embed(topic: Topic) -> dict:
    """Return the right proposal block for embed rendering — phase3 if set,
    else fall back to pilot_proposal (Sprint 1 path).

    Used by discord_io/council_embed.py to surface AWAITING_SIGNOFF data without
    branching on path.
    """
    if topic.phase3_proposal:
        return topic.phase3_proposal
    return topic.pilot_proposal
