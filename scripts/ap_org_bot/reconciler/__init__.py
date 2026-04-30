"""reconciler/ — declarative state reconciliation (blueprint v1.1 §6.4).

Sprint 2: drift mode only (compute diff between config/notion_desired_state.yaml
and live Notion DB schema; print + optionally file Council topic).

Sprint 3+: enforce mode (auto-PATCH live schema to match desired state in
dev/staging only).

Sprint 4+: extend to discord_reconciler (channels) + agent_registry_reconciler.

Why declarative reconciliation?
- AP has 8 Notion DBs. Manual drift detection is N-times work per change.
- Forking the framework to a new project (精品選物) means standing up 8 fresh
  DBs. Without reconciler that's hand-clicking each property in Notion UI.
- "Imperative migrations" (one-shot scripts) accumulate; reconcilers are
  idempotent and survive partial failures.

K8s Operator pattern: yaml = SoT, runtime = reconciled to match.
"""

from ap_org_bot.reconciler.notion_diff import (
    DBDiff,
    PropertyDiff,
    compute_db_diff,
    load_desired_state,
)

__all__ = [
    "DBDiff",
    "PropertyDiff",
    "compute_db_diff",
    "load_desired_state",
]
