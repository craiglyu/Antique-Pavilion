"""AgentRegistry: yaml load + channel resolution."""

from __future__ import annotations

import textwrap

import pytest


@pytest.fixture
def temp_registry_yaml(tmp_path, monkeypatch):
    """Create temp channels.yaml + agents.yaml and patch registry to read them."""
    cfg = tmp_path / "config"
    cfg.mkdir()

    (cfg / "agents.yaml").write_text(textwrap.dedent("""
        agents:
          - key: pm
            class: ap_org_bot.agents._core.pm.PMAgent
            active: true
          - key: marketing
            class: ap_org_bot.agents._domain.ap.marketing.MarketingAgent
            active: true
          - key: ux
            class: null
            active: false
    """).strip(), encoding="utf-8")

    (cfg / "channels.yaml").write_text(textwrap.dedent("""
        channels:
          - name: ap-pm
            id: 1001
            agent: pm
            trigger_prefix: "!agenda"
          - name: ap-marketing
            id: 1002
            agent: marketing
          - name: ap-ux
            id: 1003
            agent: ux  # bound to inactive agent — should be silently dropped
          - name: ap-feedback
            id: 1004
            agent: null
    """).strip(), encoding="utf-8")

    from ap_org_bot.infra import paths as paths_mod
    from ap_org_bot.agents import registry as registry_mod
    monkeypatch.setattr(paths_mod, "AGENTS_CONFIG", cfg / "agents.yaml")
    monkeypatch.setattr(paths_mod, "CHANNELS_CONFIG", cfg / "channels.yaml")
    monkeypatch.setattr(registry_mod, "AGENTS_CONFIG", cfg / "agents.yaml")
    monkeypatch.setattr(registry_mod, "CHANNELS_CONFIG", cfg / "channels.yaml")
    return cfg


def test_registry_loads_active_agents(temp_registry_yaml):
    from ap_org_bot.agents.registry import AgentRegistry

    r = AgentRegistry()
    r.load_yaml()
    assert "pm" in r.active_agent_keys()
    assert "marketing" in r.active_agent_keys()
    assert "ux" not in r.active_agent_keys()  # inactive


def test_inactive_agent_dropped_from_channel(temp_registry_yaml):
    from ap_org_bot.agents.registry import AgentRegistry

    r = AgentRegistry()
    r.load_yaml()
    # ap-ux channel exists but agent is inactive → resolve returns None
    assert r.channel_binding(1003) is not None
    assert r.channel_binding(1003).agent_key is None


def test_resolve_returns_none_when_no_binding(temp_registry_yaml):
    from ap_org_bot.agents.registry import AgentRegistry

    r = AgentRegistry()
    r.load_yaml()
    assert r.resolve_agent_for_channel(9999) is None  # unknown channel


def test_trigger_prefix_filters_dispatch(temp_registry_yaml):
    """A channel with trigger_prefix only dispatches when message matches it."""
    from ap_org_bot.agents.base import HeadlessAgent
    from ap_org_bot.agents.registry import AgentRegistry

    class StubAgent(HeadlessAgent):
        name = "pm"
        prompt_name = "pm"

    r = AgentRegistry()
    r.load_yaml()
    stub = StubAgent.__new__(StubAgent)  # no __init__ — we just need .name
    stub.name = "pm"
    r.register_instance(stub)

    # Message matches prefix → resolved
    resolved = r.resolve_agent_for_channel(1001, message_content="!agenda fix Hero")
    assert resolved is stub

    # Message doesn't start with prefix → not resolved
    assert r.resolve_agent_for_channel(1001, message_content="hi PM") is None


def test_no_trigger_prefix_dispatches_any_message(temp_registry_yaml):
    from ap_org_bot.agents.base import HeadlessAgent
    from ap_org_bot.agents.registry import AgentRegistry

    class StubMarketing(HeadlessAgent):
        name = "marketing"
        prompt_name = "marketing"

    r = AgentRegistry()
    r.load_yaml()
    stub = StubMarketing.__new__(StubMarketing)
    stub.name = "marketing"
    r.register_instance(stub)

    assert r.resolve_agent_for_channel(1002, message_content="anything goes") is stub


def test_channel_with_str_id_is_skipped(tmp_path, monkeypatch):
    """Channel id must be int-coercible; non-int entries are silently skipped."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "agents.yaml").write_text("agents: [{key: pm, active: true}]", encoding="utf-8")
    (cfg / "channels.yaml").write_text(
        "channels:\n  - name: bad\n    id: not-a-number\n    agent: pm\n",
        encoding="utf-8",
    )

    from ap_org_bot.agents import registry as registry_mod
    monkeypatch.setattr(registry_mod, "AGENTS_CONFIG", cfg / "agents.yaml")
    monkeypatch.setattr(registry_mod, "CHANNELS_CONFIG", cfg / "channels.yaml")

    r = registry_mod.AgentRegistry()
    r.load_yaml()
    assert r.channel_ids() == []
