"""Split text into Discord-friendly chunks.

Discord hard limit is 2000 chars/message. We use 1900 to leave room for
prefixes ("🤖 **PM Sonnet** — `AG-...`\n") that some callers prepend.
"""

from __future__ import annotations

DISCORD_MESSAGE_LIMIT = 2000
DEFAULT_SPLIT_LIMIT = 1900


def split_for_discord(text: str, limit: int = DEFAULT_SPLIT_LIMIT) -> list[str]:
    """Split text on newline boundaries when possible, hard-cut at limit otherwise."""
    if not text:
        return []
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    return chunks
