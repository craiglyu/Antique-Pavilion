"""agents/ — Agent execution units.

Layer convention mirrors prompts/:
- _core/      : framework-shared agents (PM, Feedback PM)
- _domain/ap/ : Antique Pavilion-specific agents

Each Agent subclasses HeadlessAgent (base.py) and declares:
- prompt_name (key into prompts/__init__.py:_PROMPT_PATHS)
- model, max_turns, allowed_tools, timeout_s
- discord_emoji, header_label
- (optional) post-processing: parses_opus_escalate, on_complete_notion_hook

The Discord message router (handlers/message.py) consults `registry.resolve_agent_for_channel()`
to dispatch — adding a new Agent is now a yaml edit, not a code change in 4 places.
"""
