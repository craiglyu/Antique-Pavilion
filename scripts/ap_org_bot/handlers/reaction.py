"""Council sign-off via Discord reactions (blueprint v1.1 §3.4).

Replaces the CLI-only sign-off (`scripts/ap_council_runner.py signoff`) with a
Discord-native UX: Craig reacts ✅ or ❌ on a posted Council embed in
#council-decisions, and the handler:

1. Verifies the reactor is Craig (only Tier 1 sign-off)
2. Maps message → topic_id via embed footer (set by council_embed.py)
3. Loads topic JSON, transitions state machine, persists
4. Dispatches follow-up tasks to memory/agent_tasks.yaml (if approved)
5. Edits the original message's embed to reflect new state

Idempotent: same reaction firing twice (e.g. user adding then removing then
re-adding) is safe — `transition()` no-ops if already in the target state.

Cross-restart: nothing in this handler relies on in-memory state. The bot
restarts, the embed stays, the state file stays, and a fresh reaction still works.

Graceful degradation: if `council_decisions_channel_id == 0`, every reaction is
silently ignored — bot doesn't crash if the channel hasn't been created yet.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

import discord

from ap_org_bot.council.dispatcher import append_dispatched_tasks
from ap_org_bot.council.persistence import load_topic, save_topic
from ap_org_bot.council.state_machine import (
    IllegalTransitionError,
    State,
    Topic,
    transition,
)
from ap_org_bot.discord_io.council_embed import (
    build_council_embed,
    extract_topic_id,
)

log = logging.getLogger("ap_org_bot.handlers.reaction")

# Reaction emoji → target State. 💬 reopens for re-debate (Sprint 2 will wire
# the actual reopening flow; for now we just record but don't transition).
REACTION_TO_TARGET: dict[str, State] = {
    "✅": State.SIGNED_OFF,
    "❌": State.REJECTED,
}

# 💬 isn't in the dispatch map but we still record it as a "soft signal" that
# Craig wants reconsideration — it should not transition the state machine.
COMMENT_REACTION = "💬"


class CouncilReactionHandler:
    """Wire Discord reactions to Council state machine transitions."""

    def __init__(
        self,
        bot: discord.Client,
        *,
        council_decisions_channel_id: int,
        is_craig: Callable[[str], bool],
    ):
        self.bot = bot
        self.channel_id = council_decisions_channel_id
        self.is_craig = is_craig

    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        # ── Filter 1: graceful skip if no channel configured ───────
        if self.channel_id <= 0:
            return
        if payload.channel_id != self.channel_id:
            return

        # ── Filter 2: ignore bot's own reactions (we add ✅/❌ as guidance) ─
        if self.bot.user is not None and payload.user_id == self.bot.user.id:
            return

        # ── Filter 3: Craig only ───────────────────────────────────
        if not self.is_craig(str(payload.user_id)):
            log.debug("[reaction] non-Craig user %s reacted — ignoring", payload.user_id)
            return

        # ── Filter 4: only recognised reactions ────────────────────
        emoji = str(payload.emoji)
        if emoji == COMMENT_REACTION:
            log.info("[reaction] 💬 reaction noted on %s — Sprint 2 will reopen flow",
                     payload.message_id)
            return
        target_state = REACTION_TO_TARGET.get(emoji)
        if target_state is None:
            return  # any other reaction (curiosity, fyi) — no-op

        # ── Step 5: fetch the message + extract topic_id from footer ─
        try:
            channel = self.bot.get_channel(payload.channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            log.warning("[reaction] message %s not found", payload.message_id)
            return
        except Exception as e:
            log.exception("[reaction] cannot fetch message %s: %s",
                          payload.message_id, e)
            return

        topic_id = extract_topic_id(message)
        if not topic_id:
            log.debug("[reaction] message %s has no topic_id footer — ignoring",
                      payload.message_id)
            return

        # ── Step 6: load topic, transition ─────────────────────────
        topic = load_topic(topic_id)
        if topic is None:
            log.warning("[reaction] topic file not found: %s", topic_id)
            return

        if topic.state != State.AWAITING_SIGNOFF:
            log.info(
                "[reaction] topic %s in state %s, not AWAITING_SIGNOFF — ignoring",
                topic_id, topic.state.value,
            )
            return

        try:
            transition(
                topic, target_state,
                actor=f"craig:{payload.user_id}",
                payload={"reaction": emoji, "via": "discord"},
            )
        except IllegalTransitionError as e:
            log.error("[reaction] illegal transition for %s: %s", topic_id, e)
            return

        # ── Step 7: record sign-off metadata ───────────────────────
        topic.signoff = {
            "decision": "approve" if target_state == State.SIGNED_OFF else "reject",
            "decided_by": f"craig:{payload.user_id}",
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "reaction": emoji,
            "discord_message_id": str(payload.message_id),
            "discord_channel_id": str(payload.channel_id),
        }

        # ── Step 8: stage follow-up tasks if approved ──────────────
        if target_state == State.SIGNED_OFF:
            for task in (topic.pilot_proposal or {}).get("follow_up_tasks", []):
                topic.dispatched_tasks.append(task)

        save_topic(topic)

        # ── Step 9: write tasks to agent_tasks.yaml (idempotent) ────
        if target_state == State.SIGNED_OFF:
            try:
                wrote = append_dispatched_tasks(topic)
                if wrote:
                    log.info("[reaction] dispatched %d task(s) for %s → %s",
                             len(topic.dispatched_tasks), topic_id, wrote)
            except Exception:
                log.exception("[reaction] dispatch failed for %s", topic_id)

        # ── Step 10: edit the embed to show the new state ──────────
        try:
            new_embed = build_council_embed(topic)
            await message.edit(embed=new_embed)
            log.info("[reaction] %s → %s (by %s, reaction %s)",
                     topic_id, topic.state.value, payload.user_id, emoji)
        except Exception:
            log.exception("[reaction] failed to edit embed for %s", topic_id)


# ── Helper for slash command (post a topic to #council-decisions) ──

async def post_topic_to_decisions_channel(
    bot: discord.Client,
    *,
    topic: Topic,
    council_decisions_channel_id: int,
) -> Optional[discord.Message]:
    """Post a Topic embed to #council-decisions and seed the ✅/❌ reactions.

    Records the resulting message_id back into topic.signoff for reverse lookup.
    Used by `slash.py:/council-show <topic_id>`.
    """
    if council_decisions_channel_id <= 0:
        log.warning("[reaction] #council-decisions channel not configured — skipping post")
        return None

    channel = bot.get_channel(council_decisions_channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(council_decisions_channel_id)
        except Exception as e:
            log.error("[reaction] cannot resolve #council-decisions: %s", e)
            return None

    embed = build_council_embed(topic)
    try:
        message = await channel.send(embed=embed)
    except Exception as e:
        log.error("[reaction] failed to send embed: %s", e)
        return None

    # Seed the reactions as a usability hint — Craig clicks one of these.
    if topic.state == State.AWAITING_SIGNOFF:
        for emoji in ("✅", "❌"):
            try:
                await message.add_reaction(emoji)
            except Exception as e:
                log.warning("[reaction] failed to seed %s: %s", emoji, e)

    # Record message_id so any future operation can locate this exact embed.
    topic.signoff = {
        **(topic.signoff or {}),
        "discord_message_id": str(message.id),
        "discord_channel_id": str(channel.id),
    }
    save_topic(topic)

    return message
