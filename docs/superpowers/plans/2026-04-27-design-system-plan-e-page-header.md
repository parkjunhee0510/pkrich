# Design System — Plan E: Page Header Pattern (Pilot) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the 4-slot page-header pattern (eyebrow / headline / meta / actions) in a new `parts/page-header.css`, and apply it as the pilot on **one** route (`/api-status`). The other 4 routes from spec §8.3 (Watchlist, Portfolio, Signals, Ticker Detail) are deferred to follow-up plans, allowing for a single calibrated visual review before broader rollout.

**Architecture:** Pure CSS pattern — no React component abstraction yet (Open Question §12.1 deferred). Pilot route keeps its existing `<div className="api-status-page">` wrapper but replaces the inner `<div className="dashboard-header">` markup with the 4-slot `<header className="page-header">` structure. This is the **first plan that produces an intentional visual change** on its pilot — a calibrated band redesign on `/api-status` only, all other routes pixel-identical.

**Tech Stack:** CSS, React/TSX (one file edit). Spec reference: `docs/superpowers/specs/2026-04-27-design-system-foundation-design.md` §8.

**Why no tests:** No CSS unit-test harness. Verification is `npm run build`, `npm run lint:css` errors === 0, and manual visual check that (1) ApiStatus shows the new editorial-slot header layout, (2) all other routes render unchanged.

**Prerequisites:**
- Plans A, B, C, D landed. Verify: `cd web && grep -c '\\-\\-color-bg-page:' src/styles/parts/tokens.css` returns `1`.

**Out of scope (deferred):**
- Applying `.page-header` to Watchlist (`/`), Portfolio (`/portfolio`), Signals (`/signals`), Ticker Detail (`/ticker/:ticker`) — each is a separate follow-up plan with its own visual sign-off.
- Building a `<PageHeader eyebrow headline meta actions>` React component — Open Question §12.1; revisit when ≥3 routes have adopted the pattern and abstraction value is clear.
- Removing the legacy `.dashboard-header` rule — keeps working for non-pilot routes; remove in a later cleanup plan.

---

### Task 1: Create `parts/page-header.css` with the 4-slot pattern

**Files:**
- Create: `web/src/styles/parts/page-header.css`

- [ ] **Step 1: Write the file**

Write the full content to `web/src/styles/parts/page-header.css`:

```css
/* ============================================================
   Page header pattern (Plan E)
   Spec: 2026-04-27-design-system-foundation-design.md §8
   4-slot Editorial Slot pattern: eyebrow / headline / meta / actions.
   ============================================================ */

.page-header {
  padding: var(--space-6);
  background: var(--color-bg-page);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-card);
  margin-bottom: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.page-header__eyebrow {
  font-family: var(--font-sans);
  /* stylelint-disable-next-line scale-unlimited/declaration-strict-value */
  font-size: 10px;
  font-weight: 600;
  line-height: 1.5;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--color-fg-eyebrow);
}

.page-header__row {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.page-header__headline {
  font-family: var(--font-serif);
  /* stylelint-disable-next-line scale-unlimited/declaration-strict-value */
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.3px;
  color: var(--color-fg-headline);
  margin: 0;
}

.page-header__meta {
  font-family: var(--font-sans);
  /* stylelint-disable-next-line scale-unlimited/declaration-strict-value */
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5;
  color: var(--color-fg-muted);
  margin: 0;
}

.page-header__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  flex-shrink: 0;
}
```

- [ ] **Step 2: Verify standalone lint**

Run: `cd web && npx stylelint src/styles/parts/page-header.css 2>&1`
Expected: empty output (0 problems). All literals have inline disable comments or use tokens.

If warnings appear, recheck Step 1.

---

### Task 2: Wire the import into `global.css`

**Files:**
- Modify: `web/src/styles/global.css`

- [ ] **Step 1: Add `@import './parts/page-header.css';` after `tone.css`**

Edit `global.css`. The import block should read:

```css
/* AUTO-GENERATED: split into ./parts/*.css for maintainability.
   Edit individual files; this file only orders the cascade. */

@import './parts/tokens.css';
@import './parts/typography.css';
@import './parts/cards.css';
@import './parts/tone.css';
@import './parts/page-header.css';
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
Expected: `✓ built in <ms>`. CSS bundle slightly larger (~700 bytes for the 5 selectors).

- [ ] **Step 3: Verify total lint warnings did not jump**

Run: `cd web && npm run lint:css 2>&1 | tail -3`
Expected: warnings within ±5 of pre-Plan-E count (~960). page-header.css has zero warnings on its own.

- [ ] **Step 4: Commit**

```bash
git add web/src/styles/parts/page-header.css web/src/styles/global.css
git commit -m "feat(design-system): add .page-header 4-slot pattern (Plan E.1)"
```

---

### Task 3: Apply pilot — convert `/api-status` to the page-header pattern

**Files:**
- Modify: `web/src/pages/ApiStatus.tsx` (lines 108–123)

**Why this is safe enough:** Only one route changes. The conversion replaces an existing `.dashboard-header` block with semantically equivalent content in the new slots. The legacy `.dashboard-header` CSS is unaffected (it still renders on Signals and other routes). The visual change on `/api-status` is intentional — that's the point of the pilot.

- [ ] **Step 1: Replace the existing header block**

Open `web/src/pages/ApiStatus.tsx`. Find lines 108–123:

```tsx
    <div className="api-status-page">
      <div className="dashboard-header">
        <div>
          <h2>API 상태</h2>
          <p className="section-kicker">
            최신 파이프라인 실행 기준으로 공급자별 건강 상태와 티커별 실제 사용 여부를 확인합니다.
          </p>
        </div>
        <div className="api-status-run-meta">
          <span className={`api-state-pill ${data.summary.pipeline_completed ? 'state-used' : 'state-failed'}`}>
            {data.summary.pipeline_completed ? 'pipeline completed' : 'pipeline incomplete'}
          </span>
          <span className="status">{data.summary.run_date}</span>
        </div>
      </div>
```

Replace with:

```tsx
    <div className="api-status-page">
      <header className="page-header">
        <div className="page-header__eyebrow">DIAGNOSTICS · API STATUS</div>
        <div className="page-header__row">
          <h2 className="page-header__headline">API 상태</h2>
          <div className="page-header__actions">
            <span className={`api-state-pill ${data.summary.pipeline_completed ? 'state-used' : 'state-failed'}`}>
              {data.summary.pipeline_completed ? 'pipeline completed' : 'pipeline incomplete'}
            </span>
            <span className="status">{data.summary.run_date}</span>
          </div>
        </div>
        <p className="page-header__meta">
          최신 파이프라인 실행 기준으로 공급자별 건강 상태와 티커별 실제 사용 여부를 확인합니다.
        </p>
      </header>
```

Slot mapping:
- **eyebrow** — `DIAGNOSTICS · API STATUS` (section path per spec §8.4 rule)
- **headline** — `API 상태` (kept as-is, semantically the page title; serif treatment via `.page-header__headline`)
- **meta** — the long descriptive sentence (was `.section-kicker`)
- **actions** — pipeline status pill + run date (was `.api-status-run-meta`)

- [ ] **Step 2: Verify build**

Run: `cd web && npm run build`
Expected: `✓ built in <ms>`. No TypeScript errors.

- [ ] **Step 3: Visual check — ApiStatus**

Run: `cd web && npm run dev` (separate terminal).

Open `http://localhost:5173/api-status`. Expected:

- A new `.page-header` band at the top: cream background, 1px gold-soft border, 14px radius, 24px padding.
- Eyebrow `DIAGNOSTICS · API STATUS` in 10px gold uppercase.
- Headline `API 상태` in 28px Georgia serif.
- Right side: existing pill + run-date span (still using their legacy classes).
- Below: the description in 12px muted text.
- All cards below the header render unchanged (only the header markup changed).

- [ ] **Step 4: Smoke-check 4 other routes**

Confirm pixel-identical to pre-Plan-E:
- `http://localhost:5173/` (Watchlist) — unchanged
- `http://localhost:5173/portfolio` — unchanged
- `http://localhost:5173/signals` — `.dashboard-header` legacy still renders (NOT migrated in this plan); confirm signals page header looks the same as before
- `http://localhost:5173/ticker/AAPL` — unchanged

Plan E only modified ApiStatus.tsx. All other routes use legacy `.dashboard-header` CSS untouched.

- [ ] **Step 5: Stop dev server (Ctrl+C)**

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/ApiStatus.tsx
git commit -m "feat(design-system): apply page-header pattern to ApiStatus (Plan E.2)"
```

---

### Task 4: Push and update spec status

**Files:**
- Modify: `docs/superpowers/specs/2026-04-27-design-system-foundation-design.md`

- [ ] **Step 1: Update status line**

Change to:

```
**Status:** Plans A–E landed (full design system foundation: tokens, typography, spacing, card system + pilot, tone matrix + pilot, page-header pattern + pilot). Per-component / per-route migrations are follow-up work.
```

- [ ] **Step 2: Commit and push**

```bash
git add docs/superpowers/specs/2026-04-27-design-system-foundation-design.md
git commit -m "docs(design-system): mark Plan E complete in spec status"
git push origin main
```

Expected: 3 commits pushed (Tasks 1+2, Task 3, Task 4). No conflicts.

---

## Plan E Verification Checklist

After all tasks complete:

- `web/src/styles/parts/page-header.css` exists with `.page-header`, `.page-header__eyebrow`, `.page-header__row`, `.page-header__headline`, `.page-header__meta`, `.page-header__actions`. Total ~55 lines.
- `web/src/styles/global.css` `@import` order has `page-header.css` between `tone.css` and `base.css`.
- `web/src/pages/ApiStatus.tsx` uses `<header className="page-header">` with the 4-slot structure.
- `npm run build` succeeds.
- `npm run lint:css` errors === 0, warnings within ±5 of pre-Plan-E baseline.
- `/api-status` renders with the new band header.
- 4 other routes render pixel-identical.
- `git log --oneline -4` shows 3 Plan E commits + spec status commit.

When all check, the design-system foundation is **complete**. Future work is incremental:
- Roll out `.page-header` to remaining 4 spec routes — each as its own small plan with visual sign-off.
- Migrate the 15+ card definitions onto `.surface-card` — gradual.
- Migrate the 50+ pill/badge/chip definitions onto `.pill/.chip/.badge × .tone-*` — gradual.
- After ≥3 page-header adopters, decide on `<PageHeader>` React component (Open Question §12.1).
- Consider removing legacy rules (`.dashboard-header`, `.cozy-premium-banner`, etc.) once their usage is fully replaced.
