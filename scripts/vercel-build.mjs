import { cpSync, existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { execSync } from 'node:child_process'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..')
const webRoot = path.join(repoRoot, 'web')
const distDataRoot = path.join(webRoot, 'dist', 'output', 'data')
const sourceDataRoot = path.join(repoRoot, 'output', 'data')
const forceDataOverwrite = process.env.CI === 'true' || process.env.VERCEL === '1'

const npmEnv = {
  ...process.env,
}

execSync('npm install --no-audit --no-fund', {
  cwd: webRoot,
  stdio: 'inherit',
  env: npmEnv,
})

execSync('npm run build', {
  cwd: webRoot,
  stdio: 'inherit',
  env: npmEnv,
})

mkdirSync(distDataRoot, { recursive: true })

function copyIfChanged(sourcePath, targetPath) {
  if (!forceDataOverwrite && existsSync(targetPath)) {
    return
  }

  if (
    existsSync(targetPath) &&
    readFileSync(sourcePath).equals(readFileSync(targetPath))
  ) {
    return
  }

  cpSync(sourcePath, targetPath, { force: true })
}

const dataFiles = [
  'index.json',
  'dashboard.json',
  'dashboard_history.json',
  'price_history.json',
  'ticker_timelines.json',
  'backtest_summary.json',
  'monthly_summary.json',
  'api_status.json',
  'api_ticker_matrix.json',
  'api_ticker_matrix.csv',
  'analysis_quality.json',
  'cost_log.json',
  'routing_outcome.json',
  'direction_alignment.json',
  'ab_test_results.json',
  'calibration.json',
  'factor_audit.json',
  'signal_quality.json',
  'policy_impact.json',
  'sectors.json',
  'tuning_report.json',
  'validation_warnings.json',
]

for (const filename of dataFiles) {
  const sourcePath = path.join(sourceDataRoot, filename)
  if (!existsSync(sourcePath)) continue
  copyIfChanged(sourcePath, path.join(distDataRoot, filename))
}

const tickerSourceRoot = path.join(sourceDataRoot, 'tickers')
const tickerDistRoot = path.join(distDataRoot, 'tickers')
if (existsSync(tickerSourceRoot)) {
  if (forceDataOverwrite || !existsSync(tickerDistRoot)) {
    rmSync(tickerDistRoot, { recursive: true, force: true })
    cpSync(tickerSourceRoot, tickerDistRoot, {
      recursive: true,
      force: true,
    })
  }
}
