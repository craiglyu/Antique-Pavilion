"""Integration tests: CouncilDaemon + RealAgentInvoker + scheduler wiring (Sprint 4).

Avoids pytest-asyncio by wrapping async calls in asyncio.run() — consistent
with the existing test_council_daemon.py pattern. No live HeadlessClient
subprocess is called in any test.

apscheduler is a production-only dependency (the bot machine has it; CI
test environments don't need it). Scheduler-touching tests skip cleanly
when apscheduler is unavailable.
"""

from __future__ import annotations

import asyncio
import importlib.util

import pytest

from ap_org_bot.council.agent_invoker_real import RealAgentInvoker
from ap_org_bot.council.daemon import AgentInvoker, CouncilDaemon, DaemonRun
from ap_org_bot.infra.claude_cli import HeadlessClient


# ── Shared helpers ────────────────────────────────────────────────────


class _StubInvoker(AgentInvoker):
    """Test stub — never calls the claude CLI."""

    async def invoke(self, agent_name: str, prompt: str) -> str:
        return ""


_HAS_APSCHEDULER = importlib.util.find_spec("apscheduler") is not None


# ── CouncilDaemon + RealAgentInvoker ──────────────────────────────────


def test_daemon_tick_with_no_active_topics_succeeds(isolated_memory_dir):
    """poll_and_advance returns a DaemonRun with topics_polled=0 when state dir empty."""
    daemon = CouncilDaemon(invoker=_StubInvoker())
    run = asyncio.run(daemon.poll_and_advance())
    assert isinstance(run, DaemonRun)
    assert run.topics_polled == 0
    assert run.topics_advanced == 0
    assert run.errors == []


def test_real_agent_invoker_constructs_correctly_without_calling():
    """RealAgentInvoker stores the HeadlessClient reference; no I/O on construct."""
    claude = HeadlessClient()
    invoker = RealAgentInvoker(claude)
    assert invoker.claude is claude


def test_real_agent_invoker_satisfies_agent_invoker_contract():
    """RealAgentInvoker is a structural AgentInvoker (inherits from base class)."""
    claude = HeadlessClient()
    invoker = RealAgentInvoker(claude)
    assert isinstance(invoker, AgentInvoker)


# ── Scheduler wiring (skipped if apscheduler not installed) ──────────


@pytest.mark.skipif(not _HAS_APSCHEDULER, reason="apscheduler not installed in this env")
def test_scheduler_invokes_daemon_at_correct_hours():
    """Daemon cron jobs are registered at POLL_HOUR_MORNING and POLL_HOUR_EVENING."""
    # Lazy import — only when we actually reach this test, so collection
    # succeeds even when apscheduler isn't on the path.
    from ap_org_bot.handlers.scheduler import (
        POLL_HOUR_EVENING,
        POLL_HOUR_MORNING,
        build_scheduler,
    )

    async def noop() -> None:
        pass

    sched = build_scheduler(
        poll_coroutine=noop,
        expiry_coroutine=noop,
        daemon_tick=noop,
    )

    morning = sched.get_job("daemon_morning")
    evening = sched.get_job("daemon_evening")
    assert morning is not None, "daemon_morning job missing from scheduler"
    assert evening is not None, "daemon_evening job missing from scheduler"

    def _cron_hour(job) -> int:
        for field in job.trigger.fields:
            if field.name == "hour":
                return field.expressions[0].first
        raise AssertionError(f"no hour field in trigger for {job.id}")

    assert _cron_hour(morning) == POLL_HOUR_MORNING
    assert _cron_hour(evening) == POLL_HOUR_EVENING


@pytest.mark.skipif(not _HAS_APSCHEDULER, reason="apscheduler not installed in this env")
def test_scheduler_omits_daemon_jobs_when_daemon_tick_is_none():
    """When daemon_tick=None, no daemon_* jobs are created (backward compatible)."""
    from ap_org_bot.handlers.scheduler import build_scheduler

    async def noop() -> None:
        pass

    sched = build_scheduler(poll_coroutine=noop, expiry_coroutine=noop)
    assert sched.get_job("daemon_morning") is None
    assert sched.get_job("daemon_evening") is None
