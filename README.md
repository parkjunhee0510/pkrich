# Stock Research Automation

Low-cost, batch-based stock research automation for daily notes.

## Quick start

1. Create a Python 3.11+ environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy environment variables from `.env.example`.
4. Edit `config/watchlist.yaml`.
5. Run:

```bash
python main.py
```

To enable live market/news collection, set `ENABLE_EXTERNAL_FETCH=true`.

## Output

- `output/daily/YYYY-MM-DD.md`
- `output/tickers/<TICKER>/YYYY-MM-DD.md`
- `output/data/price_history.csv`

## Testing

```bash
python -m unittest discover -s tests -v
```

## GitHub Actions Validation

- The workflow runs tests before the scheduled pipeline execution.
- Live collection is enabled in GitHub Actions with `ENABLE_EXTERNAL_FETCH=true`.
- Generated files under `output/` are auto-committed after a successful run.
- Required repository secrets:
  - `OPENAI_API_KEY`
  - `OPENAI_MODEL` (optional, defaults in code if omitted)
  - `SLACK_WEBHOOK_URL` (optional for future Slack integration)

## Notes

- The pipeline preserves `collect -> analyze -> output`.
- If optional providers or API keys are unavailable, the pipeline degrades gracefully and still writes deterministic placeholder notes.
