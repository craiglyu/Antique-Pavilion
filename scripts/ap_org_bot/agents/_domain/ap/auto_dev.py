"""Auto-Dev Agent — button-triggered autonomous frontend execution.

Triggered when Craig approves a P0/P1/P2 visual-design or interaction proposal
in #ap-feedback. Uses Edit/Write/Bash to actually modify index.html + Publish/
+ git push, NOT just suggest changes.

Different from message-triggered agents:
- No `MessageContext` — input comes from a proposal dict (title/problem/solution).
- Caller posts the headers + result chunks to channel itself (this class just executes).
"""

from __future__ import annotations

import logging
from typing import Optional

from ap_org_bot.agents.base import HeadlessAgent
from ap_org_bot.agents.context import AgentResult
from ap_org_bot.infra.notion_client import create_decision, is_enabled as notion_enabled

log = logging.getLogger("ap_org_bot.agents.auto_dev")


class AutoDevAgent(HeadlessAgent):
    name = "auto_dev"
    prompt_name = "auto_dev"
    discord_emoji = "⚙️"
    header_label = "Auto-Dev Agent"

    allowed_tools = "Read,Edit,Write,Glob,Grep,Bash"
    max_turns = 20
    timeout_s = 600
    parses_opus_escalate = False
    requires_authorized_user = False  # button trigger already checks authorization

    async def run_for_proposal(
        self, proposal: dict, *, ticket: str
    ) -> AgentResult:
        prompt_args = {
            "ticket": ticket,
            "title": proposal.get("title", "未命名任務"),
            "problem": proposal.get("problem", ""),
            "solution": proposal.get("solution", ""),
        }
        result = await self.execute(prompt_args, ticket_id=ticket)
        if notion_enabled():
            try:
                success = "✅" in (result.raw_text or "") or "自動執行完成" in (result.raw_text or "")
                create_decision(
                    title=f"[{ticket}] {prompt_args['title']}",
                    signoff_status="通過" if success else "重議",
                    tldr=prompt_args["title"][:300],
                    recommended=prompt_args["solution"][:1500],
                    risks=prompt_args["problem"][:1500],
                    follow_up=(result.raw_text or result.error or "")[:1500],
                )
            except Exception as e:
                log.warning("[auto_dev] notion decision write failed: %s", e)
        return result
