"""Opus Design Researcher — Phase 1 of the Opus design ruling flow.

Triggered after Craig confirms an OPUS_ESCALATE button. Writes a complete
Design Decision Package (DD-XXX) markdown to memory/opus_inbox/ — that file
is then fed to Opus 4.7 for the ruling itself (see opus_flow.py).
"""

from __future__ import annotations

from ap_org_bot.agents.base import HeadlessAgent
from ap_org_bot.agents.context import AgentResult


class OpusDesignResearcherAgent(HeadlessAgent):
    name = "opus_design_researcher"
    prompt_name = "opus_design_researcher"
    discord_emoji = "📦"
    header_label = "Opus DD Researcher"

    model = "claude-sonnet-4-6"
    max_turns = 12
    timeout_s = 300
    parses_opus_escalate = False
    requires_authorized_user = False

    async def write_dd_package(
        self, *, dd_id: str, topic: str
    ) -> AgentResult:
        return await self.execute(
            {"dd_id": dd_id, "topic": topic},
            ticket_id=dd_id,
        )
