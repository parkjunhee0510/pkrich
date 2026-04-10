import { useCallback, useEffect, useRef, useState } from 'react'

type PendingAction = 'add' | 'run' | null

export type LocalResearchStage =
  | 'idle'
  | 'watchlist_updated'
  | 'starting'
  | 'collecting'
  | 'analyzing'
  | 'writing'
  | 'completed'
  | 'failed'

export interface LocalResearchStatus {
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

type WatchlistResponse = {
  ok: boolean
  added: boolean
  ticker: string
  message: string
  status: LocalResearchStatus
}

const STATUS_URL = '/api/local-research/status'
const WATCHLIST_URL = '/api/local-research/watchlist'
const RUN_URL = '/api/local-research/run'

const INITIAL_STATUS: LocalResearchStatus = {
  available: false,
  running: false,
  stage: 'idle',
  stageLabel: '대기',
  message: '로컬 자동화 연결 상태를 확인하는 중입니다.',
  lastTicker: null,
  startedAt: null,
  finishedAt: null,
  updatedAt: null,
  lastResult: 'idle',
}

export function useLocalResearchAutomation({ onRunCompleted }: { onRunCompleted?: () => void } = {}) {
  const [status, setStatus] = useState<LocalResearchStatus>(INITIAL_STATUS)
  const [pendingAction, setPendingAction] = useState<PendingAction>(null)
  const wasRunningRef = useRef(false)

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(STATUS_URL, { cache: 'no-store' })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const payload = (await response.json()) as LocalResearchStatus
      setStatus(payload)
    } catch {
      setStatus({
        ...INITIAL_STATUS,
        message: '로컬 자동화는 개발 서버에서만 사용할 수 있습니다. `npm run dev` 환경인지 확인해보세요.',
      })
    }
  }, [])

  useEffect(() => {
    void fetchStatus()
  }, [fetchStatus])

  useEffect(() => {
    const intervalMs = status.running ? 1500 : 8000
    const interval = window.setInterval(() => {
      void fetchStatus()
    }, intervalMs)
    return () => window.clearInterval(interval)
  }, [fetchStatus, status.running])

  useEffect(() => {
    if (wasRunningRef.current && !status.running && status.lastResult === 'success') {
      onRunCompleted?.()
    }
    wasRunningRef.current = status.running
  }, [onRunCompleted, status.lastResult, status.running])

  const addTickerToWatchlist = useCallback(
    async (rawTicker: string) => {
      const ticker = rawTicker.trim().toUpperCase()
      if (!ticker) {
        return {
          ok: false,
          added: false,
          ticker: '',
          message: '추가할 티커를 먼저 입력해주세요.',
          status,
        }
      }

      setPendingAction('add')
      try {
        const response = await fetch(WATCHLIST_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ticker }),
        })
        const payload = (await response.json()) as WatchlistResponse
        setStatus(payload.status)
        return payload
      } catch {
        const failedStatus = {
          ...status,
          message: 'watchlist 반영 요청에 실패했습니다. 개발 서버가 실행 중인지 확인해주세요.',
        }
        setStatus(failedStatus)
        return {
          ok: false,
          added: false,
          ticker,
          message: failedStatus.message,
          status: failedStatus,
        }
      } finally {
        setPendingAction(null)
      }
    },
    [status],
  )

  const runResearch = useCallback(async () => {
    setPendingAction('run')
    try {
      const response = await fetch(RUN_URL, { method: 'POST' })
      const payload = (await response.json()) as { ok: boolean; message: string; status: LocalResearchStatus }
      setStatus(payload.status)
      return payload
    } catch {
      const failedStatus = {
        ...status,
        stage: 'failed' as const,
        stageLabel: '실패',
        message: '리서치 실행 요청에 실패했습니다. 개발 서버와 Python 실행 환경을 확인해주세요.',
        lastResult: 'error' as const,
      }
      setStatus(failedStatus)
      return { ok: false, message: failedStatus.message, status: failedStatus }
    } finally {
      setPendingAction(null)
    }
  }, [status])

  return {
    status,
    pendingAction,
    available: status.available,
    addTickerToWatchlist,
    runResearch,
    refreshStatus: fetchStatus,
  }
}
