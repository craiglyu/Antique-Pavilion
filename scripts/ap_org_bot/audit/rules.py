"""Audit rules — pure functions over file contents.

Each rule has signature `(text: str, *, target_path: str = "") -> RuleResult`.
No I/O. The runner (audit/runner.py) reads files and feeds content here.

Sprint 2 ships 4 rules (AP-1 / AP-5 / AP-6 / AP-7). The other 5 are stubs in
blueprint v1.1 §8.4 — Sprint 3 wires them.
"""

from __future__ import annotations

import re
from typing import Callable

from ap_org_bot.audit.context import Dimension, RuleResult, Severity


# ── AP-1: forbidden ad-tone words ───────────────────────────────────

# Single source of truth for "agency-speak" words AP brand voice forbids.
# Mirrors curator's FORBIDDEN_AD_TONE_WORDS (kept in sync deliberately —
# a violation by Editor here = Curator R1 reject for Auth Log entries).
FORBIDDEN_AD_TONE_WORDS: frozenset[str] = frozenset({
    "絕世", "典藏級", "天下無雙", "舉世罕見", "千古一見", "稀世珍寶",
    # extras specific to written content (not Auth Log entries):
    "絕無僅有", "獨步天下", "曠世奇珍", "蓋世稀有",
})


def rule_ap1_forbidden_ad_tone(text: str, *, target_path: str = "") -> RuleResult:
    """AP-1: scan for forbidden ad-tone words.

    Pure text scan — works on HTML, markdown, plain text. Uses substring match
    (no word boundary) because Chinese has no spaces.
    """
    found: list[tuple[str, int]] = []
    for word in FORBIDDEN_AD_TONE_WORDS:
        # Find all occurrences with line numbers
        for m in re.finditer(re.escape(word), text):
            line_no = text.count("\n", 0, m.start()) + 1
            found.append((word, line_no))

    violations = [f"line {ln}: 出現「{w}」" for w, ln in found]
    return RuleResult(
        rule_id="AP-1",
        rule_name="廣告腔禁用詞掃描",
        dimension=Dimension.BRAND_TONE,
        passed=len(found) == 0,
        severity=Severity.P3 if len(found) == 0 else (
            Severity.P0 if len(found) >= 3 else Severity.P1
        ),
        violations=violations,
        target_path=target_path,
        details={"matches": found, "rule_set": sorted(FORBIDDEN_AD_TONE_WORDS)},
    )


# ── AP-5: Compliance disclaimer presence ───────────────────────────

# Required disclaimer phrases for any page that displays Curator/鑑定 results.
# Either form is acceptable.
COMPLIANCE_DISCLAIMERS: tuple[str, ...] = (
    "僅供參考",
    "非鑑定書",
    "本平台所載鑑定僅供參考",
)

# Heuristic: a page "displays authentication results" if it contains any of these markers.
AUTHENTICATION_MARKERS: tuple[str, ...] = (
    "鑑定", "信心度", "authentic", "appraisal", "拍賣參考", "refItem",
)


def rule_ap5_compliance_disclaimer(
    text: str, *, target_path: str = ""
) -> RuleResult:
    """AP-5: pages with authentication content must include a disclaimer.

    If the page shows Gemini's authentication output, it MUST include either
    "僅供參考" or "非鑑定書" (or the longer form).
    Pages without authentication content auto-pass.
    """
    has_auth = any(m in text for m in AUTHENTICATION_MARKERS)
    if not has_auth:
        return RuleResult(
            rule_id="AP-5",
            rule_name="鑑定結果合規聲明檢查",
            dimension=Dimension.COMPLIANCE,
            passed=True,
            severity=Severity.P3,
            violations=[],
            target_path=target_path,
            details={"trigger": "no authentication markers — auto-pass"},
        )

    has_disclaimer = any(d in text for d in COMPLIANCE_DISCLAIMERS)
    if has_disclaimer:
        return RuleResult(
            rule_id="AP-5",
            rule_name="鑑定結果合規聲明檢查",
            dimension=Dimension.COMPLIANCE,
            passed=True,
            severity=Severity.P3,
            violations=[],
            target_path=target_path,
            details={"trigger": "disclaimer found"},
        )

    return RuleResult(
        rule_id="AP-5",
        rule_name="鑑定結果合規聲明檢查",
        dimension=Dimension.COMPLIANCE,
        passed=False,
        severity=Severity.P0,
        violations=[
            "頁面含鑑定內容但缺少「僅供參考」「非鑑定書」聲明 — "
            "違反 AP 對外宣稱政策（CLAUDE.md §5 Tier 1）"
        ],
        target_path=target_path,
        details={"required_one_of": list(COMPLIANCE_DISCLAIMERS)},
    )


# ── AP-6: Schema.org structured data presence ──────────────────────

SCHEMA_LD_JSON_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>',
    re.IGNORECASE,
)

REQUIRED_SCHEMA_TYPES: tuple[str, ...] = (
    "CollectionPage",
    "Article",
    "Product",
    "WebSite",
    "Organization",
)


def rule_ap6_schema_org(text: str, *, target_path: str = "") -> RuleResult:
    """AP-6: HTML pages should include a Schema.org JSON-LD block.

    Skip non-HTML files. For HTML, require at least one ld+json block AND at
    least one of REQUIRED_SCHEMA_TYPES name in it.
    """
    if "<html" not in text.lower() and "<!doctype html" not in text.lower():
        return RuleResult(
            rule_id="AP-6",
            rule_name="Schema.org JSON-LD 標記檢查",
            dimension=Dimension.SCHEMA,
            passed=True,
            severity=Severity.P3,
            violations=[],
            target_path=target_path,
            details={"trigger": "non-HTML — skipped"},
        )

    blocks = SCHEMA_LD_JSON_PATTERN.findall(text)
    if not blocks:
        return RuleResult(
            rule_id="AP-6",
            rule_name="Schema.org JSON-LD 標記檢查",
            dimension=Dimension.SCHEMA,
            passed=False,
            severity=Severity.P1,
            violations=["HTML 缺少任何 <script type=\"application/ld+json\"> 區塊"],
            target_path=target_path,
            details={"required_types": list(REQUIRED_SCHEMA_TYPES)},
        )

    # Check at least one schema type appears in the JSON-LD bodies.
    found_types: list[str] = []
    for stype in REQUIRED_SCHEMA_TYPES:
        if f'"{stype}"' in text or f"'{stype}'" in text:
            found_types.append(stype)

    if not found_types:
        return RuleResult(
            rule_id="AP-6",
            rule_name="Schema.org JSON-LD 標記檢查",
            dimension=Dimension.SCHEMA,
            passed=False,
            severity=Severity.P2,
            violations=[
                f"找到 {len(blocks)} 個 ld+json 區塊但都沒包含預期 schema 類型"
            ],
            target_path=target_path,
            details={
                "blocks_count": len(blocks),
                "required_one_of": list(REQUIRED_SCHEMA_TYPES),
            },
        )

    return RuleResult(
        rule_id="AP-6",
        rule_name="Schema.org JSON-LD 標記檢查",
        dimension=Dimension.SCHEMA,
        passed=True,
        severity=Severity.P3,
        violations=[],
        target_path=target_path,
        details={"blocks_count": len(blocks), "found_types": found_types},
    )


# ── AP-7: <img> alt text ───────────────────────────────────────────

IMG_TAG_PATTERN = re.compile(r"<img\s+[^>]*?>", re.IGNORECASE | re.DOTALL)
ALT_ATTR_PATTERN = re.compile(r"\balt\s*=\s*['\"]([^'\"]*)['\"]", re.IGNORECASE)


def rule_ap7_image_alt_text(text: str, *, target_path: str = "") -> RuleResult:
    """AP-7: every <img> tag must have a non-empty alt attribute (WCAG AA)."""
    if "<img" not in text.lower():
        return RuleResult(
            rule_id="AP-7",
            rule_name="圖片 alt 屬性檢查",
            dimension=Dimension.ACCESSIBILITY,
            passed=True,
            severity=Severity.P3,
            violations=[],
            target_path=target_path,
            details={"trigger": "no <img> tags"},
        )

    img_tags = IMG_TAG_PATTERN.findall(text)
    missing: list[str] = []
    empty: list[str] = []

    for tag in img_tags:
        m = ALT_ATTR_PATTERN.search(tag)
        if m is None:
            missing.append(tag[:80])
        elif not m.group(1).strip():
            empty.append(tag[:80])

    violations: list[str] = []
    if missing:
        violations.append(f"{len(missing)} 個 <img> 缺 alt 屬性")
    if empty:
        violations.append(f"{len(empty)} 個 <img> alt 為空字串")

    passed = len(violations) == 0
    return RuleResult(
        rule_id="AP-7",
        rule_name="圖片 alt 屬性檢查",
        dimension=Dimension.ACCESSIBILITY,
        passed=passed,
        severity=Severity.P3 if passed else Severity.P1,
        violations=violations,
        target_path=target_path,
        details={
            "total_imgs": len(img_tags),
            "missing_alt": len(missing),
            "empty_alt": len(empty),
            "samples_missing": missing[:3],
        },
    )


# ── AP-2: Heuristic performance check (Sprint 3) ───────────────────

# Render-blocking script pattern: <script src=...> without async or defer.
_SCRIPT_SRC_PATTERN = re.compile(
    r"<script\s+[^>]*src\s*=\s*['\"][^'\"]+['\"][^>]*>",
    re.IGNORECASE | re.DOTALL,
)
_HAS_ASYNC_OR_DEFER = re.compile(r"\b(async|defer)\b", re.IGNORECASE)

_IMG_LOADING_PATTERN = re.compile(r"<img\s+[^>]*?>", re.IGNORECASE | re.DOTALL)
_LOADING_LAZY = re.compile(r'\bloading\s*=\s*["\']lazy["\']', re.IGNORECASE)


def rule_ap2_performance_heuristic(text: str, *, target_path: str = "") -> RuleResult:
    """AP-2: heuristic Lighthouse-like check (no real browser required).

    Checks:
    - Render-blocking <script src=...> without async/defer
    - <img> tags without loading="lazy"

    Severity: P2 if render-blocking scripts exist; P3 otherwise.
    """
    if "<html" not in text.lower() and "<!doctype html" not in text.lower():
        return RuleResult(
            rule_id="AP-2",
            rule_name="效能啟發式檢查",
            dimension=Dimension.PERFORMANCE,
            passed=True,
            severity=Severity.P3,
            violations=[],
            target_path=target_path,
            details={"trigger": "non-HTML — skipped"},
        )

    scripts = _SCRIPT_SRC_PATTERN.findall(text)
    blocking = [s for s in scripts if not _HAS_ASYNC_OR_DEFER.search(s)]

    imgs = _IMG_LOADING_PATTERN.findall(text)
    no_lazy = [img for img in imgs if not _LOADING_LAZY.search(img)]

    violations: list[str] = []
    if blocking:
        violations.append(
            f"{len(blocking)} 個 <script src> 缺少 async/defer（render-blocking）"
        )
    if no_lazy and imgs:
        pct = len(no_lazy) / len(imgs) * 100
        if pct > 50:
            violations.append(
                f"{len(no_lazy)}/{len(imgs)} 張圖缺少 loading=\"lazy\""
            )

    passed = len(violations) == 0
    return RuleResult(
        rule_id="AP-2",
        rule_name="效能啟發式檢查",
        dimension=Dimension.PERFORMANCE,
        passed=passed,
        severity=Severity.P3 if passed else Severity.P2,
        violations=violations,
        target_path=target_path,
        details={
            "script_tags": len(scripts),
            "render_blocking": len(blocking),
            "imgs_total": len(imgs),
            "imgs_no_lazy": len(no_lazy),
        },
    )


# ── AP-3: Traditional Chinese language consistency (Sprint 3) ────────

# Simplified-only characters that should never appear in Traditional Chinese UI.
# These code points exist only in Simplified Chinese and are distinct from their
# Traditional counterparts.
_SIMPLIFIED_ONLY: frozenset[str] = frozenset(
    "爱来说这们为时国对发现还没关问面动们经样发该员"
)

_HTML_LANG_PATTERN = re.compile(
    r"<html[^>]*\blang\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
_TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def rule_ap3_traditional_chinese(text: str, *, target_path: str = "") -> RuleResult:
    """AP-3: Traditional Chinese brand consistency.

    Checks:
    - <html lang="zh-TW"> or lang="zh-Hant" (not zh-CN / zh)
    - <title> tag free of simplified-only characters
    """
    if "<html" not in text.lower() and "<!doctype html" not in text.lower():
        return RuleResult(
            rule_id="AP-3",
            rule_name="繁體中文語言一致性",
            dimension=Dimension.BRAND_TONE,
            passed=True,
            severity=Severity.P3,
            violations=[],
            target_path=target_path,
            details={"trigger": "non-HTML — skipped"},
        )

    violations: list[str] = []

    # Check lang attribute
    lang_match = _HTML_LANG_PATTERN.search(text)
    lang_value = lang_match.group(1).lower() if lang_match else None

    if lang_value is None:
        violations.append("<html> 缺少 lang 屬性 — 請加 lang=\"zh-TW\"")
    elif lang_value in ("zh-cn", "zh-hans"):
        violations.append(
            f"lang=\"{lang_match.group(1)}\" 為簡中標記 — 應使用 lang=\"zh-TW\" 或 zh-Hant"
        )
    elif lang_value not in ("zh-tw", "zh-hant", "zh-hant-tw"):
        violations.append(
            f"lang=\"{lang_match.group(1)}\" 未明確指定繁體 — 建議 lang=\"zh-TW\""
        )

    # Check title for simplified chars
    title_match = _TITLE_PATTERN.search(text)
    if title_match:
        title_text = re.sub(r"<[^>]+>", "", title_match.group(1))
        found_simplified = [c for c in title_text if c in _SIMPLIFIED_ONLY]
        if found_simplified:
            violations.append(
                f"<title> 包含簡體字：{''.join(set(found_simplified))}"
            )

    passed = len(violations) == 0
    severity = Severity.P3 if passed else (
        Severity.P1 if lang_value in ("zh-cn", "zh-hans") else Severity.P2
    )
    return RuleResult(
        rule_id="AP-3",
        rule_name="繁體中文語言一致性",
        dimension=Dimension.BRAND_TONE,
        passed=passed,
        severity=severity,
        violations=violations,
        target_path=target_path,
        details={"lang": lang_value, "title_checked": title_match is not None},
    )


# ── AP-4: GAS endpoint reference (Sprint 3) ─────────────────────────

# GAS Web App URLs contain this domain, and exec-URL paths follow the pattern
# /macros/s/<key>/exec. A comment or JS variable referencing it is sufficient.
_GAS_URL_PATTERN = re.compile(
    r"script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec",
    re.IGNORECASE,
)
_GAS_COMMENT_PATTERN = re.compile(r"GAS[_\s:-]?(URL|doGet|endpoint)", re.IGNORECASE)


def rule_ap4_gas_endpoint_label(text: str, *, target_path: str = "") -> RuleResult:
    """AP-4: HTML must reference the GAS doGet endpoint URL.

    Ensures the deployed file is wired to the correct GAS deployment so drift
    (wrong URL after GAS re-deploy) is caught by the audit before it reaches prod.
    Non-HTML files auto-pass.
    """
    if "<html" not in text.lower() and "<!doctype html" not in text.lower():
        return RuleResult(
            rule_id="AP-4",
            rule_name="GAS 端點版本標籤",
            dimension=Dimension.SCHEMA,
            passed=True,
            severity=Severity.P3,
            violations=[],
            target_path=target_path,
            details={"trigger": "non-HTML — skipped"},
        )

    has_gas_url = bool(_GAS_URL_PATTERN.search(text))
    has_gas_comment = bool(_GAS_COMMENT_PATTERN.search(text))

    if has_gas_url or has_gas_comment:
        return RuleResult(
            rule_id="AP-4",
            rule_name="GAS 端點版本標籤",
            dimension=Dimension.SCHEMA,
            passed=True,
            severity=Severity.P3,
            violations=[],
            target_path=target_path,
            details={"has_gas_url": has_gas_url, "has_gas_comment": has_gas_comment},
        )

    return RuleResult(
        rule_id="AP-4",
        rule_name="GAS 端點版本標籤",
        dimension=Dimension.SCHEMA,
        passed=False,
        severity=Severity.P2,
        violations=[
            "HTML 未包含 GAS doGet 端點 URL（script.google.com/macros/s/.../exec）"
            " — 部署後無法確認版本對齊"
        ],
        target_path=target_path,
        details={"has_gas_url": False, "has_gas_comment": False},
    )


# ── AP-8: SEO meta tags (Sprint 3) ──────────────────────────────────

_META_DESC_PATTERN = re.compile(
    r'<meta\s+[^>]*name\s*=\s*["\']description["\']',
    re.IGNORECASE,
)
_OG_TITLE_PATTERN = re.compile(
    r'<meta\s+[^>]*property\s*=\s*["\']og:title["\']',
    re.IGNORECASE,
)
_OG_IMAGE_PATTERN = re.compile(
    r'<meta\s+[^>]*property\s*=\s*["\']og:image["\']',
    re.IGNORECASE,
)


def rule_ap8_seo_meta_tags(text: str, *, target_path: str = "") -> RuleResult:
    """AP-8: HTML must include meta description and Open Graph tags.

    Required for gallery discoverability and social sharing preview.
    Non-HTML files auto-pass.
    """
    if "<html" not in text.lower() and "<!doctype html" not in text.lower():
        return RuleResult(
            rule_id="AP-8",
            rule_name="SEO meta / OG 標籤",
            dimension=Dimension.SCHEMA,
            passed=True,
            severity=Severity.P3,
            violations=[],
            target_path=target_path,
            details={"trigger": "non-HTML — skipped"},
        )

    missing: list[str] = []
    if not _META_DESC_PATTERN.search(text):
        missing.append("<meta name=\"description\">")
    if not _OG_TITLE_PATTERN.search(text):
        missing.append("<meta property=\"og:title\">")
    if not _OG_IMAGE_PATTERN.search(text):
        missing.append("<meta property=\"og:image\">")

    if not missing:
        return RuleResult(
            rule_id="AP-8",
            rule_name="SEO meta / OG 標籤",
            dimension=Dimension.SCHEMA,
            passed=True,
            severity=Severity.P3,
            violations=[],
            target_path=target_path,
            details={"all_present": True},
        )

    severity = Severity.P1 if len(missing) >= 2 else Severity.P2
    return RuleResult(
        rule_id="AP-8",
        rule_name="SEO meta / OG 標籤",
        dimension=Dimension.SCHEMA,
        passed=False,
        severity=severity,
        violations=[f"缺少 {t}" for t in missing],
        target_path=target_path,
        details={"missing_tags": missing},
    )


# ── Registry ────────────────────────────────────────────────────────

# Type alias for clarity
RuleFn = Callable[[str], RuleResult]

ALL_RULES: dict[str, Callable] = {
    "AP-1": rule_ap1_forbidden_ad_tone,
    "AP-2": rule_ap2_performance_heuristic,
    "AP-3": rule_ap3_traditional_chinese,
    "AP-4": rule_ap4_gas_endpoint_label,
    "AP-5": rule_ap5_compliance_disclaimer,
    "AP-6": rule_ap6_schema_org,
    "AP-7": rule_ap7_image_alt_text,
    "AP-8": rule_ap8_seo_meta_tags,
}
