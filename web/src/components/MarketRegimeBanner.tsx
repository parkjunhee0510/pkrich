import type { MarketRegimeData } from '../types'

const REGIME_CONFIG: Record<string, { emoji: string; label: string; className: string }> = {
  risk_on: { emoji: '🟢', label: '공격적으로 보기 좋은 장세', className: 'regime-risk-on' },
  neutral: { emoji: '🟡', label: '중립 장세', className: 'regime-neutral' },
  risk_off: { emoji: '🔴', label: '조심스럽게 봐야 하는 장세', className: 'regime-risk-off' },
}

interface MarketRegimeBannerProps {
  regime: MarketRegimeData | null | undefined
}

export function MarketRegimeBanner({ regime }: MarketRegimeBannerProps) {
  if (!regime || !regime.regime) return null

  const config = REGIME_CONFIG[regime.regime] ?? REGIME_CONFIG.neutral
  const driverEntries = Object.entries(regime.drivers ?? {})

  return (
    <section className={`market-regime-banner ${config.className}`}>
      <div className="regime-header">
        <span className="regime-badge">
          {config.emoji} {config.label}
        </span>
        <span className="regime-confidence">확신도 {regime.confidence}%</span>
      </div>
      {regime.implication ? <p className="regime-implication">{regime.implication}</p> : null}
      {driverEntries.length > 0 ? (
        <div className="regime-drivers">
          {driverEntries.map(([key, value]) => (
            <span key={key} className="regime-driver-chip">
              {value}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  )
}
