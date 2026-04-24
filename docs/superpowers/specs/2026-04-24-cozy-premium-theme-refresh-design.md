# Cozy Premium Theme Refresh — Design Spec

**Date:** 2026-04-24
**Scope:** Global theme refresh of the `web/` dashboard
**Direction:** A + B hybrid — Editorial Magazine (Bloomberg Businessweek feel) fused with Modern Warm (Linear/Stripe-style soft shadows and rounded shapes)

---

## 1. Goal

Make the dashboard visibly prettier and more premium without changing its information architecture. The current `cozy.css` overlay is functional but flat: uniform shadows, inconsistent typographic hierarchy, and no visual distinction between primary vs. supporting blocks. The refresh introduces a disciplined token system, a serif/sans typography pair, and a three-tier shadow scale so the eye knows what to read first.

Non-goals: dark mode, mobile redesign, chart recoloring, information architecture changes.

---

## 2. Design Tokens

All tokens live in `web/src/styles/cozy.css` under a single `:root` block. Existing variable names are kept where possible; new names use the `--cozy-` prefix.

### 2.1 Color

```
--cozy-cream:      #fbf6ec   /* page / card base */
--cozy-cream-2:    #f4ebd6   /* secondary surface, hover */
--cozy-paper:      #fdf9ef   /* banner gradient start */
--cozy-paper-2:    #f5ecd4   /* banner gradient end */

--cozy-ink:        #2a1f10   /* headlines, strong numbers */
--cozy-ink-soft:   #4a3b22   /* body text */
--cozy-muted:      #8a7655   /* captions, eyebrow neutral */
--cozy-border:     #e8dcc0   /* all borders, hairlines */

--cozy-gold:       #b8893a   /* primary accent */
--cozy-gold-2:     #c9a14a   /* gradient pair with gold */
--cozy-gold-soft:  #e8d8a8   /* pill / badge backgrounds */

--cozy-good:       #3fa96b   /* up moves, Buy verdict */
--cozy-bad:        #c25a4e   /* down moves, Avoid verdict */
--cozy-warn:       #d99a3a   /* Watch verdict */
```

### 2.2 Typography

```
--font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
--font-serif: Georgia, "Times New Roman", serif;
```

- Sans is default for body, UI controls, numbers.
- Serif is used only for headlines (h2/h3/h4), ticker symbols, large numeric displays, and the brand logo.
- All numeric cells apply `font-variant-numeric: tabular-nums`.

Inter is loaded via Google Fonts `<link>` in `web/index.html` with `display=swap`; fallback to system sans if blocked.

### 2.3 Shape & Space

```
--radius-card:   16px
--radius-chip:   8px
--radius-pill:   999px

--space-card-gap: 20px
--space-card-pad: 22px
```

### 2.4 Shadows (three-tier scale)

```
--shadow-sm: 0 1px 2px rgba(80,60,30,.04);
--shadow:    0 1px 2px rgba(80,60,30,.04), 0 8px 24px -12px rgba(80,60,30,.14);
--shadow-lg: 0 2px 4px rgba(80,60,30,.06), 0 20px 40px -20px rgba(80,60,30,.2);
```

Usage:
- `shadow-sm` — list cards, watchlist, secondary panels
- `shadow` — Market Regime banner, Decision Highlight
- `shadow-lg` — modals, hover-emphasized CTAs

---

## 3. Typography Hierarchy

Utility classes added to `cozy.css` (prefix `.cozy-` to avoid collision with existing styles):

| Class | Style | Usage |
|---|---|---|
| `.cozy-eyebrow` | sans, 11px, 2.5px letter-spacing, uppercase, `--cozy-gold`, weight 700 | Section context label above headlines (e.g. "MARKET REGIME · APR 24") |
| `.cozy-headline` | serif, 22–28px, -0.5px letter-spacing, weight 700, `--cozy-ink`; `em` → italic + gold | Card/banner titles |
| `.cozy-impl` | serif italic, 14px, `--cozy-ink-soft` | Single-line summary sentence below headline |
| `.cozy-body` | sans, 14px, line-height 1.5 | Default body |
| `.cozy-caption` | sans, 11px, uppercase, 1.5px letter-spacing, `--cozy-muted`, weight 700 | Table headers, meta strings |
| `.cozy-numeric-xl` | serif, 32–42px, `--cozy-ink`, tabular-nums | Conviction score, large metric display |
| `.cozy-numeric` | sans, 13–15px, tabular-nums | In-table numbers |
| `.cozy-chip` | sans 12px, 6×10px padding, `--radius-chip`, white-70 bg, 1px `--cozy-border`, tabular-nums | Score/metric chip used in banner driver rows |
| `.cozy-pill` | sans 12px weight 600, `--cozy-gold-soft` bg, `--cozy-ink` text, `--radius-pill` | Confidence/status badge inline with headline |

Heading defaults (`h2`/`h3`/`h4`) inherit serif; set in base block near top of `cozy.css`.

---

## 4. Component Rules

### 4.1 `MarketRegimeBanner` (`web/src/components/MarketRegimeBanner.tsx`)

- Background: `linear-gradient(180deg, var(--cozy-paper) 0%, var(--cozy-paper-2) 100%)`
- Top accent: 3px pseudo-element with `linear-gradient(90deg, gold 0%, gold-2 50%, gold 100%)`
- Structure:
  - `.cozy-eyebrow` with colored status dot (good/warn/bad by `regime.regime`)
  - `.cozy-headline` with `<em>` on emphasis word; pill confidence badge inline-baseline
  - `.cozy-impl` (italic serif, one line)
  - `.regime-drivers` chip row using `.cozy-chip` with `+N` / `-N` score colored by sign
- Shadow: `--shadow`
- Existing `REGIME_CONFIG` emoji is replaced by the status dot; labels and class names (`regime-risk-on/neutral/risk_off`) are kept for backward compat.

### 4.2 Decision Highlight card (new composition on Dashboard)

- 3-column grid: `[big serif score] [eyebrow + verdict + reason] [CTA button]`
- Big score uses `.cozy-numeric-xl`
- CTA: dark ink background, gold-soft text, 10px radius

### 4.3 `WatchlistTable` (and sibling list tables)

- Ticker symbol: serif bold, 15px, `--cozy-ink`
- Company name: sans 11px, `--cozy-muted`, displayed below symbol
- Verdict badge: pill-shape, colored background per `buy`/`watch`/`avoid`
- Conviction column: inline gold bar (46×6px) + tabular-nums number
- Row hover: background `--cozy-cream-2`

### 4.4 Top Navigation

- Container: cream card with `--shadow-sm` and `--radius-card`
- Nav links default: `--cozy-muted`, weight 500
- Active link: `--cozy-ink` background, `--cozy-gold-soft` text, weight 600
  - (Resolves the previously fixed `nav-active` invisibility issue at the token level.)
- Right-aligned tabular date caption (uppercase, muted)

### 4.5 Generic card

- Background `--cozy-cream`, 1px `--cozy-border`, `--radius-card`, `--shadow-sm`
- Internal header: serif title + caption subtitle + right-aligned count/meta

---

## 5. Scope & Rollout Order

**In this spec:**
1. Rewrite token section of `web/src/styles/cozy.css` (colors, typography, shape, shadow scale).
2. Add typography utility classes listed in §3.
3. Load Inter via `web/index.html`.
4. Re-style the four components listed in §4: `MarketRegimeBanner`, the Dashboard Decision Highlight composition, `WatchlistTable`, and the top navigation.

**Out of scope (future specs):**
- `TickerDetail` page redesign
- Dark-mode toggle
- Chart palette alignment
- Mobile-specific layout tuning
- Other pages (`Sectors`, `Signals`, `Portfolio`, `Backtest`, etc.) — inherit tokens naturally but are not explicitly re-styled here.

---

## 6. Implementation Notes & Constraints

- `cozy.css` currently overrides `global.css`. The refresh keeps that layering — no changes to `global.css` in this spec.
- Existing class names used by components (`.market-regime-banner`, `.regime-risk-on`, `.watchlist`, etc.) are preserved so TSX files change only where new structure (eyebrow, dot, chip row) is added.
- No new runtime dependencies. Inter is loaded as a stylesheet link, not a JS package.
- No changes to TypeScript data types or backend.
- Accessibility: all color pairs used for text satisfy WCAG AA contrast (to verify during implementation: muted on cream, gold-soft on ink, good/bad/warn on cream).

---

## 7. Success Criteria

1. Dashboard at `/` visibly matches the approved hybrid mockup: gold-top-line banner, serif headlines, pill badge, chip score row, serif tickers in Watchlist.
2. No active `nav-link` invisibility — the nav regression test visually verified.
3. `cozy.css` tokens section is self-contained under a single `:root` and documented with comments.
4. Inter loads successfully or falls back gracefully; no FOUC layout shift beyond typical `swap` behavior.
5. No other pages (Sectors, Signals, etc.) regress visually — they should inherit tokens cleanly.

---

## 8. Open Questions

None blocking. During implementation, the exact line-heights and pill padding may be tuned against the live dashboard; the mockup values are starting points.
