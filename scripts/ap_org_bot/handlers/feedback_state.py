"""Feedback PM state persistence (feedback_state.json).

Lifted from legacy ap_org_bot.py:178-202. Behaviour preserved exactly. The
state file is gitignored (`.gitignore` line 17).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytz

from ap_org_bot.infra.paths import FEEDBACK_STATE_FILE

TAIPEI_TZ = pytz.timezone("Asia/Taipei")


def load_state() -> dict[str, Any]:
    if FEEDBACK_STATE_FILE.exists():
        with open(FEEDBACK_STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {
        "last_feedback_message_id": None,
        "monthly_calls": 0,
        "month_key": "",
        "proposals": {},
    }


def save_state(state: dict[str, Any]) -> None:
    FEEDBACK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def reset_monthly_counter_if_needed(state: dict[str, Any]) -> dict[str, Any]:
    now_key = datetime.now(TAIPEI_TZ).strftime("%Y-%m")
    if state.get("month_key") != now_key:
        state["monthly_calls"] = 0
        state["month_key"] = now_key
    return state
