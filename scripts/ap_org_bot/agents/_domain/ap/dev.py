"""Dev Agent — channel #ap-frontend (legacy #ap-web-dev).

Read-only HTML/CSS/JS + GAS analysis. Emits implementation suggestions.
Will be split into Frontend / Backend agents in Phase 1 of blueprint v1.1.
"""

from __future__ import annotations

from ap_org_bot.agents.base import HeadlessAgent


class DevAgent(HeadlessAgent):
    name = "dev"
    prompt_name = "dev"
    discord_emoji = "💻"
    header_label = "Dev Agent"

    max_turns = 12
    timeout_s = 300
    parses_opus_escalate = True
