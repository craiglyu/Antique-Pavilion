---
id: skill_taste_skill
type: skill
layer: domain
loaded_by: [Designer]
version: v0.1
schema_version: 1
last_updated: 2026-04-28
change_notes: "初版 — 高奢品牌設計規範 + anti-AI-slop"
---

# Taste Skill — High-Agency UI/UX Engineering

Source: github.com/Leonxlnx/taste-skill (free, open source)

## 吉寶軒 Context
Pure HTML/CSS/JS (no Tailwind/React). Apply principles via vanilla CSS custom properties and native animations.

## Core Configuration
- DESIGN_VARIANCE: 8 (high — avoid safe/generic layouts)
- MOTION_INTENSITY: 6 (medium-high — subtle spring physics)
- VISUAL_DENSITY: 4 (medium — breathing room, not sparse)

## Anti-AI-Slop Rules (ENFORCE THESE)
- NO centered hero + 3-column icon grid layouts
- NO purple/neon/oversaturated gradients
- NO Inter font for premium contexts (use LXGW WenKai TC / Ma Shan Zheng)
- NO placeholder names like "藏品001" — use specific item names
- NO equal-width card rows — use asymmetric masonry or varied sizing
- NO generic CTAs — use specific, evocative text

## Typography (吉寶軒 Brand)
- Headlines: `Ma Shan Zheng` or `Zhi Mang Xing` — calligraphic weight
- Body: `LXGW WenKai TC` — warm, readable
- Size scale: 12 / 14 / 16 / 20 / 28 / 40 / 60px (modular)
- Line length: max 65ch for body, unconstrained for display text
- Letter-spacing: `tracking-tighter` equivalent for large headlines

## Color Constraints
- Primary palette: `--gold: #c49a45` / `--ink: #2c2c2c` / `--paper: #f7f4ed` / `--seal-red: #8a2a2a`
- Max ONE accent color per component
- Saturation < 80% for all non-accent elements
- Background: use textured paper tones, never pure white

## Motion Standards
- Use CSS `transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1)` for micro-interactions
- Hover states: subtle lift (translateY -2px) + shadow deepening
- Never animate `width`, `height`, `top`, `left` — only `transform` + `opacity`
- Page-level: fade-in on load (opacity 0→1, 0.6s ease)

## Layout Principles
- Asymmetric compositions preferred over symmetric grids
- Use CSS Grid with named areas for complex layouts
- Vary card proportions — 2:3, 3:4, 16:9 mixing is intentional
- Replace `height: 100vh` with `min-height: 100dvh`

## Pre-Flight Checklist
Before any UI output:
- [ ] Mobile responsive at 375px / 768px / 1440px?
- [ ] Touch targets ≥ 44×44px?
- [ ] No hardcoded colors (use CSS variables)?
- [ ] Animations use only transform/opacity?
- [ ] Fonts loaded via Google Fonts link?
