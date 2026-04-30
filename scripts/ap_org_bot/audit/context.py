"""Dataclasses + enums for audit rules and reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Dimension(str, Enum):
    """5 score dimensions (blueprint v1.1 §8.4 audit_runner)."""

    BRAND_TONE = "Brand Tone"
    PERFORMANCE = "Performance"  # Sprint 3 (Lighthouse)
    COMPLIANCE = "Compliance"
    ACCESSIBILITY = "Accessibility"
    SCHEMA = "Schema"


class Severity(str, Enum):
    """Same scale as impeccable-audit P0-P3."""

    P0 = "P0"  # blocking — must fix before merge
    P1 = "P1"  # major — should fix before merge
    P2 = "P2"  # minor — fix in next sprint
    P3 = "P3"  # polish — backlog


@dataclass(frozen=True)
class RuleResult:
    """One rule's verdict on one input file."""

    rule_id: str            # e.g. "AP-1"
    rule_name: str          # human-readable
    dimension: Dimension
    passed: bool            # True if NO violations
    severity: Severity      # severity if violations exist (P3 if passed)
    violations: list[str] = field(default_factory=list)
    target_path: str = ""   # which file was audited
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "dimension": self.dimension.value,
            "passed": self.passed,
            "severity": self.severity.value,
            "violations": list(self.violations),
            "target_path": self.target_path,
            "details": dict(self.details),
        }


@dataclass
class AuditReport:
    """Aggregate of all RuleResults from a single audit run."""

    target: str  # path that was audited (e.g. "Publish/index.html")
    results: list[RuleResult] = field(default_factory=list)
    dimension_scores: dict[str, float] = field(default_factory=dict)
    overall_score: float = 0.0
    passed_overall: bool = False
    audited_at: str = ""

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "results": [r.to_dict() for r in self.results],
            "dimension_scores": dict(self.dimension_scores),
            "overall_score": self.overall_score,
            "passed_overall": self.passed_overall,
            "audited_at": self.audited_at,
        }

    def violations(self) -> list[str]:
        out: list[str] = []
        for r in self.results:
            for v in r.violations:
                out.append(f"[{r.rule_id} {r.severity.value}] {v}")
        return out
