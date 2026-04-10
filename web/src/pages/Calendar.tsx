import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useDashboardData } from '../hooks/useDashboardData'
import { TablePageSkeleton } from '../components/Skeleton'
import { ErrorState } from '../components/ErrorState'
import type { UpcomingEvent } from '../types'

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
  event: '일정',
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  earnings: 'var(--color-accent)',
  ex_dividend: '#f59e0b',
  dividend: '#22c55e',
  event: 'var(--color-neutral)',
}

function daysUntilBadgeClass(daysUntil: number): string {
  if (daysUntil <= 3) return 'calendar-badge-urgent'
  if (daysUntil <= 7) return 'calendar-badge-soon'
  if (daysUntil <= 14) return 'calendar-badge-upcoming'
  return 'calendar-badge-later'
}

export function Calendar() {
  const { data, loading, error } = useDashboardData()
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('ALL')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    document.title = '이벤트 캘린더 · Stock Research'
  }, [])

  if (loading) return <TablePageSkeleton title="이벤트 캘린더" />
  if (error) return <ErrorState message={error} />
  if (!data || data.days.length === 0) return <p className="status">No data available.</p>

  const latestDay = data.days[data.days.length - 1]

  // Aggregate all upcoming events across all tickers
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

  // Sort by date (ascending)
  const sortedEvents = [...allEvents].sort((a, b) => a.date.localeCompare(b.date))

  // Get unique event types for filter
  const eventTypes = Array.from(new Set(sortedEvents.map((e) => e.type))).sort()

  // Apply filters
  const normalizedQuery = searchQuery.trim().toLowerCase()
  const filteredEvents = sortedEvents.filter((event) => {
    const matchType = eventTypeFilter === 'ALL' || event.type === eventTypeFilter
    const matchQuery =
      normalizedQuery.length === 0 ||
      event.ticker.toLowerCase().includes(normalizedQuery) ||
      event.name.toLowerCase().includes(normalizedQuery)
    return matchType && matchQuery
  })

  // Group events by date
  const groupedByDate = filteredEvents.reduce<Record<string, CalendarEvent[]>>((acc, event) => {
    const dateKey = event.date
    return { ...acc, [dateKey]: [...(acc[dateKey] ?? []), event] }
  }, {})

  const earningsCount = allEvents.filter((e) => e.type === 'earnings').length
  const thisWeekCount = allEvents.filter((e) => {
    const days = parseInt(e.days_until, 10)
    return !isNaN(days) && days <= 7
  }).length

  return (
    <div className="calendar-page">
      <div className="dashboard-header">
        <h2>이벤트 캘린더 · {latestDay.date}</h2>
        <div className="calendar-stats">
          <span className="calendar-stat-badge">실적 {earningsCount}건</span>
          <span className="calendar-stat-badge calendar-stat-urgent">이번 주 {thisWeekCount}건</span>
        </div>
      </div>

      {/* Filters */}
      <div className="dashboard-controls">
        <input
          className="dashboard-search"
          type="search"
          placeholder="티커 또는 종목명 검색"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <select
          className="dashboard-filter"
          value={eventTypeFilter}
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

      {/* Events grouped by date */}
      {Object.keys(groupedByDate).length === 0 ? (
        <p className="status">예정된 이벤트가 없습니다.</p>
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
                        <span style={{ color: event.dailyChange.includes('-') ? 'var(--color-down)' : 'var(--color-up)' }}>
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
