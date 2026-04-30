"""pytest config — make `ap_org_bot` package importable + provide shared fixtures.

Run from project root:
    pytest -q
    pytest tests/test_council.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Project root contains scripts/ — push onto sys.path so `import ap_org_bot.*` works.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
for p in (str(_SCRIPTS_DIR), str(_PROJECT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)


import pytest  # noqa: E402


@pytest.fixture
def isolated_memory_dir(tmp_path, monkeypatch):
    """Redirect MEMORY_DIR + COUNCIL_STATE_DIR + BUDGET_STATE_FILE to a tmp dir.

    Tests that touch persistence layer should request this fixture so they
    don't pollute the real memory/ folder or interfere with each other.
    """
    fake_memory = tmp_path / "memory"
    fake_memory.mkdir()
    fake_council = fake_memory / "ap_council_state"
    fake_council.mkdir()

    from ap_org_bot.infra import paths as paths_mod
    monkeypatch.setattr(paths_mod, "MEMORY_DIR", fake_memory)
    monkeypatch.setattr(paths_mod, "COUNCIL_STATE_DIR", fake_council)
    monkeypatch.setattr(paths_mod, "BUDGET_STATE_FILE",
                        fake_memory / "budget_state.sqlite")
    monkeypatch.setattr(paths_mod, "FEEDBACK_STATE_FILE",
                        tmp_path / "feedback_state.json")
    monkeypatch.setattr(paths_mod, "VETO_FILE", fake_memory / "VETO_ACTIVE.json")
    monkeypatch.setattr(paths_mod, "OPUS_INBOX_DIR", fake_memory / "opus_inbox")
    monkeypatch.setattr(paths_mod, "OPUS_RULINGS_DIR", fake_memory / "opus_rulings")

    # Also patch already-imported modules that captured the constants by name.
    from ap_org_bot.council import persistence as persistence_mod
    monkeypatch.setattr(persistence_mod, "COUNCIL_STATE_DIR", fake_council)
    from ap_org_bot.infra import budget_gate as budget_mod
    monkeypatch.setattr(budget_mod, "BUDGET_STATE_FILE",
                        fake_memory / "budget_state.sqlite")
    monkeypatch.setattr(budget_mod, "MEMORY_DIR", fake_memory)
    # Sprint 2 fix: dispatcher writes agent_tasks.yaml — patch its MEMORY_DIR too,
    # else reaction tests pollute production memory/agent_tasks.yaml.
    from ap_org_bot.council import dispatcher as dispatcher_mod
    monkeypatch.setattr(dispatcher_mod, "MEMORY_DIR", fake_memory)

    yield fake_memory


@pytest.fixture
def clean_env(monkeypatch):
    """Remove .env-related environment variables before a test."""
    for key in list(os.environ.keys()):
        if key.startswith("DISCORD_") or key.startswith("NOTION_"):
            monkeypatch.delenv(key, raising=False)
    yield
