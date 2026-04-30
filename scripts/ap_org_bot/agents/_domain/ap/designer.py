"""Designer Agent — channel #ap-design (legacy #ap-web-design).

Loads taste-skill.md + impeccable-audit.md + Publish/index.html and emits a DP-XXX
proposal. May escalate to Opus design ruling for high-conflict design decisions.
"""

from __future__ import annotations

from ap_org_bot.agents.base import HeadlessAgent


class DesignerAgent(HeadlessAgent):
    name = "designer"
    prompt_name = "designer"
    discord_emoji = "🎨"
    header_label = "Designer Agent"

    max_turns = 18
    timeout_s = 300
    parses_opus_escalate = True
