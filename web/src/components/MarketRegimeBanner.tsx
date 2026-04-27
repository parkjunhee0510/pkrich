import type { MarketRegimeData } from '../types'

type RegimeKind = MarketRegimeData['regime']

const REGIME_CONFIG: Record<string, { dotClass: string; label: string; className: string }> = {
  risk_on:         { dotClass: '',     label: '공격적으로 보기 좋은 장세', className: 'regime-risk-on' },
  neutral:         { dotClass: 'warn', label: '중립 장세',                  className: 'regime-neutral' },
  risk_off:        { dotClass: 'bad',  label: '조심스럽게 봐야 하는 장세',  className: 'regime-risk-off' },
  reflation:       { dotClass: '',     label: '리플레이션 구간',            className: 'regime-reflation' },
  defensive_bias:  { dotClass: 'warn', label: '방어적 편향',                className: 'regime-defensive' },
}

interface MarketRegimeBannerProps {
  regime: MarketRegimeData | null | undefined
}

function formatEyebrowDate(assessedAt: string | undefined): string {
  if (!assessedAt) return ''
  const d = new Date(assessedAt)
  if (Number.isNaN(d.getTime())) return ''
  const months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
  return `${months[d.getMonth()]} ${String(d.getDate()).padStart(2, '0')}`
}

export function MarketRegimeBanner({ regime }: MarketRegimeBannerProps) {
  if (!regime || !regime.regime) return null

  const key: RegimeKind | 'neutral' = regime.regime in REGIME_CONFIG ? regime.regime : 'neutral'
  const config = REGIME_CONFIG[key] ?? REGIME_CONFIG.neutral
  const driverEntries = Object.entries(regime.drivers ?? {})
  const eyebrowDate = formatEyebrowDate(regime.assessed_at)

  return (
    <section className={`surface-card surface-card--hero market-regime-banner cozy-premium-banner ${config.className}`}>
      <div className="cozy-eyebrow">
        <span className={`dot ${config.dotClass}`.trim()}></span>
        MARKET REGIME{eyebrowDate ? ` · ${eyebrowDate}` : ''}
      </div>
      <div className="regime-head-row">
        <h3 className="cozy-headline">{config.label}</h3>
        <span className="cozy-pill">확신도 {regime.confidence}%</span>
      </div>
      {regime.implication ? <p className="cozy-impl">{regime.implication}</p> : null}
      {driverEntries.length > 0 ? (
        <div className="regime-drivers">
          {driverEntries.map(([key, value]) => (
            <span key={key} className="cozy-chip regime-driver-chip">
              {value}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  )
}
