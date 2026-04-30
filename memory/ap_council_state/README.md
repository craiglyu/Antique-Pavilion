# `memory/ap_council_state/`

One JSON file per Council topic. See `_schema.json` for the wire format.

This directory is **gitignored** (state file, not source) but the directory
itself + this README + `_schema.json` are checked in so the structure exists
on every clone.

## Inspection

```bash
# List all active topics:
python -u scripts/ap_council_runner.py list

# Pretty-print one topic's full state:
python -u scripts/ap_council_runner.py show ap-2026-04-30-103200-001

# Or directly:
cat memory/ap_council_state/ap-2026-04-30-103200-001.json | jq .
```

## Cleaning up

`*.json.tmp` files should never persist — they're atomic-write intermediates
that get renamed on success. If you see one, the bot crashed mid-write — safe
to delete; the previous state file is still intact.

## Schema versioning

When `schema_version` bumps in `state_machine.py`, add a migration under
`config/migrations/` (per blueprint v1.1 §6.4 + Sustainability v0.2 優化 #4).
Old topic files stay readable; the migration translates them on read.
