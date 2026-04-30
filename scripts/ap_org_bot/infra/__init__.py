"""infra/ — process-wide primitives with NO Discord dependencies.

Anything in here must be importable by daemons (council_runner, audit_runner,
catchup_protocol, ...) without dragging in discord.py or the bot main loop.
"""
