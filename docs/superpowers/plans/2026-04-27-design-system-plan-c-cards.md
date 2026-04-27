# Design System — Plan C: Card System (Pilot) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the `.surface-card` / `.surface-card--hero` / `.surface-card--list-row` system in a new `parts/cards.css` file, and apply it as a non-destructive additive layer to one pilot component (Market Regime Banner). All other 15+ existing card types are deferred to follow-up migration plans.

**Architecture:** The 3 surface-card classes have specificity `(0,0,1,0)`. They're imported early in the cascade (right after `typography.css`) so that existing higher-specificity rules (e.g. `.market-regime-banner.cozy-premium-banner` at `(0,0,2,0)`) continue to win. The pilot adds `surface-card surface-card--hero` to the MarketRegimeBanner JSX — both old and new rules apply, the old rule keeps winning, and we prove the new system runs alongside without conflict. The base `.surface-card` matches the look of the most common cozy-premium card so future per-component migrations are drop-in.

**Tech Stack:** CSS, React/TSX (one file edit). Spec reference: `docs/superpowers/specs/2026-04-27-design-system-foundation-design.md` §6.

**Why no tests:** No CSS unit-test harness. Verification is `npm run build`, `npm run lint:css` errors === 0, and visual diff on 5 routes. The pilot must look pixel-identical because the existing higher-specificity rule still wins.

**Prerequisites:**
- Plans A & B landed (Tier 2/3 tokens, 8pt spacing tokens). Verify: `cd web && grep -c '\\-\\-shadow-card:' src/styles/parts/tokens.css` returns `1`.

**Out of scope (deferred to follow-up plans):**
- Migrating all `.watchlist-card` / `.decision-card` / `.api-provider-card` / `.earnings-hero-card` instances — too many call sites; do gradually.
- Removing the legacy `.market-regime-banner.cozy-premium-banner` rule — kept as the source of truth until all hero adopters are converted.
- Implementing `--list-row` adopters (signal-row, api-provider-row) — class is defined but not yet applied.
- Retuning `--space-card-pad` from 22px to 20px — happens when components actually adopt `.surface-card`.

---

### Task 1: Create `parts/cards.css` with the 3 variants

**Files:**
- Create: `web/src/styles/parts/cards.css`

- [ ] **Step 1: Write the file**

Write the full content to `web/src/styles/parts/cards.css`:

```css
/* ============================================================
   Card system (Plan C)
   Spec: 2026-04-27-design-system-foundation-design.md §6
   3 variants: base / hero / list-row.
   Specificity is intentionally low (single class, 0,0,1,0) so existing
   component rules with compound selectors keep winning. Migration of
   legacy classes happens incrementally in follow-up plans.
   ============================================================ */

.surface-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: var(--space-card-pad);
  position: relative;
  transition: border-color 120ms ease, box-shadow 120ms ease;
}

.surface-card:hover {
  border-color: var(--cozy-gold-soft);
  box-shadow: var(--shadow-hard-lg);
}

/* Hero variant — for Market Regime Banner, Top Conviction, Macro hero.
   Mirrors the existing .market-regime-banner.cozy-premium-banner look so
   the pilot adoption is pixel-equivalent. */
.surface-card--hero {
  background: linear-gradient(180deg, var(--cozy-paper) 0%, var(--cozy-paper-2) 100%);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-card);
  padding: var(--space-card-pad-hero);
  box-shadow: var(--shadow);
  position: relative;
  overflow: hidden;
}

.surface-card--hero::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--cozy-gold) 0%, var(--cozy-gold-2) 50%, var(--cozy-gold) 100%);
}

.surface-card--hero:hover {
  /* Hero already commands attention — no hover lift. */
  border-color: var(--color-border-subtle);
  box-shadow: var(--shadow);
}

/* List-row variant — for tabular rows inside larger panels (signal rows,
   api-provider rows). Border-bottom only, no radius, no shadow. */
.surface-card--list-row {
  background: var(--color-bg-card);
  border: 0;
  border-bottom: 1px solid var(--color-border-subtle);
  border-radius: 0;
  box-shadow: none;
  padding: var(--space-3) var(--space-card-pad);
  transition: background-color 120ms ease;
}

.surface-card--list-row:hover {
  background: rgba(255, 255, 255, 0.4);
}

.surface-card--list-row:last-child {
  border-bottom: 0;
}
```

- [ ] **Step 2: Verify standalone lint**

Run: `cd web && npx stylelint src/styles/parts/cards.css 2>&1 | tail -5`
Expected: no output (0 problems). The file uses only tokens for color/font-size/padding/margin; the lone `rgba(255,255,255,0.4)` literal is allowed by the `/^rgba?\(/` ignoreValue.

If warnings appear, recheck Step 1.

---

### Task 2: Wire the import into `global.css`

**Files:**
- Modify: `web/src/styles/global.css`

- [ ] **Step 1: Add `@import` after `typography.css`**

Edit `global.css`. Insert one line so the file reads:

```css
/* AUTO-GENERATED: split into ./parts/*.css for maintainability.
   Edit individual files; this file only orders the cascade. */

@import './parts/tokens.css';
@import './parts/typography.css';
@import './parts/cards.css';
@import './parts/base.css';
@import './parts/dashboard.css';
@import './parts/components.css';
@import './parts/utilities.css';
@import './parts/patches.css';
@import './parts/admin.css';
@import './parts/cozy.css';
```

- [ ] **Step 2: Verify build**

Run: `cd web && npm run build`
Expected: `✓ built in <ms>`. CSS bundle slightly larger (~700 bytes for the 3 variants).

- [ ] **Step 3: Verify total lint warnings did not jump unexpectedly**

Run: `cd web && npm run lint:css 2>&1 | tail -3`
Expected: warnings within ±5 of pre-Plan-C count (~960). cards.css contributes near-zero new warnings because it uses only tokens.

- [ ] **Step 4: Commit**

```bash
git add web/src/styles/parts/cards.css web/src/styles/global.css
git commit -m "feat(design-system): add .surface-card variants (Plan C.1)"
```

---

### Task 3: Apply pilot — add `.surface-card surface-card--hero` to MarketRegimeBanner

**Files:**
- Modify: `web/src/components/MarketRegimeBanner.tsx`

**Why this is safe:** The existing rule `.market-regime-banner.cozy-premium-banner { ... }` has specificity `(0,0,2,0)`, beating `.surface-card--hero` at `(0,0,1,0)`. So the existing rule continues to render the banner. Adding the new classes is purely "label" — proves the system can run alongside without conflict. The only declarations from `.surface-card--hero` that win are properties NOT set on the legacy rule (e.g. `transition` is not on the legacy rule, so the new one applies).

- [ ] **Step 1: Edit the className**

Open `web/src/components/MarketRegimeBanner.tsx`. Find line 34:

```tsx
<section className={`market-regime-banner cozy-premium-banner ${config.className}`}>
```

Change to:

```tsx
<section className={`surface-card surface-card--hero market-regime-banner cozy-premium-banner ${config.className}`}>
```

The order matters only for readability — both classes apply equally. We list the new design-system classes first so they read as the "primary" label.

- [ ] **Step 2: Verify build**

Run: `cd web && npm run build`
Expected: `✓ built in <ms>`. No TypeScript errors.

- [ ] **Step 3: Visual diff — Market Regime Banner**

Run: `cd web && npm run dev` (separate terminal).

Open `http://localhost:5173/` and inspect the Market Regime Banner at the top of the page. Expected behaviour:

- Banner background is identical (paper gradient).
- Top 3px gold line is unchanged.
- Border, radius, padding, eyebrow, headline, drivers all pixel-identical.
- A 120ms `transition` on `border-color` and `box-shadow` is now present (only visible if you hover-toggle dev tools — minor enhancement).

If anything visually changes, stop and inspect: open dev-tools → Computed tab → look at `border`, `background`, `padding`. The legacy rule (with `2,0` specificity) should be the winner for these properties.

- [ ] **Step 4: Smoke-check 4 other routes**

In the same dev session, navigate to:
- `http://localhost:5173/portfolio` — confirm dashboard cards unchanged
- `http://localhost:5173/signals` — confirm rows unchanged
- `http://localhost:5173/ticker/AAPL` — confirm detail card unchanged
- `http://localhost:5173/api-status` — confirm api provider cards unchanged

Plan C did not modify any other component, so all these should look identical to pre-Plan-C.

- [ ] **Step 5: Stop dev server (Ctrl+C)**

- [ ] **Step 6: Commit**

```bash
git add web/src/components/MarketRegimeBanner.tsx
git commit -m "feat(design-system): apply .surface-card--hero to MarketRegimeBanner (Plan C.2)"
```

---

### Task 4: Push and update spec status

**Files:**
- Modify: `docs/superpowers/specs/2026-04-27-design-system-foundation-design.md`

- [ ] **Step 1: Update status line**

Change the status line near the top of the spec to:

```
**Status:** Plans A, B, C landed (tokens, typography, spacing, card system + 1 hero pilot). Plans D, E pending. Card migration of remaining 15+ components is follow-up work.
```

- [ ] **Step 2: Commit and push**

```bash
git add docs/superpowers/specs/2026-04-27-design-system-foundation-design.md
git commit -m "docs(design-system): mark Plan C complete in spec status"
git push origin main
```

Expected: 3 commits pushed (Tasks 1+2 combined, Task 3, Task 4). No conflicts.

---

## Plan C Verification Checklist

After all tasks complete:

- `web/src/styles/parts/cards.css` exists with `.surface-card`, `.surface-card--hero`, `.surface-card--list-row`, plus `:hover` rules. Total ~50 lines.
- `web/src/styles/global.css` `@import` order has `cards.css` between `typography.css` and `base.css`.
- `web/src/components/MarketRegimeBanner.tsx` line 34 className includes `surface-card surface-card--hero` prefix.
- `npm run build` succeeds.
- `npm run lint:css` errors === 0, warnings within ±5 of pre-Plan-C baseline.
- Market Regime Banner renders pixel-identical to pre-Plan-C.
- 4 other routes (portfolio, signals, ticker detail, api-status) render pixel-identical.
- `git log --oneline -4` shows 3 Plan C commits + spec status commit.

When all check, the next step is **incremental migration plans** (one per component group): apply `.surface-card` to watchlist cards, then decision cards, then api provider cards, etc. Each migration removes the per-component padding/border duplication once `.surface-card` provides a clean base. That's outside Plan C's scope — Plan D (pill system) is the next design-system plan.
