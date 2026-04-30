"""Catchup Protocol — Bot resilience after restart / Discord outage / Gemini quota burst.

Per blueprint v1.1 §8.4 (fork Thor V11.1 Wave 2A) — but AP scope reduced from
6 source types to 5 (no separate auto-progression watermark).

## Why this exists

When the bot crashes / WSL2 restarts / Discord has a 30-minute outage, the bot
needs to know:
- Which #ap-feedback messages it ALREADY processed (so it doesn't double-spawn agents)
- How many Gemini calls it ALREADY made this month (so it respects budget caps)
- Which Notion entries it ALREADY wrote (so it doesn't double-create)
- Which Council topics are mid-flight (AWAITING_SIGNOFF — should be visible on restart)
- When the last heartbeat happened (alert if > N minutes ago)

Each tracked thing has a "watermark" — a small JSON file at
`memory/ap_catchup/<source>.json` recording the last-known checkpoint.

## Sprint 2 scope (this file)

- **WatermarkStore** — atomic JSON CRUD per source type
- **CatchupCoordinator.on_bot_startup()** — invoked from `main.py` after Discord login.
  - Lists active Council topics (proves persistence works)
  - Reports each watermark age (alerts if > 24h)
  - Currently READ-ONLY — does not actually replay missed Discord messages.
- **Tests** — covering CRUD, schema versioning, source-type registration

## Sprint 3 scope (deferred)

- Actual replay logic (re-scan #ap-feedback history since last watermark)
- Gemini quota reconciliation (fetch usage stats from Google Cloud)
- Council state machine catch-up (auto-resume PHASE2_DEBATE if Bot crashed mid-debate)

The Sprint 2 skeleton is enough to **prove the contract** (idempotent restarts
don't double-process). Sprint 3 wires the active replay.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from ap_org_bot.infra.paths import CATCHUP_DIR

log = logging.getLogger("ap_org_bot.handlers.catchup")


class SourceType(str, Enum):
    """5 watermark source types tracked by the bot."""

    DISCORD_FEEDBACK = "discord_feedback"  # last processed #ap-feedback message_id
    GEMINI_CALLS = "gemini_calls"           # last gemini call timestamp
    NOTION_WRITES = "notion_writes"         # last successful Notion page_id (per DB)
    COUNCIL_STATE = "council_state"         # last council state transition timestamp
    BOT_HEARTBEAT = "bot_heartbeat"         # last bot main-loop tick timestamp


SCHEMA_VERSION = 1
STALE_WATERMARK_AGE_HOURS = 24


@dataclass(frozen=True)
class Watermark:
    """One source's checkpoint record."""

    source: SourceType
    value: str            # opaque string — message_id / ISO timestamp / page_id
    updated_at: str       # ISO timestamp (UTC)
    schema_version: int = SCHEMA_VERSION
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": self.source.value,
            "value": self.value,
            "updated_at": self.updated_at,
            "schema_version": self.schema_version,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, doc: dict) -> "Watermark":
        return cls(
            source=SourceType(doc["source"]),
            value=str(doc.get("value", "")),
            updated_at=doc.get("updated_at", ""),
            schema_version=int(doc.get("schema_version", SCHEMA_VERSION)),
            extra=dict(doc.get("extra", {}) or {}),
        )

    def age_hours(self, *, now: Optional[datetime] = None) -> Optional[float]:
        """Hours since updated_at, or None if updated_at unparseable."""
        try:
            updated = datetime.fromisoformat(self.updated_at)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None
        ref = now or datetime.now(timezone.utc)
        return (ref - updated).total_seconds() / 3600.0


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WatermarkStore:
    """Atomic per-source watermark persistence at memory/ap_catchup/<source>.json.

    Threading: single-writer (bot is single-process). Reads are safe in async tasks.
    Crash safety: writes go through a .tmp + rename pattern (matches council/persistence).
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or CATCHUP_DIR

    def _path_for(self, source: SourceType) -> Path:
        return self.base_dir / f"{source.value}.json"

    def set(self, source: SourceType, value: str, *, extra: Optional[dict] = None) -> Watermark:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        wm = Watermark(
            source=source,
            value=value,
            updated_at=_now_utc_iso(),
            extra=extra or {},
        )
        path = self._path_for(source)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(wm.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(path)
        log.debug("[catchup] %s ← %s", source.value, value[:32])
        return wm

    def get(self, source: SourceType) -> Optional[Watermark]:
        path = self._path_for(source)
        if not path.exists():
            return None
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            log.warning("[catchup] corrupt watermark %s: %s", path.name, e)
            return None
        return Watermark.from_dict(doc)

    def list_all(self) -> list[Watermark]:
        if not self.base_dir.exists():
            return []
        out: list[Watermark] = []
        for source in SourceType:
            wm = self.get(source)
            if wm:
                out.append(wm)
        return out

    def clear(self, source: SourceType) -> bool:
        path = self._path_for(source)
        if path.exists():
            path.unlink()
            return True
        return False


class CatchupCoordinator:
    """Drives the on-startup audit. Call once after Discord login."""

    def __init__(self, store: Optional[WatermarkStore] = None):
        self.store = store or WatermarkStore()

    def on_bot_startup(self) -> dict[str, Any]:
        """Sprint 2 read-only audit: report watermark ages + active Council topics.

        Returns a dict suitable for log emission + later telemetry.
        Does NOT actually replay missed events (Sprint 3 will).
        """
        # Lazy import — Council depends on persistence which depends on infra.paths;
        # importing at module level can create circular issues during test setup.
        from ap_org_bot.council.persistence import list_active_topics

        active_topics = list_active_topics()
        watermarks = self.store.list_all()
        now = datetime.now(timezone.utc)

        stale: list[Watermark] = []
        fresh: list[Watermark] = []
        for wm in watermarks:
            age = wm.age_hours(now=now)
            if age is None or age > STALE_WATERMARK_AGE_HOURS:
                stale.append(wm)
            else:
                fresh.append(wm)

        report = {
            "active_council_topics": [t.topic_id for t in active_topics],
            "active_topic_count": len(active_topics),
            "fresh_watermarks": [w.source.value for w in fresh],
            "stale_watermarks": [w.source.value for w in stale],
            "missing_watermarks": [
                s.value for s in SourceType
                if s not in {w.source for w in watermarks}
            ],
            "checked_at": now.isoformat(),
        }

        log.info("[catchup] %d active council topic(s); watermarks: %d fresh, "
                 "%d stale, %d missing",
                 report["active_topic_count"], len(fresh), len(stale),
                 len(report["missing_watermarks"]))
        if stale:
            for wm in stale:
                age = wm.age_hours(now=now)
                age_str = "unknown" if age is None else f"{age:.1f}h"
                log.warning("[catchup] stale watermark %s — last update %s ago",
                            wm.source.value, age_str)

        return report

    def heartbeat(self) -> Watermark:
        """Convenience — bump BOT_HEARTBEAT watermark to now. Bot loop calls this periodically."""
        return self.store.set(SourceType.BOT_HEARTBEAT, _now_utc_iso())
