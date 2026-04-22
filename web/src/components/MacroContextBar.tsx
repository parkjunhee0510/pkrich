import type { MacroContext } from '../types'

const EVENT_LABEL_KO: Record<string, string> = {
  'FOMC Rate Decision': 'FOMC 금리 결정',
  'CPI Consumer Inflation': 'CPI 소비자물가',
  'PPI Producer Inflation': 'PPI 생산자물가',
  'NFP Payrolls': 'NFP 비농업고용',
  'Unemployment Rate': '실업률',
  'Retail Sales': '소매판매',
}

function localizeLabel(label: string): string {
  return EVENT_LABEL_KO[label] ?? label
}

function sensitivityLabel(value: string | undefined): string {
  if (value === 'high') return 'high'
  if (value === 'medium') return 'medium'
  return 'low'
}

function buildShockSummary(macroContext?: MacroContext | null): string | null {
  const macroEvents = macroContext?.macro_events ?? []
  if (!macroEvents.length) return null
  const topEvent = macroEvents[0]
  const summary = topEvent?.summary_ko?.trim()
  if (!summary) return null
  const severity = topEvent?.severity ? String(topEvent.severity).toUpperCase() : ''
  const prefix = severity ? `${severity} 충격` : '거시 충격'
  return `${prefix}: ${summary}`
}

function buildShockImpacts(macroContext?: MacroContext | null): string[] {
  const topEvent = macroContext?.macro_events?.[0]
  if (!topEvent) return []
  const industries = (topEvent.affected_industries ?? [])
    .map((item) => item.trim())
    .filter(Boolean)
  if (industries.length > 0) {
    return industries.slice(0, 4)
  }
  return (topEvent.affected_sectors ?? [])
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 4)
}

export function MacroContextBar({ macroContext }: { macroContext?: MacroContext | null }) {
  const vix = macroContext?.vix
  const curve2s10s = macroContext?.yield_curve_10y_2y
  const credit = macroContext?.credit_spread
  const surprise = macroContext?.surprise_score
  const macroSeries = [
    { label: 'US10Y', value: macroContext?.us10y?.level ?? macroContext?.us10y?.price, change: macroContext?.us10y?.change },
    { label: 'DXY', value: macroContext?.dxy?.level ?? macroContext?.dxy?.price, change: macroContext?.dxy?.change },
    { label: 'WTI', value: macroContext?.oil_wti?.level ?? macroContext?.oil_wti?.price, change: macroContext?.oil_wti?.change },
    { label: 'Copper', value: macroContext?.copper?.level ?? macroContext?.copper?.price, change: macroContext?.copper?.change },
    { label: 'Gold', value: macroContext?.gold?.level ?? macroContext?.gold?.price, change: macroContext?.gold?.change },
    curve2s10s?.level
      ? { label: '10Y-2Y', value: curve2s10s.level, change: curve2s10s.status ?? '' }
      : { label: '', value: undefined, change: undefined },
    credit?.level
      ? { label: 'HY/IG', value: credit.level, change: '' }
      : { label: '', value: undefined, change: undefined },
    surprise && typeof surprise.composite === 'number'
      ? {
          label: 'Surprise',
          value: surprise.composite.toFixed(2),
          change: surprise.confidence ?? '',
        }
      : { label: '', value: undefined, change: undefined },
  ].filter((item) => item.value)
  const macroEvents = (macroContext?.portfolio_event_sensitivity ?? macroContext?.upcoming_macro_events ?? []).slice(0, 3)
  const sensitivitySummary = macroContext?.portfolio_sensitivity_summary
  const shockSummary = buildShockSummary(macroContext)
  const shockImpacts = buildShockImpacts(macroContext)

  if (!vix && macroEvents.length === 0 && macroSeries.length === 0 && !shockSummary) {
    return null
  }

  return (
    <section className="macro-context-bar">
      <div className="macro-context-summary">
        <span className="macro-context-eyebrow">거시경제 현황 요약</span>
        <div className="macro-context-main">
          <strong>VIX {vix?.level ?? 'N/A'}</strong>
          <span>{vix?.regime ?? '정보 없음'}</span>
          {vix?.change && vix.change !== 'N/A' ? <small>{vix.change}</small> : null}
        </div>
        {sensitivitySummary && sensitivitySummary !== 'N/A' ? (
          <p className="macro-context-summary-text">{sensitivitySummary}</p>
        ) : null}
        {shockSummary ? (
          <div className="macro-context-shock-block">
            <p className="macro-context-shock-summary">{shockSummary}</p>
            {shockImpacts.length > 0 ? (
              <div className="macro-context-impact-chips" aria-label="macro shock impacted industries">
                {shockImpacts.map((impact) => (
                  <span key={impact} className="macro-context-impact-chip">{impact}</span>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="macro-context-detail">
        {macroSeries.length > 0 ? (
          <div className="macro-series-grid">
            {macroSeries.map((item) => (
              <div key={item.label} className="macro-series-card">
                <span className="macro-event-type">{item.label}</span>
                <strong>{item.value}</strong>
                {item.change && item.change !== 'N/A' ? <small>{item.change}</small> : null}
              </div>
            ))}
          </div>
        ) : null}
        {macroEvents.length > 0 ? (
          <div className="macro-event-list">
            {macroEvents.map((event) => (
              <div key={`${event.event_code ?? event.type}-${event.date}`} className={`macro-event-card impact-${event.impact ?? 'medium'}`}>
                <span className="macro-event-type">{event.event_code ?? event.type}</span>
                <strong>{localizeLabel(event.label)}</strong>
                <small>
                  {event.date} · D-{event.days_until}
                </small>
                {event.market_bias ? <small>{event.market_bias}</small> : null}
                {event.sensitive_holdings && event.sensitive_holdings.length > 0 ? (
                  <div className="macro-sensitive-holdings">
                    {event.sensitive_holdings.slice(0, 3).map((holding) => (
                      <span key={`${event.event_code}-${holding.ticker}`} className={`macro-sensitive-chip sensitivity-${sensitivityLabel(holding.sensitivity)}`}>
                        {holding.ticker} ({holding.sensitivity})
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <div className="macro-event-empty">예정된 주요 매크로 이벤트가 없습니다.</div>
        )}
      </div>
    </section>
  )
}
