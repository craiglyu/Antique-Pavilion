"""Env loader — reads `.env.antique`, falls back to os.environ.

Replaces the duplicated `_load_env()` + `_env()` pair previously in both
`ap_org_bot.py` (line 84-98) and `notion_writer.py` (line 41-54).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .paths import ENV_FILE


def _load_env_file(env_file: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


_FILE_ENV: dict[str, str] = _load_env_file(ENV_FILE)


def env(key: str, default: str = "") -> str:
    """Look up an env var: os.environ wins over .env.antique wins over default.

    Why os.environ wins: lets CI / cron jobs override config without editing .env.antique.
    """
    val = os.environ.get(key)
    if val:
        return val
    return _FILE_ENV.get(key, default)


def env_int(key: str, default: int) -> int:
    raw = env(key, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_bool(key: str, default: bool = False) -> bool:
    raw = env(key, "").lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def reload_env_file() -> None:
    """Re-read .env.antique from disk. Used by tests; not called in prod."""
    global _FILE_ENV
    _FILE_ENV = _load_env_file(ENV_FILE)
