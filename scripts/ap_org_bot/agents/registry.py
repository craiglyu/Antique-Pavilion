"""AgentRegistry — yaml-driven Agent dispatch.

Replaces the if/elif chain in legacy `on_message` (ap_org_bot.py:1132-1213).
Adding a new Agent is now: (1) write prompt md, (2) write agent .py, (3) add
yaml entry — instead of editing on_message in two places.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import yaml

from ap_org_bot.infra.paths import AGENTS_CONFIG, CHANNELS_CONFIG

from .base import HeadlessAgent

log = logging.getLogger("ap_org_bot.agents.registry")


@dataclass
class ChannelBinding:
    channel_name: str          # e.g. "ap-pm"
    channel_id: int
    agent_key: Optional[str]   # which agent (if any) is bound to this channel
    trigger_prefix: Optional[str] = None   # e.g. "!agenda" for #ap-pm; None = any message


class AgentRegistry:
    """Loads agents.yaml + channels.yaml and produces channel_id → Agent lookups."""

    def __init__(self):
        self._channels: dict[int, ChannelBinding] = {}
        self._agent_keys: set[str] = set()
        self._instances: dict[str, HeadlessAgent] = {}

    def load_yaml(self) -> None:
        if not AGENTS_CONFIG.exists():
            log.warning("[registry] %s missing — no agents loaded", AGENTS_CONFIG)
            return
        if not CHANNELS_CONFIG.exists():
            log.warning("[registry] %s missing — no channel bindings", CHANNELS_CONFIG)
            return

        agents_doc = yaml.safe_load(AGENTS_CONFIG.read_text(encoding="utf-8")) or {}
        channels_doc = yaml.safe_load(CHANNELS_CONFIG.read_text(encoding="utf-8")) or {}

        # Active agents
        for entry in agents_doc.get("agents", []):
            if not entry.get("active", True):
                continue
            self._agent_keys.add(entry["key"])

        # Channel bindings
        for entry in channels_doc.get("channels", []):
            ch_id_raw = entry.get("id")
            if not ch_id_raw:
                continue
            try:
                ch_id = int(ch_id_raw)
            except (TypeError, ValueError):
                log.warning("[registry] skip channel with non-int id: %r", ch_id_raw)
                continue
            agent_key = entry.get("agent")
            if agent_key and agent_key not in self._agent_keys:
                log.warning("[registry] channel %s binds to inactive agent %s",
                            entry.get("name"), agent_key)
                agent_key = None
            self._channels[ch_id] = ChannelBinding(
                channel_name=entry.get("name", "<unnamed>"),
                channel_id=ch_id,
                agent_key=agent_key,
                trigger_prefix=entry.get("trigger_prefix"),
            )

    def register_instance(self, agent: HeadlessAgent) -> None:
        if agent.name not in self._agent_keys:
            log.debug("[registry] registering %s (not in yaml — ok if it's "
                      "internal/button-triggered)", agent.name)
        self._instances[agent.name] = agent

    def get_agent(self, key: str) -> Optional[HeadlessAgent]:
        return self._instances.get(key)

    def channel_binding(self, channel_id: int) -> Optional[ChannelBinding]:
        return self._channels.get(channel_id)

    def resolve_agent_for_channel(
        self, channel_id: int, *, message_content: str = ""
    ) -> Optional[HeadlessAgent]:
        binding = self._channels.get(channel_id)
        if binding is None or binding.agent_key is None:
            return None
        if binding.trigger_prefix:
            if not message_content.lower().startswith(binding.trigger_prefix.lower()):
                return None
        return self._instances.get(binding.agent_key)

    def channel_ids(self) -> list[int]:
        return list(self._channels.keys())

    def active_agent_keys(self) -> list[str]:
        return sorted(self._agent_keys)
