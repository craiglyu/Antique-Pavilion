"""
Visual regression baseline capture script.
Uses Chrome CDP (via websockets) to capture viewport screenshots
at 5 breakpoints in normal + modal states, and collects perf data.

Usage:
    python3 scripts/take_baseline.py
"""

import asyncio
import base64
import json
import os
import subprocess
import sys

# Force UTF-8 stdout so Chinese/special chars don't crash on Windows cp950
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import time
from pathlib import Path
from datetime import date

import requests
import websockets

# ── paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = ROOT / "tests" / "visual" / "baseline"
REPORTS_DIR = ROOT / "reports"
BASELINE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://localhost:8000/index.html"
DEBUG_PORT = 9223
TODAY = date.today().isoformat()

# ── viewport definitions ────────────────────────────────────────────────────
VIEWPORTS = [
    {"name": "1920x1080", "width": 1920, "height": 1080, "label": "desktop-wide"},
    {"name": "1440x900",  "width": 1440, "height": 900,  "label": "desktop-standard"},
    {"name": "1024x768",  "width": 1024, "height": 768,  "label": "tablet-landscape"},
    {"name": "768x1024",  "width": 768,  "height": 1024, "label": "tablet-portrait"},
    {"name": "390x844",   "width": 390,  "height": 844,  "label": "iphone-13-14"},
]


# ── CDP helper ──────────────────────────────────────────────────────────────
class CDPSession:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self._ws = None
        self._id = 0
        self._responses: dict[int, asyncio.Future] = {}
        self._events: list[dict] = []

    async def connect(self):
        self._ws = await websockets.connect(self.ws_url, max_size=50 * 1024 * 1024)
        asyncio.create_task(self._recv_loop())

    async def _recv_loop(self):
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if "id" in msg and msg["id"] in self._responses:
                    self._responses[msg["id"]].set_result(msg)
                else:
                    self._events.append(msg)
        except Exception:
            pass

    async def send(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        mid = self._id
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._responses[mid] = fut
        payload = {"id": mid, "method": method, "params": params or {}}
        await self._ws.send(json.dumps(payload))
        result = await asyncio.wait_for(fut, timeout=30)
        del self._responses[mid]
        return result

    async def close(self):
        if self._ws:
            await self._ws.close()


# ── screenshot helper ───────────────────────────────────────────────────────
async def screenshot_png(cdp: CDPSession, path: Path):
    resp = await cdp.send("Page.captureScreenshot", {
        "format": "png",
        "fromSurface": True,
        "captureBeyondViewport": False,  # viewport only (full-page needs scrolling)
    })
    data = resp.get("result", {}).get("data", "")
    path.write_bytes(base64.b64decode(data))
    print(f"  [OK] {path.name}  ({path.stat().st_size // 1024} KB)")


async def set_viewport(cdp: CDPSession, width: int, height: int):
    await cdp.send("Emulation.setDeviceMetricsOverride", {
        "width": width,
        "height": height,
        "deviceScaleFactor": 1,
        "mobile": width < 500,
    })


async def navigate_and_wait(cdp: CDPSession, url: str, wait_ms: int = 2000):
    await cdp.send("Page.enable", {})
    await cdp.send("Page.navigate", {"url": url})
    await asyncio.sleep(wait_ms / 1000)


async def eval_js(cdp: CDPSession, expr: str) -> dict:
    resp = await cdp.send("Runtime.evaluate", {
        "expression": expr,
        "returnByValue": True,
        "awaitPromise": True,
    })
    return resp.get("result", {}).get("result", {}).get("value")


# ── perf collection ─────────────────────────────────────────────────────────
PERF_JS = """
(function() {
    const nav = performance.getEntriesByType('navigation')[0];
    const paint = performance.getEntriesByType('paint');
    const lcp = performance.getEntriesByType('largest-contentful-paint');
    const imgs = document.querySelectorAll('img');
    return {
        domInteractive: nav ? Math.round(nav.domInteractive) : null,
        domContentLoaded: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
        loadEventEnd: nav ? Math.round(nav.loadEventEnd) : null,
        transferSize: nav ? nav.transferSize : null,
        fcp: (paint.find(p => p.name === 'first-contentful-paint') || {}).startTime
            ? Math.round(paint.find(p => p.name === 'first-contentful-paint').startTime) : null,
        lcp: lcp.length ? Math.round(lcp[lcp.length - 1].startTime) : null,
        imageCount: imgs.length,
        imagesWithAlt: Array.from(imgs).filter(i => i.alt).length,
        hasCanvas: !!document.querySelector('canvas'),
        title: document.title,
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
    };
})()
"""

CONSOLE_JS = """
(function() {
    // Return any errors stored in window or document
    return {
        jsErrors: window.__capturedErrors || [],
        note: 'console.error interception requires pre-injection; run after page load'
    };
})()
"""


# ── main ────────────────────────────────────────────────────────────────────
async def main():
    # 1. Start Chrome with remote debugging
    print("Starting Chrome with remote debugging…")
    user_data = str(REPORTS_DIR / "_chrome_profile")
    proc = subprocess.Popen(
        [
            CHROME,
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={user_data}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-infobars",
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)  # wait for Chrome to start

    # 2. Get WebSocket debugger URL
    try:
        tabs = requests.get(f"http://localhost:{DEBUG_PORT}/json", timeout=5).json()
    except Exception as e:
        print(f"Failed to connect to Chrome debugger: {e}")
        proc.terminate()
        sys.exit(1)

    tab = next((t for t in tabs if t.get("type") == "page"), tabs[0])
    ws_url = tab["webSocketDebuggerUrl"]
    print(f"Connected to Chrome tab: {tab.get('title', '?')}")

    cdp = CDPSession(ws_url)
    await cdp.connect()

    perf_data = {}
    console_data = {"captured_at": TODAY, "viewports": {}}

    # 3. For each viewport: navigate → wait → screenshot normal + modal
    for vp in VIEWPORTS:
        name = vp["name"]
        w, h = vp["width"], vp["height"]
        print(f"\n--- {name} ({vp['label']}) ---")

        # Set viewport
        await set_viewport(cdp, w, h)

        # Navigate + wait for page + animations
        await navigate_and_wait(cdp, BASE_URL, wait_ms=3000)

        # Normal state screenshot
        out_normal = BASELINE_DIR / f"{name}.png"
        await screenshot_png(cdp, out_normal)

        # Collect performance at 1440x900 (representative desktop)
        if name == "1440x900":
            perf = await eval_js(cdp, PERF_JS)
            perf_data = perf or {}

        # Modal state: open modal(0) → wait for animation → screenshot
        await eval_js(cdp, "openModal(0)")
        await asyncio.sleep(0.8)  # CSS transition ~400ms
        out_modal = BASELINE_DIR / f"{name}_modal.png"
        await screenshot_png(cdp, out_modal)

        # Close modal before next viewport
        await eval_js(cdp, "closeModal()")
        await asyncio.sleep(0.3)

        # Capture console messages from this viewport
        console_info = await eval_js(cdp, CONSOLE_JS)
        console_data["viewports"][name] = console_info

    # 4. Collect console messages (network errors visible in Performance entries)
    print("\nCollecting network / resource timing…")
    resource_js = """
    (function() {
        const res = performance.getEntriesByType('resource');
        const failed = res.filter(r => r.transferSize === 0 && r.decodedBodySize === 0);
        return {
            totalResources: res.length,
            failedResources: failed.map(r => ({ name: r.name, initiatorType: r.initiatorType })),
            resourceTypes: [...new Set(res.map(r => r.initiatorType))],
        };
    })()
    """
    resource_data = await eval_js(cdp, resource_js)

    await cdp.close()
    proc.terminate()

    # 5. Write perf JSON
    perf_out = {
        "captured_at": TODAY,
        "url": BASE_URL,
        "viewport_for_perf": "1440x900",
        "metrics": perf_data,
        "resources": resource_data,
    }
    perf_path = REPORTS_DIR / f"perf_baseline_{TODAY}.json"
    perf_path.write_text(json.dumps(perf_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] Performance JSON -> {perf_path.name}")

    # 6. Write console JSON
    console_path = REPORTS_DIR / f"console_baseline_{TODAY}.json"
    console_path.write_text(json.dumps(console_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Console JSON -> {console_path.name}")

    # 7. Print summary
    print("\n-- Perf baseline summary --")
    m = perf_data or {}
    print(f"  FCP          : {m.get('fcp', 'N/A')} ms")
    print(f"  LCP          : {m.get('lcp', 'N/A')} ms")
    print(f"  DOMInteractive: {m.get('domInteractive', 'N/A')} ms")
    print(f"  LoadEvent    : {m.get('loadEventEnd', 'N/A')} ms")
    print(f"  Images       : {m.get('imageCount', 'N/A')} total  "
          f"({m.get('imagesWithAlt', 'N/A')} with alt)")
    print(f"  Has Canvas   : {m.get('hasCanvas', 'N/A')}")

    return perf_data, resource_data


if __name__ == "__main__":
    asyncio.run(main())
