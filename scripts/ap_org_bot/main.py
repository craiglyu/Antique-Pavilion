"""ap_org_bot/main.py — entry point for the refactored bot.

Replaces the bottom 200 lines of legacy `scripts/ap_org_bot.py` (run_bot, on_ready,
on_message, scheduler setup). This file is intentionally < 200 lines: every
substantive piece lives in its own module under handlers/ / agents/ / infra/.

Run:
    python -u scripts/ap_org_bot/main.py        # direct
    python -u scripts/ap_org_bot.py             # via thin shim (legacy path)
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

# Allow `python scripts/ap_org_bot/main.py` direct invocation.
_THIS_FILE = Path(__file__).resolve()
_SCRIPTS_DIR = _THIS_FILE.parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# 1. SSL bypass FIRST, before any HTTPS-using import (discord.py, urllib).
from ap_org_bot.infra.ssl_patch import apply_enterprise_ssl_bypass  # noqa: E402

apply_enterprise_ssl_bypass()
warnings.filterwarnings("ignore")

# 2. Now standard imports.
import discord  # noqa: E402
from discord.ext import commands  # noqa: E402

from ap_org_bot.agents._core.feedback_pm import FeedbackPMAgent  # noqa: E402
from ap_org_bot.agents._core.pm import PMAgent  # noqa: E402
from ap_org_bot.agents._domain.ap.auto_dev import AutoDevAgent  # noqa: E402
from ap_org_bot.agents._domain.ap.curator import CuratorAgent  # noqa: E402
from ap_org_bot.agents._domain.ap.designer import DesignerAgent  # noqa: E402
from ap_org_bot.agents._domain.ap.dev import DevAgent  # noqa: E402
from ap_org_bot.agents._domain.ap.gas_dev import GasDevAgent  # noqa: E402
from ap_org_bot.agents._domain.ap.marketing import MarketingAgent  # noqa: E402
from ap_org_bot.agents._domain.ap.opus_flow import OpusEscalationFlow  # noqa: E402
from ap_org_bot.agents._domain.ap.opus_researcher import OpusDesignResearcherAgent  # noqa: E402
from ap_org_bot.agents.registry import AgentRegistry  # noqa: E402
from ap_org_bot.discord_io.views import SingleProposalView  # noqa: E402
from ap_org_bot.handlers.feedback_poll import (  # noqa: E402
    check_expired_proposals,
    run_feedback_poll,
)
from ap_org_bot.handlers.message import MessageDispatcher  # noqa: E402
from ap_org_bot.handlers.proposal_actions import ProposalActionHandler  # noqa: E402
from ap_org_bot.handlers.scheduler import build_scheduler  # noqa: E402
from ap_org_bot.handlers.slash import register_slash_commands  # noqa: E402
from ap_org_bot.infra.claude_cli import HeadlessClient  # noqa: E402
from ap_org_bot.infra.env import env, env_int  # noqa: E402
from ap_org_bot.infra.paths import ensure_runtime_dirs  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("ap_org_bot.main")


def _build_authorization():
    craig_id = env("DISCORD_CRAIG_USER_ID", "566565645483769863")
    partner_id = env("DISCORD_PARTNER_USER_ID", "1495302135112401067")
    allowed = {craig_id, partner_id}

    def is_craig(uid: str) -> bool:
        return bool(craig_id) and uid == craig_id

    def is_authorized(uid: str) -> bool:
        return uid in allowed

    return craig_id, allowed, is_craig, is_authorized


def main() -> None:
    ensure_runtime_dirs()

    token = env("DISCORD_ORG_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_ORG_BOT_TOKEN not set in .env.antique")

    feedback_channel_id = env_int(
        "DISCORD_CHANNEL_AP_FEEDBACK", 1497066777677398026
    )
    dev_channel_id = env_int(
        "DISCORD_CHANNEL_AP_DEV", 1495280247590097059
    )

    craig_id, allowed_ids, is_craig, is_authorized = _build_authorization()

    # ── Discord bot ────────────────────────────────────────────────────
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    tree = bot.tree

    # ── Headless client + agents ──────────────────────────────────────
    claude = HeadlessClient()

    feedback_pm = FeedbackPMAgent(claude)

    # OpusEscalationFlow gives us the on_escalate callback for views.
    opus_researcher = OpusDesignResearcherAgent(
        claude, is_craig=is_craig, is_authorized=is_authorized,
    )
    opus_flow = OpusEscalationFlow(opus_researcher, claude)

    pm = PMAgent(claude, is_craig=is_craig, is_authorized=is_authorized,
                 opus_escalate_handler=opus_flow.run)
    designer = DesignerAgent(claude, is_craig=is_craig, is_authorized=is_authorized,
                             opus_escalate_handler=opus_flow.run)
    dev = DevAgent(claude, is_craig=is_craig, is_authorized=is_authorized,
                   opus_escalate_handler=opus_flow.run)
    marketing = MarketingAgent(claude, is_craig=is_craig, is_authorized=is_authorized)
    auto_dev = AutoDevAgent(claude, is_craig=is_craig, is_authorized=is_authorized)
    gas_dev = GasDevAgent(claude, is_craig=is_craig, is_authorized=is_authorized)

    # Curator (Sprint 1) — rule-based, NOT channel-message-triggered.
    # Entry: scripts/ap_curator_runner.py CLI. Sprint 2 will add cron + Notion query.
    # Not registered with AgentRegistry because dispatcher only routes message-triggered agents.
    curator = CuratorAgent()

    registry = AgentRegistry()
    registry.load_yaml()
    for agent in (pm, designer, dev, marketing, auto_dev, gas_dev,
                  opus_researcher):
        registry.register_instance(agent)

    log.info("[main] active agents: %s", registry.active_agent_keys())
    log.info("[main] bound channels: %d", len(registry.channel_ids()))
    log.info(
        "[main] Curator on (rule-based, threshold=%.2f) — invoke via "
        "scripts/ap_curator_runner.py",
        curator.confidence_threshold,
    )

    # ── Proposal action handler (needs dev_channel after on_ready) ────
    action_holder: dict = {"handler": None}

    def proposal_view_factory(proposal: dict, poll_id: str, idx: int):
        handler: ProposalActionHandler | None = action_holder["handler"]
        if handler is None:
            log.warning("[main] proposal view requested before on_ready completed")
        return SingleProposalView(
            proposal, poll_id, idx,
            is_authorized=is_authorized,
            on_approve=(handler.on_approve if handler else _noop_callback),
            on_veto=(handler.on_veto if handler else _noop_callback),
        )

    # ── Discord events ────────────────────────────────────────────────
    @bot.event
    async def on_ready():
        log.info("ORG Bot ready as %s (ID: %s)", bot.user, bot.user.id)
        try:
            synced = await tree.sync()
            log.info("Synced %d slash commands.", len(synced))
        except Exception as e:
            log.error("Failed to sync slash commands: %s", e)

        dev_channel = bot.get_channel(dev_channel_id)
        if dev_channel is None:
            log.error("[main] Dev channel %s not resolvable", dev_channel_id)
            return
        action_holder["handler"] = ProposalActionHandler(
            dev_channel=dev_channel,
            auto_dev=auto_dev,
            gas_dev=gas_dev,
        )

        async def _poll_once():
            await run_feedback_poll(
                feedback_channel=bot.get_channel(feedback_channel_id),
                feedback_pm=feedback_pm,
                allowed_user_ids=allowed_ids,
                proposal_view_factory=proposal_view_factory,
            )

        if not getattr(on_ready, "_scheduler_started", False):
            sched = build_scheduler(
                poll_coroutine=_poll_once,
                expiry_coroutine=check_expired_proposals,
            )
            sched.start()
            on_ready._scheduler_started = True  # type: ignore[attr-defined]

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        log.error("Command error: %s", error)

    dispatcher = MessageDispatcher(
        registry,
        bot_user_id=0,  # patched below in on_ready hook setup
        feedback_channel_id=feedback_channel_id,
        allowed_feedback_user_ids=allowed_ids,
        craig_user_id=craig_id,
    )

    @bot.event
    async def on_message(message: discord.Message):
        # Patch dispatcher.bot_user_id once we know it (only available after login).
        if dispatcher.bot_user_id == 0 and bot.user is not None:
            dispatcher.bot_user_id = bot.user.id
        await dispatcher.dispatch(message)
        await bot.process_commands(message)

    # ── Slash commands ────────────────────────────────────────────────
    async def _poll_now_callback():
        await run_feedback_poll(
            feedback_channel=bot.get_channel(feedback_channel_id),
            feedback_pm=feedback_pm,
            allowed_user_ids=allowed_ids,
            proposal_view_factory=proposal_view_factory,
        )

    register_slash_commands(
        tree,
        is_craig=is_craig,
        is_authorized=is_authorized,
        poll_now=_poll_now_callback,
    )

    bot.run(token, log_handler=None)


async def _noop_callback(*_args, **_kwargs):
    log.warning("[main] noop callback fired — handler not yet wired")


if __name__ == "__main__":
    main()
