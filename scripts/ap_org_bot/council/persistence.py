"""JSON persistence for Council topics.

One file per topic at memory/ap_council_state/<topic_id>.json.
Bot crashes / restarts read all *.json on startup, replay any pending state
transitions, and continue without losing in-flight councils.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Iterable, Optional

from ap_org_bot.infra.paths import COUNCIL_STATE_DIR

from .state_machine import State, Topic

log = logging.getLogger("ap_org_bot.council.persistence")


def topic_path(topic_id: str) -> Path:
    return COUNCIL_STATE_DIR / f"{topic_id}.json"


def save_topic(topic: Topic) -> Path:
    COUNCIL_STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = topic_path(topic.topic_id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(topic.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)  # atomic write — survives crash mid-write
    return path


def load_topic(topic_id: str) -> Optional[Topic]:
    path = topic_path(topic_id)
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log.error("[council] corrupt topic file %s: %s", path, e)
        return None
    return Topic.from_dict(doc)


def list_topics() -> list[Topic]:
    """All topics, ordered by created_at ascending."""
    if not COUNCIL_STATE_DIR.exists():
        return []
    topics: list[Topic] = []
    for path in COUNCIL_STATE_DIR.glob("*.json"):
        if path.name.startswith("_"):
            continue  # _schema.json etc. are not topic files
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            topics.append(Topic.from_dict(doc))
        except (json.JSONDecodeError, KeyError) as e:
            log.warning("[council] skipping unreadable %s: %s", path.name, e)
    topics.sort(key=lambda t: t.created_at)
    return topics


def list_active_topics() -> list[Topic]:
    """Topics not in terminal state (ARCHIVED). Used on Bot restart for catch-up."""
    return [t for t in list_topics() if t.state != State.ARCHIVED]


def make_topic_id(prefix: str = "ap") -> str:
    """Generate a fresh topic_id like `ap-2026-04-30-013523-001`."""
    base = f"{prefix}-{time.strftime('%Y-%m-%d-%H%M%S')}"
    # If there's a collision (rare — same-second invocation), suffix with a counter.
    n = 1
    while topic_path(f"{base}-{n:03d}").exists():
        n += 1
    return f"{base}-{n:03d}"
