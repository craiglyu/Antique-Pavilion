"""Feedback PM poll & expiry handlers.

Lifted from legacy ap_org_bot.py:440-525 (run_feedback_poll, check_expired_proposals).
Now driven by FeedbackPMAgent (no inline prompt) and posts via SingleProposalView
with injected callbacks (no global ALLOWED_USER_IDS reach).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Optional

import discord
import pytz

from ap_org_bot.agents._core.feedback_pm import FeedbackPMAgent
from ap_org_bot.discord_io.embeds import build_proposal_embed
from ap_org_bot.discord_io.views import SingleProposalView
from ap_org_bot.infra.notion_client import create_topic, is_enabled as notion_enabled

from .feedback_state import (
    load_state,
    reset_monthly_counter_if_needed,
    save_state,
)

log = logging.getLogger("ap_org_bot.handlers.feedback_poll")
TAIPEI_TZ = pytz.timezone("Asia/Taipei")
PROPOSAL_EXPIRY_DAYS = 3

ProposalApproveCb = Callable[[discord.Interaction, dict, str, int], Awaitable[None]]
ProposalVetoCb = Callable[[discord.Interaction, dict, str, int], Awaitable[None]]


# ── Topics DB sync (preserves legacy behaviour from ap_org_bot.py:278-305) ──

def _sync_proposals_to_notion_topics(proposals: list[dict]) -> None:
    if not notion_enabled():
        return
    category_map = {
        "視覺設計": "視覺",
        "互動體驗": "視覺",
        "效能":     "維運",
        "文案":     "內容策略",
        "功能":     "網站架構",
    }
    prio_map = {"P0": "高", "P1": "高", "P2": "中", "P3": "低"}
    for p in proposals:
        try:
            create_topic(
                title=f"[{p.get('priority', 'P2')}] {p.get('title', '')}"[:200],
                type_=category_map.get(p.get("category", ""), "其他"),
                priority=prio_map.get(p.get("priority", ""), "中"),
                source="Feedback PM",
                description=(
                    f"問題：{p.get('problem', '')}\n\n"
                    f"方案：{p.get('solution', '')}\n\n"
                    f"工時：{p.get('effort', '')}"
                )[:1800],
            )
        except Exception as e:
            log.warning("[notion] topic write failed: %s", e)


# ── Main poll routine ───────────────────────────────────────────────

async def run_feedback_poll(
    *,
    feedback_channel: Optional[discord.TextChannel],
    feedback_pm: FeedbackPMAgent,
    allowed_user_ids: set[str],
    proposal_view_factory: Callable[[dict, str, int], SingleProposalView],
) -> None:
    """Pull last unread #ap-feedback messages, run Feedback PM, post embeds."""
    if feedback_channel is None:
        log.error("[poll] feedback channel not resolved (missing or wrong ID)")
        return

    state = load_state()
    last_id_str = state.get("last_feedback_message_id")

    messages: list[dict] = []
    async for msg in feedback_channel.history(limit=100, oldest_first=True):
        if msg.author.bot:
            continue
        if str(msg.author.id) not in allowed_user_ids:
            continue
        if last_id_str and msg.id <= int(last_id_str):
            continue
        messages.append({
            "time": msg.created_at.astimezone(TAIPEI_TZ).strftime("%m/%d %H:%M"),
            "author": msg.author.display_name,
            "content": msg.content[:500],
        })

    if not messages:
        log.info("[poll] no new feedback messages, skipping")
        return

    async for msg in feedback_channel.history(limit=1):
        state["last_feedback_message_id"] = str(msg.id)

    log.info("[poll] gathered %d messages, calling Feedback PM...", len(messages))
    proposals = await feedback_pm.generate_proposals(messages)

    state = reset_monthly_counter_if_needed(state)
    state["monthly_calls"] = state.get("monthly_calls", 0) + 1
    save_state(state)

    if not proposals:
        log.warning("[poll] Feedback PM produced no proposals")
        return

    _sync_proposals_to_notion_topics(proposals)

    poll_id = f"poll-{datetime.now(TAIPEI_TZ).strftime('%Y%m%d-%H%M')}"
    state.setdefault("proposals", {})[poll_id] = {
        "created_at": datetime.now(TAIPEI_TZ).isoformat(),
        "items": [{"status": "pending", **p} for p in proposals],
    }
    save_state(state)

    now_str = datetime.now(TAIPEI_TZ).strftime("%m/%d %H:%M")
    header = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 **PM Claude — UX 改善提案** `{poll_id}`\n"
        f"根據 **{len(messages)}** 則反饋分析 · {now_str}（台北時間）\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await feedback_channel.send(header)

    for i, proposal in enumerate(proposals):
        embed = build_proposal_embed(proposal, i + 1, len(proposals), poll_id)
        view = proposal_view_factory(proposal, poll_id, i)
        await feedback_channel.send(embed=embed, view=view)

    log.info("[poll] posted %d proposals (poll_id=%s)", len(proposals), poll_id)


async def check_expired_proposals() -> None:
    """Mark proposals older than 3 days as expired. Cron at 00:30 Asia/Taipei."""
    state = load_state()
    now = datetime.now(TAIPEI_TZ)
    changed = False

    for poll_id, poll_data in state.get("proposals", {}).items():
        try:
            created_at = datetime.fromisoformat(poll_data.get("created_at", ""))
            if created_at.tzinfo is None:
                created_at = TAIPEI_TZ.localize(created_at)
        except (ValueError, TypeError):
            continue

        if (now - created_at) > timedelta(days=PROPOSAL_EXPIRY_DAYS):
            for item in poll_data.get("items", []):
                if item.get("status") == "pending":
                    item["status"] = "expired"
                    changed = True

    if changed:
        save_state(state)
        log.info("[expiry] marked stale proposals as expired")
