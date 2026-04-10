import { useEffect, useState } from 'react'
import { useDashboardData } from '../hooks/useDashboardData'
import type { ChatResponse } from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? ''

export function Chat() {
  const { data } = useDashboardData()
  const [question, setQuestion] = useState('')
  const [response, setResponse] = useState<ChatResponse | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    document.title = '리서치 채팅 · Stock Research'
  }, [])

  async function handleAsk() {
    const trimmed = question.trim()
    if (!trimmed) return
    setLoading(true)
    try {
      if (API_BASE) {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: trimmed }),
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json = (await res.json()) as ChatResponse
        setResponse(json)
      } else {
        setResponse(buildFallbackResponse(trimmed, data))
      }
    } catch {
      setResponse(buildFallbackResponse(trimmed, data))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="signals-page">
      <div className="dashboard-header">
        <h2>리서치 채팅</h2>
        <div className="signal-overall-badge">
          {API_BASE ? 'API 연결' : '정적 fallback 모드'}
        </div>
      </div>

      <div className="portfolio-editor-toolbar">
        <div>
          <strong>질문 입력</strong>
          <p>현재 저장된 리서치 데이터 기준으로 답변합니다. 실시간 시세는 반영되지 않습니다.</p>
        </div>
      </div>

      <div className="dashboard-controls" style={{ marginTop: '1rem' }}>
        <input
          className="dashboard-search"
          type="search"
          placeholder="예: AAPL이 왜 약해?"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              void handleAsk()
            }
          }}
        />
        <button type="button" className="primary-action-button" onClick={() => void handleAsk()} disabled={loading}>
          {loading ? '답변 생성 중...' : '질문하기'}
        </button>
      </div>

      {response ? (
        <div className="ticker-detail-section-shell">
          <h3>답변</h3>
          <div className="detail-note-card">
            <p>{response.answer}</p>
            {response.matched_tickers.length > 0 ? (
              <div className="watchlist-chip-row">
                {response.matched_tickers.map((ticker) => (
                  <span key={ticker} className="period-badge">{ticker}</span>
                ))}
              </div>
            ) : null}
          </div>

          {response.sources.length > 0 ? (
            <div style={{ marginTop: '1rem' }}>
              <h3>참고 소스</h3>
              <ul className="news-list">
                {response.sources.map((source, index) => (
                  <li key={`${source.ticker}-${index}`} className="news-item">
                    <span className="filing-form-chip">{source.ticker}</span>
                    {source.link ? (
                      <a href={source.link} target="_blank" rel="noopener noreferrer">{source.title}</a>
                    ) : (
                      <span>{source.title}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="status">질문을 입력하면 저장된 리서치 데이터를 바탕으로 답변을 생성합니다.</p>
      )}
    </div>
  )
}

function buildFallbackResponse(question: string, data: ReturnType<typeof useDashboardData>['data']): ChatResponse {
  const latestDay = data?.days?.[data.days.length - 1]
  const tickers = latestDay?.tickers ?? []
  const normalized = question.toLowerCase()
  const matched = tickers.filter(
    (ticker) =>
      ticker.ticker.toLowerCase().includes(normalized) ||
      ticker.name.toLowerCase().includes(normalized),
  )
  const lead = matched[0] ?? tickers[0]
  if (!lead) {
    return { answer: '현재 저장된 리서치 데이터가 없습니다.', matched_tickers: [], sources: [] }
  }
  return {
    answer: `${lead.ticker} 기준 요약입니다. ${lead.summary} 한줄 판단은 ${lead.signal_or_takeaway} 입니다.`,
    matched_tickers: [lead.ticker],
    sources: (lead.news_references ?? []).slice(0, 3).map((source) => ({
      ticker: lead.ticker,
      title: source.title,
      link: source.link,
    })),
  }
}
