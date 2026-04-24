# PM Workflow Design

## Summary

Add a portfolio-manager workflow layer on top of the existing ticker research system. The new layer does not replace `buy/watch/avoid` decisions. It curates daily review priorities for a user managing multiple positions at once.

The scope is limited to three PM jobs:

1. Swap or replacement candidate review
2. Event-driven exposure management review
3. A daily priority queue for what to inspect first

The system proposes candidates and reasons only. It does not produce execution instructions such as "sell A and buy B."

## Goals

- Help a portfolio-manager-style user scan what deserves attention today
- Reuse existing `decision`, `portfolio_risk`, `upcoming_events`, and output payloads
- Keep the current decision engine as the official source of trading stance
- Add a thin, explainable PM prioritization layer with minimal architectural disruption

## Non-Goals

- No automatic trade execution
- No new source of truth for ticker actions
- No hidden PM model that overrides `buy/watch/avoid`
- No broad refactor of dashboard, portfolio, or decision architecture

## Users

Primary user: a portfolio-manager-style operator who manages multiple positions at once and needs help deciding what to review, compare, and monitor each day.

## Product Principles

- Explanation first: every PM suggestion must say why it exists
- Separation of concerns: PM prioritization is not decision generation
- Additive data model: new payload fields extend current JSON rather than replacing it
- Review support only: wording must stay at the level of candidates, reasons, and checks

## Proposed Approach

Use a hybrid design:

- Keep existing `decision/conviction` as the base signal
- Add a thin PM-specific prioritization layer
- Render the results in two places with distinct roles:
  - `Dashboard`: top-level daily PM queue
  - `Portfolio`: detailed portfolio review and comparison context

This avoids two common failures:

- Reusing `conviction` alone would only reshuffle existing ticker rankings and would not answer PM questions well
- Creating a fully separate PM scoring system would drift away from the current decision engine and create interpretation conflicts

## New PM Scores

Introduce three PM helper scores. They are review-priority signals, not investment actions.

### `swap_candidate_score`

Represents how strongly a held position should be reviewed as a replacement or swap candidate.

Higher when:

- the held ticker's `conviction` has weakened
- the held ticker moves toward `avoid` or weaker `watch`
- the held ticker carries near-term event risk
- the held ticker is a large contributor to concentration or correlation risk
- a non-held ticker with similar exposure shows better conviction and cleaner near-term setup

Output example:

- held ticker
- comparison candidate
- score
- short explanation
- overlapping exposure reason

### `event_risk_score`

Represents how urgently a held position should be reviewed due to upcoming events or event-sensitive volatility.

Higher when:

- earnings are within `D-7`
- macro events with high impact matter for the ticker
- important filings or catalysts are near
- ATR, IV, gap risk, or other volatility cues are elevated
- the position is already large inside the portfolio

Output example:

- ticker
- event and D-day
- score
- why this event matters
- review checkpoints

### `today_priority_score`

Represents overall review urgency for the PM dashboard queue.

Higher when:

- ticker action or conviction changed materially
- new strong catalyst appeared
- `swap_candidate_score` is high
- `event_risk_score` is high
- portfolio risk warnings increase urgency

This is the main sort key for the top daily queue.

## Data Flow

The PM layer must consume finalized pipeline data only.

1. Existing pipeline computes `decision`, `portfolio_risk`, `upcoming_events`, `factor_reasoning`, and signal history/statistics.
2. A new PM prioritization step reads finalized data only.
3. That step produces an additive PM review payload.
4. Output exports the PM payload into existing JSON artifacts without recomputing decisions.
5. The web app renders PM data as presentation and review support.

Boundary rules:

- no data fetching
- no LLM calls
- no decision recomputation
- no direct override of `buy/watch/avoid`

## Proposed Output Shape

Add an additive `pm_view` payload near the daily web/dashboard data. Exact naming can be adjusted in implementation, but the structure should support:

- `swap_candidates`
- `event_exposure_items`
- `today_priority_queue`

Representative item shapes:

### Swap candidate item

- `held_ticker`
- `candidate_ticker`
- `swap_candidate_score`
- `summary`
- `reasons[]`
- `overlap_context`
- `review_points[]`

### Event exposure item

- `ticker`
- `event_risk_score`
- `event_label`
- `event_date`
- `days_until`
- `summary`
- `reasons[]`
- `review_points[]`

### Daily priority queue item

- `priority_type`
- `ticker`
- `related_ticker?`
- `today_priority_score`
- `summary`
- `reasons[]`
- `destination`

## Candidate Matching Logic

### Swap and replacement comparisons

Only compare within relevant exposure neighborhoods so the result remains explainable.

Preferred matching rules:

- same sector first
- similar theme or factor profile second
- avoid arbitrary cross-sector replacements unless clearly justified

Candidate tickers should generally be non-held names that:

- have better current conviction than the held name
- have recent `hard` or `medium` catalyst support
- have cleaner near-term event risk
- do not obviously worsen concentration risk

Every comparison must expose why the pair was matched, for example:

- same semiconductor exposure
- same AI infrastructure theme
- similar factor profile, cleaner upcoming event calendar

### Event management candidates

Only held tickers participate.

Priority rises with combinations such as:

- earnings within `D-7`
- high-impact macro sensitivity
- elevated IV, ATR, or gap risk
- weakening conviction
- heavy portfolio weight or strong contribution to portfolio risk

The output language must remain review-oriented, for example:

- check whether event exposure is oversized
- review overlapping exposure with similar holdings
- confirm announcement timing and volatility context

## UI Design

### Dashboard role: scan and prioritize

`Dashboard` becomes the home for a PM daily queue at the top of the page.

Add three sections:

1. `Swap Review Candidates`
2. `Event Exposure Review`
3. `Today Priority Queue`

#### `Swap Review Candidates`

Show the top 3 to 5 replacement-review candidates.

Each card should include:

- held ticker
- comparison candidate
- `swap_candidate_score`
- 2 to 3 short reasons
- overlap context
- link into deeper portfolio review

#### `Event Exposure Review`

Show held tickers that need event-related review.

Each card should include:

- ticker
- event and D-day
- `event_risk_score`
- why review is needed
- explicit review checkpoints

#### `Today Priority Queue`

This is the most important PM section.

Queue items may include:

- `swap review`
- `event review`
- `decision change`
- `risk warning`

Each item should be one-line scannable and route the user to deeper detail.

### Portfolio role: inspect and compare

`Portfolio` remains the deeper review surface.

Add a `Portfolio Actions Review` section above or near the current holdings summary and risk content.

For each relevant held ticker, expose:

- current action and conviction
- recent conviction or action change
- nearby events
- portfolio risk contribution
- comparison candidates
- why the comparison exists
- review points

Design intent:

- `Dashboard` answers: "What should I inspect first today?"
- `Portfolio` answers: "Why is this name on the review list?"

## UX and Language Rules

The PM layer must not sound like an execution engine.

Allowed language:

- review candidate
- compare with
- monitor
- check
- review points

Disallowed language:

- sell this
- buy that
- cut by half
- rotate now

The product should guide inspection, not issue trade commands.

## Empty and Error States

Empty states must explain why the list is empty.

Examples:

- "No swap review candidates today. Current holdings remain relatively stable on conviction and event calendar."
- "No urgent event exposure reviews today."

Requirements:

- no broken layout when a section is empty
- no generic blank placeholders without explanation
- no null-sensitive rendering failures when portfolio data is absent

## Testing Strategy

### Backend

- PM scores compute safely when portfolio holdings are empty
- comparison candidate search handles no-match cases
- additive PM payload does not replace or mutate official decision fields
- score ordering is deterministic

### Frontend

- dashboard PM sections render correctly in full, partial, and empty states
- portfolio comparison and event panels render conditionally without layout regressions
- queue ordering follows `today_priority_score`

### Product behavior

- every item includes candidate, reason, and review point context
- PM layer never emits execution wording
- PM data stays consistent with current `decision` and `portfolio_risk` context

## Risks

- If comparison matching is too loose, suggestions will feel arbitrary
- If PM scores become too complex, they will compete with the existing decision model
- If the dashboard adds too much detail, it will lose scan speed

## Recommendation

Implement the PM layer as a thin, additive prioritization system that reuses the existing decision engine and portfolio risk data. Keep the dashboard focused on daily scan and the portfolio page focused on detailed review. This gives the user a portfolio-manager workflow without introducing a second decision engine.
