---
id: skill_audit
type: skill
layer: core
loaded_by: [Audit, Designer]
version: v0.1
schema_version: 1
last_updated: 2026-04-28
change_notes: "初版 — Impeccable 5 維度評分（slash command 快版）"
---

# /audit — Impeccable Design Audit

Source: github.com/pbakaus/impeccable (Apache 2.0)

**Purpose**: Systematic quality assessment across 5 dimensions. Generates scored report with P0-P3 severity ratings.

## Scoring (0-4 per dimension, 20 total)
| Score | Rating |
|-------|--------|
| 18-20 | Excellent |
| 14-17 | Good |
| 10-13 | Acceptable |
| 6-9   | Poor |
| 0-5   | Critical |

## 5 Audit Dimensions

### 1. Accessibility (0-4)
- WCAG AA contrast compliance
- ARIA labels on interactive elements
- Keyboard navigation (Tab order logical)
- Alt text on all antique images
- Form usability (if any inputs exist)

### 2. Performance (0-4)
- Image optimization (WebP, compressed, lazy-loaded)
- CSS/JS not blocking render
- GAS API fetch: loading state shown, error handled
- No layout shift (CLS) during image load
- Background images not re-fetching on scroll

### 3. Responsive Design (0-4)
- All breakpoints (375/768/1440) tested
- Touch targets ≥ 44×44px
- No overflow or horizontal scroll
- Text readable at all sizes (min 16px body)

### 4. Theming (0-4)
- All colors via CSS variables (no hardcoded hex)
- Brand palette consistent: gold/ink/paper/seal-red
- Dark/light behavior if applicable
- Font loading not causing FOUT

### 5. Anti-Patterns (0-4)
- No generic 3-column equal-card layouts
- No purple gradients or neon colors
- No placeholder content in production
- No console errors or warnings
- No unused CSS/JS

## Output Format
```
AUDIT REPORT — 吉寶軒 index.html
Overall: XX/20 [Rating]

[P0 BLOCKING]
- Issue description | Fix recommendation

[P1 MAJOR]
...

[POSITIVE FINDINGS]
...

Recommended next commands: /polish, /typeset
```

Run this audit against the current Publish/index.html. Read the file first, then score each dimension with specific evidence from the code.
