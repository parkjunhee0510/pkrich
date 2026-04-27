# Cozy Premium Theme Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the `web/` dashboard with the approved A+B hybrid cozy-premium theme — editorial serif headlines, gold top accents, soft modern cards — without changing information architecture.

**Architecture:** Additive refresh on top of the existing `cozy.css` overlay. New design tokens and typography utility classes are appended to a fresh `:root` block at the top of `cozy.css`; existing tokens and downstream consumers remain valid. Four components (`MarketRegimeBanner`, top navigation in `Layout`, `WatchlistTable`, `TraderDecisionBoard`) receive explicit restyling. No new runtime dependencies.

**Tech Stack:** React 19 + TypeScript (Vite), plain CSS (`cozy.css` overlay over `global.css`), Inter + JetBrains Mono already loaded in `web/index.html`.

**Spec:** `docs/superpowers/specs/2026-04-24-cozy-premium-theme-refresh-design.md`

**Verification model:** This project has no test framework. Each task verifies with (a) `npm run build` for TypeScript + Vite build success, (b) `npm run lint` for ESLint cleanliness, and (c) manual visual verification via `npm run dev` at named checkpoints.

---

## File Structure

**Files to create:**
- None (no new files — tokens/utilities added to existing `cozy.css`)

**Files to modify:**
- `web/src/styles/cozy.css` — Add refresh tokens + utility classes at top; retune existing values where they conflict
- `web/src/components/MarketRegimeBanner.tsx` — New structure (eyebrow, status dot, chip row)
- `web/src/components/WatchlistTable.tsx` — New row layout (serif ticker + sub company name, colored verdict badge, gold bar)
- `web/src/components/TraderDecisionBoard.tsx` — Decision Highlight composition refresh
- `web/src/components/Layout.tsx` — Nav structure tweaks (brand logo + date caption)
- `web/index.html` — Verify Inter already loaded; no change expected

**Files to inspect but not modify:**
- `web/src/styles/global.css` — Base layer; do not change
- `web/src/types.ts` — Confirm `MarketRegimeData` shape for typing new props if needed

---

## Token Conflict Resolution

**Conflict:** The spec declares `--cozy-border` as a color (`#e8dcc0`). The existing `cozy.css` already uses `--cozy-border` as a border shorthand (`1.5px solid var(--cozy-gold-soft)`).

**Resolution:** Deviate from the spec by introducing `--cozy-border-color: #e8dcc0` for color and keeping `--cozy-border` as the shorthand. Wherever the spec says `var(--cozy-border)` as a color, the plan uses `var(--cozy-border-color)`. Document this in a comment block in `cozy.css`.

---

## Task 1: Add Refresh Tokens to cozy.css

**Files:**
- Modify: `web/src/styles/cozy.css` (top of file, just under the existing `@import url(...)` line)

- [ ] **Step 1: Read the current top of cozy.css to find insertion point**

Run: Read `web/src/styles/cozy.css` lines 1-20 to locate the `@import` statement and the start of the existing `:root` block.

- [ ] **Step 2: Insert the refresh token block immediately after the existing `@import url(...)` line**

Add this CSS block (do NOT remove the existing `:root` that follows; these new values override by virtue of appearing first, and the override pattern documented below):

```css
/* ============================================================
   COZY PREMIUM REFRESH — 2026-04-24
   A+B hybrid: editorial serif + modern warm.
   Spec: docs/superpowers/specs/2026-04-24-cozy-premium-theme-refresh-design.md

   Note on --cozy-border: the existing skin uses this name as a
   border shorthand. We add --cozy-border-color for the color only
   and keep --cozy-border shorthand untouched for backward compat.
   ============================================================ */

:root {
  /* Refresh color palette (overrides warmer/darker cream + gold) */
  --cozy-cream:      #fbf6ec;
  --cozy-cream-2:    #f4ebd6;
  --cozy-paper:      #fdf9ef;
  --cozy-paper-2:    #f5ecd4;

  --cozy-ink:        #2a1f10;
  --cozy-ink-soft:   #4a3b22;
  --cozy-muted:      #8a7655;
  --cozy-border-color: #e8dcc0;

  --cozy-gold:       #b8893a;
  --cozy-gold-2:     #c9a14a;
  --cozy-gold-soft:  #e8d8a8;

  --cozy-good:       #3fa96b;
  --cozy-bad:        #c25a4e;
  --cozy-warn:       #d99a3a;

  /* Typography */
  --font-sans:  "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-serif: Georgia, "Times New Roman", serif;

  /* Shape */
  --radius-card: 16px;
  --radius-chip: 8px;
  --radius-pill: 999px;

  /* Space */
  --space-card-gap: 20px;
  --space-card-pad: 22px;

  /* Shadow scale */
  --shadow-sm: 0 1px 2px rgba(80,60,30,.04);
  --shadow:    0 1px 2px rgba(80,60,30,.04), 0 8px 24px -12px rgba(80,60,30,.14);
  --shadow-lg: 0 2px 4px rgba(80,60,30,.06), 0 20px 40px -20px rgba(80,60,30,.2);
}
```

- [ ] **Step 3: Run the build to confirm CSS still parses**

Run: `cd web && npm run build`
Expected: Build succeeds. No CSS parse error. Warnings unrelated to this task are OK.

- [ ] **Step 4: Commit**

```bash
cd "C:/Users/junhe/OneDrive/문서/pkrich"
git add web/src/styles/cozy.css
git commit -m "feat(web/theme): add cozy-premium refresh design tokens"
```

---

## Task 2: Add Typography Utility Classes to cozy.css

**Files:**
- Modify: `web/src/styles/cozy.css` (append at end of file)

- [ ] **Step 1: Append utility class block at end of `cozy.css`**

Add at the very bottom of the file:

```css
/* ============================================================
   COZY PREMIUM — Typography & Component Utilities
   ============================================================ */

/* Typography */
.cozy-eyebrow {
  font-family: var(--font-sans);
  font-size: 11px;
  letter-spacing: 2.5px;
  text-transform: uppercase;
  color: var(--cozy-gold);
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
.cozy-eyebrow .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--cozy-good);
  box-shadow: 0 0 0 4px rgba(63,169,107,.2);
}
.cozy-eyebrow .dot.warn { background: var(--cozy-warn); box-shadow: 0 0 0 4px rgba(217,154,58,.2); }
.cozy-eyebrow .dot.bad  { background: var(--cozy-bad);  box-shadow: 0 0 0 4px rgba(194,90,78,.2); }

.cozy-headline {
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 700;
  color: var(--cozy-ink);
  margin: 0;
  letter-spacing: -0.5px;
  line-height: 1.15;
}
.cozy-headline em { font-style: italic; color: var(--cozy-gold); }

.cozy-impl {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 14px;
  color: var(--cozy-ink-soft);
  line-height: 1.5;
  margin: 0;
}

.cozy-body {
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 1.5;
  color: var(--cozy-ink-soft);
}

.cozy-caption {
  font-family: var(--font-sans);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--cozy-muted);
  font-weight: 700;
}

.cozy-numeric {
  font-family: var(--font-sans);
  font-variant-numeric: tabular-nums;
}

.cozy-numeric-xl {
  font-family: var(--font-serif);
  font-size: 42px;
  font-weight: 700;
  color: var(--cozy-ink);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

/* Component utilities */
.cozy-pill {
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 600;
  color: var(--cozy-ink);
  background: var(--cozy-gold-soft);
  padding: 4px 11px;
  border-radius: var(--radius-pill);
  letter-spacing: 0.2px;
  display: inline-block;
}

.cozy-chip {
  font-family: var(--font-sans);
  font-size: 12px;
  padding: 6px 10px;
  background: rgba(255,255,255,0.7);
  border: 1px solid var(--cozy-border-color);
  border-radius: var(--radius-chip);
  color: var(--cozy-ink-soft);
  font-variant-numeric: tabular-nums;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.cozy-chip b { color: var(--cozy-ink); font-weight: 600; }
.cozy-chip .score-plus  { color: var(--cozy-good); font-weight: 700; }
.cozy-chip .score-minus { color: var(--cozy-bad);  font-weight: 700; }
```

- [ ] **Step 2: Run build to confirm CSS still parses**

Run: `cd web && npm run build`
Expected: Build succeeds.

- [ ] **Step 3: Run lint**

Run: `cd web && npm run lint`
Expected: No new errors introduced.

- [ ] **Step 4: Commit**

```bash
cd "C:/Users/junhe/OneDrive/문서/pkrich"
git add web/src/styles/cozy.css
git commit -m "feat(web/theme): add cozy-premium typography and chip/pill utilities"
```

---

## Task 3: Restyle `MarketRegimeBanner`

**Files:**
- Modify: `web/src/components/MarketRegimeBanner.tsx`
- Modify: `web/src/styles/cozy.css` (append banner-specific rules)

- [ ] **Step 1: Replace `MarketRegimeBanner.tsx` with the new structure**

Overwrite the file with:

```tsx
import type { MarketRegimeData } from '../types'

type RegimeKind = 'risk_on' | 'neutral' | 'risk_off'

const REGIME_CONFIG: Record<RegimeKind, { dotClass: string; label: string; className: string }> = {
  risk_on:  { dotClass: '',      label: '공격적으로 보기 좋은 장세', className: 'regime-risk-on' },
  neutral:  { dotClass: 'warn',  label: '중립 장세',                  className: 'regime-neutral' },
  risk_off: { dotClass: 'bad',   label: '조심스럽게 봐야 하는 장세',  className: 'regime-risk-off' },
}

interface MarketRegimeBannerProps {
  regime: MarketRegimeData | null | undefined
}

function formatEyebrowDate(assessedAt: string | undefined): string {
  if (!assessedAt) return ''
  const d = new Date(assessedAt)
  if (Number.isNaN(d.getTime())) return ''
  const months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
  return `${months[d.getMonth()]} ${String(d.getDate()).padStart(2, '0')}`
}

export function MarketRegimeBanner({ regime }: MarketRegimeBannerProps) {
  if (!regime || !regime.regime) return null

  const kind = (regime.regime as RegimeKind) in REGIME_CONFIG
    ? (regime.regime as RegimeKind)
    : 'neutral'
  const config = REGIME_CONFIG[kind]
  const driverEntries = Object.entries(regime.drivers ?? {})
  const eyebrowDate = formatEyebrowDate(regime.assessedAt)

  return (
    <section className={`market-regime-banner cozy-premium-banner ${config.className}`}>
      <div className="cozy-eyebrow">
        <span className={`dot ${config.dotClass}`.trim()}></span>
        MARKET REGIME{eyebrowDate ? ` · ${eyebrowDate}` : ''}
      </div>
      <div className="regime-head-row">
        <h3 className="cozy-headline">{config.label}</h3>
        <span className="cozy-pill">확신도 {regime.confidence}%</span>
      </div>
      {regime.implication ? <p className="cozy-impl">{regime.implication}</p> : null}
      {driverEntries.length > 0 ? (
        <div className="regime-drivers">
          {driverEntries.map(([key, value]) => (
            <span key={key} className="cozy-chip regime-driver-chip">
              {value}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  )
}
```

- [ ] **Step 2: Verify `MarketRegimeData` type has `assessedAt` (or adjust)**

Run: Read `web/src/types.ts` and search for `MarketRegimeData`. Confirm field name.
- If the field is `assessed_at` (snake_case), change `regime.assessedAt` to `regime.assessed_at` in Step 1's code.
- If no such field exists, remove the `eyebrowDate` usage entirely: render the eyebrow as just `MARKET REGIME`.

- [ ] **Step 3: Append banner-specific CSS to `cozy.css`**

Append at end of `cozy.css`:

```css
/* ============================================================
   COZY PREMIUM — Market Regime Banner
   ============================================================ */
.market-regime-banner.cozy-premium-banner {
  background: linear-gradient(180deg, var(--cozy-paper) 0%, var(--cozy-paper-2) 100%);
  border: 1px solid var(--cozy-border-color);
  border-radius: var(--radius-card);
  padding: 22px 26px 20px;
  box-shadow: var(--shadow);
  position: relative;
  overflow: hidden;
  margin-bottom: var(--space-card-gap);
}
.market-regime-banner.cozy-premium-banner::before {
  content: "";
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--cozy-gold) 0%, var(--cozy-gold-2) 50%, var(--cozy-gold) 100%);
}
.market-regime-banner.cozy-premium-banner .cozy-eyebrow {
  margin-bottom: 10px;
}
.market-regime-banner.cozy-premium-banner .regime-head-row {
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.market-regime-banner.cozy-premium-banner .cozy-impl {
  margin-bottom: 14px;
}
.market-regime-banner.cozy-premium-banner .regime-drivers {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
```

- [ ] **Step 4: Run build + lint**

Run: `cd web && npm run build && npm run lint`
Expected: Both succeed.

- [ ] **Step 5: Manual visual verification**

Run: `cd web && npm run dev` in a separate terminal. Open `http://localhost:5173/` (or the port Vite reports). Confirm:
1. Market Regime banner shows a gold gradient top line (3px).
2. Eyebrow reads `MARKET REGIME · <MMM DD>` with a colored status dot.
3. Headline is serif with `em` in gold italic if the label contains emphasis.
4. Pill badge on the right reads `확신도 NN%`.
5. Driver chips show the `[점수 +N]` formatting inherited from the backend.
6. Stop the dev server.

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/junhe/OneDrive/문서/pkrich"
git add web/src/components/MarketRegimeBanner.tsx web/src/styles/cozy.css
git commit -m "feat(web/banner): restyle MarketRegimeBanner with cozy-premium polish"
```

---

## Task 4: Restyle Top Navigation

**Files:**
- Modify: `web/src/components/Layout.tsx`
- Modify: `web/src/styles/cozy.css` (append nav rules)

- [ ] **Step 1: Read current `Layout.tsx`**

Run: Read `web/src/components/Layout.tsx` in full. Identify the element that wraps the nav links (likely `<nav>` with class `app-nav` or similar) and where links are rendered.

- [ ] **Step 2: Locate the existing nav structure and add brand + date caption**

Edit `Layout.tsx` to ensure the nav container has:
- A leading brand element `<span className="cozy-brand">pk<em>rich</em></span>`
- A trailing date caption `<span className="cozy-nav-date">{todayLabel}</span>` where `todayLabel` is computed at render time:

Add near the top of the component body (before the return):

```tsx
const today = new Date()
const weekdays = ['SUNDAY','MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY']
const months = ['JANUARY','FEBRUARY','MARCH','APRIL','MAY','JUNE','JULY','AUGUST','SEPTEMBER','OCTOBER','NOVEMBER','DECEMBER']
const todayLabel = `${weekdays[today.getDay()]} · ${months[today.getMonth()]} ${today.getDate()}, ${today.getFullYear()}`
```

Insert the brand `<span>` as the first child inside the nav container, and the date `<span>` as the last child. Leave existing `NavLink`s unchanged structurally.

If there is no single `<nav>` wrapper (for example, the header holds multiple rows), only add the brand + date to the same row the nav links live in.

- [ ] **Step 3: Append nav-specific CSS to `cozy.css`**

Append at end of `cozy.css`:

```css
/* ============================================================
   COZY PREMIUM — Top Navigation
   ============================================================ */
.cozy-brand {
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 18px;
  color: var(--cozy-ink);
  letter-spacing: -0.3px;
  margin-right: 22px;
}
.cozy-brand em {
  color: var(--cozy-gold);
  font-style: italic;
}

.cozy-nav-date {
  margin-left: auto;
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--cozy-muted);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.5px;
}

/* Active nav link: dark ink bg, gold-soft text (resolves prior invisibility) */
.nav-link.nav-active,
.nav-link.active,
a.nav-link[aria-current="page"] {
  background: var(--cozy-ink);
  color: var(--cozy-gold-soft) !important;
  border-color: var(--cozy-ink);
  font-weight: 600;
}
```

- [ ] **Step 4: Run build + lint**

Run: `cd web && npm run build && npm run lint`
Expected: Both succeed.

- [ ] **Step 5: Manual visual verification**

Run: `cd web && npm run dev`. Confirm:
1. Top nav shows `pkrich` (with `rich` in italic gold) on the far left.
2. Today's date shows uppercase on the far right (e.g. `FRIDAY · APRIL 24, 2026`).
3. Active nav link has dark ink background + gold-soft text, clearly visible.
4. Inactive nav links remain in muted/brown tone.
5. Stop the dev server.

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/junhe/OneDrive/문서/pkrich"
git add web/src/components/Layout.tsx web/src/styles/cozy.css
git commit -m "feat(web/nav): add serif brand logo, date caption, and hardened active-link contrast"
```

---

## Task 5: Restyle `WatchlistTable`

**Files:**
- Modify: `web/src/components/WatchlistTable.tsx`
- Modify: `web/src/styles/cozy.css` (append watchlist rules)

- [ ] **Step 1: Read current `WatchlistTable.tsx`**

Run: Read `web/src/components/WatchlistTable.tsx` in full. Identify:
- The table element and its class (likely `.watchlist`, `.watchlist-table`, or similar)
- The row structure for a ticker (ticker symbol, price, daily change, verdict, conviction)
- The class used for verdict buckets (e.g. `buy` / `watch` / `avoid`)

- [ ] **Step 2: Add `cozy-premium-watchlist` class to the table container**

Add the class `cozy-premium-watchlist` to the outermost wrapper (keep existing classes). Inside each row, ensure:
- The ticker symbol is rendered inside `<span className="cozy-ticker">` and the company name inside `<span className="cozy-company">`. If the component does not currently render the company name, add it conditionally only if the data source provides it; otherwise skip.
- Verdict is rendered as `<span className={\`cozy-badge ${verdictKind}\`}>` where `verdictKind` is one of `buy`, `watch`, `avoid` (derive from existing logic).
- Conviction cell renders `<span className="cozy-score-bar" style={{ ['--fill' as any]: \`${score}%\` }} /> <span className="cozy-numeric">{score}</span>`.

Do not rename any existing props or change the component's external API.

- [ ] **Step 3: Append watchlist CSS to `cozy.css`**

Append at end of `cozy.css`:

```css
/* ============================================================
   COZY PREMIUM — Watchlist
   ============================================================ */
.cozy-premium-watchlist {
  background: var(--cozy-cream);
  border: 1px solid var(--cozy-border-color);
  border-radius: var(--radius-card);
  padding: 18px 22px 20px;
  box-shadow: var(--shadow-sm);
}
.cozy-premium-watchlist table { width: 100%; border-collapse: collapse; font-size: 13px; font-family: var(--font-sans); }
.cozy-premium-watchlist th {
  text-align: left;
  font-size: 10px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--cozy-muted);
  font-weight: 700;
  padding: 0 0 8px;
}
.cozy-premium-watchlist th.num,
.cozy-premium-watchlist td.num { text-align: right; font-variant-numeric: tabular-nums; }
.cozy-premium-watchlist td {
  padding: 10px 0;
  border-top: 1px solid rgba(232,220,192,.5);
  color: var(--cozy-ink-soft);
}
.cozy-premium-watchlist tr:hover td { background: var(--cozy-cream-2); }

.cozy-ticker {
  font-family: var(--font-serif);
  font-weight: 700;
  color: var(--cozy-ink);
  font-size: 15px;
  letter-spacing: 0.3px;
}
.cozy-company {
  display: block;
  font-size: 11px;
  color: var(--cozy-muted);
  font-weight: 400;
  font-family: var(--font-sans);
  letter-spacing: 0;
}

.cozy-badge {
  font-family: var(--font-sans);
  font-size: 10px;
  padding: 3px 8px;
  border-radius: var(--radius-pill);
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  display: inline-block;
}
.cozy-badge.buy   { background: rgba(63,169,107,.14); color: #2a7a4a; border: 1px solid rgba(63,169,107,.3); }
.cozy-badge.watch { background: rgba(217,154,58,.15); color: #8a5e16; border: 1px solid rgba(217,154,58,.35); }
.cozy-badge.avoid { background: rgba(194,90,78,.12); color: #8a3e34; border: 1px solid rgba(194,90,78,.3); }

.cozy-score-bar {
  display: inline-block;
  width: 46px;
  height: 6px;
  border-radius: 3px;
  background: var(--cozy-cream-2);
  position: relative;
  overflow: hidden;
  vertical-align: middle;
  margin-right: 8px;
}
.cozy-score-bar::after {
  content: "";
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: var(--fill, 0%);
  background: linear-gradient(90deg, var(--cozy-gold), var(--cozy-gold-2));
}
```

- [ ] **Step 4: Run build + lint**

Run: `cd web && npm run build && npm run lint`
Expected: Both succeed.

- [ ] **Step 5: Manual visual verification**

Run: `cd web && npm run dev`. Confirm:
1. Watchlist cards use the cream background with a soft shadow and 16px radius.
2. Ticker symbols render in Georgia serif, company names below in small muted sans.
3. Verdict badges are colored pills (green/yellow/red).
4. Conviction column shows a short gold bar with fill proportional to score.
5. Row hover tints to cream-2.
6. Stop the dev server.

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/junhe/OneDrive/문서/pkrich"
git add web/src/components/WatchlistTable.tsx web/src/styles/cozy.css
git commit -m "feat(web/watchlist): restyle rows with serif tickers, verdict badges, gold conviction bars"
```

---

## Task 6: Restyle `TraderDecisionBoard` Highlight Card

**Files:**
- Modify: `web/src/components/TraderDecisionBoard.tsx`
- Modify: `web/src/styles/cozy.css` (append decision rules)

- [ ] **Step 1: Read current `TraderDecisionBoard.tsx`**

Run: Read `web/src/components/TraderDecisionBoard.tsx` in full. Identify:
- The element that renders the top-conviction / primary decision (big score + verdict + reason)
- Whether a CTA button ("자세히 보기" or similar) already exists

- [ ] **Step 2: Wrap the primary decision row with the highlight composition**

Add the class `cozy-premium-decision` to the outermost element of the highlight card. Inside, ensure three columns exist:
- Left: `<div className="cozy-numeric-xl">{score}<small>/100</small></div>`
- Middle: eyebrow (`TOP CONVICTION · <TICKER>`), serif verdict headline, reason sentence
- Right: existing CTA button, augmented with `className="cozy-cta"`

If the component currently uses a different layout (e.g. a table row), add the `cozy-premium-decision` grid only when the component is rendering a single highlighted top pick — do not break list rendering.

- [ ] **Step 3: Append decision CSS to `cozy.css`**

Append at end of `cozy.css`:

```css
/* ============================================================
   COZY PREMIUM — Decision Highlight
   ============================================================ */
.cozy-premium-decision {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 18px;
  align-items: center;
  background: var(--cozy-cream);
  border: 1px solid var(--cozy-border-color);
  border-radius: var(--radius-card);
  padding: 18px 22px;
  box-shadow: var(--shadow);
  margin-bottom: var(--space-card-gap);
  font-family: var(--font-sans);
}
.cozy-premium-decision .cozy-numeric-xl small {
  font-family: var(--font-sans);
  font-size: 16px;
  color: var(--cozy-muted);
  font-weight: 400;
  margin-left: 2px;
}
.cozy-premium-decision .cozy-eyebrow { margin-bottom: 3px; }
.cozy-premium-decision .verdict {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  color: var(--cozy-ink);
  margin: 0 0 3px;
}
.cozy-premium-decision .reason {
  font-size: 13px;
  color: var(--cozy-ink-soft);
  margin: 0;
}
.cozy-cta {
  background: var(--cozy-ink);
  color: var(--cozy-gold-soft);
  border: 0;
  padding: 10px 16px;
  border-radius: 10px;
  font-family: var(--font-sans);
  font-weight: 600;
  font-size: 13px;
  letter-spacing: 0.3px;
  cursor: pointer;
}
.cozy-cta:hover { background: var(--cozy-ink-soft); }

@media (max-width: 640px) {
  .cozy-premium-decision {
    grid-template-columns: 1fr;
    gap: 10px;
  }
}
```

- [ ] **Step 4: Run build + lint**

Run: `cd web && npm run build && npm run lint`
Expected: Both succeed.

- [ ] **Step 5: Manual visual verification**

Run: `cd web && npm run dev`. Confirm:
1. Decision highlight card shows a 3-column layout on desktop (big serif score | eyebrow + verdict + reason | CTA).
2. The big score uses Georgia serif at 42px with `/100` in smaller muted sans.
3. The CTA button is dark ink with gold-soft text, hover shifts to ink-soft.
4. On narrow screens the card stacks vertically.
5. Stop the dev server.

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/junhe/OneDrive/문서/pkrich"
git add web/src/components/TraderDecisionBoard.tsx web/src/styles/cozy.css
git commit -m "feat(web/decision): restyle top-conviction highlight with serif score and dark CTA"
```

---

## Task 7: Final Verification and Push

**Files:**
- Inspect only

- [ ] **Step 1: Full build**

Run: `cd web && npm run build`
Expected: `tsc -b` passes, `vite build` passes, SPA fallback script runs.

- [ ] **Step 2: Full lint**

Run: `cd web && npm run lint`
Expected: Zero new errors. Existing unrelated errors, if any, unchanged.

- [ ] **Step 3: End-to-end visual pass**

Run: `cd web && npm run dev`. Walk the app:
1. `/` (Dashboard) — banner, decision highlight, watchlist all reflect new style
2. Navigate between 3 top nav tabs — active state is always legible, date caption persists
3. At least one ticker detail — verify nothing that previously used `var(--cozy-cream)` etc. has regressed visually (colors slightly warmer is expected and intended)
4. Stop the dev server.

- [ ] **Step 4: Accessibility spot-check**

In the running app (or from the CSS), confirm these text/background pairs are visually legible (target: WCAG AA 4.5:1 for body, 3:1 for large text):
- `.cozy-muted` (#8a7655) on `.cozy-cream` (#fbf6ec) — body caption
- `.cozy-gold-soft` (#e8d8a8) on `.cozy-ink` (#2a1f10) — active nav link, CTA text
- `.cozy-badge.watch` amber text on its tinted background
If any pair looks marginal, log an open question (do not fix in this plan — defer to a follow-up).

- [ ] **Step 5: Push**

```bash
cd "C:/Users/junhe/OneDrive/문서/pkrich"
git push
```

Expected: Push succeeds to `main` (or the current branch).

- [ ] **Step 6: Close out**

Leave a final note in the session summarizing: the 6 commits landed, which pages were visually verified, any a11y follow-ups that deferred.

---

## Notes for the Implementer

- **Every new class is additive.** Do not remove or rename any existing class on an element — add the new `cozy-*` class alongside. This keeps regressions to zero on pages we did not explicitly re-style.
- **`cozy.css` grows long.** That is expected for this refresh. A future pass may split `cozy.css` into `cozy.tokens.css` / `cozy.components.css`, but that split is explicitly out of scope here.
- **Inter is already loaded** via `web/index.html` (existing `@import` in cozy.css also pulls three extra fonts, which are unused but harmless). No change to `index.html` required.
- **If `npm run build` fails with a type error unrelated to this work**, stop and surface the error — do not suppress.
