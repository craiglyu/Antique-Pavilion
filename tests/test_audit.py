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
    rule_ap2_performance_heuristic,
    rule_ap3_traditional_chinese,
    rule_ap4_gas_endpoint_label,
    rule_ap5_compliance_disclaimer,
    rule_ap6_schema_org,
    rule_ap7_image_alt_text,
    rule_ap8_seo_meta_tags,
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


# ── AP-2 performance heuristic ─────────────────────────────────────


def test_ap2_non_html_skips():
    r = rule_ap2_performance_heuristic("# plain markdown")
    assert r.passed
    assert "skipped" in r.details["trigger"]


def test_ap2_no_scripts_passes():
    html = "<!doctype html><html><body><p>hello</p></body></html>"
    r = rule_ap2_performance_heuristic(html)
    assert r.passed
    assert r.details["render_blocking"] == 0


def test_ap2_render_blocking_script_p2():
    html = ('<!doctype html><html><head>'
            '<script src="app.js"></script>'
            '</head><body></body></html>')
    r = rule_ap2_performance_heuristic(html)
    assert not r.passed
    assert r.severity == Severity.P2
    assert r.details["render_blocking"] == 1


def test_ap2_deferred_script_passes():
    html = ('<!doctype html><html><head>'
            '<script src="app.js" defer></script>'
            '</head><body></body></html>')
    r = rule_ap2_performance_heuristic(html)
    assert r.passed


def test_ap2_async_script_passes():
    html = ('<!doctype html><html><head>'
            '<script src="app.js" async></script>'
            '</head><body></body></html>')
    r = rule_ap2_performance_heuristic(html)
    assert r.passed


def test_ap2_lazy_loading_flag():
    html = ('<!doctype html><html><body>'
            + '<img src="a.jpg">' * 3
            + '</body></html>')
    r = rule_ap2_performance_heuristic(html)
    # 3 imgs without lazy — > 50% → violation
    assert not r.passed
    assert r.details["imgs_no_lazy"] == 3


def test_ap2_majority_lazy_passes():
    html = ('<!doctype html><html><body>'
            '<img src="a.jpg" loading="lazy">'
            '<img src="b.jpg" loading="lazy">'
            '<img src="c.jpg">'
            '</body></html>')
    r = rule_ap2_performance_heuristic(html)
    # Only 1/3 missing lazy (33%) → under 50% threshold → pass on lazy
    assert r.passed or r.details["imgs_no_lazy"] == 1


# ── AP-3 traditional Chinese ────────────────────────────────────────


def test_ap3_non_html_skips():
    r = rule_ap3_traditional_chinese("plain text 普通文字")
    assert r.passed
    assert "skipped" in r.details["trigger"]


def test_ap3_correct_lang_passes():
    html = '<!doctype html><html lang="zh-TW"><head><title>吉寶軒</title></head></html>'
    r = rule_ap3_traditional_chinese(html)
    assert r.passed
    assert r.details["lang"] == "zh-tw"


def test_ap3_zh_hant_passes():
    html = '<!doctype html><html lang="zh-Hant"><head><title>吉寶軒</title></head></html>'
    r = rule_ap3_traditional_chinese(html)
    assert r.passed


def test_ap3_missing_lang_p2():
    html = "<!doctype html><html><head><title>吉寶軒</title></head></html>"
    r = rule_ap3_traditional_chinese(html)
    assert not r.passed
    assert r.severity == Severity.P2
    assert any("lang" in v for v in r.violations)


def test_ap3_simplified_lang_p1():
    html = '<!doctype html><html lang="zh-CN"><head><title>吉寶軒</title></head></html>'
    r = rule_ap3_traditional_chinese(html)
    assert not r.passed
    assert r.severity == Severity.P1


def test_ap3_simplified_char_in_title():
    html = '<!doctype html><html lang="zh-TW"><head><title>爱好骨董</title></head></html>'
    r = rule_ap3_traditional_chinese(html)
    assert not r.passed
    assert any("簡體字" in v for v in r.violations)


# ── AP-4 GAS endpoint label ─────────────────────────────────────────


def test_ap4_non_html_skips():
    r = rule_ap4_gas_endpoint_label("plain text")
    assert r.passed


def test_ap4_has_gas_url_passes():
    html = ('<!doctype html><html><body>'
            '<script>const GAS_URL="https://script.google.com/macros/s/AKfycbXXX/exec";</script>'
            '</body></html>')
    r = rule_ap4_gas_endpoint_label(html)
    assert r.passed
    assert r.details["has_gas_url"] is True


def test_ap4_gas_comment_passes():
    html = ('<!doctype html><html><body>'
            '<!-- GAS_URL: https://script.google.com/macros/s/AKfy/exec -->'
            '</body></html>')
    r = rule_ap4_gas_endpoint_label(html)
    assert r.passed
    assert r.details["has_gas_url"] is True


def test_ap4_missing_gas_reference_p2():
    html = "<!doctype html><html><body><p>no GAS reference</p></body></html>"
    r = rule_ap4_gas_endpoint_label(html)
    assert not r.passed
    assert r.severity == Severity.P2


def test_ap4_gas_comment_keyword_passes():
    html = ('<!doctype html><html><body>'
            '<!-- GAS doGet endpoint wired above -->'
            '</body></html>')
    r = rule_ap4_gas_endpoint_label(html)
    assert r.passed
    assert r.details["has_gas_comment"] is True


# ── AP-8 SEO meta tags ──────────────────────────────────────────────


def test_ap8_non_html_skips():
    r = rule_ap8_seo_meta_tags("plain text")
    assert r.passed


def test_ap8_all_tags_present_passes():
    html = """<!doctype html><html><head>
<meta name="description" content="吉寶軒骨董展示">
<meta property="og:title" content="吉寶軒">
<meta property="og:image" content="https://example.com/img.jpg">
</head></html>"""
    r = rule_ap8_seo_meta_tags(html)
    assert r.passed
    assert r.details["all_present"] is True


def test_ap8_missing_description_p2():
    html = """<!doctype html><html><head>
<meta property="og:title" content="吉寶軒">
<meta property="og:image" content="https://example.com/img.jpg">
</head></html>"""
    r = rule_ap8_seo_meta_tags(html)
    assert not r.passed
    assert r.severity == Severity.P2
    assert any("description" in v for v in r.violations)


def test_ap8_two_missing_p1():
    html = '<!doctype html><html><head><title>only title</title></head></html>'
    r = rule_ap8_seo_meta_tags(html)
    assert not r.passed
    assert r.severity == Severity.P1
    assert len(r.details["missing_tags"]) >= 2


def test_ap8_og_image_only_violation():
    html = """<!doctype html><html><head>
<meta name="description" content="desc">
<meta property="og:title" content="title">
</head></html>"""
    r = rule_ap8_seo_meta_tags(html)
    assert not r.passed
    assert any("og:image" in v for v in r.violations)


# ── ALL_RULES registry ─────────────────────────────────────────────


def test_all_rules_registry_has_8_entries():
    assert len(ALL_RULES) == 8
    assert {"AP-1", "AP-2", "AP-3", "AP-4", "AP-5", "AP-6", "AP-7", "AP-8"} == set(ALL_RULES.keys())


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
