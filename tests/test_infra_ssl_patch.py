"""CHANGE SSL-AIOHTTP-CACHE: the opt-in bypass must reach aiohttp's import-time
cached SSLContext, otherwise discord.py still verifies the enterprise proxy's
self-signed chain (regression observed 2026-09-03).

Runs in a subprocess so the process-wide patch never leaks into other tests.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_PROBE = r"""
import sys, ssl
sys.path.insert(0, r"%s")
import aiohttp.connector as c
from ap_org_bot.infra.ssl_patch import apply_enterprise_ssl_bypass, is_enterprise_bypass_active
before = int(c._SSL_CONTEXT_VERIFIED.verify_mode)
apply_enterprise_ssl_bypass()
after = int(c._SSL_CONTEXT_VERIFIED.verify_mode)
default_ctx = ssl.create_default_context()
print(before, after, c._SSL_CONTEXT_VERIFIED.check_hostname, int(default_ctx.verify_mode), is_enterprise_bypass_active())
"""


def test_bypass_neutralises_aiohttp_cached_context():
    pytest.importorskip("aiohttp")
    out = subprocess.run(
        [sys.executable, "-c", _PROBE % (ROOT / "scripts")],
        capture_output=True, text=True, timeout=60, check=True,
    ).stdout.split()
    before, after, hostname, default_mode, active = out
    assert before == str(int(__import__("ssl").CERT_REQUIRED))
    assert after == str(int(__import__("ssl").CERT_NONE))
    assert hostname == "False"
    assert default_mode == str(int(__import__("ssl").CERT_NONE))
    assert active == "True"


def test_bypass_is_noop_without_aiohttp_shape(monkeypatch):
    """The helper must never raise when aiohttp is missing or restructured."""
    from ap_org_bot.infra import ssl_patch

    monkeypatch.setitem(sys.modules, "aiohttp.connector", None)  # import -> ImportError
    ssl_patch._neutralise_aiohttp_cached_contexts()  # no exception is the assertion
