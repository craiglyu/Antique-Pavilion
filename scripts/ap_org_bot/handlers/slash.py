"""Slash commands: /veto, /sprint, /poll-now, /usage-status, /council-show, /council-list.

Lifted from legacy ap_org_bot.py:1227-1276 + Sprint 1 additions:
- /usage-status now reads budget_gate's SQLite ledger
- /veto writes to memory/VETO_ACTIVE.json
- /council-show <topic_id> posts a Council embed to #council-decisions for sign-off
- /council-list shows currently-active Council topics
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Awaitable, Callable, Optional

import discord
from discord import app_commands

from ap_org_bot.council.persistence import list_active_topics, load_topic
from ap_org_bot.handlers.reaction import post_topic_to_decisions_channel
from ap_org_bot.infra.budget_gate import usage_summary
from ap_org_bot.infra.paths import MEMORY_DIR, VETO_FILE

log = logging.getLogger("ap_org_bot.handlers.slash")

PollNowCb = Callable[[], Awaitable[None]]


def register_slash_commands(
    tree: app_commands.CommandTree,
    *,
    is_craig: Callable[[str], bool],
    is_authorized: Callable[[str], bool],
    poll_now: PollNowCb,
    bot: Optional[discord.Client] = None,
    council_decisions_channel_id: int = 0,
) -> None:
    @tree.command(name="veto", description="緊急凍結：停止所有 in-flight agent 調用。")
    @app_commands.describe(reason="凍結原因")
    async def veto_cmd(interaction: discord.Interaction, reason: str):
        if not is_craig(str(interaction.user.id)):
            await interaction.response.send_message(
                "只有 Craig 可以發出 VETO。", ephemeral=True
            )
            return
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        VETO_FILE.write_text(
            json.dumps(
                {
                    "active": True,
                    "reason": reason,
                    "issued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        await interaction.response.send_message(
            f"🛑 **VETO ACTIVE**\n原因：_{reason}_"
        )

    @tree.command(name="sprint", description="查看當前 Sprint 任務狀態。")
    async def sprint_cmd(interaction: discord.Interaction):
        tasks_file = MEMORY_DIR / "agent_tasks.yaml"
        if not tasks_file.exists():
            await interaction.response.send_message(
                "❌ `memory/agent_tasks.yaml` 不存在。", ephemeral=True
            )
            return
        content = tasks_file.read_text(encoding="utf-8")[:1800]
        await interaction.response.send_message(
            f"📋 **Sprint 狀態**\n```yaml\n{content}\n```"
        )

    @tree.command(name="poll-now", description="立即觸發 #ap-feedback 反饋彙整（Craig 專用）")
    async def poll_now_cmd(interaction: discord.Interaction):
        if not is_authorized(str(interaction.user.id)):
            await interaction.response.send_message(
                "只有授權用戶可以執行。", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "⚙️ 手動觸發 Feedback Poll，請稍候...", ephemeral=True
        )
        asyncio.create_task(poll_now())

    @tree.command(name="usage-status", description="查看本月 API 配額使用量")
    async def usage_status_cmd(interaction: discord.Interaction):
        if not is_authorized(str(interaction.user.id)):
            await interaction.response.send_message(
                "只有授權用戶可以查看。", ephemeral=True
            )
            return
        summary = usage_summary()
        lines = ["📊 **本月 API 使用量**（budget_gate.py 累計）"]
        for provider, info in summary.items():
            pct = info["pct"]
            bar = "🟩" if pct < 50 else ("🟨" if pct < 80 else "🟥")
            lines.append(
                f"{bar} `{provider:>11}` — {info['used']} / {info['cap']} ({pct}%)"
            )
        await interaction.response.send_message(
            "\n".join(lines), ephemeral=True
        )

    @tree.command(
        name="council-show",
        description="把 Council 議題 post 到 #council-decisions 等簽核 (Craig only)",
    )
    @app_commands.describe(topic_id="議題 ID（如 ap-2026-04-30-085208-001）")
    async def council_show_cmd(interaction: discord.Interaction, topic_id: str):
        if not is_craig(str(interaction.user.id)):
            await interaction.response.send_message(
                "只有 Craig 可以 post 議題到 #council-decisions。", ephemeral=True
            )
            return
        topic = load_topic(topic_id)
        if topic is None:
            await interaction.response.send_message(
                f"❌ 找不到議題 `{topic_id}`", ephemeral=True
            )
            return
        if council_decisions_channel_id <= 0:
            await interaction.response.send_message(
                "❌ #council-decisions 頻道未設定（`config/channels.yaml` id=0）。\n"
                "請先在 Discord 建頻道並更新 channels.yaml + .env.antique。",
                ephemeral=True,
            )
            return
        if bot is None:
            await interaction.response.send_message(
                "❌ bot reference 未注入 — 請檢查 main.py 是否傳了 bot 給 register_slash_commands",
                ephemeral=True,
            )
            return

        message = await post_topic_to_decisions_channel(
            bot,
            topic=topic,
            council_decisions_channel_id=council_decisions_channel_id,
        )
        if message is None:
            await interaction.response.send_message(
                "❌ post 失敗 — 看 bot terminal log", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"📌 已 post `{topic_id}` ({topic.state.value}) 到 #council-decisions\n"
            f"{message.jump_url}",
            ephemeral=True,
        )

    @tree.command(name="council-list", description="顯示當前 active Council 議題")
    async def council_list_cmd(interaction: discord.Interaction):
        if not is_authorized(str(interaction.user.id)):
            await interaction.response.send_message(
                "只有授權用戶可以查看。", ephemeral=True
            )
            return
        topics = list_active_topics()
        if not topics:
            await interaction.response.send_message(
                "📋 **無 active 議題**", ephemeral=True
            )
            return

        lines = [f"📋 **{len(topics)} 個 active Council 議題**\n"]
        for t in topics[:10]:  # cap at 10 to fit Discord 2000-char limit
            preview = (t.raw_input or "(untitled)")[:60]
            lines.append(
                f"• `{t.topic_id}` — `{t.state.value}` — {preview}"
            )
        if len(topics) > 10:
            lines.append(f"_(... 共 {len(topics)} 個，顯示前 10 個)_")
        await interaction.response.send_message(
            "\n".join(lines), ephemeral=True
        )
