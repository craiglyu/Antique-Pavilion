# Strangler-fig migration notes

Sprint 0 refactor moved 1288-LoC `scripts/ap_org_bot.py` into the new
`scripts/ap_org_bot/` package. This file documents what changed, what to verify,
and how to roll back if something goes wrong.

## What changed (functionally)

| Behavior                              | Legacy                          | New                                               |
|--------------------------------------|---------------------------------|---------------------------------------------------|
| Run command                          | `python -u scripts/ap_org_bot.py` | Same — shim delegates to `ap_org_bot.main.main()` |
| Discord event dispatch               | Hardcoded if/elif chain         | `AgentRegistry` reads `config/channels.yaml`      |
| Agent prompts                        | Python f-strings in `.py`        | `prompts/<layer>/<agent>.md` with frontmatter     |
| SSL bypass                           | Module-level (every import)     | Opt-in via `apply_enterprise_ssl_bypass()`        |
| Budget protection                    | None                            | `budget_gate.py` SQLite hard cap before each call |
| Council state                        | None (or in `feedback_state.json`) | `memory/ap_council_state/<topic>.json`         |
| `/usage-status` source               | `feedback_state.json` count     | `budget_gate` SQLite ledger                       |
| Tests                                | None                            | 6 test files, ~40 assertions                       |

## What stayed the same

- Discord channel IDs (still hardcoded as fallback in main.py + listed in channels.yaml).
- `feedback_state.json` location and format.
- Notion DB writes (still through `notion_writer.py` — re-exported via `infra/notion_client.py`).
- Slash commands (`/veto`, `/sprint`, `/poll-now`, `/usage-status`).
- Daily poll cron times (11:00 / 20:00 Asia/Taipei).
- Opus design ruling flow (Sonnet writes DD → Opus rules).
- All 8 prompts have **identical content** to legacy — only the storage location changed.

## Verification checklist

After deploying the new package, watch for these in the first 14 days:

- [ ] `python -u scripts/ap_org_bot.py` starts cleanly (Bot logs into Discord).
- [ ] `!agenda <topic>` in #ap-pm produces a PM Sonnet response (smoke test the registry).
- [ ] Any message in #ap-marketing produces a Marketing response (smoke test for non-prefix channels).
- [ ] Daily 11:00/20:00 Feedback Poll runs and posts proposals.
- [ ] `/usage-status` shows the new per-provider breakdown (claude_cli / gemini / opus_api / notion).
- [ ] Approving a P2 visual proposal → `_spawn_auto_execute_task` equivalent fires (Auto-Dev runs).
- [ ] Approving a P2 functional proposal → GAS-Dev fires.
- [ ] An OPUS_ESCALATE button click → Opus design ruling flow completes.
- [ ] Bot survives one restart with no in-flight Council topics being lost.

## Rollback procedure

If a regression is found within the first 14 days:

```bash
# 1. Stop the bot.
# 2. Replace the shim with the legacy implementation.
mv scripts/ap_org_bot.py scripts/ap_org_bot.py.shim
mv scripts/ap_org_bot_legacy.py scripts/ap_org_bot.py

# 3. Restart the bot.
python -u scripts/ap_org_bot.py
```

The new package directory (`scripts/ap_org_bot/`) is harmless to leave in place
— nothing imports it once the legacy file is back at the original path.

## Eventual cleanup

After 14 days of stable production:

```bash
git rm scripts/ap_org_bot_legacy.py
git rm scripts/ap_org_bot.py.bak.*
```

Keep `MIGRATION.md` for institutional memory.
