#!/usr/bin/env python3
"""ap_audit_runner.py — content-quality audit CLI (blueprint v1.1 §8.4).

Sprint 2 ships 4 rules across 4 dimensions. CI label
`audit-runner-passed` is granted iff overall score ≥ 3.0/4 AND no P0 violations.

Run examples:

    # audit a specific file
    python3 scripts/ap_audit_runner.py audit Publish/index.html

    # audit + write JSON report
    python3 scripts/ap_audit_runner.py audit index.html --json out.json

    # CI strict mode — exit 1 if not passed
    python3 scripts/ap_audit_runner.py audit Publish/index.html --strict

    # list all rules
    python3 scripts/ap_audit_runner.py rules
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from any cwd.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from ap_org_bot.audit import (  # noqa: E402
    ALL_RULES,
    Dimension,
    RuleResult,
    Severity,
    score_report,
)


def _print_result(r: RuleResult) -> None:
    icon = "✅" if r.passed else (
        "🔴" if r.severity == Severity.P0 else
        "🟠" if r.severity == Severity.P1 else
        "🟡" if r.severity == Severity.P2 else "ℹ️"
    )
    print(f"  {icon} [{r.rule_id} {r.severity.value}] {r.rule_name} ({r.dimension.value})")
    for v in r.violations:
        print(f"        ↳ {v}")


def cmd_audit(args: argparse.Namespace) -> int:
    target = Path(args.target)
    if not target.exists():
        print(f"❌ target not found: {target}", file=sys.stderr)
        return 2

    text = target.read_text(encoding="utf-8", errors="replace")
    print(f"🔍 Auditing {target} ({len(text)} chars, {len(ALL_RULES)} rules)\n")

    rules_to_run = ALL_RULES
    if args.only:
        ids = set(args.only.split(","))
        rules_to_run = {k: v for k, v in ALL_RULES.items() if k in ids}
        if not rules_to_run:
            print(f"❌ no rules match {args.only}", file=sys.stderr)
            return 2

    results: list[RuleResult] = []
    for rule_id, rule_fn in rules_to_run.items():
        result = rule_fn(text, target_path=str(target))
        results.append(result)
        _print_result(result)

    print()
    report = score_report(str(target), results)

    print("=== dimension scores ===")
    for dim, score in report.dimension_scores.items():
        bar = "🟩" if score >= 3.5 else ("🟨" if score >= 3.0 else "🟥")
        print(f"  {bar} {dim:<14} {score}/4.00")
    print(f"  ────")
    overall_bar = "🟩" if report.overall_score >= 3.5 else (
        "🟨" if report.overall_score >= 3.0 else "🟥"
    )
    print(f"  {overall_bar} {'Overall':<14} {report.overall_score}/4.00")

    print()
    if report.passed_overall:
        print("✅ AUDIT PASSED — auto-merge label `audit-runner-passed` would be granted")
    else:
        print("❌ AUDIT FAILED — auto-merge blocked")

    if args.json:
        Path(args.json).write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n📄 Full report written to {args.json}")

    if args.strict and not report.passed_overall:
        return 1
    return 0


def cmd_rules(_args: argparse.Namespace) -> int:
    print(f"📋 {len(ALL_RULES)} rules (Sprint 2):\n")
    for rule_id, rule_fn in ALL_RULES.items():
        # Run with empty input to get dimension/name
        sample = rule_fn("", target_path="<info>")
        print(f"  {rule_id:<6} {sample.rule_name:<26} ({sample.dimension.value})")
    print(f"\nDeferred (Sprint 3): AP-2, AP-3, AP-4, AP-8, AP-9")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ap_audit_runner",
        description="AP content-quality audit (blueprint v1.1 §8.4)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("audit", help="audit a file with all (or selected) rules")
    p.add_argument("target", help="file to audit (HTML / markdown)")
    p.add_argument("--only", help="comma-separated rule IDs (e.g. AP-1,AP-7)")
    p.add_argument("--json", help="write full JSON report to this path")
    p.add_argument("--strict", action="store_true",
                   help="exit 1 if audit doesn't pass (CI mode)")

    sub.add_parser("rules", help="list all rules")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {"audit": cmd_audit, "rules": cmd_rules}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
