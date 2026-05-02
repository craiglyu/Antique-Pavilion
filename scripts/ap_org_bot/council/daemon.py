"""CouncilDaemon — auto-triggers Phase 1/2/3 for active Council topics.

Sprint 3 scope: polls topics in STRUCTURED/PHASE1_INDEPENDENT/PHASE2_DEBATE states
and advances them without manual CLI intervention.

Architecture:
- AgentInvoker: injectable protocol so tests never make live LLM calls.
- CouncilDaemon.poll_and_advance(): called by the bot scheduler (11:00 / 20:00).
- Phase 1: each convened agent gives an independent stance.
- Phase 2: PM mediates divergent stances in up to MAX_DEBATE_ROUNDS rounds.
- Phase 3: PM integrates all responses into a final proposal.
- Each phase saves the topic to disk before returning.

Stance vocabulary (Phase 1 responses must contain one of these):
    支持 / 贊成 — agent agrees with proposed direction
    反對 / 否決 — agent opposes; requires their reasoning for Phase 2
    修改建議 / 建議修改 — partial agreement with proposed changes
    中立 / 保留意見 — no strong stance; PM can short-circuit debate
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ap_org_bot.council.persistence import list_active_topics, save_topic
from ap_org_bot.council.state_machine import (
    PhaseStateError,
    State,
    Topic,
    add_phase1_response,
    add_phase2_debate_round,
    set_phase3_proposal,
    transition,
)

log = logging.getLogger("ap_org_bot.council.daemon")

MAX_DEBATE_ROUNDS = 2
PHASE1_TIMEOUT_HOURS = 24  # if agent doesn't respond in time, mark as 中立

# Canonical stance keywords → normalised stance value
_STANCE_KEYWORDS: dict[str, str] = {
    "支持": "支持",
    "贊成": "支持",
    "反對": "反對",
    "否決": "反對",
    "修改建議": "修改建議",
    "建議修改": "修改建議",
    "中立": "中立",
    "保留意見": "中立",
}


class AgentInvoker:
    """Protocol for invoking an agent and getting its text response.

    The real implementation calls HeadlessClient.run_with_args().
    Tests inject a FakeAgentInvoker that returns canned responses.
    """

    async def invoke(self, agent_name: str, prompt: str) -> str:
        raise NotImplementedError


def parse_stance(text: str) -> str:
    """Extract a normalised stance from free-form agent text.

    Looks for patterns like:
        立場: 支持     (colon, full-width colon, or after bold/heading markers)
        **立場**: 反對
    Falls back to keyword search across the whole text.
    Returns one of: 支持 / 反對 / 修改建議 / 中立 / 未知
    """
    # Pattern 1: 「立場:」 or 「立場：」 on its own line / inline
    m = re.search(r"立場[：:]\s*([^\n,，。.]{2,10})", text)
    if m:
        fragment = m.group(1).strip()
        for kw, normalised in _STANCE_KEYWORDS.items():
            if kw in fragment:
                return normalised

    # Pattern 2: scan full text for stance keywords (order matters — more specific first)
    for kw in ("修改建議", "建議修改", "保留意見", "支持", "贊成", "反對", "否決", "中立"):
        if kw in text:
            return _STANCE_KEYWORDS[kw]

    return "未知"


def _phase1_prompt(topic: Topic, agent_name: str) -> str:
    structured = topic.structured
    return (
        f"【Council Phase 1 — 獨立立場評估】\n\n"
        f"議題 ID: {topic.topic_id}\n"
        f"議題類型: {topic.topic_type}\n"
        f"議題摘要: {structured.get('summary', topic.raw_input[:200])}\n\n"
        f"你是 {agent_name} 代理人。請在不參考其他代理人意見的情況下，"
        f"就此議題表達你的獨立立場。\n\n"
        f"**必要格式**（第一行開始）：\n"
        f"立場: [支持 / 反對 / 修改建議 / 中立]\n"
        f"理由: [50-200 字說明]\n\n"
        f"如有修改建議，請具體說明建議方向。"
    )


def _phase2_prompt(
    topic: Topic,
    divergence_point: str,
    stances: dict[str, dict],
) -> str:
    stances_text = "\n".join(
        f"- {name}: 立場={data.get('stance','?')} — {data.get('reasoning','')[:120]}"
        for name, data in stances.items()
    )
    return (
        f"【Council Phase 2 — 辯論與協調】\n\n"
        f"議題: {topic.topic_id} ({topic.topic_type})\n"
        f"分歧點: {divergence_point}\n\n"
        f"各代理人立場：\n{stances_text}\n\n"
        f"請作為辯論協調者，說明雙方核心分歧，提出一個可被多數接受的折衷方向。\n"
        f"**格式**：\n"
        f"核心分歧: [1-2 句]\n"
        f"折衷方向: [具體建議]\n"
        f"收斂狀態: [已收斂 / 未收斂]"
    )


def _phase3_prompt(topic: Topic) -> str:
    p1 = topic.phase1_responses
    p2 = topic.phase2_debate
    summaries = "\n".join(
        f"- {name}: {data.get('stance','?')} — {data.get('reasoning','')[:100]}"
        for name, data in p1.items()
    )
    debate_summary = ""
    if p2:
        debate_summary = "\n\n辯論記錄摘要：\n" + "\n".join(
            f"- {r['divergence_point']}: {r['convergence'][:80]}"
            for r in p2
        )
    return (
        f"【Council Phase 3 — 整合提案】\n\n"
        f"議題: {topic.topic_id} ({topic.topic_type})\n"
        f"原始議題: {topic.raw_input[:300]}\n\n"
        f"Phase 1 各代理人立場：\n{summaries}"
        f"{debate_summary}\n\n"
        f"請作為 PM，整合上述意見，生成最終提案。\n"
        f"**格式**：\n"
        f"TLDR: [一句話]\n"
        f"建議方向: [2-4 句]\n"
        f"理由: [2-3 句]\n"
        f"後續任務: [bullet list, 每行用 - 開頭]"
    )


def _parse_phase3_response(text: str) -> dict[str, Any]:
    """Parse PM's Phase 3 integration response into structured fields."""
    def _extract(label: str) -> str:
        m = re.search(rf"{label}[：:]\s*(.+?)(?=\n[^\s-]|\Z)", text, re.DOTALL)
        return m.group(1).strip() if m else ""

    tldr = _extract("TLDR")
    recommended = _extract("建議方向")
    reasoning = _extract("理由")

    tasks_raw = _extract("後續任務")
    follow_up: list[dict] = []
    if tasks_raw:
        for line in tasks_raw.splitlines():
            line = line.lstrip("-• ").strip()
            if line:
                follow_up.append({"task": line, "assigned_to": "PM"})

    return {
        "tldr": tldr or text[:80],
        "recommended": recommended,
        "reasoning": reasoning,
        "follow_up_tasks": follow_up,
        "body": text,
    }


@dataclass
class DaemonRun:
    """Summary of one poll_and_advance() execution."""

    topics_polled: int = 0
    topics_advanced: int = 0
    phases_executed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "topics_polled": self.topics_polled,
            "topics_advanced": self.topics_advanced,
            "phases_executed": self.phases_executed,
            "errors": self.errors,
        }


class CouncilDaemon:
    """Polls active Council topics and auto-advances them through Phase 1/2/3.

    Wired into the bot scheduler via main.py (Sprint 3). Called at 11:00 + 20:00.
    Can also be triggered manually via `ap_council_runner.py daemon-poll` (Sprint 4+).
    """

    def __init__(self, invoker: Optional[AgentInvoker] = None):
        self.invoker = invoker  # None means "dry-run" / no LLM calls

    async def poll_and_advance(self) -> DaemonRun:
        """Scan all active topics and advance those in actionable states.

        Actionable states:
        - STRUCTURED with full 9-state path → Phase 1
        - PHASE1_INDEPENDENT with all agents responded → detect divergence
        - PHASE2_DEBATE with rounds complete → Phase 3
        - PHASE3_INTEGRATION with no proposal yet → generate proposal
        """
        run = DaemonRun()
        topics = list_active_topics()
        run.topics_polled = len(topics)

        for topic in topics:
            try:
                advanced = await self._advance_topic(topic, run)
                if advanced:
                    run.topics_advanced += 1
            except Exception as exc:
                msg = f"{topic.topic_id}: {type(exc).__name__}: {exc}"
                log.error("[daemon] error advancing topic %s", msg)
                run.errors.append(msg)

        log.info(
            "[daemon] poll complete: %d polled, %d advanced, %d errors",
            run.topics_polled, run.topics_advanced, len(run.errors),
        )
        return run

    async def _advance_topic(self, topic: Topic, run: DaemonRun) -> bool:
        """Return True if topic was advanced (state changed)."""
        if topic.state == State.STRUCTURED and topic.convened:
            return await self._run_phase1(topic, run)

        if topic.state == State.PHASE1_INDEPENDENT:
            return await self._maybe_close_phase1(topic, run)

        if topic.state == State.PHASE2_DEBATE:
            return await self._run_phase3(topic, run)

        if topic.state == State.PHASE3_INTEGRATION and not topic.phase3_proposal:
            return await self._run_phase3(topic, run)

        return False

    async def _run_phase1(self, topic: Topic, run: DaemonRun) -> bool:
        """Transition STRUCTURED → PHASE1_INDEPENDENT then invoke agents."""
        if self.invoker is None:
            log.info("[daemon] %s: no invoker — skipping Phase 1", topic.topic_id)
            return False

        topic = transition(
            topic, State.PHASE1_INDEPENDENT, actor="CouncilDaemon",
            payload={"trigger": "auto-phase1"},
        )
        save_topic(topic)

        for agent_name in topic.convened:
            prompt = _phase1_prompt(topic, agent_name)
            try:
                response = await self.invoker.invoke(agent_name, prompt)
            except Exception as exc:
                log.error("[daemon] %s phase1 agent %s error: %s",
                          topic.topic_id, agent_name, exc)
                response = "立場: 中立\n理由: 代理人呼叫失敗，自動標記中立。"

            stance = parse_stance(response)
            reasoning = re.sub(r"立場[：:][^\n]*\n?", "", response).strip()[:300]
            add_phase1_response(
                topic,
                agent_name=agent_name,
                stance=stance,
                reasoning=reasoning,
            )
            log.info("[daemon] %s phase1 ← %s: %s", topic.topic_id, agent_name, stance)

        save_topic(topic)
        run.phases_executed.append(f"{topic.topic_id}:phase1")
        return True

    async def _maybe_close_phase1(self, topic: Topic, run: DaemonRun) -> bool:
        """Check if all convened agents have responded; if so, detect divergence."""
        responded = set(topic.phase1_responses.keys())
        convened = set(topic.convened)

        if not convened.issubset(responded):
            missing = convened - responded
            log.info("[daemon] %s: awaiting phase1 from %s", topic.topic_id, missing)
            return False

        # All responded — detect divergence
        divergent = _detect_divergence(topic.phase1_responses)

        if divergent and self.invoker is not None:
            return await self._run_phase2(topic, divergent, run)
        else:
            # No divergence (or no invoker) — skip to Phase 3 or AWAITING_SIGNOFF
            topic = transition(
                topic, State.PHASE3_INTEGRATION, actor="CouncilDaemon",
                payload={"skip_debate": True, "reason": "no_divergence"},
            )
            save_topic(topic)
            run.phases_executed.append(f"{topic.topic_id}:phase1-close-nodiv")
            return await self._run_phase3(topic, run)

    async def _run_phase2(
        self,
        topic: Topic,
        divergent_pairs: list[str],
        run: DaemonRun,
    ) -> bool:
        """Transition to PHASE2_DEBATE, run up to MAX_DEBATE_ROUNDS per divergence."""
        topic = transition(
            topic, State.PHASE2_DEBATE, actor="CouncilDaemon",
            payload={"divergent_points": divergent_pairs},
        )
        save_topic(topic)

        for div_point in divergent_pairs[:MAX_DEBATE_ROUNDS]:
            prompt = _phase2_prompt(topic, div_point, topic.phase1_responses)
            try:
                response = await self.invoker.invoke("PM", prompt)  # type: ignore[union-attr]
            except Exception as exc:
                response = f"核心分歧: 協調失敗\n折衷方向: 無法收斂\n收斂狀態: 未收斂\n({exc})"

            convergence = ""
            m = re.search(r"折衷方向[：:]\s*(.+?)(?=\n|$)", response)
            if m:
                convergence = m.group(1).strip()

            add_phase2_debate_round(
                topic,
                divergence_point=div_point,
                rounds=[{"response": response[:400]}],
                convergence=convergence or "PM 協調中",
            )

        save_topic(topic)
        run.phases_executed.append(f"{topic.topic_id}:phase2")
        # Immediately advance to Phase 3
        return await self._run_phase3(topic, run)

    async def _run_phase3(self, topic: Topic, run: DaemonRun) -> bool:
        """Generate PM integration proposal → transition to AWAITING_SIGNOFF."""
        if self.invoker is None:
            log.info("[daemon] %s: no invoker — skipping Phase 3", topic.topic_id)
            return False

        # Ensure correct state for set_phase3_proposal
        if topic.state != State.PHASE3_INTEGRATION:
            try:
                topic = transition(
                    topic, State.PHASE3_INTEGRATION, actor="CouncilDaemon",
                    payload={"trigger": "auto-phase3"},
                )
                save_topic(topic)
            except Exception as exc:
                log.error("[daemon] %s cannot reach PHASE3_INTEGRATION: %s",
                          topic.topic_id, exc)
                return False

        prompt = _phase3_prompt(topic)
        try:
            response = await self.invoker.invoke("PM", prompt)
        except Exception as exc:
            log.error("[daemon] %s phase3 PM invoke failed: %s",
                      topic.topic_id, exc)
            return False

        parsed = _parse_phase3_response(response)
        try:
            set_phase3_proposal(
                topic,
                tldr=parsed["tldr"],
                recommended=parsed["recommended"],
                reasoning=parsed["reasoning"],
                follow_up_tasks=parsed["follow_up_tasks"],
                body=parsed["body"],
                model="daemon",
            )
        except PhaseStateError as exc:
            log.error("[daemon] %s set_phase3_proposal: %s", topic.topic_id, exc)
            return False

        topic = transition(
            topic, State.AWAITING_SIGNOFF, actor="CouncilDaemon",
            payload={"trigger": "auto-phase3-complete"},
        )
        save_topic(topic)
        run.phases_executed.append(f"{topic.topic_id}:phase3")
        log.info("[daemon] %s → AWAITING_SIGNOFF (tldr: %s)",
                 topic.topic_id, parsed["tldr"][:60])
        return True


def _detect_divergence(phase1_responses: dict[str, dict]) -> list[str]:
    """Return list of divergence point labels if agents disagree.

    Simple rule: if any agent has stance 反對 while at least one has 支持,
    that's a divergence. Returns a list of human-readable divergence point labels.
    """
    stances = {name: data.get("stance", "未知") for name, data in phase1_responses.items()}
    unique_stances = set(stances.values()) - {"未知", "中立"}

    if len(unique_stances) < 2:
        return []

    # Build divergence description per opposing pair
    groups: dict[str, list[str]] = {}
    for name, stance in stances.items():
        if stance not in ("未知", "中立"):
            groups.setdefault(stance, []).append(name)

    if len(groups) < 2:
        return []

    divergences: list[str] = []
    stance_list = sorted(groups.keys())
    for i, s1 in enumerate(stance_list):
        for s2 in stance_list[i + 1:]:
            agents1 = groups[s1]
            agents2 = groups[s2]
            label = (f"{'+'.join(agents1)} ({s1}) vs "
                     f"{'+'.join(agents2)} ({s2})")
            divergences.append(label)
    return divergences
