"""RealDiscordFetcher — production wrapper for discord.py channel.history().

Implements the DiscordFetcher contract from catchup_protocol so
CatchupCoordinator.replay_feedback_channel() can re-scan #ap-feedback
messages after a bot restart.

Wiring (main.py, after bot.is_ready()):
    from ap_org_bot.handlers.catchup_protocol import CatchupCoordinator
    from ap_org_bot.handlers.discord_fetcher_real import RealDiscordFetcher

    coord = CatchupCoordinator(fetcher=RealDiscordFetcher(bot))

discord.py is imported lazily inside fetch_after() so this module can be
imported in test environments without discord.py installed. Tests should
mock sys.modules['discord'] before calling fetch_after().
"""

from __future__ import annotations

import logging
from typing import Optional

from .catchup_protocol import DiscordFetcher

log = logging.getLogger("ap_org_bot.handlers.discord_fetcher_real")


class RealDiscordFetcher(DiscordFetcher):
    """Wraps discord.py TextChannel.history() to satisfy DiscordFetcher.

    The CatchupCoordinator contract uses str channel/message IDs (Discord
    snowflakes serialise cleanly as JSON strings). Internally this class
    converts to int for the discord.py API.
    """

    def __init__(self, bot) -> None:
        self._bot = bot

    async def fetch_after(
        self,
        channel_id: str,
        after_message_id: Optional[str],
        limit: int = 200,
    ) -> list[dict]:
        """Fetch up to ``limit`` messages posted after ``after_message_id``.

        Returns list[dict] ordered oldest-first with keys:
          - id (str)
          - attachments (list[dict] with id/url/filename — empty if no files)
          - author_id (str)
          - content (str)
          - created_at (ISO timestamp)

        Returns [] if the channel is not in the bot's cache.
        Re-raises any discord API errors after logging them.
        """
        import discord  # noqa: PLC0415 — lazy; requires bot runtime, mocked in tests

        try:
            channel = self._bot.get_channel(int(channel_id))
        except (TypeError, ValueError):
            log.warning("[fetcher] invalid channel_id %r — returning []", channel_id)
            return []

        if channel is None:
            log.warning("[fetcher] channel %s not in bot cache — returning []", channel_id)
            return []

        after_obj = None
        if after_message_id is not None:
            try:
                after_obj = discord.Object(id=int(after_message_id))
            except (TypeError, ValueError):
                log.warning("[fetcher] invalid after_message_id %r — fetching from start",
                            after_message_id)

        messages: list[dict] = []

        try:
            async for msg in channel.history(after=after_obj, limit=limit, oldest_first=True):
                messages.append({
                    "id": str(msg.id),
                    "author_id": str(msg.author.id),
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                    "attachments": [
                        {
                            "id": str(a.id),
                            "url": a.url,
                            "filename": a.filename,
                        }
                        for a in msg.attachments
                    ],
                })
        except Exception as exc:
            log.error("[fetcher] channel %s history error: %s", channel_id, exc)
            raise

        log.debug(
            "[fetcher] channel %s: fetched %d message(s) after id=%s",
            channel_id, len(messages), after_message_id or "beginning",
        )
        return messages
