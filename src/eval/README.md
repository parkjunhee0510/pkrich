# src/eval — LLM Quality Audit

One-shot diagnostic for the analyzer's LLM outputs over a 14-day window. Read-only against `output/data/` and `logs/pipeline/`. Writes two artifacts:

- `docs/reports/llm-audit-YYYY-MM-DD.md` (human)
- `output/data/llm_audit/YYYY-MM-DD.json` (machine)

## Run

```bash
python -m src.eval.runner                           # default: 14-day window, ALL 14 checks
python -m src.eval.runner --skip-replay             # free mode (no LLM calls)
python -m src.eval.runner --dry-run                 # cost estimate only
python -m src.eval.runner --checks I1,O2,D2         # subset
python -m src.eval.runner --max-replay-cost-usd 0.5 # tighter budget
python -m src.eval.runner --suffix evening          # second run same day, separate file
```

## Cost

D1 (semantic_drift) is the only check that calls the LLM. Default budget: 5 tickers × 3 runs ≈ $0.30–$0.80 per audit on the `economy` profile. Cap defaults to `$1.0`. Other 13 checks are free.

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

Thresholds live in `src/eval/config.py`. Adjust there only — do not hard-code in checks.

## Tests

```bash
python -m unittest discover -s tests/eval -v
```

Refresh golden:

```bash
UPDATE_GOLDENS=1 python -m unittest tests.eval.test_golden -v
```
