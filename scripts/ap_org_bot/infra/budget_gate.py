"""Budget gate — minimum-viable cost protection (Sprint 0 优化 #2).

Why this exists:
- Gemini monthly cap = USD 30, Opus = USD 15 (project_tech_constraints.md).
- A single Council session (4-6 agents × 2 phases) easily exceeds USD 1.
- Without a gate, the first real Council run can hit month-end on day 1.

Scope of this minimum-viable version:
- Per-provider monthly call counter (Claude CLI / Gemini API / Opus / Notion).
- Hard cap: BudgetExceeded raised if monthly_count exceeds threshold.
- Persistence: SQLite at memory/budget_state.sqlite (gitignored).
- NOT included (deferred to full ap_budget_governor.py):
  - Per-call USD cost ledger
  - Weekly / daily caps
  - Council-token cost attribution
  - Notion DB sync of usage stats

Design notes:
- We count CALLS (proxy for cost), not actual USD. Claude Code CLI uses MAX/Pro
  subscription so per-call USD is N/A; what matters is throttling runaway loops.
- Gemini / Opus genuinely cost USD per call — for those we use a tighter cap.
- All writes are synchronous SQLite (single-writer; bot is single-process).
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

import pytz

from .paths import BUDGET_STATE_FILE, MEMORY_DIR

log = logging.getLogger("ap_org_bot.budget_gate")

TAIPEI_TZ = pytz.timezone("Asia/Taipei")


class BudgetExceeded(RuntimeError):
    def __init__(self, provider: str, current: int, cap: int):
        self.provider = provider
        self.current = current
        self.cap = cap
        super().__init__(
            f"[budget_gate] {provider} monthly cap reached: {current} / {cap}"
        )


# Caps are CALL counts per month (proxy for cost). Tighten for paid APIs.
MONTHLY_CAPS: dict[str, int] = {
    "claude_cli": 500,   # MAX/Pro subscription — large quota, throttle runaways only
    "gemini":     800,   # Hard USD cap is $30, ~ $0.04/call → 800 calls
    "opus_api":   100,   # Hard USD cap is $15, ~ $0.15/call → 100 calls
    "notion":   5000,    # Free tier, throttle abuse only
}


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(BUDGET_STATE_FILE)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_calls (
                provider TEXT NOT NULL,
                agent TEXT NOT NULL,
                month_key TEXT NOT NULL,
                ts TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_calls_provider_month "
            "ON api_calls(provider, month_key)"
        )
        yield conn
        conn.commit()
    finally:
        conn.close()


def _current_month_key() -> str:
    return datetime.now(TAIPEI_TZ).strftime("%Y-%m")


def get_monthly_count(provider: str) -> int:
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) FROM api_calls WHERE provider=? AND month_key=?",
            (provider, _current_month_key()),
        ).fetchone()
        return row[0] if row else 0


def check_call_allowed(provider: str, *, raise_on_exceed: bool = True) -> bool:
    """Return True if a new call is within budget. Raise (or False) if not.

    Call this BEFORE making the API call — once the call is made, use record_call_attempt
    to log it (which also re-checks).
    """
    cap = MONTHLY_CAPS.get(provider)
    if cap is None:
        log.warning("[budget_gate] unknown provider %s — allowing", provider)
        return True
    current = get_monthly_count(provider)
    if current >= cap:
        if raise_on_exceed:
            raise BudgetExceeded(provider, current, cap)
        return False
    return True


def record_call_attempt(*, provider: str, agent: str) -> int:
    """Record one API call. Raises BudgetExceeded if the cap was already hit.

    Returns the new monthly count for that provider.
    """
    cap = MONTHLY_CAPS.get(provider)
    now_ts = datetime.now(TAIPEI_TZ).isoformat()
    month = _current_month_key()
    with _conn() as c:
        if cap is not None:
            current = c.execute(
                "SELECT COUNT(*) FROM api_calls WHERE provider=? AND month_key=?",
                (provider, month),
            ).fetchone()[0]
            if current >= cap:
                raise BudgetExceeded(provider, current, cap)
        c.execute(
            "INSERT INTO api_calls(provider, agent, month_key, ts) VALUES (?, ?, ?, ?)",
            (provider, agent, month, now_ts),
        )
        return c.execute(
            "SELECT COUNT(*) FROM api_calls WHERE provider=? AND month_key=?",
            (provider, month),
        ).fetchone()[0]


def usage_summary() -> dict[str, dict]:
    """For /usage-status slash command. Returns {provider: {used, cap, pct}}."""
    out: dict[str, dict] = {}
    for provider, cap in MONTHLY_CAPS.items():
        used = get_monthly_count(provider)
        out[provider] = {"used": used, "cap": cap,
                         "pct": round(used / cap * 100, 1) if cap else 0.0}
    return out
