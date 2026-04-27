# Design System — Plan A: Tokens & Typography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the Tier 2 (semantic roles) + Tier 3 (component) design tokens and typography utility classes that all subsequent plans (B–E) build on.

**Architecture:** Add new token blocks to existing `parts/tokens.css` and create a new `parts/typography.css` with 8 utility classes. No existing component CSS is modified — Plan A is purely additive. Existing tokens remain as Tier 1 primitives; new Tier 2 tokens reference them via `var()`.

**Tech Stack:** CSS custom properties, stylelint (existing), Vite build (existing). Spec reference: `docs/superpowers/specs/2026-04-27-design-system-foundation-design.md` sections 3–4.

**Why no tests:** This project has no CSS unit-test harness. Verification is `npm run build` (no errors), `npm run lint:css` (no new errors), and a manual visual check that the app renders identically (Plan A is additive — utilities are unused by any component yet).

---

### Task 1: Add Tier 2 color role tokens

**Files:**
- Modify: `web/src/styles/parts/tokens.css` (append inside the existing `:root { ... }` block at the end of the file, before the closing `}`)

- [ ] **Step 1: Locate the end of the `:root` block**

Run: `grep -n '^}' web/src/styles/parts/tokens.css | tail -3`
Expected output: line numbers of `}` tokens. The `:root` closing `}` is the last one in the file.

- [ ] **Step 2: Insert Tier 2 surface/text/border tokens before the `:root` closing brace**

Add this block immediately before the final `}` in `parts/tokens.css`:

```css

  /* ============================================================
     Tier 2 — Semantic role tokens (Plan A)
     Components consume these instead of Tier 1 primitives.
     Spec: 2026-04-27-design-system-foundation-design.md §3
     ============================================================ */

  /* Surfaces */
  --color-bg-page: var(--cozy-cream-2);
  --color-bg-card: var(--paper);
  --color-bg-card-raised: var(--cozy-paper-2);

  /* Text */
  --color-fg-headline: var(--cozy-ink);
  --color-fg-body: var(--cozy-ink-soft);
  --color-fg-eyebrow: var(--cozy-gold);
  --color-fg-muted: var(--cozy-muted);

  /* Borders */
  --color-border-subtle: var(--cozy-border-color);
  --color-border-strong: var(--cozy-gold);
```

- [ ] **Step 3: Verify build still works**

Run: `cd web && npm run build`
Expected: build completes with `✓ built in <ms>` line. No CSS parse errors.

- [ ] **Step 4: Commit**

```bash
git add web/src/styles/parts/tokens.css
git commit -m "feat(design-system): add Tier 2 surface/text/border tokens (Plan A.1)"
```

---

### Task 2: Add Tier 2 semantic color tokens (5 roles × 7 sub-tokens)

**Files:**
- Modify: `web/src/styles/parts/tokens.css` (append after Task 1 block, still inside `:root`)

- [ ] **Step 1: Insert the semantic color matrix immediately after the Task 1 block**

Add this block before the final `}` in `parts/tokens.css`:

```css

  /* Semantic colors — 5 roles × {solid, fg, soft-bg, soft-fg, soft-border, outline-fg, outline-border}
     The 18% / 30% opacity values match the mockup approved during brainstorming. */

  /* Positive (BUY, beat, risk-on) */
  --color-positive: var(--cozy-good);
  --color-positive-fg: #fff;
  --color-positive-soft-bg: rgba(63, 169, 107, 0.18);
  --color-positive-soft-fg: #2a7a4a;
  --color-positive-soft-border: rgba(63, 169, 107, 0.3);
  --color-positive-outline-fg: #2a7a4a;
  --color-positive-outline-border: var(--cozy-good);

  /* Negative (AVOID, miss, risk-off) */
  --color-negative: var(--cozy-bad);
  --color-negative-fg: #fff;
  --color-negative-soft-bg: rgba(194, 90, 78, 0.18);
  --color-negative-soft-fg: #8a3e34;
  --color-negative-soft-border: rgba(194, 90, 78, 0.3);
  --color-negative-outline-fg: #8a3e34;
  --color-negative-outline-border: var(--cozy-bad);

  /* Caution (WATCH, neutral, FED) */
  --color-caution: var(--cozy-warn);
  --color-caution-fg: #fff;
  --color-caution-soft-bg: rgba(217, 154, 58, 0.18);
  --color-caution-soft-fg: #8a5e16;
  --color-caution-soft-border: rgba(217, 154, 58, 0.3);
  --color-caution-outline-fg: #8a5e16;
  --color-caution-outline-border: var(--cozy-warn);

  /* Info (context, ancillary) */
  --color-info: #5a7da8;
  --color-info-fg: #fff;
  --color-info-soft-bg: rgba(90, 125, 168, 0.18);
  --color-info-soft-fg: #36506e;
  --color-info-soft-border: rgba(90, 125, 168, 0.3);
  --color-info-outline-fg: #36506e;
  --color-info-outline-border: #5a7da8;

  /* Accent (score, system highlight — gold) */
  --color-accent: var(--cozy-gold);
  --color-accent-fg: #fff;
  --color-accent-soft-bg: rgba(184, 134, 47, 0.18);
  --color-accent-soft-fg: #7a5a2e;
  --color-accent-soft-border: rgba(184, 134, 47, 0.3);
  --color-accent-outline-fg: #7a5a2e;
  --color-accent-outline-border: var(--cozy-gold);
```

- [ ] **Step 2: Verify build**

Run: `cd web && npm run build`
Expected: build completes with `✓ built in <ms>`.

- [ ] **Step 3: Verify lint:css does not regress**

Run: `cd web && npm run lint:css 2>&1 | tail -3`
Expected: warning count unchanged (we added new tokens but kept existing rules; rgba literals here are inside token defs which `--fix` previously normalized).

- [ ] **Step 4: Commit**

```bash
git add web/src/styles/parts/tokens.css
git commit -m "feat(design-system): add 5 semantic color roles × 7 sub-tokens (Plan A.2)"
```

---

### Task 3: Add Tier 3 component tokens (spacing, radius, shadow)

**Files:**
- Modify: `web/src/styles/parts/tokens.css` (append after Task 2 block)

- [ ] **Step 1: Insert spacing scale and component tokens before the final `}`**

```css

  /* ============================================================
     Tier 2 — Spacing scale (8pt grid, Plan A.3)
     Used by Plan B for padding/margin/gap throughout components.
     ============================================================ */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-7: 32px;
  --space-8: 40px;
  --space-9: 48px;

  /* ============================================================
     Tier 3 — Component tokens
     ============================================================ */
  --space-card-pad: var(--space-5);
  --space-card-pad-hero: var(--space-6);
  --space-card-gap: var(--space-4);
  --space-section-gap: var(--space-6);
  --space-page-pad: var(--space-7);

  --radius-badge: 6px;
  /* --radius-card, --radius-pill, --radius-chip already defined in Tier 1 above */

  --shadow-card: 0 2px 0 0 rgba(184, 134, 47, 0.18), 0 8px 22px -10px rgba(122, 90, 46, 0.28);
```

- [ ] **Step 2: Verify build**

Run: `cd web && npm run build`
Expected: `✓ built in <ms>`.

- [ ] **Step 3: Commit**

```bash
git add web/src/styles/parts/tokens.css
git commit -m "feat(design-system): add Tier 3 spacing and component tokens (Plan A.3)"
```

---

### Task 4: Create `parts/typography.css` with 8 utility classes

**Files:**
- Create: `web/src/styles/parts/typography.css`
- Modify: `web/src/styles/global.css` (add `@import` after `tokens.css`)

- [ ] **Step 1: Create the file with 8 utility classes**

Write the full content to `web/src/styles/parts/typography.css`:

```css
/* ============================================================
   Typography utilities (Plan A.4)
   Spec: 2026-04-27-design-system-foundation-design.md §4
   Scale: B Modern Balanced (24px serif headline / 13px sans body / 10px eyebrow).
   Apply via class on any element; raw <h1>/<h2>/<h3> use these too.
   ============================================================ */

.type-display {
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.3px;
  color: var(--color-fg-headline);
}

.type-headline {
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.2px;
  color: var(--color-fg-headline);
}

.type-title {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 700;
  line-height: 1.3;
  color: var(--color-fg-headline);
}

.type-body {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 400;
  line-height: 1.55;
  color: var(--color-fg-body);
}

.type-body-strong {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
  font-variant-numeric: tabular-nums;
  color: var(--color-fg-headline);
}

.type-meta {
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5;
  color: var(--color-fg-muted);
}

.type-eyebrow {
  font-family: var(--font-sans);
  font-size: 10px;
  font-weight: 600;
  line-height: 1.5;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--color-fg-eyebrow);
}

.type-mono {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
  color: var(--color-fg-headline);
}
```

- [ ] **Step 2: Wire the import into `global.css`**

Edit `web/src/styles/global.css`. Add `@import './parts/typography.css';` immediately after the existing `@import './parts/tokens.css';` line. The full file should look like:

```css
/* AUTO-GENERATED: split into ./parts/*.css for maintainability.
   Edit individual files; this file only orders the cascade. */

@import './parts/tokens.css';
@import './parts/typography.css';
@import './parts/base.css';
@import './parts/dashboard.css';
@import './parts/components.css';
@import './parts/utilities.css';
@import './parts/patches.css';
@import './parts/admin.css';
@import './parts/cozy.css';
```

- [ ] **Step 3: Verify build**

Run: `cd web && npm run build`
Expected: `✓ built in <ms>`. CSS bundle slightly larger (~600 bytes for the 8 utility classes).

- [ ] **Step 4: Verify lint:css**

Run: `cd web && npm run lint:css 2>&1 | tail -3`
Expected: warning count unchanged (the new file uses only tokens — zero new warnings).

- [ ] **Step 5: Commit**

```bash
git add web/src/styles/parts/typography.css web/src/styles/global.css
git commit -m "feat(design-system): add typography utility classes (Plan A.4)"
```

---

### Task 5: Sanity-check render (no visual regression)

**Files:** none modified.

- [ ] **Step 1: Start dev server**

Run: `cd web && npm run dev` (in a separate terminal)
Expected: Vite reports `Local: http://localhost:5173/`.

- [ ] **Step 2: Open these 5 routes in the browser and confirm they render unchanged**

- `http://localhost:5173/` (Watchlist)
- `http://localhost:5173/portfolio`
- `http://localhost:5173/signals`
- `http://localhost:5173/ticker/AAPL` (any ticker)
- `http://localhost:5173/api-status`

Expected: all 5 pages render identical to before Plan A. No layout shifts, no font changes, no color changes. Plan A is purely additive — utilities and new tokens are not yet referenced by any component.

- [ ] **Step 3: Stop dev server**

Press `Ctrl+C` in the dev-server terminal.

- [ ] **Step 4: Push the Plan A commits**

```bash
git push origin main
```

Expected: 4 commits pushed (Tasks 1, 2, 3, 4). No conflicts.

---

### Task 6: Extend stylelint to warn on font-size literals

**Files:**
- Modify: `web/.stylelintrc.json`

**Why:** Spec §9 Plan A says font-size literals should surface as lint debt so future component edits naturally adopt `.type-*` utilities. We add `font-size` to the existing `scale-unlimited/declaration-strict-value` rule at `severity: warning` (not error) so existing rules keep working — promotion to `error` happens after components migrate.

- [ ] **Step 1: Edit `.stylelintrc.json` to add `font-size` to the strict-value list**

Find the existing `scale-unlimited/declaration-strict-value` rule. Change the property list from:

```json
"scale-unlimited/declaration-strict-value": [
  ["/color$/", "fill", "stroke", "background-color", "border-color"],
  ...
]
```

to:

```json
"scale-unlimited/declaration-strict-value": [
  ["/color$/", "fill", "stroke", "background-color", "border-color", "font-size"],
  ...
]
```

The `ignoreValues` and `severity: warning` blocks stay unchanged.

- [ ] **Step 2: Run lint to capture the new baseline**

Run: `cd web && npm run lint:css 2>&1 | tail -3`
Expected: warning count rises (additional `font-size` warnings flagged across components.css, dashboard.css, etc.). Errors must still be 0. If errors appear, the rule is misconfigured — re-check Step 1.

- [ ] **Step 3: Confirm `parts/typography.css` itself is clean**

Run: `cd web && npm run lint:css -- src/styles/parts/typography.css 2>&1 | tail -3`
Expected: 0 errors, 0 warnings (typography.css uses only literal `px` values for font-size, but those literals ARE the source of truth — they need to be ignored).

If typography.css produces warnings, add an inline disable on each declaration that defines a font-size token, e.g.:

```css
.type-display {
  font-family: var(--font-serif);
  /* stylelint-disable-next-line scale-unlimited/declaration-strict-value */
  font-size: 28px;
  ...
}
```

Apply the same disable comment to all 8 utility classes.

- [ ] **Step 4: Re-run lint and confirm typography.css clean**

Run: `cd web && npm run lint:css -- src/styles/parts/typography.css 2>&1 | tail -3`
Expected: 0 warnings.

- [ ] **Step 5: Commit**

```bash
git add web/.stylelintrc.json web/src/styles/parts/typography.css
git commit -m "feat(design-system): add font-size to stylelint strict-value (Plan A.5)"
```

---

### Task 7: Update spec status & document Plan A completion

**Files:**
- Modify: `docs/superpowers/specs/2026-04-27-design-system-foundation-design.md`

- [ ] **Step 1: Mark Plan A as completed in the spec**

Edit the spec file. Change the line `**Status:** Spec — pending plan generation.` near the top to:

```
**Status:** Plan A landed (tokens + typography utilities). Plans B–E pending.
```

- [ ] **Step 2: Commit and push**

```bash
git add docs/superpowers/specs/2026-04-27-design-system-foundation-design.md
git commit -m "docs(design-system): mark Plan A complete in spec status"
git push origin main
```

---

## Plan A Verification Checklist

After all tasks complete, the following should be true:

- `web/src/styles/parts/tokens.css` contains Tier 2 surface/text/border tokens, 5×7 semantic color matrix, spacing scale (1–9), Tier 3 component tokens. Total ≥ 50 new lines.
- `web/src/styles/parts/typography.css` exists with exactly 8 utility classes (`.type-display`, `.type-headline`, `.type-title`, `.type-body`, `.type-body-strong`, `.type-meta`, `.type-eyebrow`, `.type-mono`).
- `web/src/styles/global.css` `@import` order includes `typography.css` between `tokens.css` and `base.css`.
- `npm run build` succeeds.
- `npm run lint:css` warning count ≤ 34 (no new warnings).
- `git log --oneline -7` shows 6 Plan A commits (Tasks 1–4 implementation, Task 6 stylelint, Task 7 spec status).
- Visual: app renders identically to pre-Plan A (no component yet consumes the new tokens/utilities).

When all check, Plan B can begin: it will reference the spacing tokens to consolidate `padding`/`margin`/`gap` literals across components.
