"""PM Agent — coordinator. Handles `!agenda <topic>` in #ap-pm."""

from __future__ import annotations

from ap_org_bot.agents.base import HeadlessAgent


class PMAgent(HeadlessAgent):
    name = "pm"
    prompt_name = "pm"
    discord_emoji = "🤖"
    header_label = "PM Sonnet"

    max_turns = 8
    timeout_s = 300
    parses_opus_escalate = True
