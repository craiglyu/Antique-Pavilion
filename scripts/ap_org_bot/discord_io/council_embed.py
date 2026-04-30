"""Render a Council Topic as a Discord Embed for #council-decisions.

The footer is **load-bearing**: it carries `topic_id: <id>` so the reaction
handler (handlers/reaction.py) can map an incoming reaction back to the topic
state file without needing a separate sidecar database.

Per blueprint v1.1 §3.4 — sign-off should be < 60 seconds. Embed surfaces:
- TL;DR + recommended option (the "what")
- Problem + goal (just enough why for Craig to judge)
- Convened agents + dispatched tasks count (transparency)
- Reaction guidance (✅ approve / ❌ reject)

Bigger debate transcripts live in #council-meetings, not in the embed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord

from ap_org_bot.council.state_machine import State, Topic

# State → Embed colour. Gold for waiting (吉寶軒 brand), green for approved,
# red for rejected, gray for transient.
COUNCIL_EMBED_COLORS: dict[State, int] = {
    State.NEW: 0x6B7280,
    State.STRUCTURED: 0x6B7280,
    State.PHASE1_INDEPENDENT: 0x6B7280,
    State.PHASE2_DEBATE: 0x6B7280,
    State.PHASE3_INTEGRATION: 0x6B7280,
    State.AWAITING_SIGNOFF: 0xB8960C,   # 吉寶軒 gold
    State.SIGNED_OFF: 0x2D7D46,
    State.REJECTED: 0xDC2626,
    State.REOPENED: 0xD97706,
    State.ARCHIVED: 0x9CA3AF,
}

DEFAULT_COLOR = 0xB8960C
FOOTER_TOPIC_PREFIX = "topic_id:"


def _truncate(text: str, limit: int) -> str:
    """Discord embed field value cap is 1024 chars. Truncate with ellipsis."""
    if not text:
        return "—"
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def build_council_embed(topic: Topic) -> discord.Embed:
    """Render a Council topic as a Discord Embed.

    Footer text format: `topic_id: <id> • <state>` — both pieces parseable.
    """
    embed = discord.Embed(
        title=f"📋 {_truncate(topic.raw_input or '(untitled)', 240)}",
        color=COUNCIL_EMBED_COLORS.get(topic.state, DEFAULT_COLOR),
        timestamp=datetime.now(timezone.utc),
    )

    # ── Structured topic (4-segment) ────────────────────────────────
    structured = topic.structured or {}
    if structured.get("problem"):
        embed.add_field(
            name="🔍 問題",
            value=_truncate(structured["problem"], 1024),
            inline=False,
        )
    if structured.get("goal"):
        embed.add_field(
            name="🎯 目標",
            value=_truncate(structured["goal"], 1024),
            inline=False,
        )
    if structured.get("constraints"):
        embed.add_field(
            name="⚖️ 限制",
            value=_truncate(structured["constraints"], 1024),
            inline=False,
        )

    # ── PM proposal ─────────────────────────────────────────────────
    proposal = topic.pilot_proposal or {}
    if proposal.get("tldr"):
        embed.add_field(
            name="💡 TL;DR",
            value=_truncate(proposal["tldr"], 1024),
            inline=False,
        )
    if proposal.get("recommended"):
        recommended = proposal["recommended"]
        reasoning = proposal.get("reasoning", "")
        body = recommended if not reasoning else f"**{recommended}**\n{reasoning}"
        embed.add_field(
            name="✨ 推薦方案",
            value=_truncate(body, 1024),
            inline=False,
        )

    follow_up = proposal.get("follow_up_tasks") or []
    if follow_up:
        items_text = "\n".join(
            f"• `{t.get('task_id', '?')}` ({t.get('agent', '?')}) — {t.get('description', '')[:120]}"
            for t in follow_up[:5]
        )
        if len(follow_up) > 5:
            items_text += f"\n… 共 {len(follow_up)} 項"
        embed.add_field(
            name="📌 後續任務（若通過）",
            value=_truncate(items_text, 1024),
            inline=False,
        )

    # ── Sidebar (convened + state) ──────────────────────────────────
    if topic.convened:
        embed.add_field(
            name="👥 召集",
            value=" / ".join(topic.convened),
            inline=True,
        )
    embed.add_field(
        name="📊 狀態",
        value=f"`{topic.state.value}`",
        inline=True,
    )

    # ── Sign-off guidance (only when relevant) ──────────────────────
    if topic.state == State.AWAITING_SIGNOFF:
        embed.add_field(
            name="🖋️ 簽核",
            value=("**✅ 通過 / ❌ 否決** （Craig 直接 reaction，"
                   "通過後自動 dispatch 後續任務）"),
            inline=False,
        )
    elif topic.state == State.SIGNED_OFF:
        signoff = topic.signoff or {}
        decided_by = signoff.get("decided_by", "?")
        embed.add_field(
            name="✅ 已通過",
            value=f"by {decided_by} @ {signoff.get('decided_at', '?')}",
            inline=False,
        )
        n_tasks = len(topic.dispatched_tasks)
        if n_tasks:
            embed.add_field(
                name="🚀 已派發",
                value=f"{n_tasks} 個 task 寫入 `memory/agent_tasks.yaml`",
                inline=False,
            )
    elif topic.state == State.REJECTED:
        signoff = topic.signoff or {}
        embed.add_field(
            name="❌ 已否決",
            value=f"by {signoff.get('decided_by', '?')} @ {signoff.get('decided_at', '?')}",
            inline=False,
        )

    # ── Footer (REQUIRED — reaction handler depends on this) ────────
    embed.set_footer(text=f"{FOOTER_TOPIC_PREFIX} {topic.topic_id} • {topic.state.value}")

    return embed


def extract_topic_id(message: discord.Message) -> Optional[str]:
    """Inverse of build_council_embed footer: pull topic_id from a posted message.

    Returns the first match across all embeds on the message; None if no match.
    Used by `handlers/reaction.py` to route reactions back to the right topic.
    """
    for embed in message.embeds:
        footer = getattr(embed, "footer", None)
        if footer is None:
            continue
        text = getattr(footer, "text", None) or ""
        idx = text.find(FOOTER_TOPIC_PREFIX)
        if idx == -1:
            continue
        # Slice out everything after the prefix until ' •' or end-of-string.
        rest = text[idx + len(FOOTER_TOPIC_PREFIX):].strip()
        # topic_id can be followed by ' • <state>'
        for sep in (" •", " ·", "•", "·", "  "):
            if sep in rest:
                return rest.split(sep, 1)[0].strip()
        return rest.strip() or None
    return None
