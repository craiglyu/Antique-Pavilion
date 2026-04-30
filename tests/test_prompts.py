"""prompts: each registered prompt loads and frontmatter is stripped."""

from __future__ import annotations

import pytest

from ap_org_bot.prompts import _PROMPT_PATHS, list_prompts, load_prompt


def test_list_prompts_returns_eight_entries():
    prompts = list_prompts()
    assert len(prompts) == 8
    for required in ["pm", "feedback_pm", "designer", "dev", "marketing",
                     "auto_dev", "gas_dev", "opus_design_researcher"]:
        assert required in prompts


def test_each_prompt_file_exists():
    for name, path in _PROMPT_PATHS.items():
        assert path.exists(), f"missing prompt file for {name}: {path}"


def test_each_prompt_starts_with_frontmatter():
    for name, path in _PROMPT_PATHS.items():
        raw = path.read_text(encoding="utf-8")
        assert raw.startswith("---"), f"{name} missing YAML frontmatter"


def test_load_prompt_strips_frontmatter():
    body = load_prompt("pm")
    assert not body.startswith("---")
    assert "schema_version" not in body.split("\n", 1)[0]


def test_load_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        load_prompt("nonexistent_agent")


def test_pm_prompt_contains_expected_placeholders():
    body = load_prompt("pm")
    # Must contain the placeholders the PMAgent.build_prompt_args produces.
    assert "{ticket_id}" in body
    assert "{topic}" in body
    assert "{context_block}" in body


def test_auto_dev_prompt_contains_proposal_placeholders():
    body = load_prompt("auto_dev")
    for ph in ("{ticket}", "{title}", "{problem}", "{solution}"):
        assert ph in body


def test_feedback_pm_uses_double_brace_for_literal_json():
    """Feedback PM emits a JSON template — `{` in the JSON example must be `{{`
    or str.format() would treat it as a placeholder."""
    body = load_prompt("feedback_pm")
    # Body should be safely format-able with no kwargs.
    body.format()
