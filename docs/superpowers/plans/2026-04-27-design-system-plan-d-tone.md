# Design System — Plan D: Pill/Badge/Chip Tone System (Pilot) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the `.pill` / `.chip` / `.badge` shape classes × `.tone-{role}--{treatment}` matrix (5 semantic roles × 3 treatments = 15 modifier classes) in a new `parts/tone.css`, and apply it as an additive layer to one pilot adopter (Market Regime Banner driver chips). Migration of 50+ existing pills is deferred to follow-up plans.

**Architecture:** Two-class composition — shape (`.pill`/`.chip`/`.badge`) plus tone (`.tone-positive--solid`, etc.). Pilot adoption is purely additive: existing rules with higher specificity (e.g. `.market-regime-banner.cozy-premium-banner .cozy-chip.regime-driver-chip` at `(0,0,3,0)`) keep winning, so pixel rendering is unchanged. The new system is staged for future migrations.

**Tech Stack:** CSS, React/TSX (one className edit). Spec reference: `docs/superpowers/specs/2026-04-27-design-system-foundation-design.md` §7. Color tokens are from Plan A.2 (`--color-positive`, `--color-positive-fg`, `--color-positive-soft-bg`, etc.).

**Why no tests:** No CSS unit-test harness. Verification is `npm run build`, `npm run lint:css` errors === 0, visual diff on 5 routes (pixel-identical expected because legacy specificity wins).

**Prerequisites:**
- Plans A, B, C landed. Verify: `cd web && grep -c '\\-\\-color-positive-soft-bg:' src/styles/parts/tokens.css` returns `1`.

**Out of scope (deferred):**
- Migrating 50+ existing pill/badge/chip definitions (`.watchlist-decision-pill`, `.options-chip`, `.setup-score-badge`, etc.) — too many call sites; gradual per-component plans.
- Removing legacy `.cozy-chip` and `.regime-driver-chip` rules — kept until all adopters migrate.
- Producing a comprehensive class-mapping table — the spec's §7.5 has the high-level mapping; per-component plans will refine.

---

### Task 1: Create `parts/tone.css` with shape and tone matrix

**Files:**
- Create: `web/src/styles/parts/tone.css`

- [ ] **Step 1: Write the file**

Write the full content to `web/src/styles/parts/tone.css`:

```css
/* ============================================================
   Pill / Chip / Badge tone system (Plan D)
   Spec: 2026-04-27-design-system-foundation-design.md §7
   Compose: shape class + tone class.
     <span class="pill tone-positive--solid">BUY</span>
     <span class="chip tone-positive--soft">EPS BEAT</span>
     <span class="badge tone-accent--soft">78</span>
   Specificity is intentionally low (single class, 0,0,1,0) so existing
   component rules with compound selectors keep winning during gradual
   migration.
   ============================================================ */

/* ---------- Shape ---------- */

.pill {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 4px 14px;
  border-radius: var(--radius-pill);
  font-family: var(--font-sans);
  /* stylelint-disable-next-line scale-unlimited/declaration-strict-value */
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.3px;
  line-height: 1.4;
  white-space: nowrap;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 4px 10px;
  border-radius: var(--radius-chip);
  font-family: var(--font-sans);
  /* stylelint-disable-next-line scale-unlimited/declaration-strict-value */
  font-size: 11px;
  font-weight: 600;
  line-height: 1.4;
  white-space: nowrap;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 3px 8px;
  border-radius: var(--radius-badge);
  font-family: var(--font-sans);
  /* stylelint-disable-next-line scale-unlimited/declaration-strict-value */
  font-size: 10px;
  font-weight: 700;
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* ---------- Tone × Treatment matrix ----------
   5 semantic roles (positive, negative, caution, info, accent)
   × 3 treatments (solid, soft, outline)
   = 15 utility modifiers.
   Each treatment provides {background, color, border}. */

/* Solid — strong fill. Use sparingly: max 1 per card. */
.tone-positive--solid {
  background: var(--color-positive);
  color: var(--color-positive-fg);
  border: 1px solid var(--color-positive);
}
.tone-negative--solid {
  background: var(--color-negative);
  color: var(--color-negative-fg);
  border: 1px solid var(--color-negative);
}
.tone-caution--solid {
  background: var(--color-caution);
  color: var(--color-caution-fg);
  border: 1px solid var(--color-caution);
}
.tone-info--solid {
  background: var(--color-info);
  color: var(--color-info-fg);
  border: 1px solid var(--color-info);
}
.tone-accent--solid {
  background: var(--color-accent);
  color: var(--color-accent-fg);
  border: 1px solid var(--color-accent);
}

/* Soft — light tint background, dark text, subtle border. Default for meta. */
.tone-positive--soft {
  background: var(--color-positive-soft-bg);
  color: var(--color-positive-soft-fg);
  border: 1px solid var(--color-positive-soft-border);
}
.tone-negative--soft {
  background: var(--color-negative-soft-bg);
  color: var(--color-negative-soft-fg);
  border: 1px solid var(--color-negative-soft-border);
}
.tone-caution--soft {
  background: var(--color-caution-soft-bg);
  color: var(--color-caution-soft-fg);
  border: 1px solid var(--color-caution-soft-border);
}
.tone-info--soft {
  background: var(--color-info-soft-bg);
  color: var(--color-info-soft-fg);
  border: 1px solid var(--color-info-soft-border);
}
.tone-accent--soft {
  background: var(--color-accent-soft-bg);
  color: var(--color-accent-soft-fg);
  border: 1px solid var(--color-accent-soft-border);
}

/* Outline — white background, colored border, colored text. For inactive / candidate states. */
.tone-positive--outline {
  background: var(--color-bg-card);
  color: var(--color-positive-outline-fg);
  border: 1px solid var(--color-positive-outline-border);
}
.tone-negative--outline {
  background: var(--color-bg-card);
  color: var(--color-negative-outline-fg);
  border: 1px solid var(--color-negative-outline-border);
}
.tone-caution--outline {
  background: var(--color-bg-card);
  color: var(--color-caution-outline-fg);
  border: 1px solid var(--color-caution-outline-border);
}
.tone-info--outline {
  background: var(--color-bg-card);
  color: var(--color-info-outline-fg);
  border: 1px solid var(--color-info-outline-border);
}
.tone-accent--outline {
  background: var(--color-bg-card);
  color: var(--color-accent-outline-fg);
  border: 1px solid var(--color-accent-outline-border);
}
```

- [ ] **Step 2: Verify standalone lint**

Run: `cd web && npx stylelint src/styles/parts/tone.css 2>&1`
Expected: empty output (0 problems). Padding/font-size literals are explicitly disabled inline; all colors come from tokens.

If warnings appear, recheck Step 1 — every `font-size` line needs the disable comment.

---

### Task 2: Wire the import into `global.css`

**Files:**
- Modify: `web/src/styles/global.css`

- [ ] **Step 1: Add `@import './parts/tone.css';` after `cards.css`**

Edit `global.css`. The import block should read:

```css
/* AUTO-GENERATED: split into ./parts/*.css for maintainability.
   Edit individual files; this file only orders the cascade. */

@import './parts/tokens.css';
@import './parts/typography.css';
@import './parts/cards.css';
@import './parts/tone.css';
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
Expected: `✓ built in <ms>`. CSS bundle slightly larger (~1.5KB for the matrix).

- [ ] **Step 3: Verify total lint warnings did not jump**

Run: `cd web && npm run lint:css 2>&1 | tail -3`
Expected: warnings within ±5 of pre-Plan-D count (~960). tone.css has zero warnings on its own.

- [ ] **Step 4: Commit**

```bash
git add web/src/styles/parts/tone.css web/src/styles/global.css
git commit -m "feat(design-system): add .pill/.chip/.badge × .tone-* matrix (Plan D.1)"
```

---

### Task 3: Apply pilot — `.chip.tone-info--soft` on Market Regime Banner driver chips

**Files:**
- Modify: `web/src/components/MarketRegimeBanner.tsx`

**Why this is safe:** The existing rule `.market-regime-banner.cozy-premium-banner .cozy-chip.regime-driver-chip` has specificity `(0,0,3,0)`, which beats `.chip.tone-info--soft` at `(0,0,2,0)`. So the existing chip styling continues to render. Adding the new classes is a label — proves the system runs alongside without conflict.

- [ ] **Step 1: Edit the className**

Open `web/src/components/MarketRegimeBanner.tsx`. Find line 47 (the driver-chip span):

```tsx
<span key={key} className="cozy-chip regime-driver-chip">
```

Change to:

```tsx
<span key={key} className="chip tone-info--soft cozy-chip regime-driver-chip">
```

The new classes (`chip` + `tone-info--soft`) come first as the design-system "label"; legacy classes follow.

- [ ] **Step 2: Verify build**

Run: `cd web && npm run build`
Expected: `✓ built in <ms>`. No TypeScript errors.

- [ ] **Step 3: Visual diff — Market Regime Banner driver chips**

Run: `cd web && npm run dev` (separate terminal).

Open `http://localhost:5173/` and inspect the driver chips below the regime headline. Expected:

- Chip background, border, and text color identical to pre-Plan-D (legacy rule wins).
- DOM inspector shows both class sets applied.

If anything visually changes, stop and inspect: dev-tools → Computed tab → confirm the legacy `.market-regime-banner.cozy-premium-banner .cozy-chip.regime-driver-chip` rule supplies `background`, `color`, `border`.

- [ ] **Step 4: Smoke-check 4 other routes**

Confirm pixel-identical to pre-Plan-D:
- `http://localhost:5173/portfolio`
- `http://localhost:5173/signals`
- `http://localhost:5173/ticker/AAPL`
- `http://localhost:5173/api-status`

Plan D modified no other component, so all should render unchanged.

- [ ] **Step 5: Stop dev server (Ctrl+C)**

- [ ] **Step 6: Commit**

```bash
git add web/src/components/MarketRegimeBanner.tsx
git commit -m "feat(design-system): apply .chip.tone-info--soft to regime drivers (Plan D.2)"
```

---

### Task 4: Push and update spec status

**Files:**
- Modify: `docs/superpowers/specs/2026-04-27-design-system-foundation-design.md`

- [ ] **Step 1: Update status line**

Change to:

```
**Status:** Plans A, B, C, D landed (tokens, typography, spacing, card system + 1 pilot, tone system + 1 pilot). Plan E pending. Per-component migrations of cards (15+) and pills (50+) are follow-up work.
```

- [ ] **Step 2: Commit and push**

```bash
git add docs/superpowers/specs/2026-04-27-design-system-foundation-design.md
git commit -m "docs(design-system): mark Plan D complete in spec status"
git push origin main
```

Expected: 3 commits pushed (Tasks 1+2, Task 3, Task 4). No conflicts.

---

## Plan D Verification Checklist

After all tasks complete:

- `web/src/styles/parts/tone.css` exists with `.pill`, `.chip`, `.badge`, plus 15 `.tone-{role}--{treatment}` modifiers (5 roles × 3 treatments). Total ~115 lines.
- `web/src/styles/global.css` `@import` order has `tone.css` between `cards.css` and `base.css`.
- `web/src/components/MarketRegimeBanner.tsx` line 47 className includes `chip tone-info--soft` prefix.
- `npm run build` succeeds.
- `npm run lint:css` errors === 0, warnings within ±5 of pre-Plan-D baseline.
- Market Regime Banner driver chips render pixel-identical (legacy specificity wins).
- 4 other routes render pixel-identical.
- `git log --oneline -4` shows 3 Plan D commits + spec status commit.

When all check, the next step is **Plan E (page header pattern)**, the final design-system foundation plan. After that, follow-up work is incremental per-component migration of the 15+ cards and 50+ pills onto the established matrix.
