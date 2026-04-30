"""Parse `OPUS_ESCALATE:` markers out of agent responses.

Several agents (PM, Designer, Dev) end their output with:
    OPUS_ESCALATE:
    - Item 1
    - Item 2

This is the trigger for Craig-confirmed Opus design ruling escalation. We split
the marker section out so the clean response can be posted to Discord, and
the items can drive a button view.
"""

from __future__ import annotations

OPUS_MARKER = "OPUS_ESCALATE:"
MAX_OPUS_ITEMS = 3


def parse_opus_items(text: str) -> tuple[str, list[str]]:
    """Return (clean_text, opus_items). opus_items capped at MAX_OPUS_ITEMS."""
    if OPUS_MARKER not in text:
        return text, []
    head, _, tail = text.partition(OPUS_MARKER)
    clean = head.strip()
    items = [
        line.strip().lstrip("-•·").strip()
        for line in tail.strip().splitlines()
        if line.strip()
    ]
    return clean, items[:MAX_OPUS_ITEMS]
