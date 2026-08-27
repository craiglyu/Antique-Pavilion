---
id: skill_polish
type: skill
layer: core
loaded_by: [Audit, Designer]
version: v0.1
schema_version: 1
last_updated: 2026-04-28
change_notes: "初版 — pre-ship refinement gate"
---

# /polish — Impeccable Design Polish

Source: github.com/pbakaus/impeccable (Apache 2.0)

**Purpose**: Final pre-ship refinement pass. Only invoke AFTER functional completeness.

## Polish Dimensions

### Visual Alignment
- Grid adherence and pixel-perfect spacing
- Optical centering (visually centered ≠ mathematically centered)
- Consistent spacing rhythm (use multiples of 4px or 8px)

### Typography
- Hierarchy clarity: H1 > H2 > body contrast ratio ≥ 2:1 between levels
- Line length 45-75 characters for body text
- Consistent heading styles across all pages

### Color & Contrast
- WCAG AA: normal text ≥ 4.5:1, large text ≥ 3:1
- Consistent use of CSS custom properties (no hardcoded hex)
- Hover/focus states visible and distinct

### Micro-interactions
- Transitions: 150-300ms, appropriate easing (ease-out for entrances, ease-in for exits)
- No janky reflow during animations
- Loading states for async operations (GAS doGet fetch)

### Content Consistency
- Uniform terminology (「器物」vs「藏品」— pick one)
- Consistent date/price formatting
- No orphaned words at line ends in key headings

### Responsiveness
- 44×44px minimum touch targets
- Test at 375px (iPhone SE), 768px (iPad), 1440px (desktop)
- No horizontal scroll at any breakpoint

## 吉寶軒-Specific Checks
- [ ] Gold `#c49a45` used consistently, not mixed with other yellows
- [ ] LXGW WenKai TC loaded and rendering correctly
- [ ] Item cards all have consistent image aspect ratios
- [ ] Modal overlay z-index correct (no content bleeding through)
- [ ] GAS API loading state shows (not blank white flash)
- [ ] Footer seal-red `#8a2a2a` consistent

## Output Format
List issues by severity: P0 Blocking → P1 Major → P2 Minor → P3 Polish

Read Publish/index.html first, then provide the polish checklist with specific line references.
