"""council/ — Council Protocol state machine.

Implements blueprint v1.1 §3.6 in two phases:

Sprint 1 — 3-state pilot (THIS module):
  NEW → STRUCTURED → AWAITING_SIGNOFF → {SIGNED_OFF | REJECTED}

Sprint 3 — full 9-state (later):
  NEW → STRUCTURED → PHASE1_INDEPENDENT → PHASE2_DEBATE → PHASE3_INTEGRATION →
  AWAITING_SIGNOFF → {SIGNED_OFF | REJECTED | REOPENED}

The pilot proves out:
- JSON persistence at memory/ap_council_state/<topic_id>.json
- Idempotent state transitions (safe across Bot restarts)
- Routing yaml integration (which agents would have been convened)
- Discord embed → reaction → dispatch_tasks roundtrip

Once it runs ≥ 3 real councils green, we extend to 9-state by adding
phase1/phase2/phase3 transitions in state_machine.py — the persistence and
dispatch layers stay the same.
"""

from __future__ import annotations
