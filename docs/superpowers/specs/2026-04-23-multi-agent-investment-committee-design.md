# Multi-Agent Investment Committee Design

## Summary

Add a role-based investment committee inside the analyzer flow.
Each ticker receives independent role opinions from multiple LLM calls, followed by a PM conclusion.
The committee output is always shown in default user-facing outputs, while the existing rule-based decision layer remains the official source of truth for `buy/watch/avoid`.

## Goals

* Show a visible multi-role committee debate for every ticker
* Keep official pipeline decisions rule-based
* Use independent calls for each role
* Control cost by using `economy` by default and selective `deep` re-review
* Preserve deterministic schemas and stable downstream output contracts

## Non-Goals

* Replacing the current decision layer as the official action engine
* Running full deep review for every ticker
* Allowing free-form unstructured committee output
* Introducing external dependencies or real-time behavior

## User-Facing Behavior

Every ticker output includes a committee section by default.

The section shows:

* `Growth Analyst` opinion in 1 to 2 sentences
* `Value Skeptic` opinion in 1 to 2 sentences
* `Risk Manager` opinion in 1 to 2 sentences
* `Macro Strategist` opinion in 1 to 2 sentences
* `PM` final conclusion in 2 to 3 sentences
* agreement status
* whether deep re-review ran

The PM produces a five-level recommendation:

* `strong_buy`
* `buy`
* `watch`
* `reduce`
* `avoid`

This recommendation is always displayed, but the existing pipeline still maps official output actions from the rule-based decision layer.

## Architecture Direction

The committee lives inside the analyzer layer as a new structured orchestration path.
It runs after the baseline ticker analysis exists, because role prompts depend on collected data plus analyzer outputs.

The official architecture remains:

`collect -> analyze -> state -> output -> store -> log`

The committee extends `analyze`; it does not create a new top-level stage.

## Committee Roles

### Growth Analyst

Focus:

* upside narrative
* growth durability
* catalyst strength

### Value Skeptic

Focus:

* valuation stretch
* narrative overreach
* downside from expectations reset

### Risk Manager

Focus:

* loss scenarios
* position risk
* invalidation and asymmetric downside

### Macro Strategist

Focus:

* rates
* FX
* liquidity
* macro regime pressure

### PM

Focus:

* synthesize prior role outputs
* produce final committee recommendation
* report confidence and rationale

## Call Flow

### Round 1: Economy Committee

For each ticker:

1. Run independent `economy` call for `Growth Analyst`
2. Run independent `economy` call for `Value Skeptic`
3. Run independent `economy` call for `Risk Manager`
4. Run independent `economy` call for `Macro Strategist`
5. Run independent `economy` call for `PM`

The PM receives the four role outputs plus the ticker analysis context.

### Deep Re-Review Trigger

Run selective deep re-review when any of the following is true:

* PM confidence is below a configured threshold
* `Risk Manager` emits a strong objection
* `Macro Strategist` emits a strong objection

### Round 2: Selective Deep Re-Review

Only these roles rerun with `deep`:

* `Risk Manager`
* `Macro Strategist`
* `PM`

This keeps the extra cost focused on the roles that drive escalation.

## Structured Output Contract

Committee output must be schema-first.
Free-form text without normalized fields is not acceptable.

Suggested structure:

```json
{
  "committee_analysis": {
    "status": "economy_only | deep_reviewed",
    "agreement_status": "aligned | mixed | contested",
    "deep_review_triggered": true,
    "deep_review_reasons": ["pm_low_confidence", "risk_strong_objection"],
    "roles": {
      "growth_analyst": {
        "stance": "strong_buy",
        "summary": "..."
      },
      "value_skeptic": {
        "stance": "watch",
        "summary": "..."
      },
      "risk_manager": {
        "stance": "reduce",
        "summary": "...",
        "strong_objection": true
      },
      "macro_strategist": {
        "stance": "watch",
        "summary": "...",
        "strong_objection": false
      },
      "pm": {
        "stance": "buy",
        "summary": "...",
        "confidence": 0.62
      }
    }
  }
}
```

## Recommendation Mapping

Committee recommendation is five-level.
Existing pipeline action stays three-level.

Mapping:

* `strong_buy -> buy`
* `buy -> buy`
* `watch -> watch`
* `reduce -> avoid`
* `avoid -> avoid`

This mapping is for compatibility and display alignment only.
It does not replace the rule-based decision layer in the first implementation.

## Data Flow

1. `collect` produces normalized ticker inputs
2. existing analyzer flow produces ticker analysis
3. committee orchestrator generates role outputs
4. deep re-review runs selectively for escalated tickers
5. committee payload is attached to ticker analysis output
6. output serializers include committee data in default JSON and Markdown views
7. decision layer may inspect committee metadata later, but official action remains rule-based in phase 1

## Output Integration

Committee output must appear in default output, not as an optional detail view.

Required output surfaces:

* ticker JSON payloads
* dashboard-facing JSON when ticker detail is serialized
* daily Markdown
* per-ticker Markdown

Optional later:

* weekly summaries
* dedicated committee diagnostics output

## Config

Add config for:

* committee enabled flag
* PM low-confidence threshold
* strong-objection trigger behavior
* role-specific model profile
* sentence or token budget per role

Default behavior:

* all roles use `economy`
* selective deep re-review uses `deep`

## Cost Strategy

Independent calls are required, so cost control must be explicit.

Rules:

* round 1 runs on `economy`
* deep re-review is selective
* only `Risk Manager`, `Macro Strategist`, and `PM` rerun in `deep`
* role outputs stay short
* cost logging should separate committee activity from existing ensemble activity

## Testing Strategy

Required test coverage:

* committee schema contract tests
* escalation trigger tests
* five-level stance mapping tests
* serializer tests for JSON and Markdown
* regression tests to ensure official rule-based decision flow still works
* cost logging tests for committee usage accounting

## Risks

### Cost Risk

Independent calls on every ticker can exceed budget if prompts or responses grow.

Mitigation:

* short response budgets
* selective deep reruns only
* explicit cost tracking

### Output Bloat

Always-visible committee text can overwhelm users.

Mitigation:

* hard sentence limits
* schema-driven summaries
* default concise style

### Role Collapse

Different roles may sound too similar if prompts are weak.

Mitigation:

* role-specific prompt contracts
* stance-specific justification requirements
* tests or review snapshots for role separation

### Architecture Drift

Committee output could begin to replace decision logic informally.

Mitigation:

* keep rule-based decision as official source of truth in phase 1
* document that committee output is explanatory and advisory

## Recommended Implementation Scope

Phase 1 should include:

* committee orchestrator
* structured role prompts
* economy round for all tickers
* selective deep re-review for `Risk Manager`, `Macro Strategist`, and `PM`
* default output rendering
* schema and regression tests

Phase 1 should not include:

* full replacement of decision logic
* all-role deep reruns
* advanced committee memory across days

## Acceptance Criteria

The design is successful when:

* every ticker shows committee output in default views
* all role calls are independent
* deep re-review triggers only on configured escalation signals
* official `buy/watch/avoid` still comes from the rule-based decision layer
* output remains schema-stable and regression-testable
* cost remains controlled through economy-first execution
