"""Claude Code CLI subprocess wrapper.

Consolidates `_build_claude_cmd`, `_build_headless_cmd`, `_run_claude_cli`
previously duplicated patterns across 6 `_spawn_*_headless` functions in
legacy `ap_org_bot.py` (line 129-176, 670-1077).

Design:
- One `HeadlessClient` class with two call styles:
  - `run_with_args(...)`     — pass prompt as -p argv (legacy `_build_claude_cmd`)
  - `run_with_stdin(...)`    — pass prompt via stdin (legacy `_run_claude_cli`)
- Both return (stdout_text, stderr_text, exit_code) — caller decides how to handle.
- Auto-detects WSL on Windows; on other platforms runs claude directly.
- Each call goes through `budget_gate.check_call_allowed()` first (Sprint 0 protection).
"""

from __future__ import annotations

import asyncio
import logging
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .budget_gate import BudgetExceeded, record_call_attempt
from .paths import PROJECT_ROOT

log = logging.getLogger("ap_org_bot.claude_cli")

DEFAULT_TIMEOUT_S = 120
DEFAULT_MODEL = "claude-sonnet-4-6"


@dataclass(frozen=True)
class HeadlessResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return not self.timed_out and self.exit_code == 0 and bool(self.stdout)


def _wrap_for_windows(claude_args: list[str]) -> list[str]:
    """On Windows, run via `wsl bash -c '<cmd>'` since claude CLI lives in WSL2."""
    if platform.system() != "Windows":
        return claude_args
    inner = " ".join(f'"{a}"' if " " in a else a for a in claude_args)
    return ["wsl", "bash", "-c", inner]


class HeadlessClient:
    """Async wrapper for `claude -p` subprocess calls.

    Threading model: each call spawns its own subprocess. Caller is responsible
    for asyncio.gather / asyncio.wait_for aggregation if needed.
    """

    def __init__(
        self,
        cwd: Optional[Path] = None,
        default_model: str = DEFAULT_MODEL,
        default_timeout_s: int = DEFAULT_TIMEOUT_S,
    ):
        self.cwd = cwd or PROJECT_ROOT
        self.default_model = default_model
        self.default_timeout_s = default_timeout_s

    async def run_with_args(
        self,
        prompt: str,
        *,
        agent_name: str,
        model: Optional[str] = None,
        allowed_tools: str = "Read,Grep,Glob",
        max_turns: int = 8,
        output_format: Optional[str] = None,
        timeout_s: Optional[int] = None,
    ) -> HeadlessResult:
        """Pass prompt as `-p <prompt>` argv.

        Used by Designer / Dev / Marketing / Auto-Dev / GAS-Dev / Opus.
        Triggers budget_gate first — raises BudgetExceeded if monthly cap hit.
        """
        record_call_attempt(provider="claude_cli", agent=agent_name)

        args: list[str] = [
            "claude", "-p", prompt,
            "--model", model or self.default_model,
            "--allowedTools", allowed_tools,
            "--max-turns", str(max_turns),
        ]
        if output_format:
            args.extend(["--output-format", output_format])

        return await self._exec(_wrap_for_windows(args), stdin_input=None,
                                timeout_s=timeout_s or self.default_timeout_s,
                                agent_name=agent_name)

    async def run_with_stdin(
        self,
        prompt: str,
        *,
        agent_name: str,
        model: Optional[str] = None,
        max_turns: int = 1,
        timeout_s: Optional[int] = None,
    ) -> HeadlessResult:
        """Pass prompt via stdin. Used by Feedback PM (legacy `_run_claude_cli`)."""
        record_call_attempt(provider="claude_cli", agent=agent_name)

        args: list[str] = [
            "claude", "-p",
            "--model", model or self.default_model,
            "--max-turns", str(max_turns),
        ]
        return await self._exec(_wrap_for_windows(args),
                                stdin_input=prompt.encode("utf-8"),
                                timeout_s=timeout_s or self.default_timeout_s,
                                agent_name=agent_name)

    async def _exec(
        self,
        cmd: list[str],
        stdin_input: Optional[bytes],
        timeout_s: int,
        agent_name: str,
    ) -> HeadlessResult:
        log.info("[claude_cli] spawning %s (timeout=%ds)", agent_name, timeout_s)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if stdin_input is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.cwd),
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(input=stdin_input), timeout=timeout_s
            )
            return HeadlessResult(
                stdout=stdout_b.decode("utf-8", errors="replace").strip(),
                stderr=stderr_b.decode("utf-8", errors="replace").strip(),
                exit_code=proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            log.warning("[claude_cli] %s timed out after %ds", agent_name, timeout_s)
            return HeadlessResult(stdout="", stderr=f"timeout after {timeout_s}s",
                                  exit_code=-1, timed_out=True)
        except FileNotFoundError as e:
            log.error("[claude_cli] claude binary not found: %s", e)
            return HeadlessResult(
                stdout="", stderr=f"claude CLI not found: {e}",
                exit_code=-2,
            )
        except Exception as e:
            log.exception("[claude_cli] %s failed unexpectedly", agent_name)
            return HeadlessResult(stdout="", stderr=f"{type(e).__name__}: {e}",
                                  exit_code=-3)
