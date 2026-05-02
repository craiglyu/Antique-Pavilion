"""Tests for the daemon-poll CLI subcommand added to ap_council_runner.py."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ap_council_runner import main  # conftest wires scripts/ onto sys.path


def test_daemon_poll_dry_run_no_invoker(isolated_memory_dir, capsys):
    """daemon-poll without --apply must create CouncilDaemon(invoker=None)."""
    mock_run = MagicMock()
    mock_run.to_dict.return_value = {
        "dry_run": True,
        "started_at": "2026-05-02T00:00:00+00:00",
        "ended_at": "2026-05-02T00:00:01+00:00",
        "topics_seen": [],
        "topics_advanced": [],
        "errors": [],
    }

    with patch("ap_org_bot.council.daemon.CouncilDaemon") as MockDaemon:
        MockDaemon.return_value.poll_and_advance = AsyncMock(return_value=mock_run)

        rc = main(["daemon-poll"])

    assert rc == 0
    MockDaemon.assert_called_once_with(invoker=None)

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["dry_run"] is True


def test_daemon_poll_with_apply_uses_real_invoker(isolated_memory_dir, capsys):
    """daemon-poll --apply must instantiate RealAgentInvoker and pass it to daemon."""
    mock_invoker = MagicMock()
    MockRealAgentInvoker = MagicMock(return_value=mock_invoker)

    fake_invoker_module = MagicMock()
    fake_invoker_module.RealAgentInvoker = MockRealAgentInvoker

    mock_run = MagicMock()
    mock_run.to_dict.return_value = {
        "dry_run": False,
        "started_at": "2026-05-02T00:00:00+00:00",
        "ended_at": "2026-05-02T00:00:01+00:00",
        "topics_seen": [],
        "topics_advanced": [],
        "errors": [],
    }

    with patch.dict("sys.modules", {"ap_org_bot.agents.invoker": fake_invoker_module}), \
         patch("ap_org_bot.council.daemon.CouncilDaemon") as MockDaemon:
        MockDaemon.return_value.poll_and_advance = AsyncMock(return_value=mock_run)

        rc = main(["daemon-poll", "--apply"])

    assert rc == 0
    # daemon must be wired to the real invoker, not None
    MockDaemon.assert_called_once_with(invoker=mock_invoker)

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["dry_run"] is False


def test_daemon_poll_outputs_valid_json(isolated_memory_dir, capsys):
    """daemon-poll output must be valid JSON regardless of topic count."""
    mock_run = MagicMock()
    mock_run.to_dict.return_value = {
        "dry_run": True,
        "started_at": "2026-05-02T10:00:00+00:00",
        "ended_at": "2026-05-02T10:00:00.042000+00:00",
        "topics_seen": ["ap-2026-05-02-100000-001"],
        "topics_advanced": [],
        "errors": [],
    }

    with patch("ap_org_bot.council.daemon.CouncilDaemon") as MockDaemon:
        MockDaemon.return_value.poll_and_advance = AsyncMock(return_value=mock_run)

        rc = main(["daemon-poll"])

    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert isinstance(parsed, dict)
    for key in ("dry_run", "started_at", "ended_at",
                 "topics_seen", "topics_advanced", "errors"):
        assert key in parsed
