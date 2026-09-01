"""No-network contracts for the AP local Bot Control Center.

CHANGE AP-BOT-LAUNCHER: verify allowlisted Bot controls, loopback binding,
secret-safe status/logs, health separation, and external-process non-ownership.
CHANGE AP-CONSOLE-LAUNCHER: verify the Windows one-click entrypoint remains
fixed to the AP WSL project and never contains credentials.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = REPO / "scripts" / "ap_launcher_web.py"
WINDOWS_LAUNCHER = REPO / "Start_AP_Control_Center.bat"


@pytest.fixture(scope="module")
def launcher():
    spec = importlib.util.spec_from_file_location("ap_launcher_web_under_test", LAUNCHER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_launcher_source_parses_and_uses_only_allowlisted_entrypoints():
    source = LAUNCHER_PATH.read_text(encoding="utf-8")
    ast.parse(source)
    assert '"relative_target": "ap_discord_bot.py"' in source
    assert '"relative_target": "scripts/ap_org_bot.py"' in source
    assert '"DISCORD_BOT_TOKEN"' in source
    assert '"DISCORD_ORG_BOT_TOKEN"' in source
    assert "shell=True" not in source
    assert "eval(" not in source
    assert "exec(" not in source
    assert "CHANGE AP-BOT-LAUNCHER" in source
    assert 'env_bool("AP_LAUNCHER_HEALTHCHECKS", True)' in source
    # A retired reader may flush final logs, but it must not overwrite the
    # readiness or exit state of a newly restarted child process.
    assert "if self.proc is not proc:" in source
    assert "if self.proc is proc:" in source


def test_windows_one_click_launcher_uses_fixed_wsl_control_center_without_secrets():
    source = WINDOWS_LAUNCHER.read_text(encoding="utf-8")
    assert "CHANGE AP-CONSOLE-LAUNCHER" in source
    assert "wsl.exe -d Ubuntu -- bash -lc" in source
    assert "scripts/ap_launcher_web.py" in source
    assert "/home/craig/miniconda3/envs/mamba_env/bin/python3" in source
    assert "AP_INGEST_SECRET" not in source
    assert "DISCORD_BOT_TOKEN" not in source


def test_loopback_and_browser_security_contract(launcher):
    assert launcher.BIND_HOST in launcher.LOOPBACK_HOSTS
    assert launcher._loopback_origin_allowed("") is True
    assert launcher._loopback_origin_allowed("http://127.0.0.1:8610") is True
    assert launcher._loopback_origin_allowed("http://localhost:8610") is True
    assert launcher._loopback_origin_allowed("https://attacker.example") is False
    assert "X-Content-Type-Options" in LAUNCHER_PATH.read_text(encoding="utf-8")
    assert "Content-Security-Policy" in LAUNCHER_PATH.read_text(encoding="utf-8")


def test_secret_redaction_covers_assignments_tokens_and_signed_urls(launcher):
    line = (
        "DISCORD_BOT_TOKEN=very-secret-value "
        "AP_INGEST_SECRET: another-secret "
        "https://cdn.discordapp.com/a.jpg?ex=abc&is=def&hm=ghi"
    )
    redacted = launcher.redact_log_line(line)
    for secret in ("very-secret-value", "another-secret", "abc", "def", "ghi"):
        assert secret not in redacted
    assert redacted.count("[REDACTED]") >= 5


def test_missing_config_fails_before_process_spawn(launcher, monkeypatch):
    definition = dict(launcher.SERVICE_DEFS[0])
    manager = launcher.ServiceManager(definition)
    monkeypatch.setattr(launcher, "env", lambda _key, _default="": "")
    monkeypatch.setattr(launcher, "find_external_pid", lambda *_args, **_kwargs: None)
    called = False

    def forbidden_popen(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("Popen must not run with missing config")

    monkeypatch.setattr(launcher.subprocess, "Popen", forbidden_popen)
    result = manager.start()
    assert result["ok"] is False
    assert result["state"] == "CONFIG_MISSING"
    assert called is False
    assert manager.status == "ERROR"


def test_external_process_is_reported_and_never_stopped(launcher, monkeypatch):
    manager = launcher.ServiceManager(dict(launcher.SERVICE_DEFS[1]))
    monkeypatch.setattr(launcher, "find_external_pid", lambda *_args, **_kwargs: 4242)
    stopped = manager.stop()
    assert stopped == {
        "ok": False,
        "state": "EXTERNAL_NOT_OWNED",
        "service": "org",
        "pid": 4242,
    }
    assert manager.proc is None
    assert manager.snapshot()["status"] == "EXTERNAL"


def test_health_probes_never_return_tokens(launcher, monkeypatch):
    definition = dict(launcher.SERVICE_DEFS[0])
    secret = "discord-private-token"
    monkeypatch.setattr(launcher, "env", lambda key, default="": secret if key == "DISCORD_BOT_TOKEN" else default)
    calls = []

    def fake_probe(url, headers=None):
        calls.append((url, dict(headers or {})))
        return 200, "{}"

    monkeypatch.setattr(launcher, "_http_probe", fake_probe)
    result = launcher._probe_discord(definition)
    assert result["state"] == "ONLINE"
    assert secret not in str(result)
    assert len(calls) == 2
    assert all(call[1]["Authorization"] == "Bot " + secret for call in calls)


def test_gui_has_individual_controls_responsive_layout_and_reduced_motion(launcher):
    html = launcher.HTML
    assert "serviceAction('${s.key}','start')" in html
    assert "serviceAction('${s.key}','stop')" in html
    assert "serviceAction('${s.key}','restart')" in html
    assert "啟動兩個 Bot" in html
    assert "不停止外部 tmux 程序" in html
    assert "@media(max-width:760px)" in html
    assert "prefers-reduced-motion" in html
    assert "--gold:#c49a45" in html
    assert "purple" not in html.lower()


def test_status_payload_contains_health_but_not_secret_values(launcher, monkeypatch):
    monkeypatch.setattr(launcher, "find_external_pid", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(launcher, "env", lambda _key, _default="": "configured")
    payload = launcher.status_payload()
    assert [service["key"] for service in payload["services"]] == ["intake", "org"]
    assert all("health" in service for service in payload["services"])
    serialized = str(payload)
    assert "configured" not in serialized
    assert "DISCORD_BOT_TOKEN=configured" not in serialized
