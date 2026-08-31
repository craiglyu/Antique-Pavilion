#!/usr/bin/env python3
"""吉寶軒 AP Bot Control Center — loopback-only local launcher.

CHANGE AP-BOT-LAUNCHER: provide explicit per-Bot start/stop/restart controls,
layered Discord/GAS health, external-process collision protection, secret-redacted
SSE logs, and launcher-owned process-group shutdown without changing either Bot.

Run from WSL2:
    python3 -u scripts/ap_launcher_web.py
    python3 -u scripts/ap_launcher_web.py --no-browser
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from queue import Empty, Queue
from socketserver import ThreadingMixIn
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from ap_org_bot.infra.env import env, env_bool, env_int  # noqa: E402


PYTHON = env("AP_BOT_PYTHON", sys.executable)
DEFAULT_PORT = env_int("AP_LAUNCHER_PORT", 8610)
BIND_HOST = env("AP_LAUNCHER_BIND_HOST", "127.0.0.1")
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})
HEALTH_INTERVAL_SECONDS = 30
HEALTHCHECKS_ENABLED = env_bool("AP_LAUNCHER_HEALTHCHECKS", True)
STARTUP_DEGRADED_SECONDS = 45
STOP_GRACE_SECONDS = 8

STATUS_COLORS = {
    "STOPPED": "#766f64",
    "STARTING": "#a77b2c",
    "CONNECTED": "#567060",
    "ONLINE": "#2f7355",
    "DEGRADED": "#a76426",
    "ERROR": "#922f2f",
    "EXTERNAL": "#655b82",
}

SERVICE_DEFS: tuple[dict[str, Any], ...] = (
    {
        "key": "intake",
        "name": "鑑定助手",
        "subtitle": "多圖壓縮 · GAS 鑑定 · 藏品建檔",
        "target": PROJECT_ROOT / "ap_discord_bot.py",
        "relative_target": "ap_discord_bot.py",
        "ready_markers": ("鑑定助理 Bot 上線",),
        "operational_markers": ("[CatchUp] 完成",),
        "required_env": ("DISCORD_BOT_TOKEN", "AP_GAS_DOPOST_URL", "AP_INGEST_SECRET"),
        "token_env": "DISCORD_BOT_TOKEN",
        "channel_env": None,
        "channel_default": 1495279823009087551,
        "gas_health": True,
    },
    {
        "key": "org",
        "name": "AP ORG",
        "subtitle": "Agents · Council · Feedback · Scheduler",
        "target": PROJECT_ROOT / "scripts" / "ap_org_bot.py",
        "relative_target": "scripts/ap_org_bot.py",
        "ready_markers": ("ORG Bot ready as",),
        "operational_markers": ("[scheduler] poll @",),
        "required_env": ("DISCORD_ORG_BOT_TOKEN",),
        "token_env": "DISCORD_ORG_BOT_TOKEN",
        "channel_env": "DISCORD_CHANNEL_AP_DEV",
        "channel_default": 1495280247590097059,
        "gas_health": False,
    },
)


_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(DISCORD(?:_ORG)?_BOT_TOKEN|AP_INGEST_SECRET|GEMINI_API_KEY)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_DISCORD_TOKEN_RE = re.compile(r"\b[MN][A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}\b")
_SIGNED_QUERY_RE = re.compile(r"(?i)([?&](?:ex|is|hm|signature|token)=)[^&\s]+")


def redact_log_line(value: str) -> str:
    """Remove likely secrets before a child line reaches memory or the browser."""
    line = str(value or "")
    line = _SECRET_ASSIGNMENT_RE.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", line)
    line = _DISCORD_TOKEN_RE.sub("[REDACTED_DISCORD_TOKEN]", line)
    return _SIGNED_QUERY_RE.sub(lambda m: m.group(1) + "[REDACTED]", line)


_master_queue: Queue[dict[str, str]] = Queue()
_log_buffer: deque[dict[str, str]] = deque(maxlen=800)
_log_buffer_lock = threading.Lock()
_subscribers: list[Queue[dict[str, str]]] = []
_subscribers_lock = threading.Lock()


def _emit(key: str, line: str) -> None:
    _master_queue.put({"key": key, "line": redact_log_line(line)})


def _dispatch_logs() -> None:
    while True:
        item = _master_queue.get()
        with _log_buffer_lock:
            _log_buffer.append(item)
        with _subscribers_lock:
            stale: list[Queue[dict[str, str]]] = []
            for subscriber in _subscribers:
                try:
                    subscriber.put_nowait(item)
                except Exception:
                    stale.append(subscriber)
            for subscriber in stale:
                if subscriber in _subscribers:
                    _subscribers.remove(subscriber)


threading.Thread(target=_dispatch_logs, daemon=True, name="ap-launcher-log-dispatch").start()


def _command_matches_service(pid: int, definition: dict[str, Any]) -> bool:
    """Recognize an AP Bot launched outside this launcher without killing it."""
    if os.name != "posix" or pid == os.getpid():
        return False
    proc_root = Path("/proc") / str(pid)
    try:
        raw = (proc_root / "cmdline").read_bytes()
        args = [chunk.decode("utf-8", "replace") for chunk in raw.split(b"\0") if chunk]
        cwd = Path(os.readlink(proc_root / "cwd")).resolve()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return False
    if cwd != PROJECT_ROOT.resolve():
        return False
    relative = str(definition["relative_target"]).replace("\\", "/")
    target_name = Path(relative).name
    normalized = [arg.replace("\\", "/") for arg in args]
    return any(arg == relative or arg.endswith("/" + relative) for arg in normalized) or (
        target_name in normalized and relative == target_name
    )


def find_external_pid(definition: dict[str, Any], owned_pid: int | None = None) -> int | None:
    if os.name != "posix" or not Path("/proc").exists():
        return None
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == owned_pid:
            continue
        if _command_matches_service(pid, definition):
            return pid
    return None


class ServiceManager:
    """Own exactly one child process and never terminate external Bot processes."""

    def __init__(self, definition: dict[str, Any]) -> None:
        self.definition = definition
        self.key = str(definition["key"])
        self.name = str(definition["name"])
        self.proc: subprocess.Popen[str] | None = None
        self.status = "STOPPED"
        self.started_at: float | None = None
        self.ready_at: float | None = None
        self.last_error = ""
        self.last_line_at: float | None = None
        self._operation_lock = threading.Lock()

    def _owned_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def missing_config(self) -> list[str]:
        return [key for key in self.definition["required_env"] if not env(key)]

    def start(self) -> dict[str, Any]:
        with self._operation_lock:
            if self._owned_running():
                return {"ok": True, "state": "ALREADY_RUNNING", "service": self.key}
            external = find_external_pid(self.definition)
            if external:
                self.status = "EXTERNAL"
                return {"ok": False, "state": "EXTERNAL", "service": self.key, "pid": external}
            missing = self.missing_config()
            if missing:
                self.status = "ERROR"
                self.last_error = "缺少設定：" + ", ".join(missing)
                _emit(self.key, self.last_error)
                return {"ok": False, "state": "CONFIG_MISSING", "service": self.key, "missing": missing}
            target = Path(self.definition["target"])
            if not target.is_file():
                self.status = "ERROR"
                self.last_error = f"找不到入口：{target}"
                _emit(self.key, self.last_error)
                return {"ok": False, "state": "ENTRYPOINT_MISSING", "service": self.key}

            command = [PYTHON, "-u", str(target)]
            child_env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
            self.status = "STARTING"
            self.last_error = ""
            self.ready_at = None
            try:
                self.proc = subprocess.Popen(
                    command,
                    cwd=str(PROJECT_ROOT),
                    env=child_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    start_new_session=os.name == "posix",
                )
            except (OSError, ValueError) as exc:
                self.proc = None
                self.status = "ERROR"
                self.last_error = redact_log_line(str(exc))
                _emit(self.key, f"啟動失敗：{self.last_error}")
                return {"ok": False, "state": "START_FAILED", "service": self.key}
            self.started_at = time.time()
            _emit(self.key, f"啟動 {self.name}（pid={self.proc.pid}）")
            threading.Thread(target=self._reader, daemon=True, name=f"ap-reader-{self.key}").start()
            return {"ok": True, "state": "STARTING", "service": self.key, "pid": self.proc.pid}

    def stop(self) -> dict[str, Any]:
        with self._operation_lock:
            if not self._owned_running():
                external = find_external_pid(self.definition)
                if external:
                    self.status = "EXTERNAL"
                    return {"ok": False, "state": "EXTERNAL_NOT_OWNED", "service": self.key, "pid": external}
                self.status = "STOPPED"
                return {"ok": True, "state": "ALREADY_STOPPED", "service": self.key}
            assert self.proc is not None
            pid = self.proc.pid
            _emit(self.key, f"送出停止訊號（pid={pid}）")
            try:
                if os.name == "posix":
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                else:
                    self.proc.terminate()
                self.proc.wait(timeout=STOP_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                _emit(self.key, f"{STOP_GRACE_SECONDS} 秒未退出；終止 launcher-owned process group")
                try:
                    if os.name == "posix":
                        os.killpg(os.getpgid(pid), signal.SIGKILL)
                    else:
                        self.proc.kill()
                    self.proc.wait(timeout=3)
                except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
                    pass
            except (ProcessLookupError, OSError):
                pass
            self.status = "STOPPED"
            return {"ok": True, "state": "STOPPED", "service": self.key}

    def restart(self) -> dict[str, Any]:
        stopped = self.stop()
        if stopped.get("state") == "EXTERNAL_NOT_OWNED":
            return stopped
        return self.start()

    def _reader(self) -> None:
        proc = self.proc
        if proc is None or proc.stdout is None:
            return
        for raw in proc.stdout:
            line = redact_log_line(raw.rstrip())
            if not line:
                continue
            _emit(self.key, line)
            # A fast manual restart can leave the previous reader thread
            # draining its final lines.  Old generations may be displayed but
            # must never overwrite the new child's readiness state.
            if self.proc is not proc:
                continue
            self.last_line_at = time.time()
            if any(marker in line for marker in self.definition["ready_markers"]):
                self.status = "CONNECTED"
                self.ready_at = time.time()
            if any(marker in line for marker in self.definition["operational_markers"]):
                self.status = "ONLINE"
            if re.search(r"\b(Traceback|CRITICAL|FAILED)\b", line, re.IGNORECASE):
                self.last_error = line[:400]
                if self.status in {"STARTING", "CONNECTED"}:
                    self.status = "DEGRADED"
        return_code = proc.wait()
        if self.proc is proc:
            if self.status != "STOPPED":
                self.status = "STOPPED" if return_code in (0, -15) else "ERROR"
            if return_code not in (0, -15):
                self.last_error = f"Process exited rc={return_code}"
        _emit(self.key, f"Process exited（rc={return_code}）")

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        running = self._owned_running()
        owned_pid = self.proc.pid if running and self.proc else None
        external_pid = None if running else find_external_pid(self.definition, owned_pid)
        effective_status = self.status
        if external_pid:
            effective_status = "EXTERNAL"
        elif not running and effective_status not in {"ERROR", "STOPPED"}:
            effective_status = "STOPPED"
        elif running and effective_status == "STARTING" and self.started_at:
            if now - self.started_at > STARTUP_DEGRADED_SECONDS:
                effective_status = "DEGRADED"
        uptime = int(now - self.started_at) if running and self.started_at else 0
        missing = self.missing_config()
        return {
            "key": self.key,
            "name": self.name,
            "subtitle": self.definition["subtitle"],
            "status": effective_status,
            "color": STATUS_COLORS[effective_status],
            "running": running,
            "owned": running,
            "pid": owned_pid or external_pid,
            "uptimeSeconds": uptime,
            "readyAt": _iso_time(self.ready_at),
            "lastLineAt": _iso_time(self.last_line_at),
            "lastError": self.last_error,
            "configReady": not missing,
            "missingConfig": missing,
        }


def _iso_time(timestamp: float | None) -> str:
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


MANAGERS = {definition["key"]: ServiceManager(definition) for definition in SERVICE_DEFS}


_health_lock = threading.Lock()
_health: dict[str, dict[str, Any]] = {
    definition["key"]: {
        "discord": {"state": "PENDING", "checkedAt": "", "detail": "尚未檢查"},
        "gas": {"state": "PENDING", "checkedAt": "", "detail": "尚未檢查"}
        if definition["gas_health"] else None,
    }
    for definition in SERVICE_DEFS
}
_health_stop = threading.Event()


def _http_probe(url: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
    request = Request(url, headers=headers or {}, method="GET")
    try:
        with urlopen(request, timeout=7) as response:
            return int(response.status), response.read(1_000_000).decode("utf-8", "replace")
    except HTTPError as exc:
        return int(exc.code), ""
    except (URLError, TimeoutError, OSError) as exc:
        return 0, exc.__class__.__name__


def _probe_discord(definition: dict[str, Any]) -> dict[str, str | int]:
    checked = datetime.now(timezone.utc).isoformat()
    token = env(definition["token_env"])
    if not token:
        return {"state": "NOT_CONFIGURED", "httpCode": 0, "checkedAt": checked, "detail": "token 未設定"}
    headers = {
        "Authorization": "Bot " + token,
        "User-Agent": "DiscordBot (https://antique-pavilion, 3.0)",
    }
    identity_code, _ = _http_probe("https://discord.com/api/v10/users/@me", headers)
    if identity_code != 200:
        return {
            "state": "ERROR", "httpCode": identity_code, "checkedAt": checked,
            "detail": f"Bot identity HTTP {identity_code or 'network'}",
        }
    channel_id = definition["channel_default"]
    if definition["channel_env"]:
        channel_id = env_int(definition["channel_env"], int(channel_id))
    channel_code, _ = _http_probe(f"https://discord.com/api/v10/channels/{channel_id}", headers)
    state = "ONLINE" if channel_code == 200 else "DEGRADED"
    return {
        "state": state, "httpCode": channel_code, "checkedAt": checked,
        "detail": "Bot 與目標頻道可讀" if channel_code == 200 else f"Channel HTTP {channel_code or 'network'}",
    }


def _probe_gas() -> dict[str, str | int]:
    checked = datetime.now(timezone.utc).isoformat()
    url = env("AP_GAS_DOPOST_URL")
    if not url:
        return {"state": "NOT_CONFIGURED", "httpCode": 0, "checkedAt": checked, "detail": "AP_GAS_DOPOST_URL 未設定"}
    separator = "&" if "?" in url else "?"
    code, body = _http_probe(url + separator + "apLauncherCanary=1")
    if code != 200:
        return {"state": "ERROR", "httpCode": code, "checkedAt": checked, "detail": f"Web App HTTP {code or 'network'}"}
    try:
        payload = json.loads(body)
    except ValueError:
        return {"state": "ERROR", "httpCode": code, "checkedAt": checked, "detail": "Web App 回傳非 JSON"}
    state = "ONLINE" if isinstance(payload, dict) and payload.get("success") is True else "DEGRADED"
    return {"state": state, "httpCode": code, "checkedAt": checked, "detail": "公開 JSON 可讀" if state == "ONLINE" else "JSON 契約不完整"}


def refresh_health_once() -> dict[str, dict[str, Any]]:
    updated: dict[str, dict[str, Any]] = {}
    for definition in SERVICE_DEFS:
        updated[definition["key"]] = {
            "discord": _probe_discord(definition),
            "gas": _probe_gas() if definition["gas_health"] else None,
        }
    with _health_lock:
        _health.clear()
        _health.update(updated)
        return json.loads(json.dumps(_health))


def _health_loop() -> None:
    while not _health_stop.is_set():
        try:
            refresh_health_once()
        except Exception as exc:
            _emit("system", f"健康檢查失敗：{exc.__class__.__name__}")
        _health_stop.wait(HEALTH_INTERVAL_SECONDS)


def status_payload() -> dict[str, Any]:
    with _health_lock:
        health_copy = json.loads(json.dumps(_health))
    services = []
    for key, manager in MANAGERS.items():
        snapshot = manager.snapshot()
        snapshot["health"] = health_copy.get(key, {})
        services.append(snapshot)
    return {
        "services": services,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "loopbackOnly": BIND_HOST in LOOPBACK_HOSTS,
    }


def start_all() -> None:
    _emit("system", "依序啟動鑑定助手與 AP ORG")
    for manager in MANAGERS.values():
        manager.start()


def stop_all() -> None:
    _emit("system", "停止所有 launcher-owned AP Bot")
    for manager in MANAGERS.values():
        manager.stop()


HTML = r"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>吉寶軒 · Bot Control Center</title>
<style>
:root{--paper:#f7f4ed;--paper-deep:#ebe4d7;--ink:#2c2c2c;--muted:#746d62;--gold:#c49a45;--gold-deep:#836429;--seal:#8a2a2a;--line:rgba(78,63,42,.19);--panel:rgba(255,253,248,.86);--shadow:0 18px 48px rgba(50,39,24,.09)}
*{box-sizing:border-box}html{background:var(--paper);color:var(--ink);font-family:"Noto Serif TC","Songti TC","Microsoft JhengHei",serif}body{margin:0;min-height:100vh;background:radial-gradient(circle at 82% 0,rgba(196,154,69,.12),transparent 34rem),linear-gradient(180deg,#faf8f2,var(--paper))}
button{font:inherit}.shell{width:min(1180px,calc(100% - 36px));margin:auto;padding:38px 0 28px}.masthead{display:flex;align-items:end;justify-content:space-between;gap:24px;padding-bottom:20px;border-bottom:1px solid var(--line)}.eyebrow{font:600 11px/1.3 system-ui,sans-serif;letter-spacing:.22em;text-transform:uppercase;color:var(--gold-deep)}h1{font-size:clamp(26px,4vw,42px);font-weight:500;letter-spacing:.08em;margin:8px 0 0}.global{font:600 12px/1.4 system-ui,sans-serif;color:var(--muted);white-space:nowrap}.global b{color:var(--ink)}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}.btn{border:1px solid var(--line);background:transparent;color:var(--ink);padding:9px 14px;border-radius:2px;cursor:pointer;transition:transform .16s ease,background .16s ease,border-color .16s ease}.btn:hover{transform:translateY(-1px);border-color:var(--gold)}.btn.primary{background:var(--ink);color:var(--paper);border-color:var(--ink)}.btn.danger{color:var(--seal)}.btn:disabled{opacity:.42;cursor:not-allowed;transform:none}
.services{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.card{position:relative;overflow:hidden;background:var(--panel);border:1px solid var(--line);box-shadow:var(--shadow);padding:22px}.card:before{content:"";position:absolute;inset:0 auto 0 0;width:3px;background:var(--state,#766f64)}.card-head{display:flex;justify-content:space-between;gap:18px}.card h2{font-size:21px;font-weight:600;letter-spacing:.06em;margin:0}.subtitle{font:12px/1.6 system-ui,sans-serif;color:var(--muted);margin-top:5px}.state{font:700 11px/1 system-ui,sans-serif;letter-spacing:.12em;color:var(--state,#766f64);white-space:nowrap}.state:before{content:"●";margin-right:7px}.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:var(--line);margin:20px 0}.metric{background:rgba(255,253,248,.92);padding:11px 12px;min-width:0}.metric span{display:block;font:10px/1.3 system-ui,sans-serif;letter-spacing:.12em;color:var(--muted);text-transform:uppercase}.metric b{display:block;margin-top:6px;font:600 12px/1.45 system-ui,sans-serif;overflow-wrap:anywhere}.card-actions{display:flex;gap:8px;flex-wrap:wrap}.error{min-height:18px;margin-top:11px;color:var(--seal);font:11px/1.5 system-ui,sans-serif;overflow-wrap:anywhere}
.log-panel{margin-top:16px;border:1px solid var(--line);background:#24211d;color:#e8dfcf;box-shadow:var(--shadow)}.log-head{display:flex;align-items:center;justify-content:space-between;padding:12px 15px;border-bottom:1px solid rgba(255,255,255,.1)}.log-head strong{font-size:13px;letter-spacing:.1em}.connection{font:11px system-ui,sans-serif;color:#c8ad71}.log{height:min(37vh,390px);overflow:auto;padding:12px 15px;white-space:pre-wrap;word-break:break-word;font:11.5px/1.65 "Cascadia Code","Noto Sans Mono CJK TC",monospace}.line-intake{color:#e3c47e}.line-org{color:#c9d6bc}.line-system{color:#aaa092}.foot{display:flex;justify-content:space-between;gap:20px;margin-top:13px;color:var(--muted);font:10.5px/1.5 system-ui,sans-serif}
@media(max-width:760px){.shell{width:min(100% - 22px,1180px);padding-top:24px}.masthead{align-items:start;flex-direction:column}.services{grid-template-columns:1fr}.card{padding:18px}.metrics{grid-template-columns:1fr 1fr}.log{height:330px}.foot{flex-direction:column;gap:4px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}.btn{transition:none}.btn:hover{transform:none}}
</style>
</head>
<body><main class="shell">
<header class="masthead"><div><div class="eyebrow">Antique Pavilion · Local Operations</div><h1>吉寶軒 Bot Control Center</h1></div><div class="global" id="global">檢查本地服務中…</div></header>
<nav class="actions" aria-label="全域 Bot 控制"><button class="btn primary" onclick="globalAction('start')">啟動兩個 Bot</button><button class="btn danger" onclick="globalAction('stop')">停止 Launcher 管理的 Bot</button><button class="btn" onclick="refreshHealth()">重新檢查連線</button></nav>
<section class="services" id="services" aria-live="polite"></section>
<section class="log-panel"><div class="log-head"><strong>運行紀錄</strong><span class="connection" id="connection">連線中…</span></div><div class="log" id="log" role="log" aria-live="polite"></div></section>
<footer class="foot"><span>僅監聽 127.0.0.1 · 不顯示憑證 · 不停止外部 tmux 程序</span><span id="generated">—</span></footer>
</main>
<script>
"use strict";
const serviceRoot=document.getElementById("services"),logRoot=document.getElementById("log"),connection=document.getElementById("connection");let lineCount=0;
function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function duration(s){s=Number(s||0);const h=Math.floor(s/3600),m=Math.floor((s%3600)/60),x=s%60;return [h,m,x].map(v=>String(v).padStart(2,"0")).join(":");}
function healthLabel(h){if(!h)return"不適用";return `${h.state||"PENDING"}${h.httpCode?" · HTTP "+h.httpCode:""}`;}
function renderService(s){const h=s.health||{},external=s.status==="EXTERNAL",canStart=!s.running&&!external,canStop=s.running&&s.owned;return `<article class="card" style="--state:${esc(s.color)}"><div class="card-head"><div><h2>${esc(s.name)}</h2><div class="subtitle">${esc(s.subtitle)}</div></div><div class="state">${esc(s.status)}</div></div><div class="metrics"><div class="metric"><span>Discord</span><b>${esc(healthLabel(h.discord))}</b></div><div class="metric"><span>${s.key==="intake"?"GAS Web App":"Scheduler"}</span><b>${s.key==="intake"?esc(healthLabel(h.gas)):(s.status==="ONLINE"?"READY":"等待 ready log")}</b></div><div class="metric"><span>Process</span><b>${s.pid?"PID "+esc(s.pid):"—"}${external?" · 外部程序":""}</b></div><div class="metric"><span>Uptime</span><b>${duration(s.uptimeSeconds)}</b></div></div><div class="card-actions"><button class="btn primary" ${canStart?"":"disabled"} onclick="serviceAction('${s.key}','start')">啟動</button><button class="btn danger" ${canStop?"":"disabled"} onclick="serviceAction('${s.key}','stop')">停止</button><button class="btn" ${canStop?"":"disabled"} onclick="serviceAction('${s.key}','restart')">重新啟動</button></div><div class="error">${esc(s.lastError||(s.missingConfig?.length?"缺少設定："+s.missingConfig.join("、"):external?"由 tmux／其他終端啟動；Launcher 不會接管或停止。":""))}</div></article>`;}
async function poll(){try{const r=await fetch('/api/status',{cache:'no-store'}),d=await r.json();serviceRoot.innerHTML=d.services.map(renderService).join('');const online=d.services.filter(s=>["ONLINE","CONNECTED","EXTERNAL"].includes(s.status)).length;document.getElementById('global').innerHTML=`<b>${online}/${d.services.length}</b> 個 Bot 已連線或由外部管理`;document.getElementById('generated').textContent=`更新 ${new Date(d.generatedAt).toLocaleTimeString()}`;}catch(_){document.getElementById('global').textContent='Launcher API 無回應';}}
async function post(path){await fetch(path,{method:'POST',headers:{'X-AP-Launcher':'1'}});setTimeout(poll,250);}
function serviceAction(key,action){post(`/api/services/${key}/${action}`)}
function globalAction(action){post(`/api/${action}-all`)}
function refreshHealth(){post('/api/health/refresh')}
function appendLog(item){const line=document.createElement('div');line.className='line-'+(item.key==='intake'||item.key==='org'?item.key:'system');line.textContent=`${item.key==='system'?'SYSTEM':item.key.toUpperCase().padEnd(7)}  ${item.line}`;logRoot.appendChild(line);lineCount++;while(lineCount>1200){logRoot.firstChild.remove();lineCount--}logRoot.scrollTop=logRoot.scrollHeight;}
function connect(){const es=new EventSource('/stream');es.onopen=()=>{connection.textContent='● LIVE';connection.style.color='#9fc29e'};es.onmessage=e=>appendLog(JSON.parse(e.data));es.onerror=()=>{connection.textContent='重新連線中…';es.close();setTimeout(connect,2200)}}
poll();setInterval(poll,1000);connect();
</script></body></html>"""


def _loopback_origin_allowed(origin: str) -> bool:
    if not origin:
        return True
    try:
        return (urlsplit(origin).hostname or "") in LOOPBACK_HOSTS
    except ValueError:
        return False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path in {"/", "/index.html"}:
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/status":
            self._json(200, status_payload())
        elif path == "/stream":
            self._stream()
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if not _loopback_origin_allowed(self.headers.get("Origin", "")):
            self._json(403, {"ok": False, "error": "non-loopback origin refused"})
            return
        path = urlsplit(self.path).path
        parts = [part for part in path.split("/") if part]
        if parts == ["api", "start-all"]:
            threading.Thread(target=start_all, daemon=True).start()
            self._json(202, {"ok": True, "state": "ACCEPTED"})
        elif parts == ["api", "stop-all"]:
            threading.Thread(target=stop_all, daemon=True).start()
            self._json(202, {"ok": True, "state": "ACCEPTED"})
        elif parts == ["api", "health", "refresh"]:
            threading.Thread(target=refresh_health_once, daemon=True).start()
            self._json(202, {"ok": True, "state": "ACCEPTED"})
        elif len(parts) == 4 and parts[:2] == ["api", "services"]:
            key, action = parts[2], parts[3]
            manager = MANAGERS.get(key)
            if manager is None or action not in {"start", "stop", "restart"}:
                self._json(404, {"ok": False, "error": "unknown service or action"})
                return
            threading.Thread(target=getattr(manager, action), daemon=True).start()
            self._json(202, {"ok": True, "state": "ACCEPTED", "service": key, "action": action})
        else:
            self._json(404, {"ok": False, "error": "unknown endpoint"})

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        subscriber: Queue[dict[str, str]] = Queue(maxsize=1000)
        with _log_buffer_lock:
            history = list(_log_buffer)
        try:
            for item in history:
                self.wfile.write(("data: " + json.dumps(item, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()
        except OSError:
            return
        with _subscribers_lock:
            _subscribers.append(subscriber)
        try:
            while True:
                try:
                    item = subscriber.get(timeout=15)
                    data = "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
                    self.wfile.write(data.encode("utf-8"))
                except Empty:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except OSError:
            pass
        finally:
            with _subscribers_lock:
                if subscriber in _subscribers:
                    _subscribers.remove(subscriber)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.15)
        return sock.connect_ex((host, port)) != 0


def pick_port(host: str, preferred: int, limit: int = 11) -> int:
    for candidate in range(preferred, preferred + limit):
        if _port_available(host, candidate):
            return candidate
    raise RuntimeError(f"找不到可用 port：{preferred}–{preferred + limit - 1}")


def _open_browser(url: str) -> None:
    for command in (["cmd.exe", "/c", "start", url], ["wslview", url]):
        try:
            subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except FileNotFoundError:
            continue
    webbrowser.open(url)


def main() -> None:
    if BIND_HOST not in LOOPBACK_HOSTS:
        raise RuntimeError("AP Launcher 無驗證機制，AP_LAUNCHER_BIND_HOST 只允許 loopback")
    port = pick_port(BIND_HOST, DEFAULT_PORT)
    server = ThreadedHTTPServer((BIND_HOST, port), Handler)
    url = f"http://127.0.0.1:{port}"
    _emit("system", f"AP Bot Control Center → {url}")
    _emit("system", f"Python={PYTHON}")
    _emit("system", "等待你從 GUI 選擇要啟動的 Bot；不會自動啟動")
    if HEALTHCHECKS_ENABLED:
        threading.Thread(target=_health_loop, daemon=True, name="ap-launcher-health").start()
    else:
        _emit("system", "AP_LAUNCHER_HEALTHCHECKS=0；外部 Discord/GAS 健康探測已停用")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.6, lambda: _open_browser(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _emit("system", "Launcher 收到 Ctrl+C，停止 launcher-owned Bot")
    finally:
        _health_stop.set()
        stop_all()
        server.server_close()


if __name__ == "__main__":
    main()
