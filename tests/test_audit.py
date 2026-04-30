"""audit/ rules + scoring — pure-function tests, no I/O."""

from __future__ import annotations

import pytest

from ap_org_bot.audit import (
    ALL_RULES,
    AuditReport,
    Dimension,
    RuleResult,
    Severity,
    score_report,
)
from ap_org_bot.audit.rules import (
    FORBIDDEN_AD_TONE_WORDS,
    rule_ap1_forbidden_ad_tone,
    rule_ap5_compliance_disclaimer,
    rule_ap6_schema_org,
    rule_ap7_image_alt_text,
)


# ── AP-1 ad-tone scan ───────────────────────────────────────────────


def test_ap1_clean_text_passes():
    r = rule_ap1_forbidden_ad_tone("這是一件清乾隆青花，胎薄釉潤")
    assert r.passed is True
    assert r.dimension == Dimension.BRAND_TONE
    assert r.violations == []


def test_ap1_single_match_p1():
    r = rule_ap1_forbidden_ad_tone("這件絕世珍品")
    assert not r.passed
    assert r.severity == Severity.P1
    assert any("絕世" in v for v in r.violations)


def test_ap1_three_matches_p0():
    r = rule_ap1_forbidden_ad_tone("絕世天下無雙稀世珍寶")
    assert not r.passed
    assert r.severity == Severity.P0


def test_ap1_reports_line_numbers():
    text = "首段\n\n這是絕世\n第三段"
    r = rule_ap1_forbidden_ad_tone(text)
    assert any("line 3" in v for v in r.violations)


def test_ap1_rule_set_in_details():
    r = rule_ap1_forbidden_ad_tone("clean")
    assert set(r.details["rule_set"]) == FORBIDDEN_AD_TONE_WORDS


# ── AP-5 compliance disclaimer ──────────────────────────────────────


def test_ap5_no_auth_content_passes():
    r = rule_ap5_compliance_disclaimer("這是普通頁面，講設計與美學")
    assert r.passed
    assert r.dimension == Dimension.COMPLIANCE


def test_ap5_auth_content_with_disclaimer_passes():
    text = "Gemini 鑑定結果顯示信心度 0.85。本平台所載僅供參考。"
    r = rule_ap5_compliance_disclaimer(text)
    assert r.passed


def test_ap5_auth_without_disclaimer_p0():
    text = "鑑定結果：清乾隆官窯，信心度 0.92"
    r = rule_ap5_compliance_disclaimer(text)
    assert not r.passed
    assert r.severity == Severity.P0
    assert "僅供參考" in r.details["required_one_of"]


def test_ap5_alt_disclaimer_phrase_accepted():
    text = "鑑定信心度 0.7。非鑑定書，僅作參考"
    r = rule_ap5_compliance_disclaimer(text)
    assert r.passed


# ── AP-6 schema.org ────────────────────────────────────────────────


def test_ap6_non_html_skips():
    r = rule_ap6_schema_org("# Markdown content\n\nPlain text.")
    assert r.passed
    assert "skipped" in r.details["trigger"]


def test_ap6_html_no_jsonld_p1():
    text = "<!doctype html><html><body>nothing</body></html>"
    r = rule_ap6_schema_org(text)
    assert not r.passed
    assert r.severity == Severity.P1


def test_ap6_jsonld_with_collection_page_passes():
    text = """<!doctype html>
<html><head>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "CollectionPage", "name": "..."}
</script>
</head><body></body></html>"""
    r = rule_ap6_schema_org(text)
    assert r.passed
    assert "CollectionPage" in r.details["found_types"]


def test_ap6_jsonld_without_recognised_type_p2():
    text = """<!doctype html>
<html><head>
<script type="application/ld+json">{"@type": "RandomThing"}</script>
</head></html>"""
    r = rule_ap6_schema_org(text)
    assert not r.passed
    assert r.severity == Severity.P2


# ── AP-7 img alt text ──────────────────────────────────────────────


def test_ap7_no_imgs_passes():
    r = rule_ap7_image_alt_text("<html><body>no images</body></html>")
    assert r.passed
    assert r.dimension == Dimension.ACCESSIBILITY


def test_ap7_all_imgs_with_alt_passes():
    text = '<img src="a.jpg" alt="清青花瓶"><img src="b.jpg" alt="銅爐">'
    r = rule_ap7_image_alt_text(text)
    assert r.passed
    assert r.details["total_imgs"] == 2


def test_ap7_missing_alt_p1():
    text = '<img src="a.jpg" alt="ok"><img src="b.jpg">'
    r = rule_ap7_image_alt_text(text)
    assert not r.passed
    assert r.severity == Severity.P1
    assert r.details["missing_alt"] == 1


def test_ap7_empty_alt_flagged():
    text = '<img src="a.jpg" alt="">'
    r = rule_ap7_image_alt_text(text)
    assert not r.passed
    assert r.details["empty_alt"] == 1


# ── ALL_RULES registry ─────────────────────────────────────────────


def test_all_rules_registry_has_4_entries():
    assert len(ALL_RULES) == 4
    assert {"AP-1", "AP-5", "AP-6", "AP-7"} == set(ALL_RULES.keys())


def test_all_rules_callable_with_empty_input():
    """Every registered rule must handle empty input without crashing."""
    for rule_id, fn in ALL_RULES.items():
        result = fn("", target_path="<test>")
        assert result.rule_id == rule_id


# ── score_report aggregation ───────────────────────────────────────


def _passing_result(rid: str, dim: Dimension) -> RuleResult:
    return RuleResult(
        rule_id=rid, rule_name=rid, dimension=dim,
        passed=True, severity=Severity.P3,
    )


def _failing_result(rid: str, dim: Dimension, sev: Severity) -> RuleResult:
    return RuleResult(
        rule_id=rid, rule_name=rid, dimension=dim,
        passed=False, severity=sev, violations=["test violation"],
    )


def test_all_passing_overall_4_0():
    results = [
        _passing_result("AP-1", Dimension.BRAND_TONE),
        _passing_result("AP-5", Dimension.COMPLIANCE),
        _passing_result("AP-6", Dimension.SCHEMA),
        _passing_result("AP-7", Dimension.ACCESSIBILITY),
    ]
    report = score_report("/test", results)
    assert report.overall_score == 4.0
    assert report.passed_overall is True
    assert all(s == 4.0 for s in report.dimension_scores.values())


def test_p1_violation_drops_dim_score():
    results = [
        _failing_result("AP-7", Dimension.ACCESSIBILITY, Severity.P1),
    ]
    report = score_report("/test", results)
    assert report.dimension_scores["Accessibility"] == 3.5  # 4.0 - 0.5


def test_p0_violation_blocks_overall_pass():
    results = [
        _failing_result("AP-5", Dimension.COMPLIANCE, Severity.P0),
        _passing_result("AP-1", Dimension.BRAND_TONE),
    ]
    report = score_report("/test", results)
    assert report.passed_overall is False  # P0 anywhere blocks


def test_overall_below_3_0_blocks():
    """Multiple P0/P1 in one dim drops it < 3.0 → fail even if no single P0."""
    results = [
        _failing_result("AP-1", Dimension.BRAND_TONE, Severity.P1),
        _failing_result("AP-1b", Dimension.BRAND_TONE, Severity.P1),
        _failing_result("AP-1c", Dimension.BRAND_TONE, Severity.P1),
    ]
    report = score_report("/test", results)
    assert report.dimension_scores["Brand Tone"] == 2.5  # 4 - 1.5
    assert report.passed_overall is False


def test_violations_method_concatenates_all_failures():
    results = [
        _failing_result("AP-7", Dimension.ACCESSIBILITY, Severity.P1),
        _passing_result("AP-1", Dimension.BRAND_TONE),
    ]
    report = score_report("/test", results)
    violations = report.violations()
    assert len(violations) == 1
    assert "AP-7" in violations[0]
    assert "P1" in violations[0]
