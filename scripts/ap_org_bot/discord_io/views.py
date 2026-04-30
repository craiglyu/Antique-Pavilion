"""Discord Button Views — interactive proposal approval & Opus design escalation.

Lifted from legacy `ap_org_bot.py` line 359-436 (SingleProposalView) and
539-561 (DesignEscalateView). Behavioural changes vs legacy:
- Both views now take dependency callbacks instead of reaching into module globals.
  This means the views are testable in isolation without spinning up the bot.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Awaitable, Callable, Optional

import discord
import pytz
from discord import ui

log = logging.getLogger("ap_org_bot.views")
TAIPEI_TZ = pytz.timezone("Asia/Taipei")

# Type aliases for the dependency callbacks we inject.
ProposalApproveCb = Callable[[discord.Interaction, dict, str, int], Awaitable[None]]
ProposalVetoCb = Callable[[discord.Interaction, dict, str, int], Awaitable[None]]
OpusEscalateCb = Callable[[str, str, discord.abc.Messageable], Awaitable[None]]


class SingleProposalView(ui.View):
    """One Approve/Veto button pair per proposal.

    Authorization is delegated to the caller via `is_authorized`. This keeps the
    list of allowed user IDs out of this module.
    """

    def __init__(
        self,
        proposal: dict,
        poll_id: str,
        proposal_idx: int,
        *,
        is_authorized: Callable[[str], bool],
        on_approve: ProposalApproveCb,
        on_veto: ProposalVetoCb,
        timeout_seconds: int = 259200,  # 3 days
    ):
        super().__init__(timeout=timeout_seconds)
        self.proposal = proposal
        self.poll_id = poll_id
        self.proposal_idx = proposal_idx
        self._is_authorized = is_authorized
        self._on_approve = on_approve
        self._on_veto = on_veto
        self.decided = False

    async def _handle(self, interaction: discord.Interaction, approved: bool) -> None:
        if not self._is_authorized(str(interaction.user.id)):
            await interaction.response.send_message(
                "只有授權用戶可以批准或否決。", ephemeral=True
            )
            return
        if self.decided:
            await interaction.response.send_message("此提案已處理。", ephemeral=True)
            return

        self.decided = True
        for child in self.children:
            child.disabled = True  # type: ignore[union-attr]
        await interaction.response.edit_message(view=self)

        try:
            if approved:
                await self._on_approve(interaction, self.proposal, self.poll_id, self.proposal_idx)
            else:
                await self._on_veto(interaction, self.proposal, self.poll_id, self.proposal_idx)
        except Exception:
            log.exception("[view] handler crashed for poll %s idx %d",
                          self.poll_id, self.proposal_idx)

    @ui.button(label="✅ 批准執行", style=discord.ButtonStyle.success)
    async def approve_btn(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await self._handle(interaction, True)

    @ui.button(label="❌ 否決", style=discord.ButtonStyle.danger)
    async def veto_btn(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await self._handle(interaction, False)


class DesignEscalateView(ui.View):
    """Buttons for Craig to confirm an Opus design ruling escalation."""

    def __init__(
        self,
        items: list[str],
        ticket_id: str,
        channel: discord.abc.Messageable,
        *,
        is_craig: Callable[[str], bool],
        on_escalate: OpusEscalateCb,
        timeout_seconds: int = 7200,
    ):
        super().__init__(timeout=timeout_seconds)
        self.channel = channel
        self.ticket_id = ticket_id
        self._is_craig = is_craig
        self._on_escalate = on_escalate
        for item in items:
            btn = ui.Button(label=f"🎨 {item[:45]}", style=discord.ButtonStyle.primary)
            btn.callback = self._make_callback(item)
            self.add_item(btn)

    def _make_callback(self, item: str):
        async def callback(interaction: discord.Interaction) -> None:
            if not self._is_craig(str(interaction.user.id)):
                await interaction.response.send_message(
                    "只有 Craig 可以送審設計決策。", ephemeral=True
                )
                return
            for child in self.children:
                child.disabled = True  # type: ignore[union-attr]
            await interaction.response.edit_message(view=self)
            dd_id = f"DD-{time.strftime('%Y%m%d-%H%M%S')}"
            await interaction.followup.send(
                f"📦 `{dd_id}` — **{item}**\n_Sonnet 正在起草設計仲裁包..._"
            )
            try:
                await self._on_escalate(item, dd_id, self.channel)
            except Exception:
                log.exception("[view] opus escalate crashed for %s", dd_id)

        return callback
