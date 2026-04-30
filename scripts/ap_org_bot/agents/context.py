"""Dataclasses passed to / returned from Agent execution.

Keeps Agent internals decoupled from discord.py types where possible — only
the .reply / .send call sites need a real Discord object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import discord


@dataclass
class MessageContext:
    """Carry everything an Agent needs from a Discord message."""

    ticket_id: str
    topic: str
    original_message: discord.Message
    channel: discord.abc.Messageable
    prior_message_text: str = ""        # filled when the user replies to a bot message
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """What an Agent's run() produces."""

    ok: bool
    body_text: str                       # the cleaned, Discord-ready body
    raw_text: str = ""                   # untouched stdout (for debugging)
    opus_items: list[str] = field(default_factory=list)
    error: Optional[str] = None
    elapsed_s: Optional[float] = None
