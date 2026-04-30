# `memory/ap_catchup/`

Watermark store for Sprint 2 catchup_protocol (blueprint v1.1 §8.4, fork Thor V11.1 Wave 2A).

One JSON file per SourceType. See `_schema.json` for the wire format.

## Inspection

```bash
# Programmatic:
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from ap_org_bot.handlers.catchup_protocol import WatermarkStore
import json
print(json.dumps([w.to_dict() for w in WatermarkStore().list_all()], indent=2, ensure_ascii=False))
"
```

## Sprint 2 vs Sprint 3 contract

- **Sprint 2** (this commit): WatermarkStore CRUD + on_bot_startup() audit reports
  age + active Council topic count. Read-only — does not replay missed events.
- **Sprint 3**: Active replay — re-scan #ap-feedback history since last watermark,
  reconcile Gemini quota, auto-resume Council mid-debate.

## Gitignored

`*.json` files here are runtime state, gitignored. `_schema.json` and this README
are checked in so the directory exists on every clone.
