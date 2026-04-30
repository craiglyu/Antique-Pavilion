"""Marketing Agent — channel #ap-marketing.

Loads copywriting.md (Voice Layers), social-content.md, marketing-psychology.md.
Routes by request scope (single caption vs calendar vs strategy). Writes the
result to Notion Content Calendar DB if NOTION_API_KEY is set.
"""

from __future__ import annotations

import logging

from ap_org_bot.agents.base import HeadlessAgent
from ap_org_bot.agents.context import AgentResult, MessageContext
from ap_org_bot.infra.notion_client import create_content_calendar, is_enabled as notion_enabled

log = logging.getLogger("ap_org_bot.agents.marketing")


class MarketingAgent(HeadlessAgent):
    name = "marketing"
    prompt_name = "marketing"
    discord_emoji = "📣"
    header_label = "Marketing Agent"

    max_turns = 15
    timeout_s = 300
    parses_opus_escalate = False

    async def on_complete(self, ctx: MessageContext, result: AgentResult) -> None:
        if not notion_enabled():
            return
        try:
            create_content_calendar(
                title=f"[{ctx.ticket_id}] {ctx.topic[:60]}",
                content_type="社群貼文",
                status="撰寫中",
                owner="Marketing",
                keywords=ctx.topic[:200],
                notes=result.body_text[:1500],
            )
        except Exception as e:
            log.warning("[marketing] notion content calendar write failed: %s", e)
