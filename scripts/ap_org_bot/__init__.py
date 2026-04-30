"""
ap_org_bot — Antique Pavilion Multi-Agent ORG Discord Bot

Refactored from single-file ap_org_bot.py (1288 LoC) into modular structure:
- infra/       — env, paths, SSL patch, Claude CLI, budget gate, Notion client (no Discord deps)
- discord_io/  — Discord output helpers (embeds, views, message split)
- prompts/     — Agent prompts as .md (separated from code)
- agents/      — Agent execution units (base + registry + per-agent modules)
- handlers/    — Discord event handlers (message, scheduler, slash commands)
- council/     — Council 9-state machine (3-state pilot for Sprint 1)
- main.py      — Entry point

Design: strangler-fig migration. Legacy `scripts/ap_org_bot.py` is preserved as a
thin shim that delegates to this package, so existing run paths still work.
"""

__version__ = "0.2.0-rc1"
