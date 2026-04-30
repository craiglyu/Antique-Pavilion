"""ap_org_bot.py — thin entry shim for the refactored bot package.

The legacy 1288-line monolith has been replaced by `scripts/ap_org_bot/` package.
This file preserves the historical run path:

    python -u scripts/ap_org_bot.py

so existing scripts / autostart / cron / docs continue to work without changes.

If you need to inspect the previous monolithic implementation for reference, see
`scripts/ap_org_bot_legacy.py` (kept for the duration of the strangler-fig
migration, deletable once the new package has run for ~14 days without regressions).

To run the bot:
    python -u scripts/ap_org_bot.py        # this shim
    python -u scripts/ap_org_bot/main.py   # equivalent direct entry
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `ap_org_bot` package importable regardless of CWD.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ap_org_bot.main import main  # noqa: E402

if __name__ == "__main__":
    main()
