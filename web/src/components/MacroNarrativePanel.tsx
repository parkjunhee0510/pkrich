import type { MacroNarrativeData, MarketRegimeData } from '../types'

interface Props {
  narrative?: MacroNarrativeData | null
  regime?: MarketRegimeData | null
}

const REGIME_TONE: Record<string, string> = {
  risk_on: 'regime-risk-on',
  risk_off: 'regime-risk-off',
  neutral: 'regime-neutral',
  reflation: 'regime-reflation',
  defensive_bias: 'regime-defensive',
}

const REGIME_LABELS: Record<string, string> = {
  risk_on: '공격적인 장세',
  risk_off: '보수적인 장세',
  neutral: '중립 장세',
  reflation: '경기 회복 기대 장세',
  defensive_bias: '방어주 선호 장세',
}

export function MacroNarrativePanel({ narrative, regime }: Props) {
  if (!narrative || !narrative.headline) return null
  const regimeKey = regime?.sub_regime || regime?.regime || 'neutral'
  const tone = REGIME_TONE[regimeKey] ?? 'regime-neutral'
  const regimeLabel = REGIME_LABELS[regimeKey] ?? REGIME_LABELS[regime?.regime ?? 'neutral'] ?? '중립 장세'

  return (
    <section className={`macro-narrative-panel ${tone}`}>
      <header className="macro-narrative-header">
        <span className="macro-narrative-eyebrow">이번 주 시장 한눈에 보기</span>
        {regime ? (
          <span className={`macro-narrative-regime-badge ${tone}`}>
            {regimeLabel}
            {regime.confidence ? ` (${regime.confidence}%)` : ''}
          </span>
        ) : null}
      </header>
      <h3 className="macro-narrative-headline">{narrative.headline}</h3>
      {narrative.three_themes && narrative.three_themes.length > 0 ? (
        <ul className="macro-narrative-themes">
          {narrative.three_themes.slice(0, 3).map((theme, idx) => (
            <li key={idx}>{theme}</li>
          ))}
        </ul>
      ) : null}
      <div className="macro-narrative-meta">
        {narrative.what_changed_this_week ? (
          <p>
            <strong>이번 주 달라진 점</strong> {narrative.what_changed_this_week}
          </p>
        ) : null}
        {narrative.risk_map ? (
          <p>
            <strong>주의할 점</strong> {narrative.risk_map}
          </p>
        ) : null}
        {narrative.source === 'fallback' ? (
          <small className="macro-narrative-source">자동 요약으로 생성된 시장 설명입니다.</small>
        ) : null}
      </div>
    </section>
  )
}
