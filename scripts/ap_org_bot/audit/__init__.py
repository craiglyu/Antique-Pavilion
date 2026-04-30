"""audit/ — content-quality audit runner (blueprint v1.1 §8.4).

Sprint 2 scope: 4 rules across 4 dimensions (Brand / Compliance / Schema / Accessibility).

Sprint 3 scope (deferred):
- AP-2 形容詞堆疊偵測 (Chinese NLP — needs jieba or similar)
- AP-3 Lighthouse 4 象限分數 (run lighthouse-cli, parse JSON output)
- AP-4 Curator 信心度交叉檢查 (cross-pull pending entries vs threshold)
- AP-8 GAS 部署版本標籤檢查 (parse memory/Antique_GAS_v9_Discord.md)
- AP-9 Notion schema drift (delegated to notion_reconciler — Block 6)

The Sprint 2 4 rules are enough to ship a real auto-merge gate (blueprint §5.4):
"audit-runner-passed" label is granted when score ≥ 3.0/4 across all 4 dims.
"""

from ap_org_bot.audit.context import (
    Dimension,
    Severity,
    RuleResult,
    AuditReport,
)
from ap_org_bot.audit.rules import ALL_RULES
from ap_org_bot.audit.scoring import score_report

__all__ = [
    "Dimension",
    "Severity",
    "RuleResult",
    "AuditReport",
    "ALL_RULES",
    "score_report",
]
