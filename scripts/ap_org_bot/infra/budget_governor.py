"""BudgetGovernor — per-call USD ledger extending budget_gate.

Sprint 4 full-version cost governance:
- Per-call USD tracking (daily / weekly / monthly windows)
- Council-topic attribution
- Backward compat: also bumps budget_gate.record_call_attempt()

NOT included here (future sessions):
- RealAgentInvoker callsite migration to record_call()
- Notion DB sync of usage stats
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterator

import pytz

from .budget_gate import BudgetExceeded, record_call_attempt

log = logging.getLogger("ap_org_bot.budget_governor")

TAIPEI_TZ = pytz.timezone("Asia/Taipei")


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    # Runtime import so monkeypatching BUDGET_STATE_FILE in tests takes effect.
    from .paths import BUDGET_STATE_FILE, MEMORY_DIR  # noqa: PLC0415

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(BUDGET_STATE_FILE)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS budget_calls_v2 (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ts         TEXT    NOT NULL,
                provider   TEXT    NOT NULL,
                agent      TEXT    NOT NULL,
                cost_usd   REAL    NOT NULL,
                topic_id   TEXT,
                tokens_in  INTEGER,
                tokens_out INTEGER
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_calls_ts "
            "ON budget_calls_v2(ts)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_calls_topic "
            "ON budget_calls_v2(topic_id) WHERE topic_id IS NOT NULL"
        )
        yield conn
        conn.commit()
    finally:
        conn.close()


class BudgetGovernor:
    """Full-version cost governance — extends budget_gate with per-call USD,
    daily/weekly caps, and Council-token cost attribution.

    Backward compatible: existing budget_gate.record_call_attempt() still
    works (BudgetGovernor.record_call() internally also bumps the call counter).
    """

    # Per-provider USD cost estimates (override per-call if known)
    PROVIDER_COST_PER_CALL_USD: dict[str, float] = {
        "claude_cli": 0.0,   # MAX/Pro subscription
        "gemini":     0.04,  # average for Council session token mix
        "opus_api":   0.15,
        "notion":     0.0,   # free tier
    }

    # USD caps from CLAUDE.md §6
    MONTHLY_CAPS_USD: dict[str, float] = {
        "gemini":   30.0,
        "opus_api": 15.0,
    }
    DAILY_CAPS_USD: dict[str, float] = {
        "gemini":   3.0,   # ~10% of monthly → 10-day burst protection
        "opus_api": 2.0,
    }
    WEEKLY_CAPS_USD: dict[str, float] = {
        "gemini":   10.0,
        "opus_api": 5.0,
    }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _window_start(self, window: str) -> str:
        """ISO timestamp (Taipei TZ) for the start of the given rolling window."""
        now = datetime.now(TAIPEI_TZ)
        if window == "daily":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif window == "weekly":
            # Monday as week start (ISO convention)
            start = (now - timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif window == "monthly":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Unknown window: {window!r}")
        return start.isoformat()

    def _sum_usd(self, provider: str, since: str) -> float:
        """Sum cost_usd for a provider from `since` (inclusive) to now."""
        with _conn() as c:
            row = c.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) FROM budget_calls_v2 "
                "WHERE provider=? AND ts>=?",
                (provider, since),
            ).fetchone()
        return row[0] if row else 0.0

    def _check_caps(self, provider: str, cost_usd: float) -> None:
        """Raise BudgetExceeded if adding cost_usd would breach any window cap."""
        for cap_dict, window in (
            (self.DAILY_CAPS_USD, "daily"),
            (self.WEEKLY_CAPS_USD, "weekly"),
            (self.MONTHLY_CAPS_USD, "monthly"),
        ):
            cap = cap_dict.get(provider)
            if cap is None:
                continue
            since = self._window_start(window)
            current = self._sum_usd(provider, since)
            if current + cost_usd > cap:
                raise BudgetExceeded(provider, current, cap)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_call(
        self,
        *,
        provider: str,
        agent: str,
        cost_usd: float | None = None,
        topic_id: str | None = None,   # Council-topic attribution
        tokens_in: int | None = None,
        tokens_out: int | None = None,
    ) -> dict:
        """Record one call. Returns {daily_used, weekly_used, monthly_used, allowed}.

        If cost_usd is None, uses PROVIDER_COST_PER_CALL_USD estimate.
        Also bumps budget_gate.record_call_attempt() for backward compat.
        Raises BudgetExceeded if any daily/weekly/monthly USD cap is hit,
        or if the legacy call-count cap is hit.
        """
        if cost_usd is None:
            cost_usd = self.PROVIDER_COST_PER_CALL_USD.get(provider, 0.0)

        # Check USD caps before any write.
        self._check_caps(provider, cost_usd)

        # Bump legacy call counter — also enforces call-count caps.
        record_call_attempt(provider=provider, agent=agent)

        # Insert into v2 USD ledger.
        now_ts = datetime.now(TAIPEI_TZ).isoformat()
        with _conn() as c:
            c.execute(
                "INSERT INTO budget_calls_v2"
                "(ts, provider, agent, cost_usd, topic_id, tokens_in, tokens_out) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (now_ts, provider, agent, cost_usd, topic_id, tokens_in, tokens_out),
            )

        return {
            "daily_used":   self._sum_usd(provider, self._window_start("daily")),
            "weekly_used":  self._sum_usd(provider, self._window_start("weekly")),
            "monthly_used": self._sum_usd(provider, self._window_start("monthly")),
            "allowed": True,
        }

    def usage_summary_usd(self) -> dict:
        """Per-provider USD breakdown with pct for all three windows.

        Returns:
            {provider: {daily, weekly, monthly, daily_pct, weekly_pct, monthly_pct}}
        Only providers that have at least one cap defined are included.
        """
        providers = sorted(
            set(self.DAILY_CAPS_USD) | set(self.WEEKLY_CAPS_USD) | set(self.MONTHLY_CAPS_USD)
        )
        result: dict[str, dict] = {}
        for provider in providers:
            daily   = self._sum_usd(provider, self._window_start("daily"))
            weekly  = self._sum_usd(provider, self._window_start("weekly"))
            monthly = self._sum_usd(provider, self._window_start("monthly"))

            d_cap = self.DAILY_CAPS_USD.get(provider)
            w_cap = self.WEEKLY_CAPS_USD.get(provider)
            m_cap = self.MONTHLY_CAPS_USD.get(provider)

            result[provider] = {
                "daily":        daily,
                "weekly":       weekly,
                "monthly":      monthly,
                "daily_pct":    round(daily   / d_cap * 100, 1) if d_cap else None,
                "weekly_pct":   round(weekly  / w_cap * 100, 1) if w_cap else None,
                "monthly_pct":  round(monthly / m_cap * 100, 1) if m_cap else None,
            }
        return result

    def attribution_by_topic(self, topic_id: str) -> dict:
        """Total USD per provider for all calls tagged with this topic_id.

        Returns:
            {provider: usd_total}  — empty dict if topic_id has no records.
        """
        with _conn() as c:
            rows = c.execute(
                "SELECT provider, COALESCE(SUM(cost_usd), 0.0) "
                "FROM budget_calls_v2 WHERE topic_id=? GROUP BY provider",
                (topic_id,),
            ).fetchall()
        return {row[0]: row[1] for row in rows}
