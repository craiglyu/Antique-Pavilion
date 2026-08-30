"""完工協議（Definition of Done）的機器檢查 — AGENTS.md §12。

背景：2026-08-27 的設計檢視發現，Publish/index.html 裡有 1429 行、橫跨四個
session 的改動從未提交，CHG_LOG.json 停在 2026-05-03，memory/gpt_polish_log.md
停在 2026-06-11。追查後確認：規則檔從來沒有規定「完工要記錄」——CHG_LOG.json
在 AGENTS.md 裡只出現一次，是目錄樹裡的一個標籤。

不是 agent 不守規矩，是沒有規矩可守。這個測試就是那條規矩的牙齒：
規則若只寫在 markdown 裡，下一個 agent（Claude / Codex / GPT / Grok）一樣會漏。

檢查三件事：
1. CHG_LOG.json 結構有效，且每筆 entry 具備宣告的必要欄位。
2. Publish/index.html 裡每一個 CHANGE tag，若不在 LEGACY_TAGS 凍結清單中，
   就必須出現在某一筆 CHG_LOG entry 的 change_tags 陣列裡。
3. 新增的 tag 必須符合 <前綴>-<描述> 命名格式。

要讓測試通過的做法只有一個：完工時補一筆 CHG_LOG entry。這是刻意的。

註：斷言訊息一律用英文。Windows console 預設 cp950，中文失敗訊息會變亂碼，
接手的 agent 讀不懂就等於沒有訊息。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CHG_LOG = REPO / "CHG_LOG.json"
PUBLISH = REPO / "Publish" / "index.html"

# CHG_LOG.json 的 description 欄位宣告的必要欄位。
REQUIRED_ENTRY_KEYS = {"ts", "category", "scope", "summary"}

# 檔內 CHANGE 註解的抓取樣式，同時涵蓋 HTML <!-- --> 與 CSS /* */ 兩種。
TAG_PATTERN = re.compile(
    r"CHANGE\s+([A-Za-z0-9][A-Za-z0-9_\-]*(?:\s+[A-Z0-9][A-Za-z0-9_\-]*)?)\s*[:：]"
)

# 新 tag 的命名格式：至少一個連字號，區分前綴與描述。
# 通過：R9-IMG、SOL-OBJECT-FIRST、A4-HONEST、QW6-EDGE
# 不通過：A1、D3、ROUND5、TIER A2、C5-a
CANONICAL_TAG = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")

# ── 凍結清單 ────────────────────────────────────────────────────────────
# 2026-08-27 建立協議當下，Publish/index.html 內已存在的 41 個 tag。
# 它們橫跨六種命名慣例，是協議之前的歷史產物，不追溯要求補登。
#
# ⚠️ 這份清單只能減少，不能增加。新增 tag 一律走 CHG_LOG.change_tags。
LEGACY_TAGS = frozenset(
    {
        "A1", "A2", "A3", "A4", "TIER A2", "TIER A4",
        "B1", "B2", "B3",
        "C1", "C2", "C3", "C5", "C5-a", "C5-c", "C5-d", "C6", "C8",
        "D2", "D3", "D4", "D6",
        "E1", "F2",
        "P2-BOX", "P2-LIFE", "P2-RAIL", "P2-ZOOM",
        "QW1", "QW3", "QW5",
        "R5-CONTRAST", "R5-ERA", "R5-SEMANTIC",
        "R6-LAYER", "R6-STORY",
        "R7-FONT", "R7-VARIANT",
        "R8-IMG",
        "ROUND5",
        "SOL-OBJECT-FIRST",
    }
)


def _load_log() -> dict:
    return json.loads(CHG_LOG.read_text(encoding="utf-8"))


def _tags_in_publish() -> set[str]:
    text = PUBLISH.read_text(encoding="utf-8")
    return {m.strip() for m in TAG_PATTERN.findall(text)}


def _logged_tags(log: dict) -> set[str]:
    logged: set[str] = set()
    for entry in log["entries"]:
        logged.update(entry.get("change_tags") or [])
    return logged


def test_chg_log_is_valid_and_entries_have_required_keys():
    log = _load_log()
    assert isinstance(log.get("entries"), list) and log["entries"], (
        "CHG_LOG.json has no entries"
    )

    for index, entry in enumerate(log["entries"]):
        missing = REQUIRED_ENTRY_KEYS - entry.keys()
        assert not missing, (
            f"CHG_LOG.json entries[{index}] is missing required keys {sorted(missing)}; "
            f"summary={entry.get('summary', '(none)')[:60]!r}"
        )


def test_every_new_change_tag_is_recorded_in_chg_log():
    """AGENTS.md section 12: touching Publish/index.html requires a CHG_LOG entry."""
    unlogged = _tags_in_publish() - LEGACY_TAGS - _logged_tags(_load_log())

    assert not unlogged, (
        f"{len(unlogged)} CHANGE tag(s) in Publish/index.html are not recorded in "
        f"CHG_LOG.json: {sorted(unlogged)}\n\n"
        "AGENTS.md section 12 (Definition of Done) requires three artefacts per slice: "
        "the in-file CHANGE comment, a CHG_LOG.json entry, and a commit.\n"
        "Fix: add a CHG_LOG.json entry listing these tags in its change_tags array."
    )


def test_new_change_tags_follow_naming_convention():
    """Legacy tags use six different conventions; new tags are <PREFIX>-<SLUG>."""
    offenders = sorted(
        tag
        for tag in _tags_in_publish() - LEGACY_TAGS
        if not CANONICAL_TAG.match(tag)
    )

    assert not offenders, (
        f"CHANGE tag(s) do not follow the <PREFIX>-<SLUG> convention "
        f"(uppercase, hyphen-separated): {offenders}\n"
        "Examples: R9-IMG, A4-HONEST, SOL-OBJECT-FIRST. "
        "Bare round numbers (A1, D3, ROUND5) predate the protocol and are not accepted."
    )


def test_legacy_allowlist_only_shrinks():
    """The freeze list must not become an escape hatch: every entry must still exist."""
    stale = sorted(LEGACY_TAGS - _tags_in_publish())

    if stale:
        pytest.fail(
            f"{len(stale)} tag(s) in LEGACY_TAGS no longer appear in Publish/index.html: "
            f"{stale}\nThose changes were removed; drop them from LEGACY_TAGS too "
            "— the freeze list may only shrink."
        )
