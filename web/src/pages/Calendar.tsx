import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useDashboardData } from '../hooks/useDashboardData'
import { TablePageSkeleton } from '../components/Skeleton'
import { ErrorState } from '../components/ErrorState'
import { EmptyState } from '../components/ui/EmptyState'
import { parseNumericChange, changeColor } from '../utils/format'
import type { MacroEvent, UpcomingEvent } from '../types'

interface CalendarEvent extends UpcomingEvent {
  ticker: string
  name: string
  price: string
  dailyChange: string
  signal: string
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  earnings: '실적 발표',
  ex_dividend: '배당락일',
  dividend: '배당 지급일',
  event: '이벤트',
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  earnings: 'var(--color-accent)',
  ex_dividend: 'var(--color-caution)',
  dividend: 'var(--color-positive)',
  event: 'var(--color-neutral)',
}

function daysUntilBadgeClass(daysUntil: number): string {
  if (daysUntil <= 3) return 'calendar-badge-urgent'
  if (daysUntil <= 7) return 'calendar-badge-soon'
  if (daysUntil <= 14) return 'calendar-badge-upcoming'
  return 'calendar-badge-later'
}

function macroImpactClass(impact?: string): string {
  if (impact === 'high') return 'calendar-badge-urgent'
  if (impact === 'medium') return 'calendar-badge-upcoming'
  return 'calendar-badge-later'
}

export function Calendar() {
  const { data, loading, error } = useDashboardData()
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('ALL')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    document.title = '캘린더 · Stock Research'
  }, [])

  if (loading) return <TablePageSkeleton title="캘린더" />
  if (error) return <ErrorState message={error} />
  if (!data || data.days.length === 0) {
    return (
      <EmptyState
        title="표시할 캘린더 데이터가 없습니다."
        description="대시보드 출력이 생성되면 실적, 배당, 이벤트 일정이 여기에 표시됩니다."
      />
    )
  }

  const latestDay = data.days[data.days.length - 1]

  const allEvents: CalendarEvent[] = latestDay.tickers.flatMap((ticker) =>
    (ticker.upcoming_events ?? []).map((event) => ({
      ...event,
      ticker: ticker.ticker,
      name: ticker.name,
      price: ticker.data_snapshot['Price'] ?? '-',
      dailyChange: ticker.data_snapshot['Daily Change'] ?? '-',
      signal: ticker.signal_or_takeaway ?? '-',
    })),
  )

  const sortedEvents = [...allEvents].sort((a, b) => a.date.localeCompare(b.date))
  const eventTypes = Array.from(new Set(sortedEvents.map((e) => e.type))).sort()

  const normalizedQuery = searchQuery.trim().toLowerCase()
  const filteredEvents = sortedEvents.filter((event) => {
    const matchType = eventTypeFilter === 'ALL' || event.type === eventTypeFilter
    const matchQuery =
      normalizedQuery.length === 0 ||
      event.ticker.toLowerCase().includes(normalizedQuery) ||
      event.name.toLowerCase().includes(normalizedQuery)
    return matchType && matchQuery
  })

  const groupedByDate = filteredEvents.reduce<Record<string, CalendarEvent[]>>((acc, event) => {
    const dateKey = event.date
    return { ...acc, [dateKey]: [...(acc[dateKey] ?? []), event] }
  }, {})

  const macroEvents = (latestDay.macro_context?.portfolio_event_sensitivity ?? latestDay.macro_context?.upcoming_macro_events ?? []) as MacroEvent[]
  const earningsCount = allEvents.filter((e) => e.type === 'earnings').length
  const thisWeekCount = allEvents.filter((e) => {
    const days = parseInt(e.days_until, 10)
    return !isNaN(days) && days <= 7
  }).length

  return (
    <div className="calendar-page">
      <div className="dashboard-header">
        <h1>캘린더 · {latestDay.date}</h1>
        <div className="calendar-stats">
          <span className="calendar-stat-badge">실적 {earningsCount}건</span>
          <span className="calendar-stat-badge calendar-stat-urgent">이번 주 {thisWeekCount}건</span>
        </div>
      </div>

      <section className="macro-calendar-panel">
        <div className="section-header-inline">
          <h3>매크로 이벤트 민감도 분석</h3>
          <p>포트폴리오 보유 종목이 민감하게 반응할 수 있는 매크로 이벤트입니다.</p>
        </div>
        {macroEvents.length === 0 ? (
          <p className="status">민감도 분석 데이터가 없거나 로딩 중입니다.</p>
        ) : (
          <div className="macro-calendar-grid">
            {macroEvents.slice(0, 6).map((event) => (
              <article key={`${event.event_code ?? event.type}-${event.date}`} className="macro-calendar-card">
                <div className="calendar-event-header">
                  <span className="calendar-event-type">{event.event_code ?? event.type}</span>
                  <span className={`calendar-day-badge ${macroImpactClass(event.impact)}`}>{event.impact ?? 'medium'}</span>
                </div>
                <strong>{event.label}</strong>
                <div className="calendar-event-meta">
                  <span>{event.date}</span>
                  <span>D-{event.days_until}</span>
                </div>
                {event.market_bias ? <p className="macro-calendar-bias">{event.market_bias}</p> : null}
                {event.sensitive_holdings && event.sensitive_holdings.length > 0 ? (
                  <div className="macro-sensitive-holdings">
                    {event.sensitive_holdings.slice(0, 5).map((holding) => (
                      <span key={`${event.event_code}-${holding.ticker}`} className={`macro-sensitive-chip sensitivity-${holding.sensitivity}`}>
                        {holding.ticker} ({holding.sensitivity})
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="macro-calendar-empty">민감 보유 종목이 없습니다.</p>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      <div className="dashboard-controls">
        <input
          className="dashboard-search"
          type="search"
          placeholder="종목명 또는 티커 검색"
          aria-label="캘린더 종목명 또는 티커 검색"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <select
          className="dashboard-filter"
          value={eventTypeFilter}
          aria-label="캘린더 이벤트 유형 필터"
          onChange={(e) => setEventTypeFilter(e.target.value)}
        >
          <option value="ALL">전체 이벤트</option>
          {eventTypes.map((type) => (
            <option key={type} value={type}>
              {EVENT_TYPE_LABELS[type] ?? type}
            </option>
          ))}
        </select>
      </div>

      {Object.keys(groupedByDate).length === 0 ? (
        <p className="status">해당 조건에 맞는 이벤트가 없습니다.</p>
      ) : (
        <div className="calendar-timeline">
          {Object.entries(groupedByDate).map(([dateStr, events]) => {
            const daysUntil = parseInt(events[0]?.days_until ?? '0', 10)
            const dayLabel = isNaN(daysUntil) ? '' : daysUntil === 0 ? '오늘' : `D-${daysUntil}`
            return (
              <div key={dateStr} className="calendar-date-group">
                <div className="calendar-date-header">
                  <span className="calendar-date-text">{dateStr}</span>
                  {dayLabel && (
                    <span className={`calendar-day-badge ${daysUntilBadgeClass(daysUntil)}`}>{dayLabel}</span>
                  )}
                </div>
                <div className="calendar-events">
                  {events.map((event, idx) => (
                    <div key={`${event.ticker}-${event.type}-${idx}`} className="calendar-event-card">
                      <div className="calendar-event-header">
                        <span
                          className="calendar-event-type"
                          style={{ color: EVENT_TYPE_COLORS[event.type] ?? 'inherit' }}
                        >
                          {EVENT_TYPE_LABELS[event.type] ?? event.type}
                        </span>
                        {event.timing && <span className="calendar-event-timing">{event.timing}</span>}
                      </div>
                      <div className="calendar-event-ticker">
                        <Link to={`/ticker/${event.ticker}`} className="ticker-link">
                          {event.ticker}
                        </Link>
                        <span className="calendar-event-name">{event.name}</span>
                      </div>
                      <div className="calendar-event-meta">
                        <span>{event.price}</span>
                        <span style={{ color: changeColor(parseNumericChange(event.dailyChange)) }}>
                          {event.dailyChange}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
