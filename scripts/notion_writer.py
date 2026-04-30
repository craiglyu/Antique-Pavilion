"""
notion_writer.py — Lightweight Notion API client for AP Bot (Phase A)
吉寶軒 ORG / Authentication Bot 寫入 Notion DBs 的單向 client。

設計原則：
1. 使用 urllib（不引入新依賴）
2. Opt-in：若 NOTION_API_KEY 沒設，所有寫入函式直接 return None（不報錯）
3. 失敗 idempotent：log error 但不 crash bot
4. 同步 + 短 timeout（15s）：避免拖慢 Bot 主流程

需要的 env vars (in .env.antique):
- NOTION_API_KEY              ← 啟用開關
- NOTION_TOPICS_DB
- NOTION_DECISIONS_DB
- NOTION_KB_DB
- NOTION_AUTH_LOG_DB
- NOTION_CONTENT_CALENDAR_DB
- NOTION_INCIDENTS_DB
- NOTION_RESEARCH_BRIEFS_DB
- NOTION_AGENT_PROMPTS_DB
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger("notion_writer")

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# ── Env loader（與 ap_org_bot.py 同一機制）─────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env.antique"
_ENV: dict = {}
if _ENV_FILE.exists():
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            _ENV[k.strip()] = v.strip()
_ENV.update({k: v for k, v in os.environ.items() if v})


def _env(key: str, default: str = "") -> str:
    return _ENV.get(key, os.environ.get(key, default))


NOTION_API_KEY = _env("NOTION_API_KEY")
DB_TOPICS = _env("NOTION_TOPICS_DB")
DB_DECISIONS = _env("NOTION_DECISIONS_DB")
DB_KB = _env("NOTION_KB_DB")
DB_AUTH_LOG = _env("NOTION_AUTH_LOG_DB")
DB_CONTENT_CAL = _env("NOTION_CONTENT_CALENDAR_DB")
DB_INCIDENTS = _env("NOTION_INCIDENTS_DB")
DB_RESEARCH = _env("NOTION_RESEARCH_BRIEFS_DB")


def is_enabled() -> bool:
    """Check if Notion writes are enabled (NOTION_API_KEY is set)."""
    return bool(NOTION_API_KEY)


# ── Low-level HTTP ──────────────────────────────────────────────

def _post(path: str, payload: dict) -> Optional[dict]:
    """Sync POST to Notion API. Returns dict on success, None on failure."""
    if not NOTION_API_KEY:
        return None

    url = f"{NOTION_API_BASE}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")

    # Enterprise SSL bypass（與 ap_org_bot.py 一致的處理）
    ctx = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        log.error("[notion] HTTP %d on %s: %s", e.code, path, body)
        return None
    except Exception as e:
        log.error("[notion] %s on %s: %s", type(e).__name__, path, e)
        return None


# ── Property builders ───────────────────────────────────────────

def _title(text: str) -> dict:
    return {"title": [{"text": {"content": (text or "")[:2000]}}]}


def _rich_text(text: str) -> dict:
    return {"rich_text": [{"text": {"content": (text or "")[:2000]}}]}


def _select(name: str) -> dict:
    if not name:
        return {"select": None}
    return {"select": {"name": name}}


def _multi_select(names: list) -> dict:
    return {"multi_select": [{"name": n} for n in names if n]}


def _date(iso_str: str) -> dict:
    return {"date": {"start": iso_str}}


def _url(url: str) -> dict:
    return {"url": url if url else None}


def _number(n) -> dict:
    return {"number": n}


# ── 公開 API：每個 DB 一個 create_xxx 函式 ─────────────────────

def create_topic(
    title: str,
    type_: str = "其他",
    priority: str = "中",
    source: str = "Feedback PM",
    description: str = "",
    discord_url: str = "",
) -> Optional[str]:
    """
    寫一筆到 Topics DB。

    Args:
        title: 議題標題
        type_: "網站架構" / "視覺" / "內容策略" / "維運" / "鑑定品質" / "行銷活動" / "其他"
        priority: "高" / "中" / "低"
        source: "Craig" / "Feedback PM" / "Research" / "Agent"
        description: 議題說明
        discord_url: Discord thread / message URL

    Returns:
        page_id (str) on success, None on failure or if Notion disabled.
    """
    if not (NOTION_API_KEY and DB_TOPICS):
        return None

    payload = {
        "parent": {"database_id": DB_TOPICS},
        "properties": {
            "議題": _title(title),
            "狀態": _select("待結構化"),
            "類型": _select(type_),
            "優先級": _select(priority),
            "來源": _select(source),
            "說明": _rich_text(description),
            "Discord Thread URL": _url(discord_url),
        },
    }
    result = _post("/pages", payload)
    if result:
        log.info("[notion] ✅ Topic created: %s", title[:40])
    return result["id"] if result else None


def create_decision(
    title: str,
    signoff_status: str = "通過",
    tldr: str = "",
    recommended: str = "",
    risks: str = "",
    follow_up: str = "",
    discord_url: str = "",
    topic_id: Optional[str] = None,
) -> Optional[str]:
    """
    寫一筆到 Decisions DB。

    Args:
        signoff_status: "待簽核" / "通過" / "否決" / "重議"
        topic_id: 對應 Topics 的 page_id（若有）
    """
    if not (NOTION_API_KEY and DB_DECISIONS):
        return None

    decision_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    properties = {
        "決議": _title(title),
        "簽核狀態": _select(signoff_status),
        "決議日期": _date(decision_date),
        "TL;DR": _rich_text(tldr),
        "推薦方案": _rich_text(recommended),
        "風險": _rich_text(risks),
        "後續任務": _rich_text(follow_up),
        "Discord Thread URL": _url(discord_url),
    }

    if topic_id:
        properties["對應議題"] = {"relation": [{"id": topic_id}]}

    payload = {
        "parent": {"database_id": DB_DECISIONS},
        "properties": properties,
    }
    result = _post("/pages", payload)
    if result:
        log.info("[notion] ✅ Decision created: %s", title[:40])
    return result["id"] if result else None


def create_content_calendar(
    title: str,
    content_type: str = "社群貼文",
    status: str = "撰寫中",
    owner: str = "Marketing",
    keywords: str = "",
    notes: str = "",
    url: str = "",
) -> Optional[str]:
    """
    寫一筆到 Content Calendar DB。

    Args:
        content_type: "網站文章" / "社群貼文" / "電子報" / "Landing Page" / "其他"
        status: "構思中" / "撰寫中" / "待審" / "已排程" / "已發布" / "撤回"
        owner: "SEO" / "Editor" / "Marketing" / "PM"
    """
    if not (NOTION_API_KEY and DB_CONTENT_CAL):
        return None

    properties = {
        "標題": _title(title),
        "狀態": _select(status),
        "類型": _select(content_type),
        "負責 Agent": _select(owner),
        "目標關鍵字": _rich_text(keywords),
        "備註": _rich_text(notes),
        "URL": _url(url),
    }

    payload = {
        "parent": {"database_id": DB_CONTENT_CAL},
        "properties": properties,
    }
    result = _post("/pages", payload)
    if result:
        log.info("[notion] ✅ Content Calendar created: %s", title[:40])
    return result["id"] if result else None


def create_authentication_log(
    title: str,
    user: str = "",
    gemini_judgment: str = "",
    confidence: Optional[float] = None,
    notes: str = "",
    upload_time: Optional[str] = None,
    curator_status: str = "未審",
) -> Optional[str]:
    """
    寫一筆到 Authentication Log DB（鑑定原始紀錄）。

    Args:
        curator_status: "通過" / "待重審" / "衝突" / "退回" / "未審"
    """
    if not (NOTION_API_KEY and DB_AUTH_LOG):
        return None

    if upload_time is None:
        upload_time = datetime.now(timezone.utc).isoformat()

    properties = {
        "鑑定": _title(title),
        "上傳時間": _date(upload_time),
        "用戶": _rich_text(user),
        "Gemini 判讀": _rich_text(gemini_judgment),
        "Curator 標註": _select(curator_status),
        "備註": _rich_text(notes),
    }

    if confidence is not None:
        properties["信心度"] = _number(confidence)

    payload = {
        "parent": {"database_id": DB_AUTH_LOG},
        "properties": properties,
    }
    result = _post("/pages", payload)
    if result:
        log.info("[notion] ✅ Authentication Log created: %s", title[:40])
    return result["id"] if result else None


def create_kb_entry(
    title: str,
    dynasty: list = None,
    category: list = None,
    kiln: str = "",
    features: str = "",
    citation: str = "",
    confidence: Optional[float] = None,
    review_status: str = "待審核",
) -> Optional[str]:
    """
    寫一筆到 Knowledge Base DB（骨董條目）。

    Args:
        dynasty: 朝代清單，例 ["清", "民國"]
        category: 品類清單，例 ["瓷器", "銅器"]
        review_status: "待審核" / "通過" / "待重審" / "退回"
    """
    if not (NOTION_API_KEY and DB_KB):
        return None

    properties = {
        "條目": _title(title),
        "窯口流派": _rich_text(kiln),
        "特徵摘要": _rich_text(features),
        "出處依據": _rich_text(citation),
        "審核狀態": _select(review_status),
    }

    if dynasty:
        properties["朝代"] = _multi_select(dynasty)
    if category:
        properties["品類"] = _multi_select(category)
    if confidence is not None:
        properties["信心度"] = _number(confidence)

    payload = {
        "parent": {"database_id": DB_KB},
        "properties": properties,
    }
    result = _post("/pages", payload)
    if result:
        log.info("[notion] ✅ KB entry created: %s", title[:40])
    return result["id"] if result else None


def create_incident(
    title: str,
    severity: str = "P3 中",
    status: str = "開放",
    service: str = "其他",
    detected_time: Optional[str] = None,
    root_cause: str = "",
    resolution: str = "",
) -> Optional[str]:
    """
    寫一筆到 Incidents DB。

    Args:
        severity: "P1 緊急" / "P2 高" / "P3 中" / "P4 低"
        status: "開放" / "處理中" / "已解決" / "誤報"
        service: "Discord Bot" / "GAS" / "Gemini API" / "GitHub Pages" / 其他
    """
    if not (NOTION_API_KEY and DB_INCIDENTS):
        return None

    if detected_time is None:
        detected_time = datetime.now(timezone.utc).isoformat()

    properties = {
        "事件": _title(title),
        "嚴重度": _select(severity),
        "狀態": _select(status),
        "服務": _select(service),
        "偵測時間": _date(detected_time),
        "Root Cause": _rich_text(root_cause),
        "Resolution": _rich_text(resolution),
    }

    payload = {
        "parent": {"database_id": DB_INCIDENTS},
        "properties": properties,
    }
    result = _post("/pages", payload)
    if result:
        log.info("[notion] ✅ Incident created: %s", title[:40])
    return result["id"] if result else None


# ── Self-test ────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print(f"NOTION_API_KEY set: {is_enabled()}")
    print(f"DB Topics:           {DB_TOPICS or '(missing)'}")
    print(f"DB Decisions:        {DB_DECISIONS or '(missing)'}")
    print(f"DB Knowledge Base:   {DB_KB or '(missing)'}")
    print(f"DB Auth Log:         {DB_AUTH_LOG or '(missing)'}")
    print(f"DB Content Calendar: {DB_CONTENT_CAL or '(missing)'}")
    print(f"DB Incidents:        {DB_INCIDENTS or '(missing)'}")
    print(f"DB Research Briefs:  {DB_RESEARCH or '(missing)'}")

    if is_enabled():
        print("\n=== Smoke test: 寫一筆 dummy Topic ===")
        page_id = create_topic(
            title="[notion_writer self-test] " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            type_="其他",
            priority="低",
            source="Agent",
            description="notion_writer.py self-test，可手動刪除",
        )
        print(f"Result: {page_id}")
    else:
        print("\n（NOTION_API_KEY 未設，跳過 smoke test）")
