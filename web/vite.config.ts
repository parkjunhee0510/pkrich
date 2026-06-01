import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { readFile, writeFile } from 'node:fs/promises'
import type { IncomingMessage, ServerResponse } from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Plugin } from 'vite'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolvePortfolioSaveHoldings } from './src/utils/localPortfolioSave.ts'
import type { PortfolioHoldingInput } from './src/types'

const WEB_ROOT = fileURLToPath(new URL('.', import.meta.url))
const REPO_ROOT = path.resolve(WEB_ROOT, '..')
const WATCHLIST_PATH = path.join(REPO_ROOT, 'config', 'watchlist.yaml')
const PORTFOLIO_PATH = path.join(REPO_ROOT, 'config', 'portfolio.yaml')
const LOGS_ROOT = path.join(REPO_ROOT, 'logs', 'pipeline')
const OUTPUT_DATA_ROOT = path.join(REPO_ROOT, 'output', 'data')

type LocalResearchStage =
  | 'idle'
  | 'watchlist_updated'
  | 'starting'
  | 'collecting'
  | 'analyzing'
  | 'writing'
  | 'completed'
  | 'failed'

type LocalResearchStatus = {
  available: boolean
  running: boolean
  stage: LocalResearchStage
  stageLabel: string
  message: string
  lastTicker: string | null
  startedAt: string | null
  finishedAt: string | null
  updatedAt: string | null
  lastResult: 'idle' | 'running' | 'success' | 'error'
}

type LocalPortfolioStatus = {
  available: boolean
  stage: 'idle' | 'saved' | 'failed'
  stageLabel: string
  message: string
  updatedAt: string | null
  holdings: PortfolioHoldingInput[]
}

const researchState: LocalResearchStatus = {
  available: true,
  running: false,
  stage: 'idle',
  stageLabel: '대기',
  message: '티커를 watchlist에 추가하고 리서치를 실행할 수 있습니다.',
  lastTicker: null,
  startedAt: null,
  finishedAt: null,
  updatedAt: null,
  lastResult: 'idle',
}

const portfolioState: LocalPortfolioStatus = {
  available: true,
  stage: 'idle',
  stageLabel: '대기',
  message: '포트폴리오를 로컬 설정 파일에 저장할 수 있습니다.',
  updatedAt: null,
  holdings: [],
}

let activeRunDate: string | null = null

function localResearchBridge(): Plugin {
  return {
    name: 'local-research-bridge',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (req.url?.startsWith('/output/data/')) {
          const served = await handleOutputDataRequest(req, res)
          if (served) {
            return
          }
        }

        if (req.url?.startsWith('/api/local-research')) {
          await handleLocalResearchRequest(req, res)
          return
        }

        if (req.url?.startsWith('/api/local-portfolio')) {
          await handleLocalPortfolioRequest(req, res)
          return
        }

        next()
      })
    },
  }
}

async function handleOutputDataRequest(req: IncomingMessage, res: ServerResponse): Promise<boolean> {
  const requestUrl = req.url ?? ''
  const pathname = requestUrl.split('?')[0] ?? ''
  const relativePath = pathname.replace(/^\/output\/data\//, '')
  if (!relativePath || relativePath.includes('..')) {
    return false
  }

  const targetPath = path.join(OUTPUT_DATA_ROOT, ...relativePath.split('/'))
  if (!existsSync(targetPath)) {
    return false
  }

  const body = await readFile(targetPath)
  res.statusCode = 200
  res.setHeader('Content-Type', inferContentType(targetPath))
  res.end(body)
  return true
}

function inferContentType(filePath: string): string {
  if (filePath.endsWith('.json')) {
    return 'application/json; charset=utf-8'
  }
  if (filePath.endsWith('.csv')) {
    return 'text/csv; charset=utf-8'
  }
  return 'application/octet-stream'
}

async function handleLocalResearchRequest(req: IncomingMessage, res: ServerResponse) {
  try {
    if (req.method === 'GET' && req.url === '/api/local-research/status') {
      await syncStateFromLogs()
      sendJson(res, 200, researchState)
      return
    }

    if (req.method === 'POST' && req.url === '/api/local-research/watchlist') {
      const payload = await readJsonBody(req)
      const ticker = normalizeTicker(payload?.ticker)
      if (!ticker) {
        sendJson(res, 400, {
          ok: false,
          added: false,
          ticker: '',
          message: '유효한 티커를 입력해주세요. 예: TSLA',
          status: researchState,
        })
        return
      }

      const result = await appendTickerToWatchlist(ticker)
      updateResearchState({
        stage: 'watchlist_updated',
        stageLabel: 'watchlist 반영',
        message: result.added
          ? `${ticker}를 watchlist에 추가했습니다. 이제 리서치를 실행해 결과를 생성할 수 있습니다.`
          : `${ticker}는 이미 watchlist에 있습니다. 바로 리서치를 실행할 수 있습니다.`,
        lastTicker: ticker,
        lastResult: 'idle',
      })

      sendJson(res, 200, {
        ok: true,
        added: result.added,
        ticker,
        message: researchState.message,
        status: researchState,
      })
      return
    }

    if (req.method === 'POST' && req.url === '/api/local-research/run') {
      if (researchState.running) {
        sendJson(res, 409, {
          ok: false,
          message: '이미 리서치 실행 중입니다. 완료될 때까지 잠시만 기다려주세요.',
          status: researchState,
        })
        return
      }

      activeRunDate = formatLocalDate(new Date())
      updateResearchState({
        running: true,
        stage: 'starting',
        stageLabel: '시작',
        message: '배치 리서치를 시작했습니다. 잠시만 기다려주세요.',
        startedAt: new Date().toISOString(),
        finishedAt: null,
        lastResult: 'running',
      })

      const child = spawn('python', ['main.py'], {
        cwd: REPO_ROOT,
        env: process.env,
        stdio: 'ignore',
        windowsHide: true,
      })

      child.on('error', (error) => {
        updateResearchState({
          running: false,
          stage: 'failed',
          stageLabel: '실패',
          message: `리서치 실행을 시작하지 못했습니다. ${error.message}`,
          finishedAt: new Date().toISOString(),
          lastResult: 'error',
        })
      })

      child.on('close', async (code) => {
        await syncStateFromLogs()
        updateResearchState({
          running: false,
          stage: code === 0 ? 'completed' : 'failed',
          stageLabel: code === 0 ? '완료' : '실패',
          message:
            code === 0
              ? '리서치 실행이 완료되었습니다. 대시보드 결과를 새로 불러옵니다.'
              : '리서치 실행에 실패했습니다. logs/pipeline 최신 로그를 확인해주세요.',
          finishedAt: new Date().toISOString(),
          lastResult: code === 0 ? 'success' : 'error',
        })
      })

      sendJson(res, 202, {
        ok: true,
        message: researchState.message,
        status: researchState,
      })
      return
    }

    sendJson(res, 404, { ok: false, message: 'Not found' })
  } catch (error) {
    updateResearchState({
      running: false,
      stage: 'failed',
      stageLabel: '실패',
      message: error instanceof Error ? error.message : '로컬 자동화 처리 중 오류가 발생했습니다.',
      finishedAt: new Date().toISOString(),
      lastResult: 'error',
    })
    sendJson(res, 500, { ok: false, message: researchState.message, status: researchState })
  }
}

async function handleLocalPortfolioRequest(req: IncomingMessage, res: ServerResponse) {
  try {
    if (req.method === 'GET' && req.url === '/api/local-portfolio/status') {
      portfolioState.holdings = await readPortfolioHoldings()
      updatePortfolioState({})
      sendJson(res, 200, portfolioState)
      return
    }

    if (req.method === 'POST' && req.url === '/api/local-portfolio/save') {
      const payload = await readJsonBody(req)
      const rawHoldings = Array.isArray(payload?.holdings) ? payload.holdings : []
      const existingHoldings = await readPortfolioHoldings()
      const holdings = resolvePortfolioSaveHoldings(existingHoldings, validatePortfolioHoldings(rawHoldings), {
        allowTruncate: payload?.allowTruncate === true,
      })
      await writePortfolioHoldings(holdings)
      await syncWatchlistFromPortfolio(holdings)

      updatePortfolioState({
        stage: 'saved',
        stageLabel: '저장됨',
        message: '포트폴리오를 저장했습니다. 대시보드 새로고침 시 합산값이 반영됩니다.',
        holdings,
      })

      sendJson(res, 200, {
        ok: true,
        message: portfolioState.message,
        status: portfolioState,
      })
      return
    }

    sendJson(res, 404, { ok: false, message: 'Not found' })
  } catch (error) {
    updatePortfolioState({
      stage: 'failed',
      stageLabel: '실패',
      message: error instanceof Error ? error.message : '포트폴리오 저장 중 오류가 발생했습니다.',
    })
    sendJson(res, 400, { ok: false, message: portfolioState.message, status: portfolioState })
  }
}

async function appendTickerToWatchlist(ticker: string): Promise<{ added: boolean }> {
  const existing = existsSync(WATCHLIST_PATH) ? await readFile(WATCHLIST_PATH, 'utf8') : 'watchlist:\n'
  if (hasWatchlistTicker(existing, ticker)) {
    return { added: false }
  }

  const scaffold = buildWatchlistScaffold(ticker)
  const next = `${existing.trimEnd()}\n${scaffold}\n`
  await writeFile(WATCHLIST_PATH, next, 'utf8')
  return { added: true }
}

async function syncWatchlistFromPortfolio(holdings: PortfolioHoldingInput[]) {
  const existing = existsSync(WATCHLIST_PATH) ? await readFile(WATCHLIST_PATH, 'utf8') : 'watchlist:\n'
  const uniqueTickers = Array.from(new Set(holdings.map((holding) => holding.ticker)))
  const missingTickers = uniqueTickers.filter((ticker) => !hasWatchlistTicker(existing, ticker))
  if (missingTickers.length === 0) {
    return
  }

  const nextBlocks = missingTickers.map(buildWatchlistScaffold).join('\n')
  const next = `${existing.trimEnd()}\n${nextBlocks}\n`
  await writeFile(WATCHLIST_PATH, next, 'utf8')
}

function buildWatchlistScaffold(ticker: string): string {
  return [`  - ticker: ${ticker}`, `    name: ${ticker}`, '    sector: ""', '    keywords: []'].join('\n')
}

function hasWatchlistTicker(contents: string, ticker: string): boolean {
  const escapedTicker = escapeRegex(ticker)
  const blockPattern = new RegExp(`^\\s*-\\s*ticker:\\s*${escapedTicker}\\s*$`, 'im')
  return blockPattern.test(contents)
}

async function readPortfolioHoldings(): Promise<PortfolioHoldingInput[]> {
  if (!existsSync(PORTFOLIO_PATH)) {
    return []
  }

  const text = await readFile(PORTFOLIO_PATH, 'utf8')
  const lines = text.split(/\r?\n/)
  const holdings: PortfolioHoldingInput[] = []
  let current: Partial<PortfolioHoldingInput> | null = null

  for (const line of lines) {
    const stripped = line.trim()
    if (!stripped || stripped.startsWith('#') || stripped === 'holdings:') {
      continue
    }

    if (stripped.startsWith('- ')) {
      if (current && current.ticker) {
        holdings.push(normalizeHoldingForStorage(current))
      }
      current = {}
      const [key, rawValue] = splitKeyValue(stripped.slice(2))
      current[key as keyof PortfolioHoldingInput] = parseScalar(rawValue) as never
      continue
    }

    if (!current) {
      continue
    }

    const [key, rawValue] = splitKeyValue(stripped)
    current[key as keyof PortfolioHoldingInput] = parseScalar(rawValue) as never
  }

  if (current && current.ticker) {
    holdings.push(normalizeHoldingForStorage(current))
  }

  return holdings
}

function validatePortfolioHoldings(rawHoldings: unknown[]): PortfolioHoldingInput[] {
  const holdings = rawHoldings.map((holding) => normalizeHoldingForStorage(holding as Partial<PortfolioHoldingInput>))
  if (holdings.length === 0) {
    throw new Error('최소 1개 이상의 보유 lot가 필요합니다.')
  }
  return holdings
}

function normalizeHoldingForStorage(rawHolding: Partial<PortfolioHoldingInput>): PortfolioHoldingInput {
  const ticker = normalizeTicker(rawHolding.ticker)
  if (!ticker) {
    throw new Error('유효하지 않은 티커가 포함되어 있습니다.')
  }

  const shares = Number(rawHolding.shares)
  if (!Number.isFinite(shares) || shares <= 0) {
    throw new Error(`${ticker}: 수량은 0보다 커야 합니다.`)
  }

  const avgCost = Number(rawHolding.avg_cost)
  if (!Number.isFinite(avgCost) || avgCost < 0) {
    throw new Error(`${ticker}: 평균단가는 0 이상이어야 합니다.`)
  }

  const currency = normalizeCurrency(rawHolding.currency)
  if (!currency) {
    throw new Error(`${ticker}: 통화는 USD 또는 KRW만 허용됩니다.`)
  }

  return {
    ticker,
    shares,
    avg_cost: avgCost,
    currency,
  }
}

async function writePortfolioHoldings(holdings: PortfolioHoldingInput[]) {
  const lines = ['holdings:']
  for (const holding of holdings) {
    lines.push(`  - ticker: ${holding.ticker}`)
    lines.push(`    shares: ${formatNumber(holding.shares)}`)
    lines.push(`    avg_cost: ${formatNumber(holding.avg_cost)}`)
    lines.push(`    currency: ${holding.currency}`)
    lines.push('')
  }

  lines.push('# NOTE:')
  lines.push('# KRW 현금은 현재 웹 편집 범위에서 제외되어 있습니다.')
  await writeFile(PORTFOLIO_PATH, `${lines.join('\n').trimEnd()}\n`, 'utf8')
}

async function syncStateFromLogs(): Promise<void> {
  if (!activeRunDate) {
    return
  }
  const logPath = path.join(LOGS_ROOT, `${activeRunDate}.jsonl`)
  if (!existsSync(logPath)) {
    return
  }

  const text = await readFile(logPath, 'utf8')
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
  if (lines.length === 0) {
    return
  }

  const latest = JSON.parse(lines[lines.length - 1]) as Record<string, unknown>
  const component = String(latest.component ?? '')
  const event = String(latest.event ?? '')
  const ticker = String(latest.ticker ?? '').trim()

  if (component === 'pipeline' && event === 'pipeline_completed') {
    updateResearchState({
      stage: 'completed',
      stageLabel: '완료',
      message: '리서치 실행이 완료되었습니다. 결과 파일을 새로 쓸 준비를 마쳤습니다.',
      lastResult: researchState.running ? 'running' : researchState.lastResult,
    })
    return
  }

  if (component === 'pipeline' && event === 'pipeline_failed') {
    updateResearchState({
      stage: 'failed',
      stageLabel: '실패',
      message: latest.error_message
        ? `리서치 실행 실패: ${String(latest.error_message)}`
        : '리서치 실행에 실패했습니다.',
      lastResult: 'error',
    })
    return
  }

  if (component === 'collector') {
    updateResearchState({
      stage: 'collecting',
      stageLabel: '수집 중',
      message: ticker ? `${ticker} 데이터와 뉴스/공시를 수집 중입니다.` : '시장 데이터와 뉴스를 수집 중입니다.',
    })
    return
  }

  if (component === 'analyzer') {
    updateResearchState({
      stage: 'analyzing',
      stageLabel: '분석 중',
      message: ticker ? `${ticker} 분석 초안을 생성 중입니다.` : 'LLM 분석을 진행 중입니다.',
    })
    return
  }

  if (component === 'output') {
    updateResearchState({
      stage: 'writing',
      stageLabel: '출력 생성 중',
      message: 'Markdown과 dashboard.json을 생성하고 있습니다.',
    })
  }
}

function updateResearchState(patch: Partial<LocalResearchStatus>) {
  Object.assign(researchState, patch, {
    available: true,
    updatedAt: new Date().toISOString(),
  })
}

function updatePortfolioState(patch: Partial<LocalPortfolioStatus>) {
  Object.assign(portfolioState, patch, {
    available: true,
    updatedAt: new Date().toISOString(),
  })
}

function sendJson(res: ServerResponse, statusCode: number, payload: unknown) {
  res.statusCode = statusCode
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.end(JSON.stringify(payload))
}

async function readJsonBody(req: IncomingMessage): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = []
  for await (const chunk of req) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk))
  }
  if (chunks.length === 0) {
    return {}
  }
  const raw = Buffer.concat(chunks).toString('utf8').trim()
  return raw ? (JSON.parse(raw) as Record<string, unknown>) : {}
}

function normalizeTicker(value: unknown): string {
  const normalized = String(value ?? '')
    .trim()
    .toUpperCase()
  return /^[A-Z][A-Z0-9.-]{0,14}$/.test(normalized) ? normalized : ''
}

function normalizeCurrency(value: unknown): string {
  const normalized = String(value ?? 'USD').trim().toUpperCase()
  if (normalized === 'USD' || normalized === 'KRW') {
    return normalized
  }
  return ''
}

function splitKeyValue(line: string): [string, string] {
  const [key, ...rest] = line.split(':')
  return [key.trim(), rest.join(':').trim()]
}

function parseScalar(value: string): string | number {
  const normalized = value.replace(/^['"]|['"]$/g, '')
  if (/^-?\d+(\.\d+)?$/.test(normalized)) {
    return Number(normalized)
  }
  return normalized
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function formatLocalDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export default defineConfig(({ command }) => {
  const isServe = command === 'serve'
  const isVercel = process.env.VERCEL === '1'

  return {
    plugins: isServe ? [react(), localResearchBridge()] : [react()],
    base: isServe || isVercel ? '/' : '/pkrich/',
  }
})
