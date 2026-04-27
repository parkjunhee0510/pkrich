# Web Committee UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dashboard and ticker-detail committee UI that surfaces `committee_analysis` without changing the existing rule-based decision semantics.

**Architecture:** Extend the web data model with committee types, then introduce small shared committee UI components that are reused by both the dashboard and ticker detail pages. The dashboard shows a separate committee strip inside each watchlist card, while ticker detail gains a dedicated `위원회` tab with a PM-first layout and role accordions.

**Tech Stack:** React 19, TypeScript, Vite, existing CSS in `web/src/styles/global.css`

---

## File Structure

### Create

- `web/src/components/CommitteeBadgeRow.tsx`
  Responsibility: shared agreement-status, deep-review, and reason-badge rendering
- `web/src/components/CommitteeSummaryStrip.tsx`
  Responsibility: compact dashboard committee strip for watchlist cards
- `web/src/components/CommitteeDetailPanel.tsx`
  Responsibility: PM-first detail-tab committee layout with role accordions

### Modify

- `web/src/types/index.ts`
  Responsibility: add web-safe committee payload types and attach them to `TickerAnalysisData`
- `web/src/components/WatchlistTable.tsx`
  Responsibility: render the committee strip inside each watchlist card
- `web/src/pages/TickerDetail.tsx`
  Responsibility: add the `위원회` tab and render the detail committee panel
- `web/src/styles/global.css`
  Responsibility: additive styles for committee strip, badges, PM card, and role accordions
- `docs/output.md`
  Responsibility: keep web-facing output contract docs aligned if needed after implementation changes

### Existing Verification Commands

- `npm run build`

---

### Task 1: Add Committee Types To The Web Data Model

**Files:**
- Modify: `web/src/types/index.ts`

- [ ] **Step 1: Add the failing type usage target**

Add these interfaces near `AnalysisConsensusData` and `TickerAnalysisData`:

```ts
export interface CommitteeRoleData {
  role?: string
  round?: string
  profile?: string
  stance?: string
  action?: string
  confidence?: number
  strong_objection?: boolean
  summary?: string
  valid?: boolean
  invalid_reason?: string
}

export interface CommitteeAnalysisData {
  status?: string
  agreement_status?: string
  deep_review_triggered?: boolean
  deep_review_reasons?: string[]
  roles?: Record<string, CommitteeRoleData>
}
```

Then extend `TickerAnalysisData`:

```ts
export interface TickerAnalysisData {
  ...
  analysis_consensus?: AnalysisConsensusData
  committee_analysis?: CommitteeAnalysisData
}
```

- [ ] **Step 2: Run the TypeScript build to verify the baseline still compiles**

Run: `npm run build`
Expected: PASS or fail only on pre-existing unrelated web issues, not on the new committee types

- [ ] **Step 3: Keep the type addition minimal**

Do not add runtime parsing code yet. This task is type-only and should not change component behavior.

- [ ] **Step 4: Re-run the build after saving**

Run: `npm run build`
Expected: PASS or unchanged failure surface

- [ ] **Step 5: Commit**

```bash
git add web/src/types/index.ts
git commit -m "feat: add web committee payload types"
```

---

### Task 2: Build Shared Committee UI Components

**Files:**
- Create: `web/src/components/CommitteeBadgeRow.tsx`
- Create: `web/src/components/CommitteeSummaryStrip.tsx`
- Create: `web/src/components/CommitteeDetailPanel.tsx`
- Modify: `web/src/styles/global.css`

- [ ] **Step 1: Create the shared badge row**

Add `web/src/components/CommitteeBadgeRow.tsx`:

```tsx
import type { CommitteeAnalysisData } from '../types'

type CommitteeBadgeRowProps = {
  committee?: CommitteeAnalysisData | null
}

export function CommitteeBadgeRow({ committee }: CommitteeBadgeRowProps) {
  const agreement = committee?.agreement_status?.trim() || 'N/A'
  const deep = committee?.deep_review_triggered
  const reasons = Array.isArray(committee?.deep_review_reasons)
    ? committee!.deep_review_reasons!.filter(Boolean)
    : []

  return (
    <div className="committee-badge-row">
      <span className="committee-badge committee-badge-agreement">합의 {agreement}</span>
      <span className={`committee-badge ${deep ? 'committee-badge-deep' : 'committee-badge-muted'}`}>
        {deep ? 'Deep Review' : 'Economy Only'}
      </span>
      {reasons.map((reason) => (
        <span key={reason} className="committee-badge committee-badge-reason">
          {reason}
        </span>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Create the dashboard strip component**

Add `web/src/components/CommitteeSummaryStrip.tsx`:

```tsx
import type { CommitteeAnalysisData } from '../types'
import { CommitteeBadgeRow } from './CommitteeBadgeRow'

const DASHBOARD_ROLE_ORDER = ['growth_analyst', 'value_skeptic', 'risk_manager', 'macro_strategist'] as const

const DASHBOARD_ROLE_LABELS: Record<string, string> = {
  growth_analyst: 'Growth',
  value_skeptic: 'Value',
  risk_manager: 'Risk',
  macro_strategist: 'Macro',
  pm: 'PM',
}

type CommitteeSummaryStripProps = {
  committee?: CommitteeAnalysisData | null
}

export function CommitteeSummaryStrip({ committee }: CommitteeSummaryStripProps) {
  const roles = committee?.roles ?? {}
  const pm = roles.pm

  return (
    <section className="committee-summary-strip" aria-label="위원회 요약">
      <CommitteeBadgeRow committee={committee} />
      <div className="committee-summary-grid">
        {DASHBOARD_ROLE_ORDER.map((roleKey) => {
          const role = roles[roleKey]
          return (
            <div key={roleKey} className="committee-summary-cell">
              <span className="committee-summary-label">{DASHBOARD_ROLE_LABELS[roleKey]}</span>
              <p>{role?.summary?.trim() || 'N/A'}</p>
            </div>
          )
        })}
      </div>
      <div className="committee-pm-summary">
        <span className="committee-summary-label">{DASHBOARD_ROLE_LABELS.pm}</span>
        <p>{pm?.summary?.trim() || 'committee unavailable'}</p>
      </div>
    </section>
  )
}
```

- [ ] **Step 3: Create the detail panel component**

Add `web/src/components/CommitteeDetailPanel.tsx`:

```tsx
import type { CommitteeAnalysisData, CommitteeRoleData } from '../types'
import { CommitteeBadgeRow } from './CommitteeBadgeRow'

const DETAIL_ROLE_ORDER = ['growth_analyst', 'value_skeptic', 'risk_manager', 'macro_strategist'] as const

const DETAIL_ROLE_LABELS: Record<string, string> = {
  growth_analyst: 'Growth Analyst',
  value_skeptic: 'Value Skeptic',
  risk_manager: 'Risk Manager',
  macro_strategist: 'Macro Strategist',
}

function renderRoleSummary(role?: CommitteeRoleData) {
  if (!role) return 'committee unavailable'
  if (role.valid === false) return role.invalid_reason?.trim() || 'committee output invalid'
  return role.summary?.trim() || 'N/A'
}

type CommitteeDetailPanelProps = {
  committee?: CommitteeAnalysisData | null
}

export function CommitteeDetailPanel({ committee }: CommitteeDetailPanelProps) {
  const roles = committee?.roles ?? {}
  const pm = roles.pm

  return (
    <section className="ticker-detail-section-shell">
      <div className="committee-detail-panel">
        <div className="committee-pm-card">
          <span className="section-kicker">PM Conclusion</span>
          <strong>{pm?.stance?.trim() || 'N/A'}</strong>
          <p>{renderRoleSummary(pm)}</p>
        </div>
        <CommitteeBadgeRow committee={committee} />
        <div className="committee-role-accordions">
          {DETAIL_ROLE_ORDER.map((roleKey) => (
            <details key={roleKey} className="committee-role-accordion">
              <summary>
                <span>{DETAIL_ROLE_LABELS[roleKey]}</span>
                <span>{roles[roleKey]?.stance?.trim() || 'N/A'}</span>
              </summary>
              <div className="committee-role-body">
                <p>{renderRoleSummary(roles[roleKey])}</p>
              </div>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 4: Add the initial CSS**

Append these styles in `web/src/styles/global.css` near other ticker-detail/dashboard section styles:

```css
.committee-summary-strip {
  margin-top: 0.9rem;
  border-top: 1px dashed var(--ink-soft);
  padding-top: 0.9rem;
  display: grid;
  gap: 0.75rem;
}

.committee-badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.committee-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0.28rem 0.6rem;
  font-size: 0.72rem;
  letter-spacing: 0.04em;
  background: var(--bone-dim);
  color: var(--ink);
}

.committee-badge-deep {
  background: var(--neg-block);
  color: var(--on-neg-block);
}

.committee-badge-muted {
  background: var(--bone);
}

.committee-badge-reason {
  background: var(--paper);
  border: 1px solid var(--bone-dim);
}

.committee-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
}

.committee-summary-cell,
.committee-pm-summary,
.committee-pm-card {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.8rem 0.9rem;
  background: color-mix(in srgb, var(--paper) 88%, var(--bone) 12%);
}

.committee-summary-label {
  display: block;
  margin-bottom: 0.3rem;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ink-soft);
}

.committee-detail-panel {
  display: grid;
  gap: 0.9rem;
}

.committee-role-accordions {
  display: grid;
  gap: 0.7rem;
}

.committee-role-accordion {
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--paper);
}

.committee-role-accordion summary {
  list-style: none;
  cursor: pointer;
  padding: 0.9rem 1rem;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

.committee-role-body {
  padding: 0 1rem 1rem;
}

@media (max-width: 768px) {
  .committee-summary-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 5: Run the web build**

Run: `npm run build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/src/components/CommitteeBadgeRow.tsx web/src/components/CommitteeSummaryStrip.tsx web/src/components/CommitteeDetailPanel.tsx web/src/styles/global.css
git commit -m "feat: add shared committee web components"
```

---

### Task 3: Add The Committee Strip To Dashboard Watchlist Cards

**Files:**
- Modify: `web/src/components/WatchlistTable.tsx`
- Modify: `web/src/types/index.ts`

- [ ] **Step 1: Import the new summary strip**

Update the imports in `web/src/components/WatchlistTable.tsx`:

```tsx
import { CommitteeSummaryStrip } from './CommitteeSummaryStrip'
```

- [ ] **Step 2: Insert the committee strip into each watchlist card**

Add this block after the existing `.watchlist-detail-grid` inside `SortableWatchlistCard`:

```tsx
      <CommitteeSummaryStrip committee={ticker.committee_analysis} />
```

The card body should then end like this:

```tsx
      <div className="watchlist-detail-grid">
        ...
      </div>

      <CommitteeSummaryStrip committee={ticker.committee_analysis} />
    </article>
```

- [ ] **Step 3: Keep dashboard semantics unchanged**

Do not move or rewrite:

* decision pill
* setup score
* conviction-driven ranking
* action-plan rendering

This task is additive display only.

- [ ] **Step 4: Run the build**

Run: `npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/components/WatchlistTable.tsx
git commit -m "feat: show committee summary on dashboard cards"
```

---

### Task 4: Add The Dedicated Committee Tab To Ticker Detail

**Files:**
- Modify: `web/src/pages/TickerDetail.tsx`

- [ ] **Step 1: Import the committee detail panel**

Add this import in `web/src/pages/TickerDetail.tsx`:

```tsx
import { CommitteeDetailPanel } from '../components/CommitteeDetailPanel'
```

- [ ] **Step 2: Add the new detail tab**

Change `DETAIL_TABS`:

```tsx
const DETAIL_TABS = ['개요', '차트', '재무', '재료', '시나리오', '위원회'] as const
```

- [ ] **Step 3: Render the committee panel inside the new tab**

Add this tab body block near the existing tab sections:

```tsx
      {activeTab === '위원회' && (
        <CommitteeDetailPanel committee={analysis.committee_analysis} />
      )}
```

- [ ] **Step 4: Keep PM-first hierarchy**

Do not place committee content above:

* the page header
* `DecisionCard`
* `TraderDecisionBoard`

The new tab is the only place for the full committee view.

- [ ] **Step 5: Run the build**

Run: `npm run build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/TickerDetail.tsx
git commit -m "feat: add committee tab to ticker detail"
```

---

### Task 5: Harden Fallbacks And Mobile Layout

**Files:**
- Modify: `web/src/components/CommitteeSummaryStrip.tsx`
- Modify: `web/src/components/CommitteeDetailPanel.tsx`
- Modify: `web/src/styles/global.css`

- [ ] **Step 1: Add explicit fallback copy for missing payloads**

Ensure these exact fallback behaviors exist:

```tsx
const pmText = pm?.summary?.trim() || 'committee unavailable'
const summaryText = role?.summary?.trim() || 'N/A'
```

And for invalid roles:

```tsx
if (role.valid === false) return role.invalid_reason?.trim() || 'committee output invalid'
```

- [ ] **Step 2: Add a more stable mobile stack if needed**

If the first build preview shows cramped cards, extend CSS with:

```css
@media (max-width: 768px) {
  .committee-badge-row {
    gap: 0.3rem;
  }

  .committee-role-accordion summary {
    flex-direction: column;
    align-items: flex-start;
  }

  .committee-pm-card {
    padding: 0.85rem;
  }
}
```

- [ ] **Step 3: Keep the copy short**

Do not add paragraph-length explanations to dashboard cards. The dashboard remains scan-first.

- [ ] **Step 4: Run the build**

Run: `npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/components/CommitteeSummaryStrip.tsx web/src/components/CommitteeDetailPanel.tsx web/src/styles/global.css
git commit -m "fix: harden committee ui fallbacks"
```

---

### Task 6: Sync Docs And Run Final Verification

**Files:**
- Modify: `docs/output.md`
- Verify: `web/src/types/index.ts`
- Verify: `web/src/components/WatchlistTable.tsx`
- Verify: `web/src/pages/TickerDetail.tsx`

- [ ] **Step 1: Update the output doc if wording needs to reflect web visibility**

Ensure `docs/output.md` contains a line like:

```md
* `committee_analysis` is consumed by the web dashboard and ticker detail UI as an always-visible debate layer
```

- [ ] **Step 2: Run final web verification**

Run: `npm run build`
Expected: PASS

- [ ] **Step 3: Perform a quick manual review checklist**

Check these in the built code before closing:

* dashboard watchlist cards now include a committee strip
* ticker detail has a `위원회` tab
* PM conclusion appears first in the detail tab
* the official `decision` card and semantics are unchanged
* missing committee data still renders safely

- [ ] **Step 4: Commit**

```bash
git add docs/output.md web/src/types/index.ts web/src/components/CommitteeBadgeRow.tsx web/src/components/CommitteeSummaryStrip.tsx web/src/components/CommitteeDetailPanel.tsx web/src/components/WatchlistTable.tsx web/src/pages/TickerDetail.tsx web/src/styles/global.css
git commit -m "docs: document committee web visibility"
```

---

## Self-Review

### Spec Coverage

* Dashboard summary plus ticker detail support: covered by Task 3 and Task 4
* Dashboard role summaries visible by default: covered by Task 2 and Task 3
* Dedicated committee tab in ticker detail: covered by Task 4
* PM conclusion fixed at top with role accordions below: covered by Task 2 and Task 4
* Shared components for reuse: covered by Task 2
* Safe fallbacks for missing or invalid payloads: covered by Task 5
* Decision semantics unchanged: reinforced in Task 3, Task 4, and Task 6

### Placeholder Scan

* No `TODO`, `TBD`, or deferred implementation markers remain
* Every code-changing task includes concrete file paths and code snippets
* Every verification step includes an exact command

### Type Consistency

* `committee_analysis` is used consistently across the type layer and both UI entry points
* `CommitteeAnalysisData` and `CommitteeRoleData` names match across all tasks
* Shared component names remain consistent across creation and wiring tasks
