---
name: ui-regression-audit
description: Use when checking or fixing frontend UI regressions around navigation delay, skeleton overexposure, shadcn/ui consistency, accessibility, mobile layout, z-index portals, focus states, WCAG contrast, dark mode, or banned pill/rounded DIV styling.
---

# UI Regression Audit

Use this for repeated UI quality passes across dashboard pages and shared components.

## Workflow

1. Read `AGENTS.md`, `docs/codex/index.md`, then use the repo `frontend` skill.
2. Use Context7 for current React, Vite, Tailwind, shadcn/ui, or Radix docs before making library-specific assumptions.
3. Preserve data flow, API contracts, and business logic.
4. Inspect shared UI primitives before page-specific fixes.
5. Fix loading states so skeletons render only for real loading and do not mask page transitions longer than necessary.
6. Ensure dropdowns/menus render through the existing portal pattern and appear above page content.
7. Remove pill, capsule, and half-rounded card/row/DIV shapes unless they are native controls where the design system requires them.
8. Confirm accessibility basics: aria labels, decorative `aria-hidden`, keyboard navigation, `focus-visible`, 44px touch targets, WCAG AA contrast, and dark-mode contrast.
9. Run relevant npm checks and browser verification when a visual or interaction path changed.

## Default Frontend Checks

```bash
npm run lint
npm run build
npm run test
npm run audit:ui
npm run audit:performance
```

Run only scripts that exist. Report skipped scripts by name.

## Report

Return:

1. Problems found
2. Fix status
3. Remaining risks, including unverified viewport, browser, or Lighthouse checks
