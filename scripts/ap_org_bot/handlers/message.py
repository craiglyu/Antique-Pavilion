"""on_message — registry-driven dispatch (replaces legacy if/elif chain).

Legacy ap_org_bot.py:1132-1213 had hardcoded channel_id checks for PM/Designer/
Dev/Marketing. Adding a new agent meant editing on_message AND on_message's reply
section. Now: channel binding lives in config/channels.yaml; this handler just
asks the registry "who handles this channel?" and dispatches.
"""

from __future__ import annotations

import logging
import time

import discord

from ap_org_bot.agents.context import MessageContext
from ap_org_bot.agents.registry import AgentRegistry

log = logging.getLogger("ap_org_bot.handlers.message")


class MessageDispatcher:
    """Single on_message handler. Holds the agent registry + acknowledged-emoji map."""

    EMOJI_FALLBACK = "⚙️"

    def __init__(
        self,
        registry: AgentRegistry,
        *,
        bot_user_id: int,
        feedback_channel_id: int,
        allowed_feedback_user_ids: set[str],
        craig_user_id: str,
    ):
        self.registry = registry
        self.bot_user_id = bot_user_id
        self.feedback_channel_id = feedback_channel_id
        self.allowed_feedback_user_ids = allowed_feedback_user_ids
        self.craig_user_id = craig_user_id

    async def dispatch(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        channel_id = message.channel.id

        # #ap-feedback: anyone allowed leaves a feedback note (gets 📝, no agent fires).
        if channel_id == self.feedback_channel_id:
            if str(message.author.id) in self.allowed_feedback_user_ids:
                log.info("[feedback] note from %s: %.80s",
                         message.author.display_name, message.content)
                try:
                    await message.add_reaction("📝")
                except Exception:
                    pass
            return

        # ORG channels: Craig-only.
        if self.craig_user_id and str(message.author.id) != self.craig_user_id:
            return

        content = message.content.strip()
        if not content:
            return

        ticket_id = f"AG-{time.strftime('%Y%m%d-%H%M%S')}"
        prior_text = ""

        # Reply continuation: thread context.
        if message.reference:
            ref = message.reference.resolved
            if ref is None:
                try:
                    ref = await message.channel.fetch_message(message.reference.message_id)
                except Exception:
                    ref = None
            if isinstance(ref, discord.Message) and ref.author.id == self.bot_user_id:
                ticket_id = f"AG-{time.strftime('%Y%m%d-%H%M%S')}-cont"
                prior_text = ref.content[:800] if ref.content else ""

        agent = self.registry.resolve_agent_for_channel(
            channel_id, message_content=content
        )
        if agent is None:
            return

        # Strip trigger prefix if any (e.g. "!agenda <topic>" → "<topic>").
        binding = self.registry.channel_binding(channel_id)
        topic = content
        if binding and binding.trigger_prefix:
            if topic.lower().startswith(binding.trigger_prefix.lower()):
                topic = topic[len(binding.trigger_prefix):].strip()
            if not topic:
                await message.reply(f"使用方式：`{binding.trigger_prefix} <議題>`")
                return

        try:
            await message.add_reaction(getattr(agent, "discord_emoji", self.EMOJI_FALLBACK))
        except Exception:
            pass

        ack = (
            f"{getattr(agent, 'discord_emoji', '🤖')} `{ticket_id}` — "
            f"{getattr(agent, 'header_label', 'Agent')} 收到，分析中..."
        )
        try:
            await message.reply(ack, mention_author=False)
        except Exception:
            log.exception("[dispatcher] ack reply failed for %s", agent.name)

        ctx = MessageContext(
            ticket_id=ticket_id,
            topic=topic,
            original_message=message,
            channel=message.channel,
            prior_message_text=prior_text,
        )
        try:
            await agent.handle_message(ctx)
        except Exception:
            log.exception("[dispatcher] agent %s crashed", agent.name)
