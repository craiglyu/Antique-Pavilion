"""Approve/Veto proposal handlers — what fires when Craig clicks the button.

Lifted from legacy SingleProposalView._handle (ap_org_bot.py:371-436).
Routes approved proposals to Auto-Dev (frontend) or GAS-Dev (backend).
"""

from __future__ import annotations

import logging
from datetime import datetime

import discord
import pytz

from ap_org_bot.agents._domain.ap.auto_dev import AutoDevAgent
from ap_org_bot.agents._domain.ap.gas_dev import GasDevAgent
from ap_org_bot.discord_io.embeds import build_approved_task_embed
from ap_org_bot.discord_io.split import split_for_discord

from .feedback_state import load_state, save_state

log = logging.getLogger("ap_org_bot.handlers.proposal_actions")
TAIPEI_TZ = pytz.timezone("Asia/Taipei")

# Mirrors legacy `FRONTEND_CATEGORIES` (ap_org_bot.py:913).
FRONTEND_CATEGORIES = {"視覺設計", "互動體驗"}


def _record_decision(
    poll_id: str, idx: int, status: str, decided_by: str
) -> None:
    state = load_state()
    polls = state.get("proposals", {})
    if poll_id not in polls:
        return
    items = polls[poll_id].get("items", [])
    if idx >= len(items):
        return
    items[idx]["status"] = status
    items[idx]["decided_by"] = decided_by
    items[idx]["decided_at"] = datetime.now(TAIPEI_TZ).isoformat()
    save_state(state)


class ProposalActionHandler:
    """Wires Approve/Veto buttons to Auto-Dev / GAS-Dev agents.

    The view uses these as callbacks, decoupling view from agent registry.
    """

    def __init__(
        self,
        *,
        dev_channel: discord.abc.Messageable,
        auto_dev: AutoDevAgent,
        gas_dev: GasDevAgent,
    ):
        self.dev_channel = dev_channel
        self.auto_dev = auto_dev
        self.gas_dev = gas_dev

    async def on_approve(
        self,
        interaction: discord.Interaction,
        proposal: dict,
        poll_id: str,
        proposal_idx: int,
    ) -> None:
        task_embed = build_approved_task_embed(
            proposal, interaction.user.display_name
        )
        await self.dev_channel.send(embed=task_embed)

        category = proposal.get("category", "")
        priority = proposal.get("priority", "P2")
        if category in FRONTEND_CATEGORIES:
            ticket = f"AUTO-{poll_id}-{priority}"
            await self.dev_channel.send(
                f"⚙️ **自動執行中** `{ticket}`\n"
                f"**{proposal.get('title', '未命名任務')}**\n"
                f"Dev Agent 正在讀取代碼並實作，約 2–3 分鐘..."
            )
            result = await self.auto_dev.run_for_proposal(proposal, ticket=ticket)
            await self._post_agent_result(ticket, result.body_text or result.error or "")
        else:
            ticket = f"GAS-{poll_id}-{priority}"
            await self.dev_channel.send(
                f"⚙️ **GAS 代碼生成中** `{ticket}`\n"
                f"**{proposal.get('title', '未命名任務')}**\n"
                f"Dev Agent 正在分析 GAS 腳本，約 1–2 分鐘..."
            )
            result = await self.gas_dev.run_for_proposal(proposal, ticket=ticket)
            await self.dev_channel.send(
                f"📋 **GAS 實作方案** — `{ticket}`\n"
                f"⚠️ 以下代碼請手動貼入 Google Apps Script 並重新部署 Web App"
            )
            for chunk in split_for_discord(result.body_text or result.error or ""):
                await self.dev_channel.send(chunk)

        await interaction.followup.send(
            f"✅ 批准 [{priority}] **{proposal.get('title')}**\n"
            f"任務已建立至 #ap-frontend，Dev Agent 自動執行中 ⚙️",
            ephemeral=True,
        )
        _record_decision(poll_id, proposal_idx, "approved", str(interaction.user))
        log.info("[proposal] approved: %s", proposal.get("title"))

    async def on_veto(
        self,
        interaction: discord.Interaction,
        proposal: dict,
        poll_id: str,
        proposal_idx: int,
    ) -> None:
        await interaction.followup.send(
            f"❌ 已否決 [{proposal.get('priority')}] **{proposal.get('title')}**",
            ephemeral=True,
        )
        _record_decision(poll_id, proposal_idx, "vetoed", str(interaction.user))
        log.info("[proposal] vetoed: %s", proposal.get("title"))

    async def _post_agent_result(self, ticket: str, body: str) -> None:
        await self.dev_channel.send(f"📋 **執行報告** — `{ticket}`")
        for chunk in split_for_discord(body or "（無回應）"):
            await self.dev_channel.send(chunk)
