import { useEffect, useMemo, useState } from 'react'
import { useDashboardData } from '../hooks/useDashboardData'
import type { ChatMessage, ChatResponse } from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? ''
const CHAT_STORAGE_KEY = 'pkrich-chat-history'

export function Chat() {
  const { data } = useDashboardData()
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    document.title = '리서치 채팅 · Stock Research'
  }, [])

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(CHAT_STORAGE_KEY)
      if (!saved) return
      const parsed = JSON.parse(saved) as ChatMessage[]
      if (Array.isArray(parsed)) {
        setMessages(parsed.filter((item) => item && (item.role === 'user' || item.role === 'assistant')))
      }
    } catch {
      // ignore corrupted local history
    }
  }, [])

  useEffect(() => {
    window.localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages))
  }, [messages])

  const recentConversation = useMemo(
    () => messages.slice(-8).map((message) => ({ role: message.role, content: message.content })),
    [messages],
  )

  async function handleAsk() {
    const trimmed = question.trim()
    if (!trimmed) return
    setQuestion('')
    setMessages((current) => [...current, { role: 'user', content: trimmed }])
    setLoading(true)
    try {
      if (API_BASE) {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: trimmed, messages: recentConversation }),
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json = (await res.json()) as ChatResponse
        setMessages((current) => [
          ...current,
          {
            role: 'assistant',
            content: json.answer,
            matched_tickers: json.matched_tickers,
            sources: json.sources,
          },
        ])
      } else {
        const fallback = buildFallbackResponse(trimmed, data)
        setMessages((current) => [
          ...current,
          {
            role: 'assistant',
            content: fallback.answer,
            matched_tickers: fallback.matched_tickers,
            sources: fallback.sources,
          },
        ])
      }
    } catch {
      const fallback = buildFallbackResponse(trimmed, data)
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: fallback.answer,
          matched_tickers: fallback.matched_tickers,
          sources: fallback.sources,
        },
      ])
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

      <div className="dashboard-controls u-mt-4">
        <input
          className="dashboard-search"
          type="search"
          placeholder="예: AAPL이 왜 약해?"
          aria-label="리서치 질문 입력"
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
        {messages.length > 0 ? (
          <button
            type="button"
            className="secondary-action-button"
            onClick={() => setMessages([])}
            disabled={loading}
          >
            대화 초기화
          </button>
        ) : null}
      </div>

      {messages.length > 0 ? (
        <div className="ticker-detail-section-shell">
          <h3>대화 이력</h3>
          <div className="chat-thread">
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`detail-note-card chat-message-card chat-${message.role}`}>
                <strong>{message.role === 'user' ? '질문' : '답변'}</strong>
                <p>{message.content}</p>
                {message.matched_tickers && message.matched_tickers.length > 0 ? (
                  <div className="watchlist-chip-row">
                    {message.matched_tickers.map((ticker) => (
                      <span key={ticker} className="period-badge">{ticker}</span>
                    ))}
                  </div>
                ) : null}
                {message.sources && message.sources.length > 0 ? (
                  <ul className="news-list">
                    {message.sources.map((source, sourceIndex) => (
                      <li key={`${source.ticker}-${sourceIndex}`} className="news-item">
                        <span className="filing-form-chip">{source.ticker}</span>
                        {source.link ? (
                          <a href={source.link} target="_blank" rel="noopener noreferrer">{source.title}</a>
                        ) : (
                          <span>{source.title}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ))}
          </div>
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
