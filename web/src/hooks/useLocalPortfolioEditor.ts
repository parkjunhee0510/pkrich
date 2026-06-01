import { useCallback, useEffect, useState } from 'react'
import type { LocalPortfolioSaveOptions, LocalPortfolioStatus, PortfolioHoldingInput } from '../types'

const STATUS_URL = '/api/local-portfolio/status'
const SAVE_URL = '/api/local-portfolio/save'

const INITIAL_STATUS: LocalPortfolioStatus = {
  available: false,
  stage: 'idle',
  stageLabel: '대기',
  message: '로컬 포트폴리오 편집 연결 상태를 확인하는 중입니다.',
  updatedAt: null,
  holdings: [],
}

let cachedLocalPortfolioStatus: LocalPortfolioStatus | null = null

export function useLocalPortfolioEditor({ onSaved }: { onSaved?: () => void } = {}) {
  const [status, setStatus] = useState<LocalPortfolioStatus>(() => cachedLocalPortfolioStatus ?? INITIAL_STATUS)
  const [loading, setLoading] = useState(() => cachedLocalPortfolioStatus === null)
  const [saving, setSaving] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(cachedLocalPortfolioStatus === null)
    try {
      const response = await fetch(STATUS_URL, { cache: 'no-store' })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const payload = (await response.json()) as LocalPortfolioStatus
      cachedLocalPortfolioStatus = payload
      setStatus(payload)
    } catch {
      const failedStatus = {
        ...INITIAL_STATUS,
        message: '포트폴리오 편집은 로컬 개발 서버에서만 사용할 수 있습니다.',
      }
      cachedLocalPortfolioStatus = failedStatus
      setStatus(failedStatus)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const saveHoldings = useCallback(
    async (holdings: PortfolioHoldingInput[], options?: LocalPortfolioSaveOptions) => {
      setSaving(true)
      try {
        const body = options?.allowTruncate ? { holdings, allowTruncate: true } : { holdings }
        const response = await fetch(SAVE_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        const payload = (await response.json()) as { ok: boolean; message: string; status: LocalPortfolioStatus }
        cachedLocalPortfolioStatus = payload.status
        setStatus(payload.status)
        if (payload.ok) {
          onSaved?.()
        }
        return payload
      } catch {
        const failedStatus = {
          ...status,
          stage: 'failed' as const,
          stageLabel: '실패',
          message: '포트폴리오 저장 요청에 실패했습니다. 로컬 개발 서버 상태를 확인해주세요.',
        }
        cachedLocalPortfolioStatus = failedStatus
        setStatus(failedStatus)
        return { ok: false, message: failedStatus.message, status: failedStatus }
      } finally {
        setSaving(false)
      }
    },
    [onSaved, status],
  )

  return {
    status,
    loading,
    saving,
    refresh,
    saveHoldings,
  }
}
