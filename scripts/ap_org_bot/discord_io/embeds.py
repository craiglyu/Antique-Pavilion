"""Discord Embed builders.

Lifted from legacy `ap_org_bot.py` line 319-357. No behavior change.
"""

from __future__ import annotations

from datetime import datetime, timezone

import discord


PRIORITY_COLORS = {
    "P0": 0xDC2626,   # 紅 — 阻塞
    "P1": 0xD97706,   # 橙 — 重要
    "P2": 0xB8960C,   # 金 — 一般（吉寶軒品牌色）
    "P3": 0x6B7280,   # 灰 — 加分
}

DEFAULT_PRIORITY_COLOR = 0xB8960C


def build_proposal_embed(
    proposal: dict, idx: int, total: int, poll_id: str
) -> discord.Embed:
    priority = proposal.get("priority", "P2")
    embed = discord.Embed(
        title=f"【{priority}】{proposal.get('title', '改善提案')}",
        color=PRIORITY_COLORS.get(priority, DEFAULT_PRIORITY_COLOR),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="🔍 問題", value=proposal.get("problem", "—"), inline=False)
    embed.add_field(name="💡 解決方案", value=proposal.get("solution", "—"), inline=False)
    embed.add_field(name="⏱ 工時", value=proposal.get("effort", "—"), inline=True)
    embed.add_field(name="📂 類別", value=proposal.get("category", "—"), inline=True)
    embed.set_footer(text=f"提案 {idx}/{total} · {poll_id} · 3 天內無回應自動失效")
    return embed


def build_approved_task_embed(proposal: dict, approved_by: str) -> discord.Embed:
    priority = proposal.get("priority", "P2")
    embed = discord.Embed(
        title=f"📌 新任務：{proposal.get('title', '開發任務')}",
        description=f"**來源**：#ap-feedback 批准提案 [{priority}]",
        color=0x2D7D46,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="問題描述", value=proposal.get("problem", "—"), inline=False)
    embed.add_field(name="實作方向", value=proposal.get("solution", "—"), inline=False)
    embed.add_field(name="預估工時", value=proposal.get("effort", "—"), inline=True)
    embed.add_field(name="類別", value=proposal.get("category", "—"), inline=True)
    embed.set_footer(text=f"由 {approved_by} 批准 · 自動建立於 #ap-web-dev")
    return embed
