# `ap_org_bot/` — Antique Pavilion Multi-Agent ORG Bot

Refactored package replacing the legacy `scripts/ap_org_bot.py` 1288-LoC monolith.
See [AP_Multi_Agent_ORG_Blueprint_v1.1.md](../../AP_Multi_Agent_ORG_Blueprint_v1.1.md)
for the design vision and [AP_Sustainability_Roadmap_v0.2.md](../../AP_Sustainability_Roadmap_v0.2.md)
for the 90-day execution plan.

## Layout

```
ap_org_bot/
├── infra/             # process-wide primitives, no Discord deps
│   ├── paths.py       # all filesystem paths
│   ├── env.py         # .env.antique loader
│   ├── ssl_patch.py   # opt-in enterprise SSL bypass (NOT module-level)
│   ├── claude_cli.py  # HeadlessClient — async wrapper around `claude -p`
│   ├── budget_gate.py # SQLite-backed monthly call cap (Sprint 0 hard gate)
│   └── notion_client.py # adapter to legacy notion_writer.py
├── discord_io/        # Discord output helpers (embeds, views, message split)
├── prompts/           # all 8 agent prompts as .md (separated from code)
│   ├── _core/         # framework-shared (PM, Feedback PM)
│   └── _domain/ap/    # AP-specific (Designer, Dev, Marketing, Auto-Dev, GAS, Opus)
├── agents/            # one file per agent, all extending HeadlessAgent
│   ├── base.py        # replaces 6 duplicated `_spawn_*_headless` functions
│   ├── registry.py    # yaml-driven channel → agent dispatch
│   ├── _core/         # framework-shared agent classes
│   └── _domain/ap/    # AP-specific agent classes + opus_flow.py coordinator
├── handlers/          # Discord event handlers
│   ├── message.py     # registry-driven on_message (replaces if/elif chain)
│   ├── proposal_actions.py # button approve/veto callbacks
│   ├── feedback_poll.py    # daily 11:00/20:00 cron
│   ├── feedback_state.py   # feedback_state.json load/save
│   ├── scheduler.py        # APScheduler setup
│   └── slash.py            # /veto, /sprint, /poll-now, /usage-status
├── council/           # 3-state Council pilot (Sprint 1; 9-state in Sprint 3)
│   ├── state_machine.py
│   ├── persistence.py
│   └── dispatcher.py
└── main.py            # entry point — wires up dependencies, runs bot
```

## Running

```bash
# Either entry point works (the .py shim delegates here):
python -u scripts/ap_org_bot.py
python -u scripts/ap_org_bot/main.py

# Council CLI (Sprint 1 pilot):
python -u scripts/ap_council_runner.py list
python -u scripts/ap_council_runner.py new "首頁 Hero 區方向" --type 視覺微調

# Tests:
pytest -q
pytest tests/test_council.py -v
```

## Adding a new Agent

In the legacy monolith this required editing `on_message`, adding a new
`_spawn_*_headless` function (~70 lines copy-paste), and updating slash command
authorization. Now:

1. Drop `prompts/_domain/ap/<name>.md` with frontmatter.
2. Drop `agents/_domain/ap/<name>.py` (subclass HeadlessAgent, ~20 lines).
3. Add an entry under `agents:` in `config/agents.yaml`.
4. Bind to a Discord channel in `config/channels.yaml` (or leave channel-less for button-triggered agents).
5. Register in `main.py` (one line).

No edits to `on_message` or any handler.

## Changing a prompt

Edit `prompts/<layer>/<agent>.md`, bump `prompt_version` in the frontmatter,
update `config/prompts_versioning.yaml`, restart the bot. **No `.py` edit, no
full file backup, no risk of breaking unrelated code.**

## Strangler-fig migration status

- [x] New package created and wired up (Sprint 0, 2026-04-30)
- [x] Legacy `scripts/ap_org_bot.py` is now a thin shim
- [x] Legacy 1288-LoC implementation preserved at `scripts/ap_org_bot_legacy.py`
- [ ] Run new package in production for 14 days without regressions
- [ ] Delete `ap_org_bot_legacy.py` and the three `.bak.*` files

## Sprint roadmap (vs `AP_Sustainability_Roadmap_v0.2.md`)

| Sprint | Status | Items                                                |
|--------|--------|------------------------------------------------------|
| 0      | ✅      | Bot 拆檔 + budget_gate + Council 3-state pilot      |
| 1      | 🚧      | First real Council session, dogfooding               |
| 2      | ⬜      | catchup_protocol + audit_runner                      |
| 3      | ⬜      | Council 9-state extension + notion_reconciler drift  |
| 4      | ⬜      | notion_reconciler enforce + migrations/              |
| 5      | ⬜      | Auto-merge GitHub Branch Protection                  |
