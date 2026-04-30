"""Council routing + post-signoff task dispatch.

Reads config/council_routing.yaml to determine convened agents per topic type.
After SIGNED_OFF, writes follow-up tasks to memory/agent_tasks.yaml so the
existing /sprint slash command can surface them.
"""

from __future__ import annotations

import logging
from typing import Optional

import yaml

from ap_org_bot.infra.paths import COUNCIL_ROUTING_CONFIG, MEMORY_DIR

from .state_machine import Topic

log = logging.getLogger("ap_org_bot.council.dispatcher")


def load_routing() -> dict:
    if not COUNCIL_ROUTING_CONFIG.exists():
        log.warning("[dispatcher] %s missing", COUNCIL_ROUTING_CONFIG)
        return {}
    return yaml.safe_load(COUNCIL_ROUTING_CONFIG.read_text(encoding="utf-8")) or {}


def convened_agents_for(topic_type: str) -> list[str]:
    routing = load_routing()
    topics = (routing.get("topics") or {})
    entry = topics.get(topic_type) or topics.get("其他") or {}
    return list(entry.get("召集", []))


def chair_for(topic_type: str) -> str:
    routing = load_routing()
    topics = (routing.get("topics") or {})
    entry = topics.get(topic_type) or topics.get("其他") or {}
    return entry.get("主席", "PM")


def required_attendees_for(topic_type: str) -> list[str]:
    routing = load_routing()
    topics = (routing.get("topics") or {})
    entry = topics.get(topic_type) or topics.get("其他") or {}
    return list(entry.get("必出席", []))


def append_dispatched_tasks(topic: Topic) -> Optional[str]:
    """Append topic's follow-up tasks to memory/agent_tasks.yaml.

    Returns the path written to (string) or None if nothing dispatched.
    Idempotent: tasks track their topic_id so re-running the same SIGNED_OFF
    transition won't duplicate entries.
    """
    if not topic.dispatched_tasks:
        return None
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    tasks_file = MEMORY_DIR / "agent_tasks.yaml"

    if tasks_file.exists():
        existing = yaml.safe_load(tasks_file.read_text(encoding="utf-8")) or {}
    else:
        existing = {}

    sprint = existing.setdefault("council_dispatched", [])
    seen_ids = {t.get("task_id") for t in sprint if isinstance(t, dict)}

    appended = 0
    for task in topic.dispatched_tasks:
        tid = task.get("task_id")
        if tid and tid in seen_ids:
            continue
        sprint.append({
            **task,
            "topic_id": topic.topic_id,
        })
        appended += 1

    if appended == 0:
        return None

    tasks_file.write_text(
        yaml.safe_dump(existing, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    log.info("[dispatcher] appended %d task(s) for topic %s",
             appended, topic.topic_id)
    return str(tasks_file)
