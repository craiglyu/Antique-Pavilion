"""Slash commands: /veto, /sprint, /poll-now, /usage-status.

Lifted from legacy ap_org_bot.py:1227-1276. Rewired so:
- /usage-status now reads budget_gate's SQLite ledger (not just feedback_state.json)
- /veto writes to memory/VETO_ACTIVE.json (path centralized in infra/paths.py)
- /poll-now and /sprint take injected dependencies (no globals)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Awaitable, Callable

import discord
from discord import app_commands

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
