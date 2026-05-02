"""RealAgentInvoker — production AgentInvoker backed by HeadlessClient.

Wraps HeadlessClient.run_with_args() so CouncilDaemon can be tested with
a lightweight stub (FakeAgentInvoker) instead of a real claude CLI subprocess.

Inherits from Sprint 3's AgentInvoker base class in council.daemon, so any
isinstance() check or contract-based code keeps working.
"""

from __future__ import annotations

import logging

from ap_org_bot.council.daemon import AgentInvoker
from ap_org_bot.infra.budget_gate import BudgetExceeded
from ap_org_bot.infra.claude_cli import HeadlessClient

log = logging.getLogger("ap_org_bot.council.agent_invoker_real")


class RealAgentInvoker(AgentInvoker):
    """Production invoker: calls the claude CLI subprocess for Council agent turns.

    Returns the agent's stdout as a string (CouncilDaemon's parse_stance /
    _parse_phase3_response handle the parsing). Returns "" on failure or
    budget exceedance — the daemon then marks the agent as 中立 (neutral)
    so the council can still proceed without that voice.
    """

    def __init__(self, claude: HeadlessClient) -> None:
        self.claude = claude

    async def invoke(self, agent_name: str, prompt: str) -> str:
        """Run ``agent_name`` with ``prompt``. Returns stdout text, or "" on failure."""
        try:
            result = await self.claude.run_with_args(
                prompt,
                agent_name=agent_name,
                allowed_tools="Read,Grep,Glob",
                max_turns=8,
            )
        except BudgetExceeded:
            log.warning("[invoker] budget exceeded — skipping %s", agent_name)
            return ""
        if not result.ok:
            log.warning(
                "[invoker] %s exit_code=%d stderr=%s",
                agent_name,
                result.exit_code,
                result.stderr[:200],
            )
        return result.stdout
