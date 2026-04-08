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

What the script does:
- verifies GitHub CLI authentication
- lists recent workflow runs
- prints the most recent successful run summary
- finds the most recent failed run
- prints the failed run summary
- prints failed job logs
- writes the same output to `.actions-check.txt` by default

## Branch Migration Checklist

Use this checklist when changing the repository default branch from `master` to `main`.

1. Confirm `main` exists on GitHub.
2. Open the repository settings page:
   - `https://github.com/parkjunhee0510/pkrich/settings/branches`
3. Change the default branch from `master` to `main`.
4. Re-open the Actions tab and confirm new runs target `main`.
5. Re-open repository settings and confirm branch protection rules, if any, now point to `main`.
6. Update any local clones:

```bash
git fetch origin
git branch -m master main
git branch -u origin/main main
git remote set-head origin -a
```

7. After confirming nothing still depends on `master`, delete the remote branch:

```bash
git push origin --delete master
```

Current observed branch state in this repo:
- local branch: `main`
- remote branches: `origin/main`, `origin/master`

## Notes

- The pipeline preserves `collect -> analyze -> output`.
- If optional providers or API keys are unavailable, the pipeline degrades gracefully and still writes deterministic placeholder notes.
