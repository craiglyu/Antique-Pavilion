"""Opt-in SSL verification bypass for Craig's enterprise SSL proxy.

Anti-pattern this fixes: legacy `ap_org_bot.py` line 41-47 patches
`ssl.create_default_context` at module top-level. ANY import of that module
silently disables SSL verification process-wide — including in tests, in CI,
and in any daemon that imports a helper from it.

Now opt-in: bot's `main.py` calls `apply_enterprise_ssl_bypass()` explicitly.
Tests, daemons, and notion_client never trigger it unless they ask for it.
"""

from __future__ import annotations

import ssl as _ssl
from typing import Optional

_applied: bool = False
_original_create_default_context = _ssl.create_default_context


def apply_enterprise_ssl_bypass() -> None:
    """Disable SSL verification globally for the current process.

    Call this from the bot's main.py only — Craig's corporate proxy injects
    self-signed certs that break Discord/Gemini/Notion HTTPS otherwise.

    Idempotent: safe to call multiple times.
    """
    global _applied
    if _applied:
        return

    def _no_verify_ctx(*args, **kwargs):
        ctx = _original_create_default_context(*args, **kwargs)
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        return ctx

    _ssl.create_default_context = _no_verify_ctx
    _applied = True


def is_enterprise_bypass_active() -> bool:
    return _applied


def make_unverified_context() -> _ssl.SSLContext:
    """Get a one-off unverified SSL context without affecting global state.

    Use this in modules that need to make a single HTTPS call (notion_client.py)
    without affecting the rest of the process.
    """
    return _ssl._create_unverified_context()
