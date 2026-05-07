"""APScheduler setup for periodic feedback poll + expiry sweep.

Lifted from legacy ap_org_bot.py:1109-1128.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger("ap_org_bot.handlers.scheduler")
TAIPEI_TZ = pytz.timezone("Asia/Taipei")

POLL_HOUR_MORNING = 11
POLL_HOUR_EVENING = 20
EXPIRY_HOUR = 0
EXPIRY_MINUTE = 30


def build_scheduler(
    *,
    poll_coroutine: Callable[[], Awaitable[None]],
    expiry_coroutine: Callable[[], Awaitable[None]],
    daemon_tick: Optional[Callable[[], Awaitable[None]]] = None,
) -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=TAIPEI_TZ)
    sched.add_job(
        lambda: asyncio.create_task(poll_coroutine()),
        trigger="cron", hour=POLL_HOUR_MORNING, minute=0,
        id="poll_morning", replace_existing=True,
    )
    sched.add_job(
        lambda: asyncio.create_task(poll_coroutine()),
        trigger="cron", hour=POLL_HOUR_EVENING, minute=0,
        id="poll_evening", replace_existing=True,
    )
    sched.add_job(
        lambda: asyncio.create_task(expiry_coroutine()),
        trigger="cron", hour=EXPIRY_HOUR, minute=EXPIRY_MINUTE,
        id="expiry_check", replace_existing=True,
    )
    if daemon_tick is not None:
        sched.add_job(
            lambda: asyncio.create_task(daemon_tick()),
            trigger="cron", hour=POLL_HOUR_MORNING, minute=0,
            id="daemon_morning", replace_existing=True,
        )
        sched.add_job(
            lambda: asyncio.create_task(daemon_tick()),
            trigger="cron", hour=POLL_HOUR_EVENING, minute=0,
            id="daemon_evening", replace_existing=True,
        )
    log.info(
        "[scheduler] poll @ %d:00 / %d:00; expiry @ %02d:%02d; daemon=%s (Asia/Taipei)",
        POLL_HOUR_MORNING, POLL_HOUR_EVENING, EXPIRY_HOUR, EXPIRY_MINUTE,
        "on" if daemon_tick else "off",
    )
    return sched
