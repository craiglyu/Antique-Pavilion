"""Adapter to legacy notion_writer.py — keeps the existing module untouched.

Why we re-export instead of moving notion_writer.py contents here:
- notion_writer.py is already 421 LoC with 7 create_xxx() functions, all working.
- It has its own env loader and SSL bypass that work; rewriting risks regression.
- Sprint 0 goal: stop the bleeding (single-file 1288-LoC bot), not refactor everything.
- Future Sprint can fold notion_writer.py into infra/notion_client.py once Notion
  reconciler arrives (v0.2 §3 Item 9).

For now this module just provides a stable import path: callers do
    from ap_org_bot.infra.notion_client import is_enabled, create_topic, ...
instead of `sys.path.insert + import notion_writer`.
"""

from __future__ import annotations

import logging
import sys

from .paths import PROJECT_ROOT

log = logging.getLogger("ap_org_bot.notion_client")

_LEGACY_SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(_LEGACY_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_LEGACY_SCRIPTS_DIR))

try:
    from notion_writer import (  # type: ignore[import-not-found]
        DB_AUTH_LOG,
        DB_CONTENT_CAL,
        DB_DECISIONS,
        DB_INCIDENTS,
        DB_KB,
        DB_RESEARCH,
        DB_TOPICS,
        create_authentication_log,
        create_content_calendar,
        create_decision,
        create_incident,
        create_kb_entry,
        create_topic,
        extract_property_value,
        is_enabled,
        query_database,
        update_page_properties,
    )

    AVAILABLE = True
except Exception as e:
    log.warning("[notion_client] notion_writer not loadable: %s", e)
    AVAILABLE = False

    DB_TOPICS = ""
    DB_DECISIONS = ""
    DB_KB = ""
    DB_AUTH_LOG = ""
    DB_CONTENT_CAL = ""
    DB_INCIDENTS = ""
    DB_RESEARCH = ""

    def is_enabled() -> bool:  # type: ignore[no-redef]
        return False

    def _stub(*_args, **_kwargs):
        return None

    create_topic = _stub  # type: ignore[assignment]
    create_decision = _stub  # type: ignore[assignment]
    create_content_calendar = _stub  # type: ignore[assignment]
    create_authentication_log = _stub  # type: ignore[assignment]
    create_kb_entry = _stub  # type: ignore[assignment]
    create_incident = _stub  # type: ignore[assignment]

    def query_database(*_args, **_kwargs):  # type: ignore[no-redef]
        return []

    def extract_property_value(*_args, **_kwargs):  # type: ignore[no-redef]
        return None

    def update_page_properties(*_args, **_kwargs):  # type: ignore[no-redef]
        return None


__all__ = [
    "AVAILABLE",
    "is_enabled",
    "create_topic",
    "create_decision",
    "create_content_calendar",
    "create_authentication_log",
    "create_kb_entry",
    "create_incident",
    "query_database",
    "extract_property_value",
    "update_page_properties",
    # DB ID env shortcuts (Sprint 1 Curator + future Sprint reconciler)
    "DB_TOPICS",
    "DB_DECISIONS",
    "DB_KB",
    "DB_AUTH_LOG",
    "DB_CONTENT_CAL",
    "DB_INCIDENTS",
    "DB_RESEARCH",
]
