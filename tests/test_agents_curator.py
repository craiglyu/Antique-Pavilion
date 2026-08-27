"""CuratorAgent: rule-based classification of Authentication Log entries.

Behaviours covered:
- Verdict R1 (退回): isValid=False, forbidden ad-tone words
- Verdict R2 (衝突): era not in 9-enum
- Verdict R3 (待重審): missing required fields
- Verdict R4 (待重審): confidence below threshold
- Verdict R5 (待重審): vague refItem/refPrice markers
- Verdict 通過: all gates pass + promote_to_kb=True
- Threshold overrides (init arg, edge cases)
- Batch reviewing + stable ordering + summary counts
- to_dict serialization shape
"""

from __future__ import annotations

import pytest

from ap_org_bot.agents._domain.ap.curator import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    FORBIDDEN_AD_TONE_WORDS,
    VALID_ERAS,
    CuratorAgent,
    CuratorReview,
    Verdict,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _good_entry(**overrides) -> dict:
    """Baseline 'should pass' entry — tests override one field at a time."""
    base = {
        "auth_log_id": "auth-test-001",
        "itemName": "粉彩穿花鳳紋瓶",
        "category": "瓷器",
        "era": "清朝",
        "confidence": 0.85,
        "story": "底款落乾隆年制四字款，胎薄釉潤。",
        "refItem": "佳士得 2018 春拍 lot 3842",
        "refPrice": "USD 120,000-180,000",
        "displayRecommendation": "玻璃罩 + 木座，正面光",
        "tags": ["官窯", "粉彩"],
        "userCaption": "朋友家收的",
        "isValid": True,
    }
    base.update(overrides)
    return base


# ── Construction / config ───────────────────────────────────────────


def test_default_threshold_is_0_8():
    assert DEFAULT_CONFIDENCE_THRESHOLD == 0.8
    assert CuratorAgent().confidence_threshold == 0.8


def test_threshold_override_accepted():
    assert CuratorAgent(confidence_threshold=0.95).confidence_threshold == 0.95


def test_invalid_threshold_raises():
    with pytest.raises(ValueError):
        CuratorAgent(confidence_threshold=1.5)
    with pytest.raises(ValueError):
        CuratorAgent(confidence_threshold=-0.1)


def test_valid_eras_count_is_9():
    assert len(VALID_ERAS) == 9
    for era in ["史前與高古", "唐宋元(含之前)", "明朝", "清朝", "民國",
                "近現代", "外國骨董", "時代不詳", "其他"]:
        assert era in VALID_ERAS


# ── R1: 退回 (rejected — gross failure) ─────────────────────────────


def test_invalid_image_returns_rejected():
    e = _good_entry(isValid=False)
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.REJECTED
    assert review.promote_to_kb is False
    assert any("isValid=False" in r for r in review.reasons)


def test_forbidden_ad_words_in_story_returns_rejected():
    e = _good_entry(story="絕世罕見的官窯精品")
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.REJECTED
    assert review.promote_to_kb is False
    assert any("廣告腔" in r or "禁用詞" in r for r in review.reasons)


def test_forbidden_word_in_tags_list_returns_rejected():
    """Tags can be a list[str] — forbidden words inside should still trigger."""
    e = _good_entry(tags=["精品", "天下無雙", "藏家好評"])
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.REJECTED


def test_invalid_takes_precedence_over_other_failures():
    """If isValid=False, that's reported even if confidence is also low."""
    e = _good_entry(isValid=False, confidence=0.3, era="火星朝")
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.REJECTED
    # Should report isValid; downstream checks short-circuited.
    assert any("isValid=False" in r for r in review.reasons)


# ── R2: 衝突 (era enum violation) ──────────────────────────────────


def test_era_not_in_enum_returns_conflict():
    e = _good_entry(era="火星朝")
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.CONFLICT
    assert review.promote_to_kb is False
    assert any("9 枚舉" in r for r in review.reasons)


def test_era_typo_extension_caught():
    """Common Gemini issue: emitting '明清' instead of just '明朝' or '清朝'."""
    e = _good_entry(era="明清")
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.CONFLICT


def test_era_in_enum_does_not_trigger_conflict():
    for era in VALID_ERAS:
        e = _good_entry(era=era)
        review = CuratorAgent().classify(e)
        # Either passes or is sent to review for OTHER reasons — but never CONFLICT.
        assert review.verdict != Verdict.CONFLICT, f"era {era!r} should not be CONFLICT"


# ── R3: 待重審 (missing required fields) ─────────────────────────────


def test_missing_item_name_pending_review():
    e = _good_entry(itemName="")
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.PENDING_REVIEW
    assert any("itemName" in r for r in review.reasons)


def test_missing_category_pending_review():
    e = _good_entry(category="   ")  # whitespace-only counts as missing
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.PENDING_REVIEW
    assert any("category" in r for r in review.reasons)


# ── R4: 待重審 (confidence below threshold) ─────────────────────────


def test_confidence_below_threshold_pending():
    e = _good_entry(confidence=0.79)
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.PENDING_REVIEW
    assert any("confidence" in r and "0.79" in r for r in review.reasons)


def test_confidence_at_threshold_passes():
    e = _good_entry(confidence=0.80)
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.PASSED


def test_confidence_missing_treated_as_zero_so_pending():
    e = _good_entry()
    e.pop("confidence")
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.PENDING_REVIEW


def test_confidence_garbage_treated_as_zero():
    e = _good_entry(confidence="not-a-number")
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.PENDING_REVIEW


def test_higher_threshold_demotes_borderline_passing_entry():
    e = _good_entry(confidence=0.83)
    strict = CuratorAgent(confidence_threshold=0.9)
    review = strict.classify(e)
    assert review.verdict == Verdict.PENDING_REVIEW


# ── R5: 待重審 (vague references) ────────────────────────────────────


def test_vague_ref_item_marker_triggers_pending():
    e = _good_entry(refItem="待補")
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.PENDING_REVIEW
    assert any("refItem" in r or "ref" in r for r in review.reasons)


def test_vague_ref_price_marker_triggers_pending():
    e = _good_entry(refPrice="未知")
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.PENDING_REVIEW


def test_vague_marker_case_insensitive():
    e = _good_entry(refItem="TBD by editor")
    review = CuratorAgent().classify(e)
    assert review.verdict == Verdict.PENDING_REVIEW


# ── 通過 (passes everything) ───────────────────────────────────────


def test_clean_entry_passes_and_recommends_kb_promotion():
    review = CuratorAgent().classify(_good_entry())
    assert review.verdict == Verdict.PASSED
    assert review.promote_to_kb is True
    assert any("≥" in r for r in review.reasons)


# ── Batch + summary ─────────────────────────────────────────────────


def test_batch_preserves_input_order():
    entries = [
        _good_entry(auth_log_id="A", confidence=0.95),
        _good_entry(auth_log_id="B", era="火星朝"),
        _good_entry(auth_log_id="C", confidence=0.5),
    ]
    reviews = CuratorAgent().review_batch(entries)
    assert [r.auth_log_id for r in reviews] == ["A", "B", "C"]
    assert reviews[0].verdict == Verdict.PASSED
    assert reviews[1].verdict == Verdict.CONFLICT
    assert reviews[2].verdict == Verdict.PENDING_REVIEW


def test_batch_empty_list_returns_empty_list():
    assert CuratorAgent().review_batch([]) == []


def test_batch_matching_image_fingerprint_routes_both_to_conflict():
    entries = [
        _good_entry(auth_log_id="A", imageFingerprint="sha256:abc123"),
        _good_entry(auth_log_id="B", imageFingerprint="SHA256:ABC123"),
    ]
    reviews = CuratorAgent().review_batch(entries)

    assert [r.verdict for r in reviews] == [Verdict.CONFLICT, Verdict.CONFLICT]
    assert all(r.promote_to_kb is False for r in reviews)
    assert "B" in reviews[0].reasons[-1]
    assert "A" in reviews[1].reasons[-1]


def test_batch_matching_drive_file_id_routes_both_to_conflict():
    entries = [
        _good_entry(
            auth_log_id="A",
            imageUrl="https://drive.google.com/file/d/abc_123-XYZ/view?usp=sharing",
        ),
        _good_entry(
            auth_log_id="B",
            imageUrl="https://drive.google.com/thumbnail?id=abc_123-XYZ&sz=w1000",
        ),
    ]
    reviews = CuratorAgent().review_batch(entries)

    assert [r.verdict for r in reviews] == [Verdict.CONFLICT, Verdict.CONFLICT]
    assert all("影像識別碼" in r.reasons[-1] for r in reviews)


def test_batch_duplicate_image_does_not_override_rejection():
    entries = [
        _good_entry(auth_log_id="bad", isValid=False, imageFingerprint="same-image"),
        _good_entry(auth_log_id="review", imageFingerprint="same-image"),
    ]
    reviews = CuratorAgent().review_batch(entries)

    assert reviews[0].verdict == Verdict.REJECTED
    assert reviews[1].verdict == Verdict.CONFLICT
    assert reviews[1].promote_to_kb is False


def test_batch_unique_or_missing_image_identity_preserves_single_item_verdicts():
    entries = [
        _good_entry(auth_log_id="A", imageFingerprint="one"),
        _good_entry(auth_log_id="B", imageFingerprint="two"),
        _good_entry(auth_log_id="C"),
    ]
    reviews = CuratorAgent().review_batch(entries)

    assert [r.verdict for r in reviews] == [Verdict.PASSED, Verdict.PASSED, Verdict.PASSED]
    assert all(r.promote_to_kb for r in reviews)


def test_summary_counts_by_verdict():
    entries = [
        _good_entry(auth_log_id="P1", confidence=0.95),
        _good_entry(auth_log_id="P2", confidence=0.92),
        _good_entry(auth_log_id="C1", era="妖獸朝"),
        _good_entry(auth_log_id="R1", confidence=0.6),
        _good_entry(auth_log_id="X1", isValid=False),
    ]
    agent = CuratorAgent()
    summary = agent.summary(agent.review_batch(entries))
    assert summary == {"通過": 2, "待重審": 1, "衝突": 1, "退回": 1}


# ── Serialization ──────────────────────────────────────────────────


def test_to_dict_round_trip_shape():
    review = CuratorAgent().classify(_good_entry())
    d = review.to_dict()
    assert set(d.keys()) == {
        "auth_log_id", "verdict", "reasons", "recommended_action", "promote_to_kb"
    }
    assert d["verdict"] == "通過"
    assert d["promote_to_kb"] is True
    assert isinstance(d["reasons"], list)


def test_review_is_immutable():
    """CuratorReview is frozen — mutating raises."""
    review = CuratorAgent().classify(_good_entry())
    with pytest.raises(Exception):  # FrozenInstanceError
        review.verdict = Verdict.REJECTED  # type: ignore[misc]
