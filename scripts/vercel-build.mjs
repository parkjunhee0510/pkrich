import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { execSync } from 'node:child_process'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..')
const webRoot = path.join(repoRoot, 'web')
const distDataRoot = path.join(webRoot, 'dist', 'output', 'data')
const sourceDataRoot = path.join(repoRoot, 'output', 'data')

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
  'calibration.json',
  'factor_audit.json',
  'sectors.json',
  'tuning_report.json',
  'validation_warnings.json',
]

for (const filename of dataFiles) {
  const sourcePath = path.join(sourceDataRoot, filename)
  if (!existsSync(sourcePath)) continue
  cpSync(sourcePath, path.join(distDataRoot, filename), { force: true })
}

const tickerSourceRoot = path.join(sourceDataRoot, 'tickers')
const tickerDistRoot = path.join(distDataRoot, 'tickers')
if (existsSync(tickerSourceRoot)) {
  rmSync(tickerDistRoot, { recursive: true, force: true })
  cpSync(tickerSourceRoot, tickerDistRoot, {
    recursive: true,
    force: true,
  })
}
