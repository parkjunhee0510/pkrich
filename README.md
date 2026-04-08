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

## Actions Log Routine

Use one of these authentication methods before checking GitHub Actions logs:

1. GitHub CLI login:

```bash
gh auth login
```

2. Token-based access in PowerShell:

```powershell
$env:GH_TOKEN = "your_token_here"
```

Then run:

```powershell
.\scripts\check-actions.ps1
```

To save the result to a custom file:

```powershell
.\scripts\check-actions.ps1 -OutputPath .\logs\actions-check.txt
```

To control auto-rotated log storage and failed-run comparison size:

```powershell
.\scripts\check-actions.ps1 -LogDirectory .\logs\actions -FailedSummaryLimit 5
```

What the script does:
- verifies GitHub CLI authentication
- lists recent workflow runs
- prints the most recent successful run summary
- prints job-level status for the most recent successful run
- prints a comparison summary for the most recent failed runs
- finds the most recent failed run
- prints the latest failed run summary
- prints job-level status for the latest failed run
- prints failed job logs
- writes the output to a date-based file under `logs/actions/` by default
- writes summary artifacts to sibling `.summary.json` and `.summary.csv` files

## Branch Status

The repository branch migration is complete.

- local branch: `main`
- remote default branch: `main`
- remote branches: `origin/main`

If another local clone still points to `master`, update it with:

```bash
git fetch origin
git branch -m master main
git branch -u origin/main main
git remote set-head origin -a
```

## Output Configuration

Daily note output rules are configurable in:

- `config/output.yaml`

Current configurable rules include:
- fallback news hiding for items without links
- optional hiding of an empty `Top News Links` section
- optional fallback hiding in ticker notes
- sector display order
- news source priority for tie-breaks

## Notes

- The pipeline preserves `collect -> analyze -> output`.
- If optional providers or API keys are unavailable, the pipeline degrades gracefully and still writes deterministic placeholder notes.
