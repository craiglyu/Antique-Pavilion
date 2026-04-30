"""HeadlessAgent — base class that replaces 6 duplicated `_spawn_*_headless` functions.

Legacy `ap_org_bot.py` (line 670-1077) had near-identical 70-line bodies for
PM / Designer / Dev / Marketing / Auto-Dev / GAS-Dev / Opus-Researcher. Each
of them did:
  1. Compose a prompt string
  2. Call `_build_claude_cmd` + `asyncio.create_subprocess_exec`
  3. Decode stdout, handle TimeoutError + Exception
  4. Run `_parse_opus_items` (sometimes)
  5. Reply to original_message + chunk-send via `_split_for_discord`
  6. Optionally write to a Notion DB

This base class encapsulates steps 2-5. Subclasses only need to specify
configuration (model, tools, max-turns, prompt name) and override
`build_prompt_args()` (and optionally `on_complete()` for Notion writes).

Adding a new Agent is now ~30 LoC of subclass instead of 70 LoC of copy-paste.

Two entry points:
- `handle_message(ctx)`        — bound to a Discord channel via registry
- `execute(prompt_args, ...)`  — internal/button-triggered (Auto-Dev, GAS-Dev, Opus)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, ClassVar, Optional

from ap_org_bot.discord_io.opus_parse import parse_opus_items
from ap_org_bot.discord_io.split import split_for_discord
from ap_org_bot.discord_io.views import DesignEscalateView
from ap_org_bot.infra.budget_gate import BudgetExceeded
from ap_org_bot.infra.claude_cli import HeadlessClient, HeadlessResult
from ap_org_bot.prompts import load_prompt

from .context import AgentResult, MessageContext

log = logging.getLogger("ap_org_bot.agents.base")

OpusEscalateHandler = Callable[[str, str, Any], Awaitable[None]]


class HeadlessAgent:
    """Base class for agents that delegate to `claude -p` headless calls."""

    # ── Subclass MUST override ──────────────────────────────────────────
    name: ClassVar[str]                       # e.g. "pm", matches prompts key
    prompt_name: ClassVar[str]                # key into prompts/__init__._PROMPT_PATHS
    discord_emoji: ClassVar[str] = "🤖"
    header_label: ClassVar[str] = "Agent"

    # ── Subclass MAY override ───────────────────────────────────────────
    model: ClassVar[str] = "claude-sonnet-4-6"
    allowed_tools: ClassVar[str] = "Read,Grep,Glob"
    max_turns: ClassVar[int] = 8
    timeout_s: ClassVar[int] = 300
    parses_opus_escalate: ClassVar[bool] = False
    requires_authorized_user: ClassVar[bool] = True

    def __init__(
        self,
        claude_client: HeadlessClient,
        *,
        is_craig: Callable[[str], bool],
        is_authorized: Callable[[str], bool],
        opus_escalate_handler: Optional[OpusEscalateHandler] = None,
    ):
        self.claude = claude_client
        self.is_craig = is_craig
        self.is_authorized = is_authorized
        self.opus_escalate_handler = opus_escalate_handler

    # ── Subclass overrides this to produce {placeholder: value} for prompt ──

    def build_prompt_args(self, ctx: MessageContext) -> dict:
        """Return kwargs to pass into `prompt_template.format(**kwargs)`.

        Default impl supplies `ticket_id`, `topic`, and an empty `context_block`.
        Override if prompt has more placeholders.
        """
        return {
            "ticket_id": ctx.ticket_id,
            "topic": ctx.topic,
            "context_block": (
                f"\n上一則回應（供參考）：\n{ctx.prior_message_text}\n"
                if ctx.prior_message_text else ""
            ),
        }

    async def on_complete(self, ctx: MessageContext, result: AgentResult) -> None:
        """Override for Notion writes or other post-success side effects."""

    # ── Public entry points ─────────────────────────────────────────────

    async def handle_message(self, ctx: MessageContext) -> AgentResult:
        """Entry from on_message — replaces legacy `_spawn_*_headless` bodies."""
        if self.requires_authorized_user:
            if not self.is_authorized(str(ctx.original_message.author.id)):
                log.info("[%s] unauthorized user %s ignored",
                         self.name, ctx.original_message.author.id)
                return AgentResult(ok=False, body_text="", error="unauthorized")

        prompt_args = self.build_prompt_args(ctx)
        result = await self.execute(prompt_args, ticket_id=ctx.ticket_id)
        await self._post_to_discord(ctx, result)
        if result.ok:
            try:
                await self.on_complete(ctx, result)
            except Exception:
                log.exception("[%s] on_complete hook crashed", self.name)
        return result

    async def execute(self, prompt_args: dict, *, ticket_id: str) -> AgentResult:
        """Run the agent with explicit prompt args. Used by button-triggered or
        internally-invoked agents (Auto-Dev, GAS-Dev, Opus-Researcher) where
        there is no `MessageContext`.

        Returns a cleaned AgentResult — caller decides how to surface it.
        """
        try:
            template = load_prompt(self.prompt_name)
        except (KeyError, FileNotFoundError) as e:
            log.error("[%s] prompt load failed: %s", self.name, e)
            return AgentResult(ok=False, body_text="", error=f"prompt load failed: {e}")

        try:
            prompt_str = template.format(**prompt_args)
        except KeyError as e:
            log.error("[%s] prompt placeholder missing: %s", self.name, e)
            return AgentResult(
                ok=False, body_text="", error=f"prompt placeholder: {e}"
            )

        start = time.monotonic()
        try:
            res: HeadlessResult = await self.claude.run_with_args(
                prompt_str,
                agent_name=self.name,
                model=self.model,
                allowed_tools=self.allowed_tools,
                max_turns=self.max_turns,
                timeout_s=self.timeout_s,
            )
        except BudgetExceeded as e:
            log.error("[%s] budget exceeded: %s", self.name, e)
            return AgentResult(
                ok=False, body_text="",
                error=f"⚠️ 月配額已達上限：{e.provider} {e.current}/{e.cap}",
            )

        elapsed = time.monotonic() - start

        if res.timed_out:
            return AgentResult(
                ok=False, body_text="",
                error=f"⚠️ {self.header_label} 逾時，票號 `{ticket_id}`",
                elapsed_s=elapsed,
            )
        if not res.ok:
            return AgentResult(
                ok=False, body_text="",
                error=f"❌ {self.header_label} 啟動錯誤：{res.stderr[:200]}",
                raw_text=res.stdout,
                elapsed_s=elapsed,
            )

        body, opus_items = (
            parse_opus_items(res.stdout) if self.parses_opus_escalate else (res.stdout, [])
        )
        if not body:
            body = f"（{self.header_label} 未產生回應）"

        return AgentResult(
            ok=True,
            body_text=body,
            raw_text=res.stdout,
            opus_items=opus_items,
            elapsed_s=elapsed,
        )

    # ── Internals ───────────────────────────────────────────────────────

    async def _post_to_discord(self, ctx: MessageContext, result: AgentResult) -> None:
        header = f"{self.discord_emoji} **{self.header_label}** — `{ctx.ticket_id}`"
        try:
            await ctx.original_message.reply(header, mention_author=False)
        except Exception:
            log.exception("[%s] header reply failed", self.name)
            return

        body = result.body_text if result.ok else (result.error or "（無回應）")
        for chunk in split_for_discord(body):
            try:
                await ctx.channel.send(chunk)
            except Exception:
                log.exception("[%s] body chunk send failed", self.name)
                break

        if result.ok and result.opus_items and self.opus_escalate_handler:
            view = DesignEscalateView(
                items=result.opus_items,
                ticket_id=ctx.ticket_id,
                channel=ctx.channel,
                is_craig=self.is_craig,
                on_escalate=self.opus_escalate_handler,
            )
            try:
                await ctx.channel.send(
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🎨 **需要 Opus 設計仲裁** — 點擊項目送審（Craig 確認後才啟動）：",
                    view=view,
                )
            except Exception:
                log.exception("[%s] opus view send failed", self.name)
