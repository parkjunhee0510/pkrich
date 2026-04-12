import type { MacroContext } from '../types'

export function MacroContextBar({ macroContext }: { macroContext?: MacroContext | null }) {
  const vix = macroContext?.vix
  const macroSeries = [
    { label: 'US10Y', value: macroContext?.us10y?.level ?? macroContext?.us10y?.price, change: macroContext?.us10y?.change },
    { label: 'DXY', value: macroContext?.dxy?.level ?? macroContext?.dxy?.price, change: macroContext?.dxy?.change },
    { label: 'Copper', value: macroContext?.copper?.level ?? macroContext?.copper?.price, change: macroContext?.copper?.change },
  ].filter((item) => item.value)
  const macroEvents = (macroContext?.upcoming_macro_events ?? []).slice(0, 3)

  if (!vix && macroEvents.length === 0 && macroSeries.length === 0) {
    return null
  }

  return (
    <section className="macro-context-bar">
      <div className="macro-context-summary">
        <span className="macro-context-eyebrow">Macro Context</span>
        <div className="macro-context-main">
          <strong>VIX {vix?.level ?? 'N/A'}</strong>
          <span>{vix?.regime ?? '레짐 데이터 없음'}</span>
          {vix?.change && vix.change !== 'N/A' ? <small>{vix.change}</small> : null}
        </div>
      </div>

      <div className="macro-context-detail">
        {macroSeries.length > 0 ? (
          <div className="macro-series-grid">
            {macroSeries.map((item) => (
              <div key={item.label} className="macro-series-card">
                <span className="macro-event-type">{item.label}</span>
                <strong>{item.value}</strong>
                {item.change && item.change !== 'N/A' ? <small>{item.change}</small> : <small>변화 데이터 없음</small>}
              </div>
            ))}
          </div>
        ) : null}
        {macroEvents.length > 0 ? (
          <div className="macro-event-list">
            {macroEvents.map((event) => (
              <div key={`${event.type}-${event.date}`} className={`macro-event-card impact-${event.impact ?? 'medium'}`}>
                <span className="macro-event-type">{event.type}</span>
                <strong>{event.label}</strong>
                <small>
                  {event.date} · D-{event.days_until}
                </small>
              </div>
            ))}
          </div>
        ) : (
          <div className="macro-event-empty">예정된 매크로 이벤트가 없습니다.</div>
        )}
      </div>
    </section>
  )
}
