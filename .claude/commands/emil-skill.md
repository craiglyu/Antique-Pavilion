---
id: skill_emil_skill
type: skill
layer: domain
loaded_by: [Designer]
version: v0.1
schema_version: 1
last_updated: 2026-04-28
change_notes: "初版 — 動畫品質工程"
---

# Emil Design Engineering Skill — 吉寶軒 Edition

Source: github.com/emilkowalski/skill (emil-design-eng)
Adapted for: Pure HTML/CSS/JS (no Tailwind/React/Framer Motion)

> "Taste is trained. Unseen details compound. Beauty is leverage."
> — Emil Kowalski

---

## 吉寶軒 Context

This skill governs **animation quality, interaction engineering, and micro-detail craft** for the Jibao Xuan antique gallery site. All techniques are adapted from Emil Kowalski's design engineering principles to work in vanilla CSS/JS — no build tools, no JS animation libraries.

---

## Core Philosophy

### The Animation Decision Tree

Before adding ANY motion, answer these three questions:

1. **Frequency** — How often does the user encounter this?
   - Every frame (scroll) → imperceptible, < 0.1s
   - Every interaction (hover) → subtle, 150–250ms
   - Occasional (filter, modal) → deliberate, 300–500ms
   - Once (page load, first reveal) → dramatic, 700–2500ms

2. **Purpose** — What does the motion communicate?
   - State change (active/inactive) → directional
   - Entrance (element appears) → translate + fade
   - Exit (element disappears) → ALWAYS 2× faster than entrance
   - Decoration (purely aesthetic) → ask: does removing it hurt? If no, remove it.

3. **Cost** — Will this run at 60fps on a mid-range Android?
   - Only `transform` and `opacity` are GPU-composited
   - `filter` is GPU on most modern browsers (test it)
   - Everything else causes layout/paint → forbidden in loops

> Rule: If you can't justify an animation against all three questions, it should not exist.

---

## Easing Catalog (吉寶軒 Approved)

```css
/* Entrance — weighted deceleration, settles with authority */
cubic-bezier(0.25, 1, 0.5, 1)

/* Exit — quick dismissal, never lingers */
cubic-bezier(0.4, 0, 1, 1)

/* Micro-interaction — snappy hover/click response */
cubic-bezier(0.4, 0, 0.2, 1)

/* Spring reveal — slight overshoot gives life (use sparingly) */
cubic-bezier(0.34, 1.56, 0.64, 1)

/* Float / atmospheric — organic, never mechanical */
ease-in-out  (for keyframe infinite loops only)
```

Never use `linear` for UI elements.
Never use `ease` default (too symmetrical, generic).
Never use `ease-in` for entrances (feels slow to start, then rushed).

---

## Duration Scale

```
Category              Duration    Easing
─────────────────────────────────────────────────────
Hover color/shadow    150ms       ease-micro
Hover lift/scale      250ms       ease-micro
Tab/filter switch     350ms       ease-micro
Modal overlay fade    300ms       ease-micro (in) / ease-exit (out)
Modal content open    480ms       ease-enter
Modal content close   240ms       ease-exit  (exits are 2× faster)
Card scroll reveal    750–850ms   ease-enter
Brand title reveal    2000ms      ease-enter  (with 1s font-load delay)
Cloud float           5000ms      ease-in-out infinite
```

---

## Performance Rules

```
✅ ANIMATE ONLY:
   transform: translate, rotate, scale
   opacity
   filter: (brightness, blur — use sparingly)

❌ NEVER ANIMATE:
   width, height, top, left, right, bottom
   padding, margin, border-width
   background-color (use opacity overlay instead)
   font-size, letter-spacing (use transform: scale on wrapper)

✅ ALWAYS ADD:
   @media (prefers-reduced-motion: reduce) {
     *, *::before, *::after {
       animation-duration: 0.01ms !important;
       animation-iteration-count: 1 !important;
       transition-duration: 0.01ms !important;
     }
   }
```

---

## Key Patterns

### Card Scroll Reveal (IntersectionObserver)
```css
.card.from-right { transform: translateY(20px) translateX(60px); opacity: 0; }
.card.from-left  { transform: translateY(20px) translateX(-60px); opacity: 0; }
.card.is-visible {
    opacity: 1;
    transform: translateY(0) translateX(0);
    transition: opacity 0.8s cubic-bezier(0.25, 1, 0.5, 1),
                transform 0.8s cubic-bezier(0.25, 1, 0.5, 1);
}
```

### Hover Lift (Premium Feel)
```css
.card {
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1),
                box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.card:hover {
    transform: translateY(-5px);
    box-shadow: 0 20px 50px rgba(196, 154, 69, 0.25);
}
```

### Image Zoom
```css
.antique-img {
    transition: transform 1.2s cubic-bezier(0.25, 1, 0.5, 1),
                filter 1.2s cubic-bezier(0.25, 1, 0.5, 1);
}
.card:hover .antique-img {
    transform: scale(1.08);
    filter: brightness(1.02);
}
```

---

## Quality Signals

1. Exit animations are always 2× faster than entrances.
2. Hover shadows use brand colors `rgba(196, 154, 69, 0.25)`, not black.
3. Seal rotation on hover is anti-clockwise (-5deg).
4. Letter-spacing on compact header brand title is 0.8rem, not 0rem.
5. Gold hairline gradients fade at top/bottom edges.
6. Loading text dots have staggered opacity, not simultaneous.

---

## Pre-Flight (Animation-Specific)
- [ ] Tested at 4× CPU throttle in DevTools — still smooth?
- [ ] `prefers-reduced-motion: reduce` tested?
- [ ] Exit animations noticeably faster than entrances?
- [ ] No `scroll` event listeners for animation triggers (use IntersectionObserver)?
- [ ] Stagger total duration < 400ms for lists > 3 items?
