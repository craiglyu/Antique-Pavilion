"""Centralized path constants — single source of truth for filesystem layout.

Anti-pattern this fixes: legacy `ap_org_bot.py` computed `PROJECT_ROOT = Path(__file__).parent.parent`
in 3 different files (`ap_org_bot.py`, `notion_writer.py`, `ap_discord_bot.py`).
Now changing the layout means editing one file.
"""

from __future__ import annotations

from pathlib import Path

# Package layout: scripts/ap_org_bot/infra/paths.py → 3 levels up = project root
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]

# Top-level files
ENV_FILE: Path = PROJECT_ROOT / ".env.antique"

# Config (yaml-driven)
CONFIG_DIR: Path = PROJECT_ROOT / "config"
PROMPTS_VERSIONING_FILE: Path = CONFIG_DIR / "prompts_versioning.yaml"
CHANNELS_CONFIG: Path = CONFIG_DIR / "channels.yaml"
AGENTS_CONFIG: Path = CONFIG_DIR / "agents.yaml"
COUNCIL_ROUTING_CONFIG: Path = CONFIG_DIR / "council_routing.yaml"
SIGNOFF_TIERS_CONFIG: Path = CONFIG_DIR / "signoff_tiers.yaml"
MIGRATIONS_DIR: Path = CONFIG_DIR / "migrations"

# Prompts (markdown — separated from .py code)
PROMPTS_DIR: Path = PROJECT_ROOT / "scripts" / "ap_org_bot" / "prompts"
PROMPTS_CORE_DIR: Path = PROMPTS_DIR / "_core"
PROMPTS_DOMAIN_AP_DIR: Path = PROMPTS_DIR / "_domain" / "ap"

# Runtime state (gitignored)
MEMORY_DIR: Path = PROJECT_ROOT / "memory"
FEEDBACK_STATE_FILE: Path = PROJECT_ROOT / "feedback_state.json"
BUDGET_STATE_FILE: Path = MEMORY_DIR / "budget_state.sqlite"
COUNCIL_STATE_DIR: Path = MEMORY_DIR / "ap_council_state"
OPUS_INBOX_DIR: Path = MEMORY_DIR / "opus_inbox"
OPUS_RULINGS_DIR: Path = MEMORY_DIR / "opus_rulings"
AGENT_INBOX_FILE: Path = MEMORY_DIR / "agent_inbox.md"
VETO_FILE: Path = MEMORY_DIR / "VETO_ACTIVE.json"

# Tests (relative to project root, used by conftest.py)
TESTS_DIR: Path = PROJECT_ROOT / "tests"


def ensure_runtime_dirs() -> None:
    """Create gitignored runtime directories on bot startup. Idempotent."""
    for d in (MEMORY_DIR, COUNCIL_STATE_DIR, OPUS_INBOX_DIR, OPUS_RULINGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
