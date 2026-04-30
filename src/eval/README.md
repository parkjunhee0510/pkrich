# src/eval - LLM Quality Audit

One-shot diagnostic for the analyzer's LLM outputs over a 14-day window. It is read-only against `output/data/` and `logs/pipeline/` except for its report artifacts:

- `docs/reports/llm-audit-YYYY-MM-DD.md` (human)
- `output/data/llm_audit/YYYY-MM-DD.json` (machine)

Ticker daily records are loaded from `output/data/tickers/<TICKER>/daily/<DATE>.json` when present, with `latest.json` used as a same-window fallback. Checks with no evaluable samples report `info` instead of `pass` so missing audit evidence is visible.

## Run

```bash
python -m src.eval.runner                           # default: 14-day window, all 14 checks
python -m src.eval.runner --skip-replay             # free mode, no LLM calls
python -m src.eval.runner --dry-run                 # cost estimate only
python -m src.eval.runner --checks I1,O2,D2         # subset
python -m src.eval.runner --max-replay-cost-usd 0.5 # tighter budget
python -m src.eval.runner --suffix evening          # second run same day, separate file
```

## Cost

D1 (`semantic_drift`) is the only check that calls the LLM. It replays the `SignalTakeawayModule` through the analyzer's structured LLM runtime on the configured model profile. The default cap is `$1.0`, and the JSON report records the actual or estimated replay cost. Other checks are free.

## Report Shape

Markdown reports include:

- Executive summary
- Verdict matrix with dimension, severity, pass rate, sample count, and top metric
- Per-check details and recommendations
- Methodology notes

JSON reports include:

- `summary.info` in addition to pass/warn/fail counts
- `checks[*].dimension`
- `checks[*].thresholds`
- `checks[*].sample_count`
- replay metadata with `cost_usd`

## Checks

| ID | Dimension |
|----|-----------|
| I1 | schema_stability |
| I2 | missingness |
| I3 | format_consistency |
| I4 | input_size_drift |
| O1 | schema_compliance |
| O2 | numeric_grounding |
| O3 | citation_integrity |
| O4 | language_consistency |
| O5 | contradiction |
| D1 | semantic_drift (replay) |
| D2 | committee_agreement |
| D3 | signal_volatility |
| R1 | pipeline_summary |
| R2 | retry_distribution |

Thresholds live in `src/eval/config.py`. Adjust them there only; do not hard-code thresholds inside checks.

## Tests

```bash
python -m unittest discover -s tests/eval -v
```

Refresh golden output only when the report contract intentionally changes:

```bash
UPDATE_GOLDENS=1 python -m unittest tests.eval.test_golden -v
```
