# Design System — Plan B: Spacing & Rhythm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate 3 high-traffic spacing declarations to the `--space-*` token scale (already defined in Plan A) and add a stylelint warning gate for `padding`/`margin`/`gap` literals so future regressions surface during PR review.

**Architecture:** Token replacement only — selectors and values stay byte-identical (current values already 8pt-aligned by accident). The new `--space-{1..9}` tokens were added in Plan A; Plan B wires them into the cascade-critical selectors. Stylelint extension is additive: severity stays at `warning` so existing literals don't block builds.

**Tech Stack:** CSS custom properties, stylelint scale-unlimited/declaration-strict-value rule (already configured in Stage 4). Spec reference: `docs/superpowers/specs/2026-04-27-design-system-foundation-design.md` §5.

**Why no tests:** No CSS unit-test harness. Verification is `npm run build`, `npm run lint:css` (warning count rises but errors stay 0), and visual diff on 5 routes (no rendered pixel difference expected).

**Prerequisites:**
- Plan A landed (verify `--space-1` … `--space-9` exist in `web/src/styles/parts/tokens.css`).
- Run `cd web && grep -c '\\-\\-space-1:' src/styles/parts/tokens.css` — must return `1`.

---

### Task 1: Migrate `.main` page-level gap to token

**Files:**
- Modify: `web/src/styles/parts/base.css:121`

**Current:** `.main { display: flex; flex-direction: column; gap: 2rem; position: relative; }`

- [ ] **Step 1: Replace the literal `2rem` with `var(--space-7)`**

Edit `web/src/styles/parts/base.css` line 121. Change:

```css
.main { display: flex; flex-direction: column; gap: 2rem; position: relative; }
```

to:

```css
.main { display: flex; flex-direction: column; gap: var(--space-7); position: relative; }
```

`--space-7` evaluates to `32px` which equals `2rem` at the project's default 16px root font-size (verified — `body { font-size: 17px }` is set in base.css but `.main` cascades from html which uses default 16px root).

- [ ] **Step 2: Verify build**

Run: `cd web && npm run build`
Expected: `✓ built in <ms>`. No errors.

- [ ] **Step 3: Verify CSS bundle size unchanged within ±200 bytes**

Run: `cd web && ls -la dist/assets/index-*.css | awk '{print $5}'`
Expected: a single number. Compare to pre-Plan-B size if curious; not a hard gate (token reference adds ~10 bytes).

- [ ] **Step 4: Commit**

```bash
git add web/src/styles/parts/base.css
git commit -m "refactor(design-system): migrate .main gap to --space-7 (Plan B.1)"
```

---

### Task 2: Migrate `.dashboard` gap to token

**Files:**
- Modify: `web/src/styles/parts/dashboard.css:2-6`

**Current:**
```css
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
```

- [ ] **Step 1: Replace the literal `1rem` with `var(--space-4)`**

Edit the `.dashboard` rule. Change `gap: 1rem;` to `gap: var(--space-4);`. The full rule should read:

```css
.dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
```

- [ ] **Step 2: Verify build**

Run: `cd web && npm run build`
Expected: `✓ built in <ms>`.

- [ ] **Step 3: Commit**

```bash
git add web/src/styles/parts/dashboard.css
git commit -m "refactor(design-system): migrate .dashboard gap to --space-4 (Plan B.2)"
```

---

### Task 3: Migrate `.watchlist-list-wrapper` gap to token

**Files:**
- Modify: `web/src/styles/parts/components.css:1768`

**Current:** `.watchlist-list-wrapper { display: flex; flex-direction: column; gap: 0.75rem; }`

- [ ] **Step 1: Replace `0.75rem` with `var(--space-3)`**

Edit line 1768. Result:

```css
.watchlist-list-wrapper { display: flex; flex-direction: column; gap: var(--space-3); }
```

- [ ] **Step 2: Verify build**

Run: `cd web && npm run build`
Expected: `✓ built in <ms>`.

- [ ] **Step 3: Commit**

```bash
git add web/src/styles/parts/components.css
git commit -m "refactor(design-system): migrate .watchlist-list-wrapper gap to --space-3 (Plan B.3)"
```

---

### Task 4: Extend stylelint to warn on padding/margin/gap literals

**Files:**
- Modify: `web/.stylelintrc.json`

**Why:** Spec §5 says spacing declarations must reference tokens. We add `padding`, `margin`, `gap` (and their longhand variants) to the existing `scale-unlimited/declaration-strict-value` rule at `severity: warning`. Existing literal usage flags as warning but build stays green; future PRs see the warnings during review.

- [ ] **Step 1: Read the current property list**

Run: `cd web && grep -A1 'scale-unlimited/declaration-strict-value' .stylelintrc.json | head -3`
Expected: a line containing the property array including `font-size` (added in Plan A.6).

- [ ] **Step 2: Edit `.stylelintrc.json` to extend the property list**

Find the line with the existing array. Change the array to include the spacing properties. Result:

```json
"scale-unlimited/declaration-strict-value": [
  ["/color$/", "fill", "stroke", "background-color", "border-color", "font-size", "padding", "/^padding-/", "margin", "/^margin-/", "gap", "row-gap", "column-gap"],
  {
    "ignoreValues": [
      "transparent", "inherit", "currentColor", "initial", "unset", "none",
      "/^var\\(/", "/^rgba?\\(/", "0", "auto"
    ],
    "severity": "warning"
  }
],
```

Note three changes:
1. Property array extended with 7 new entries (`padding`, `/^padding-/`, `margin`, `/^margin-/`, `gap`, `row-gap`, `column-gap`).
2. `ignoreValues` extends with `"0"` and `"auto"` so `padding: 0` and `margin: auto` don't flood warnings.

- [ ] **Step 3: Run lint to capture the new baseline**

Run: `cd web && npm run lint:css 2>&1 | tail -3`
Expected: warning count rises substantially (hundreds of new spacing warnings expected). **Errors must stay at 0.** If errors appear, the JSON is malformed — re-check Step 2.

- [ ] **Step 4: Confirm `parts/typography.css` is still clean**

Run: `cd web && npx stylelint src/styles/parts/typography.css 2>&1 | tail -3`
Expected: empty output (0 problems). typography.css has no padding/margin/gap declarations.

- [ ] **Step 5: Confirm tokens.css is still clean**

Run: `cd web && npx stylelint src/styles/parts/tokens.css 2>&1 | tail -3`
Expected: empty output (0 problems). tokens.css declares custom properties only — no property declarations to flag.

- [ ] **Step 6: Verify build**

Run: `cd web && npm run build`
Expected: `✓ built in <ms>`. Build is independent of lint warnings.

- [ ] **Step 7: Commit**

```bash
git add web/.stylelintrc.json
git commit -m "feat(design-system): add padding/margin/gap to stylelint strict-value (Plan B.4)"
```

---

### Task 5: Visual regression check

**Files:** none modified.

- [ ] **Step 1: Start dev server**

Run: `cd web && npm run dev` (in a separate terminal).
Expected: Vite reports `Local: http://localhost:5173/`.

- [ ] **Step 2: Open these 5 routes and confirm pixel-identical to pre-Plan-B**

- `http://localhost:5173/` (Watchlist) — confirm card-to-card vertical spacing unchanged (0.75rem == 12px == `--space-3`)
- `http://localhost:5173/portfolio` — confirm dashboard column gap unchanged (1rem == 16px == `--space-4`)
- `http://localhost:5173/signals` — confirm `.main` page-level gap unchanged (2rem == 32px == `--space-7`)
- `http://localhost:5173/ticker/AAPL` — confirm scrolled detail page spacing unchanged
- `http://localhost:5173/api-status` — confirm card grid spacing unchanged

Expected: zero rendered pixel difference. Token values are mathematically equal to the literal values they replaced.

- [ ] **Step 3: Stop dev server (Ctrl+C)**

- [ ] **Step 4: Push commits**

```bash
git push origin main
```

Expected: 4 commits pushed (Tasks 1–4). No conflicts.

---

### Task 6: Update spec status

**Files:**
- Modify: `docs/superpowers/specs/2026-04-27-design-system-foundation-design.md`

- [ ] **Step 1: Update the status line**

Change the status line near the top of the spec from:

```
**Status:** Plan A landed (tokens + typography utilities). Plans B–E pending.
```

to:

```
**Status:** Plans A & B landed (tokens, typography utilities, spacing migration + lint). Plans C–E pending.
```

- [ ] **Step 2: Commit and push**

```bash
git add docs/superpowers/specs/2026-04-27-design-system-foundation-design.md
git commit -m "docs(design-system): mark Plan B complete in spec status"
git push origin main
```

---

## Plan B Verification Checklist

After all tasks complete:

- `web/src/styles/parts/base.css` line 121 contains `gap: var(--space-7)`.
- `web/src/styles/parts/dashboard.css` `.dashboard` rule contains `gap: var(--space-4)`.
- `web/src/styles/parts/components.css` line 1768 (or near it after edits) contains `gap: var(--space-3)`.
- `web/.stylelintrc.json` strict-value property list contains the 7 spacing entries.
- `npm run build` succeeds.
- `npm run lint:css` errors === 0 (warnings rose, expected).
- Visual: 5 routes render pixel-identical to pre-Plan-B.
- `git log --oneline -5` shows Tasks 1, 2, 3, 4 commits + spec status commit.

When all check, Plan C (card system unification) can begin: it consumes `--space-card-pad-hero` and the new spacing tokens to define `.surface-card` / `--hero` / `--list-row` variants.

---

## Out of Scope (Deferred)

- Retuning legacy `--space-card-pad: 22px` and `--space-card-gap: 20px` to 8pt grid → handled by Plan C when components migrate to `.surface-card`.
- Migrating per-component padding (e.g. `.dashboard-header` `1.05rem 1.15rem`) → flagged by stylelint warnings; gradual migration in Plans C–E or per-component cleanup.
- Stack/row utility classes (e.g. `.stack-4`, `.row-2`) → spec §9 marked "선택"; not needed yet because flexbox `gap` covers the use cases.
