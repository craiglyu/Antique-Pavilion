"""Opus Design Ruling Flow — multi-step coordination for Opus design escalations.

Two phases (lifted from legacy `_spawn_opus_design_ruling` ap_org_bot.py:563-668):
1. Sonnet writes a Design Decision Package (DD) markdown to memory/opus_inbox/
   — uses OpusDesignResearcherAgent
2. Opus 4.7 reads the DD and emits a ruling — uses raw HeadlessClient because
   the system prompt is loaded from config/opus_design_system_prompt.txt and
   the prompt body IS the DD content.

The ruling is saved to memory/opus_rulings/<date>_<dd_id>.md and posted to
the same Discord channel where the escalation was triggered.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import discord

from ap_org_bot.agents.context import AgentResult
from ap_org_bot.discord_io.split import split_for_discord
from ap_org_bot.infra.budget_gate import BudgetExceeded
from ap_org_bot.infra.claude_cli import HeadlessClient
from ap_org_bot.infra.paths import (
    CONFIG_DIR,
    OPUS_INBOX_DIR,
    OPUS_RULINGS_DIR,
    PROJECT_ROOT,
)

from .opus_researcher import OpusDesignResearcherAgent

log = logging.getLogger("ap_org_bot.agents.opus_flow")

DEFAULT_OPUS_SYSTEM_PROMPT = (
    "You are a luxury design director for a high-end Chinese antique gallery. "
    "Your aesthetic references are Sotheby's Asia, Christie's Hong Kong, "
    "China Guardian (中國嘉德), and the National Palace Museum (故宮). "
    "Make decisive design rulings. Do not hedge. Do not suggest more options "
    "— pick one and explain why."
)
OPUS_MODEL = "claude-opus-4-7"


class OpusEscalationFlow:
    """Coordinates Researcher → Opus ruling → Discord post."""

    def __init__(
        self,
        researcher: OpusDesignResearcherAgent,
        opus_client: HeadlessClient,
    ):
        self.researcher = researcher
        self.opus_client = opus_client

    async def run(
        self,
        topic: str,
        dd_id: str,
        channel: discord.abc.Messageable,
    ) -> None:
        # Phase 1: Sonnet drafts DD package
        OPUS_INBOX_DIR.mkdir(parents=True, exist_ok=True)
        pkg_path = OPUS_INBOX_DIR / f"{dd_id}.md"

        dd_result: AgentResult = await self.researcher.write_dd_package(
            dd_id=dd_id, topic=topic
        )
        if not dd_result.ok or not dd_result.raw_text:
            await channel.send(
                f"❌ `{dd_id}` Sonnet 未產生 DD 包\n"
                f"{dd_result.error or '(no stderr)'}"
            )
            return

        pkg_path.write_text(dd_result.raw_text, encoding="utf-8")
        await channel.send("🎨 設計 DD 包備妥 → 送交 Opus 仲裁，請稍候（約 2–5 分鐘）...")

        # Phase 2: Opus reads DD and rules
        sys_file = CONFIG_DIR / "opus_design_system_prompt.txt"
        opus_system = (
            sys_file.read_text(encoding="utf-8")
            if sys_file.exists() else DEFAULT_OPUS_SYSTEM_PROMPT
        )
        # The DD content IS the prompt body; system prompt becomes the persona context.
        full_prompt = f"{opus_system}\n\n---\n\n{dd_result.raw_text}"

        try:
            opus_res = await self.opus_client.run_with_args(
                full_prompt,
                agent_name="opus_ruling",
                model=OPUS_MODEL,
                allowed_tools="Read,Grep,Glob",
                max_turns=5,
                output_format="json",
                timeout_s=600,
            )
        except BudgetExceeded as e:
            await channel.send(f"❌ `{dd_id}` Opus 配額已達上限：{e.provider} "
                               f"{e.current}/{e.cap}")
            return

        if not opus_res.ok:
            err_msg = ("逾時" if opus_res.timed_out
                       else f"啟動錯誤：{opus_res.stderr[:200]}")
            await channel.send(f"⚠️ `{dd_id}` Opus {err_msg}")
            return

        ruling_text = self._unwrap_json_envelope(opus_res.stdout)

        OPUS_RULINGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d")
        ruling_path = OPUS_RULINGS_DIR / f"{ts}_{dd_id}.md"
        ruling_path.write_text(ruling_text, encoding="utf-8")

        header = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚖️ **Opus 設計仲裁** — `{dd_id}`\n"
            f"⚠️ **Craig 最終確認後才執行**\n"
            f"裁決檔：`{ruling_path.relative_to(PROJECT_ROOT)}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await channel.send(header)
        for chunk in split_for_discord(ruling_text):
            await channel.send(chunk)

    @staticmethod
    def _unwrap_json_envelope(raw: str) -> str:
        """Opus with --output-format=json wraps content in {result: <json string>}."""
        try:
            wrapper = json.loads(raw)
            inner = wrapper.get("result", raw)
            payload = json.loads(inner) if isinstance(inner, str) else inner
            if isinstance(payload, dict) and "content" in payload:
                return str(payload["content"])
            return str(payload)
        except Exception:
            return raw
