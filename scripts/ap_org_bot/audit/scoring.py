"""Aggregate RuleResults → 5-dimension scores → overall pass/fail.

Score model (matches Thor V11.1 audit_runner + AP_Sustainability_Roadmap_v0.2 §3 Item 8):

For each dimension:
- Score = 4.0 if all rules in that dim pass
- Else: 4.0 - 1.0 * count(P0) - 0.5 * count(P1) - 0.25 * count(P2)
- Floor 0.0

Overall:
- Average of dimension scores (excluding dims with no rules)
- Passed if all dimensions ≥ 3.0 AND no P0 violations anywhere

The 3.0 threshold is the auto-merge gate (blueprint v1.1 §5.4):
audit_runner emits `audit-runner-passed` label only if overall passes.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from ap_org_bot.audit.context import AuditReport, Dimension, RuleResult, Severity


SEVERITY_WEIGHT: dict[Severity, float] = {
    Severity.P0: 1.0,
    Severity.P1: 0.5,
    Severity.P2: 0.25,
    Severity.P3: 0.0,  # passed rules don't dock score
}

PASS_THRESHOLD_PER_DIM = 3.0
PASS_REQUIRES_NO_P0 = True


def score_report(target: str, results: list[RuleResult]) -> AuditReport:
    """Aggregate raw results into an AuditReport with dim scores + pass/fail."""
    # Group by dimension
    by_dim: dict[Dimension, list[RuleResult]] = defaultdict(list)
    for r in results:
        by_dim[r.dimension].append(r)

    dim_scores: dict[str, float] = {}
    for dim, dim_results in by_dim.items():
        score = 4.0
        for r in dim_results:
            if not r.passed:
                score -= SEVERITY_WEIGHT.get(r.severity, 0.0)
        score = max(score, 0.0)
        dim_scores[dim.value] = round(score, 2)

    # Overall: arithmetic mean of dim scores (skip empty dims).
    overall = (
        round(sum(dim_scores.values()) / len(dim_scores), 2)
        if dim_scores else 0.0
    )

    # Pass requirement
    passed_overall = (
        all(s >= PASS_THRESHOLD_PER_DIM for s in dim_scores.values())
        and (not PASS_REQUIRES_NO_P0 or not any(
            (not r.passed) and r.severity == Severity.P0 for r in results
        ))
    )

    return AuditReport(
        target=target,
        results=list(results),
        dimension_scores=dim_scores,
        overall_score=overall,
        passed_overall=passed_overall,
        audited_at=datetime.now(timezone.utc).isoformat(),
    )
