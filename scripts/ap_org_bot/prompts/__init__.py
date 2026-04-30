"""prompts/ — agent system prompts as markdown.

Layer convention:
- _core/      : agents that ship in the framework (PM, Feedback PM)
- _domain/ap/ : Antique Pavilion-specific agents (Designer, Dev, Marketing, ...)

When forking the framework to another project, replace _domain/ap/ with
_domain/<new_project>/ and keep _core/ untouched.

Each .md file has YAML frontmatter:
    ---
    schema_version: 1
    agent: <agent_name>
    layer: core|domain
    loaded_by: [<class names that load this prompt>]
    prompt_version: vX.Y
    last_updated: YYYY-MM-DD
    notion_page_title: <matches config/prompts_versioning.yaml>
    ---

Body uses Python str.format() placeholders: {topic}, {ticket_id}, {context_block}, ...
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ap_org_bot.infra.paths import PROMPTS_CORE_DIR, PROMPTS_DOMAIN_AP_DIR

log = logging.getLogger("ap_org_bot.prompts")

# Maps logical prompt name → .md path. Single source of truth for prompt lookup.
_PROMPT_PATHS: dict[str, Path] = {
    # core
    "feedback_pm":            PROMPTS_CORE_DIR / "feedback_pm.md",
    "pm":                     PROMPTS_CORE_DIR / "pm.md",
    # domain (AP)
    "designer":               PROMPTS_DOMAIN_AP_DIR / "designer.md",
    "dev":                    PROMPTS_DOMAIN_AP_DIR / "dev.md",
    "marketing":              PROMPTS_DOMAIN_AP_DIR / "marketing.md",
    "auto_dev":               PROMPTS_DOMAIN_AP_DIR / "auto_dev.md",
    "gas_dev":                PROMPTS_DOMAIN_AP_DIR / "gas_dev.md",
    "opus_design_researcher": PROMPTS_DOMAIN_AP_DIR / "opus_researcher.md",
    "curator":                PROMPTS_DOMAIN_AP_DIR / "curator.md",  # Sprint 1
}


def _strip_frontmatter(raw: str) -> str:
    """Drop the YAML frontmatter block; return only the prompt body."""
    if not raw.startswith("---"):
        return raw.strip()
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return raw.strip()
    return parts[2].lstrip("\n")


def load_prompt(name: str) -> str:
    """Read prompt body for `name`, stripping YAML frontmatter."""
    path = _PROMPT_PATHS.get(name)
    if path is None:
        raise KeyError(f"unknown prompt: {name}")
    if not path.exists():
        raise FileNotFoundError(f"prompt file missing: {path}")
    raw = path.read_text(encoding="utf-8")
    return _strip_frontmatter(raw)


def list_prompts() -> list[str]:
    return sorted(_PROMPT_PATHS.keys())
