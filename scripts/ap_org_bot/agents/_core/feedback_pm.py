"""Feedback PM Agent — daily-poll #ap-feedback channel + emit P0-P3 proposals.

Differs from message-triggered agents:
- NOT bound to a Discord channel via registry (no on_message dispatch)
- Reads feedback messages via `feedback_ch.history()`
- Emits structured JSON parsed into proposals, not raw markdown
- Uses claude_cli with stdin (because prompt body is large enough that argv would be unwieldy)
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from ap_org_bot.infra.budget_gate import BudgetExceeded
from ap_org_bot.infra.claude_cli import HeadlessClient
from ap_org_bot.prompts import load_prompt

log = logging.getLogger("ap_org_bot.agents.feedback_pm")


class FeedbackPMAgent:
    """Standalone agent — does not extend HeadlessAgent (different I/O shape)."""

    name = "feedback_pm"
    prompt_name = "feedback_pm"
    model = "claude-sonnet-4-6"

    def __init__(self, claude_client: HeadlessClient):
        self.claude = claude_client

    async def generate_proposals(
        self, feedback_messages: list[dict]
    ) -> list[dict]:
        """Run Feedback PM on the gathered messages. Returns parsed proposal list."""
        if not feedback_messages:
            return []

        try:
            template = load_prompt(self.prompt_name)
        except (KeyError, FileNotFoundError) as e:
            log.error("[feedback_pm] prompt missing: %s", e)
            return []

        feedback_text = "\n".join(
            f"[{m['time']}] {m['author']}: {m['content']}"
            for m in feedback_messages
        )

        full_prompt = (
            f"{template}\n\n"
            "---\n\n"
            "以下是 #ap-feedback 頻道中的最新 UX 反饋意見：\n\n"
            f"{feedback_text}\n\n"
            "請根據以上反饋，分析問題並提出改善提案。只輸出 JSON 陣列。"
        )

        try:
            result = await self.claude.run_with_stdin(
                full_prompt, agent_name=self.name, model=self.model, max_turns=1,
                timeout_s=120,
            )
        except BudgetExceeded as e:
            log.error("[feedback_pm] budget exceeded: %s", e)
            return []

        if not result.ok:
            log.error("[feedback_pm] CLI failed: timed_out=%s stderr=%s",
                      result.timed_out, result.stderr[:200])
            return []

        return self._parse_proposals(result.stdout)

    @staticmethod
    def _parse_proposals(raw: str) -> list[dict]:
        """Parse Claude's JSON output, tolerating markdown code fences."""
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:].strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            log.error("[feedback_pm] JSON decode failed: %s; raw=%s", e, raw[:300])
            return []
        return parsed if isinstance(parsed, list) else []
