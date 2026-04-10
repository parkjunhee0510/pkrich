import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { readFile, writeFile } from 'node:fs/promises'
import type { IncomingMessage, ServerResponse } from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Plugin } from 'vite'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const WEB_ROOT = fileURLToPath(new URL('.', import.meta.url))
const REPO_ROOT = path.resolve(WEB_ROOT, '..')
const WATCHLIST_PATH = path.join(REPO_ROOT, 'config', 'watchlist.yaml')
const LOGS_ROOT = path.join(REPO_ROOT, 'logs', 'pipeline')

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

let activeRunDate: string | null = null

function localResearchBridge(): Plugin {
  return {
    name: 'local-research-bridge',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (!req.url?.startsWith('/api/local-research')) {
          next()
          return
        }

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
            updateState({
              stage: 'watchlist_updated',
              stageLabel: 'watchlist 반영',
              message: result.added
                ? `${ticker}를 watchlist에 추가했습니다. 이제 리서치 실행을 눌러 결과를 생성하세요.`
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
            updateState({
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
              updateState({
                running: false,
                stage: 'failed',
                stageLabel: '실패',
                message: `리서치 실행을 시작하지 못했습니다: ${error.message}`,
                finishedAt: new Date().toISOString(),
                lastResult: 'error',
              })
            })

            child.on('close', async (code) => {
              await syncStateFromLogs()
              updateState({
                running: false,
                stage: code === 0 ? 'completed' : 'failed',
                stageLabel: code === 0 ? '완료' : '실패',
                message:
                  code === 0
                    ? '리서치 실행이 완료되었습니다. 대시보드 결과를 새로 불러옵니다.'
                    : '리서치 실행이 실패했습니다. logs/pipeline 최신 로그를 확인해주세요.',
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
          updateState({
            running: false,
            stage: 'failed',
            stageLabel: '실패',
            message: error instanceof Error ? error.message : '로컬 자동화 처리 중 오류가 발생했습니다.',
            finishedAt: new Date().toISOString(),
            lastResult: 'error',
          })
          sendJson(res, 500, { ok: false, message: researchState.message, status: researchState })
        }
      })
    },
  }
}

async function appendTickerToWatchlist(ticker: string): Promise<{ added: boolean }> {
  const blockPattern = new RegExp(`^\\s*-\\s*ticker:\\s*${escapeRegex(ticker)}\\s*$`, 'im')
  const existing = existsSync(WATCHLIST_PATH) ? await readFile(WATCHLIST_PATH, 'utf8') : 'watchlist:\n'
  if (blockPattern.test(existing)) {
    return { added: false }
  }

  const scaffold = [
    '',
    `  - ticker: ${ticker}`,
    `    name: ${ticker}`,
    '    sector: ""',
    '    keywords: []',
    '',
  ].join('\n')
  const next = `${existing.trimEnd()}${scaffold}`
  await writeFile(WATCHLIST_PATH, next, 'utf8')
  return { added: true }
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
    updateState({
      stage: 'completed',
      stageLabel: '완료',
      message: '리서치 실행이 완료되었습니다. 결과 파일을 새로 쓸 준비를 마쳤습니다.',
      lastResult: researchState.running ? 'running' : researchState.lastResult,
    })
    return
  }

  if (component === 'pipeline' && event === 'pipeline_failed') {
    updateState({
      stage: 'failed',
      stageLabel: '실패',
      message: latest.error_message
        ? `리서치 실행 실패: ${String(latest.error_message)}`
        : '리서치 실행이 실패했습니다.',
      lastResult: 'error',
    })
    return
  }

  if (component === 'collector') {
    updateState({
      stage: 'collecting',
      stageLabel: '수집 중',
      message: ticker ? `${ticker} 데이터와 뉴스/공시를 수집 중입니다.` : '시장 데이터와 뉴스를 수집 중입니다.',
    })
    return
  }

  if (component === 'analyzer') {
    updateState({
      stage: 'analyzing',
      stageLabel: '분석 중',
      message: ticker ? `${ticker} 분석 초안을 생성 중입니다.` : 'LLM 분석을 진행 중입니다.',
    })
    return
  }

  if (component === 'output') {
    updateState({
      stage: 'writing',
      stageLabel: '출력 생성 중',
      message: 'Markdown과 dashboard.json을 생성하고 있습니다.',
    })
  }
}

function updateState(patch: Partial<LocalResearchStatus>) {
  Object.assign(researchState, patch, {
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

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function formatLocalDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export default defineConfig(({ command }) => ({
  plugins: command === 'serve' ? [react(), localResearchBridge()] : [react()],
  // Use the repository subpath only for production builds.
  base: command === 'serve' ? '/' : '/pkrich/',
}))
