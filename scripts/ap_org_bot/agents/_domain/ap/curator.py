"""Curator Agent — 骨董鑑定品質守門員 (Phase 1 new agent, Sprint 1).

Per blueprint v1.1 §2.11 + Sustainability Roadmap v0.2 Sprint 1 council decision
(topic ap-2026-04-30-085208-001 → recommended Curator over UX/SRE).

## Why this agent exists

Without a quality gate, every Gemini judgment flows directly into Sheets and the
public website. Low-confidence reads, era enum violations, and contradictions
with existing knowledge accumulate silently until brand integrity erodes.
The Curator is AP's "moat-keeper" — its job is to stop that drift.

## Sprint 1 scope (this file)

**Rule-based classification only**, no LLM judgment yet. Four verdicts:

| Verdict | Trigger | Routing |
|---|---|---|
| 通過       | confidence >= threshold AND era ∈ 9-enum AND no missing required fields | optional KB promotion |
| 待重審     | confidence < threshold OR refs vague                                    | ping Craig batch |
| 衝突       | era not in 9-enum                                                       | ping Craig + Librarian |
| 退回       | isValid=False from Gemini OR forbidden ad-tone words present            | log only, do NOT enter KB |

The Curator does NOT make antique authenticity calls — that's Gemini's job.
It only enforces protocol around what Gemini already produced.

## Sprint 2 scope (deferred)

- LLM judgment via HeadlessClient (claude_cli) for borderline cases
  (confidence ∈ [0.7, 0.85] where era is valid but story is contradictory)
- Cross-entry consistency check (this entry's reading vs. similar items in KB)
- Notion API query to fetch curator_status='未審' entries (currently the
  caller — ap_curator_runner.py CLI or future cron — must supply input)

## Why not subclass HeadlessAgent

HeadlessAgent's contract is "channel message → run prompt → post Discord reply".
Curator's contract is "list of dict entries → list of verdicts (+ side-effect
notifications)". Different I/O shape. Curator is closer to FeedbackPMAgent
(also non-channel-bound), and may be promoted to subclass once Sprint 2 LLM
flow stabilises.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Optional

log = logging.getLogger("ap_org_bot.agents.curator")


# ── era enum (single source of truth — must match GAS response_schema + frontend filter) ──
# Mirrors CLAUDE.md §4 and project_tech_constraints.md.
VALID_ERAS: frozenset[str] = frozenset({
    "史前與高古",
    "唐宋元(含之前)",
    "明朝",
    "清朝",
    "民國",
    "近現代",
    "外國骨董",
    "時代不詳",
    "其他",
})

# Required Notion Authentication Log fields. Missing any → 待重審 (not 退回 — these
# may be transient gaps from race conditions, not gross failures).
REQUIRED_FIELDS: frozenset[str] = frozenset({"itemName", "category", "era"})

# Ad-tone words forbidden by brand voice (from copywriting.md "Layer 1 ENFORCE list").
# Presence of any → 退回 (gross brand violation, do not enter KB).
FORBIDDEN_AD_TONE_WORDS: frozenset[str] = frozenset({
    "絕世", "典藏級", "天下無雙", "舉世罕見", "千古一見", "稀世珍寶",
})

# Vague reference terms that indicate Gemini struggled — flag 待重審.
VAGUE_REFERENCE_MARKERS: frozenset[str] = frozenset({
    "待補", "未知", "n/a", "N/A", "tbd", "TBD", "查無", "暫無",
})

DEFAULT_CONFIDENCE_THRESHOLD: float = 0.8


class Verdict(str, Enum):
    PASSED = "通過"
    PENDING_REVIEW = "待重審"
    CONFLICT = "衝突"
    REJECTED = "退回"


@dataclass(frozen=True)
class CuratorReview:
    """Per-entry result of a Curator pass."""

    auth_log_id: str
    verdict: Verdict
    reasons: list[str] = field(default_factory=list)
    recommended_action: str = ""
    promote_to_kb: bool = False

    def to_dict(self) -> dict:
        return {
            "auth_log_id": self.auth_log_id,
            "verdict": self.verdict.value,
            "reasons": list(self.reasons),
            "recommended_action": self.recommended_action,
            "promote_to_kb": self.promote_to_kb,
        }


class CuratorAgent:
    """Rule-based authentication-quality gate.

    Stateless except for the threshold (constructor arg). Safe to call from
    multiple async tasks concurrently — no shared mutable state.
    """

    name = "curator"
    prompt_name = "curator"  # used by Sprint 2 LLM judgment; loaded but not executed in Sprint 1

    def __init__(
        self,
        *,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        valid_eras: Optional[frozenset[str]] = None,
        forbidden_words: Optional[frozenset[str]] = None,
    ):
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(
                f"confidence_threshold must be in [0, 1], got {confidence_threshold}"
            )
        self.confidence_threshold = confidence_threshold
        self.valid_eras = valid_eras or VALID_ERAS
        self.forbidden_words = forbidden_words or FORBIDDEN_AD_TONE_WORDS

    # ── Public entry points ─────────────────────────────────────────

    def classify(self, entry: dict[str, Any]) -> CuratorReview:
        """Classify a single Authentication Log entry. Pure function — no I/O."""
        auth_log_id = str(
            entry.get("auth_log_id")
            or entry.get("page_id")
            or entry.get("uuid")
            or "<unknown>"
        )
        reasons: list[str] = []
        verdict = Verdict.PASSED  # optimistic default
        promote = False

        # ── Rule R1: gross failure (退回) — comes first; short-circuits everything ──
        if entry.get("isValid") is False:
            reasons.append("Gemini 標 isValid=False (圖像不可用 / 非骨董 / 仿品標示明確)")
            return CuratorReview(
                auth_log_id=auth_log_id,
                verdict=Verdict.REJECTED,
                reasons=reasons,
                recommended_action="標 Notion curator_status=退回；不入 KB",
                promote_to_kb=False,
            )

        ad_words_found = self._find_forbidden_words(entry)
        if ad_words_found:
            reasons.append(f"含廣告腔禁用詞: {', '.join(sorted(ad_words_found))}")
            return CuratorReview(
                auth_log_id=auth_log_id,
                verdict=Verdict.REJECTED,
                reasons=reasons,
                recommended_action="標 Notion curator_status=退回；通知 Editor 修文案",
                promote_to_kb=False,
            )

        # ── Rule R2: era enum violation (衝突) ──
        era = (entry.get("era") or "").strip()
        if era and era not in self.valid_eras:
            reasons.append(f"era \"{era}\" 不在 9 枚舉清單")
            return CuratorReview(
                auth_log_id=auth_log_id,
                verdict=Verdict.CONFLICT,
                reasons=reasons,
                recommended_action="標 Notion curator_status=衝突；邀 Librarian 共審",
                promote_to_kb=False,
            )

        # ── Rule R3: missing required fields (待重審) ──
        missing = [f for f in REQUIRED_FIELDS if not str(entry.get(f, "")).strip()]
        if missing:
            reasons.append(f"必填欄位缺漏: {', '.join(missing)}")
            verdict = Verdict.PENDING_REVIEW

        # ── Rule R4: confidence below threshold (待重審) ──
        confidence = self._extract_confidence(entry)
        if confidence < self.confidence_threshold:
            reasons.append(
                f"confidence {confidence:.2f} < {self.confidence_threshold} 閾值"
            )
            verdict = Verdict.PENDING_REVIEW

        # ── Rule R5: vague references (待重審) ──
        vague_in = self._find_vague_references(entry)
        if vague_in:
            reasons.append(f"refItem/refPrice 模糊: {', '.join(sorted(vague_in))}")
            verdict = Verdict.PENDING_REVIEW

        # ── Final routing ──
        if verdict == Verdict.PASSED:
            promote = True
            recommended = "通過 Curator gate；可選性 promote 到 Knowledge Base"
            reasons.append(
                f"confidence {confidence:.2f} ≥ {self.confidence_threshold}；era 在枚舉內；無模糊 ref"
            )
        else:
            recommended = "標 Notion curator_status=待重審；累積 ≥ 3 筆批次 ping Craig"

        return CuratorReview(
            auth_log_id=auth_log_id,
            verdict=verdict,
            reasons=reasons,
            recommended_action=recommended,
            promote_to_kb=promote,
        )

    def review_batch(self, entries: list[dict[str, Any]]) -> list[CuratorReview]:
        """Classify a batch and hold exact-image duplicates for human review.

        Stable order is preserved. ``imageFingerprint`` is preferred because it
        can come from a controlled image-hash job. As a fallback, matching
        Google Drive file IDs are also treated as the same uploaded image.
        This deliberately does not use image similarity or title matching:
        those require curator judgment and must not block publication here.
        """
        reviews = [self.classify(e) for e in entries]
        groups: dict[str, list[int]] = {}

        for index, entry in enumerate(entries):
            identity = self._exact_image_identity(entry)
            if identity:
                groups.setdefault(identity, []).append(index)

        for matching_indices in groups.values():
            if len(matching_indices) < 2:
                continue

            for index in matching_indices:
                review = reviews[index]
                # A gross rejection is stronger and should keep its original
                # verdict. The duplicate is still visible in the companion
                # record(s) for a human to investigate.
                if review.verdict == Verdict.REJECTED:
                    continue

                peer_ids = [
                    reviews[peer_index].auth_log_id
                    for peer_index in matching_indices
                    if peer_index != index
                ]
                duplicate_reason = (
                    "影像識別碼與另一筆資料重複: "
                    f"{', '.join(peer_ids)}；請人工確認是否同件或重複上傳"
                )
                reviews[index] = CuratorReview(
                    auth_log_id=review.auth_log_id,
                    verdict=Verdict.CONFLICT,
                    reasons=[*review.reasons, duplicate_reason],
                    recommended_action=(
                        "標 Notion curator_status=衝突；暫不公開，"
                        "人工確認同件／重複上傳後再決定保留方式"
                    ),
                    promote_to_kb=False,
                )

        return reviews

    def summary(self, reviews: list[CuratorReview]) -> dict[str, int]:
        """Return verdict counts. Useful for Discord summary message + telemetry."""
        counts = {v.value: 0 for v in Verdict}
        for r in reviews:
            counts[r.verdict.value] += 1
        return counts

    # ── Internals ───────────────────────────────────────────────────

    @staticmethod
    def _extract_confidence(entry: dict[str, Any]) -> float:
        """Extract confidence; missing or non-numeric → 0.0 (will trip threshold rule)."""
        raw = entry.get("confidence")
        if raw is None:
            return 0.0
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _exact_image_identity(entry: dict[str, Any]) -> str:
        """Return a deterministic duplicate key, or an empty string.

        ``imageFingerprint`` is intentionally opt-in: callers should provide
        a cryptographic/content hash only after their image audit. Drive IDs
        are a weaker fallback but still prove the same Drive file was supplied.
        """
        fingerprint = str(entry.get("imageFingerprint") or "").strip()
        if fingerprint:
            return f"fingerprint:{fingerprint.casefold()}"

        image_url = str(entry.get("imageUrl") or "").strip()
        if not image_url:
            return ""

        match = re.search(r"/file/d/([A-Za-z0-9_-]+)", image_url)
        if not match:
            match = re.search(r"[?&]id=([A-Za-z0-9_-]+)", image_url)
        return f"drive:{match.group(1)}" if match else ""

    def _find_forbidden_words(self, entry: dict[str, Any]) -> set[str]:
        """Search itemName + story + tags + userCaption for ad-tone words."""
        haystack_parts: list[str] = []
        for k in ("itemName", "story", "tags", "userCaption"):
            v = entry.get(k, "")
            if isinstance(v, list):
                haystack_parts.extend(str(x) for x in v)
            else:
                haystack_parts.append(str(v))
        haystack = " ".join(haystack_parts)
        return {w for w in self.forbidden_words if w in haystack}

    @staticmethod
    def _find_vague_references(entry: dict[str, Any]) -> set[str]:
        """Search refItem + refPrice + displayRecommendation for vague markers."""
        out: set[str] = set()
        for k in ("refItem", "refPrice", "displayRecommendation"):
            v = str(entry.get(k, "") or "").strip().lower()
            for marker in VAGUE_REFERENCE_MARKERS:
                if marker.lower() in v:
                    out.add(marker)
        return out
