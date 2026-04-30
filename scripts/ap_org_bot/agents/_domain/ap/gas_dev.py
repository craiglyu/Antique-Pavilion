"""GAS Dev Agent — button-triggered code generation for Google Apps Script.

For non-frontend proposals (功能 / 效能), generates GAS code that Craig manually
pastes into Google Apps Script editor and re-deploys.
"""

from __future__ import annotations

from ap_org_bot.agents.base import HeadlessAgent
from ap_org_bot.agents.context import AgentResult


class GasDevAgent(HeadlessAgent):
    name = "gas_dev"
    prompt_name = "gas_dev"
    discord_emoji = "📋"
    header_label = "GAS Dev Agent"

    max_turns = 8
    timeout_s = 300
    parses_opus_escalate = False
    requires_authorized_user = False

    async def run_for_proposal(
        self, proposal: dict, *, ticket: str
    ) -> AgentResult:
        prompt_args = {
            "ticket": ticket,
            "title": proposal.get("title", "未命名任務"),
            "problem": proposal.get("problem", ""),
            "solution": proposal.get("solution", ""),
        }
        return await self.execute(prompt_args, ticket_id=ticket)
