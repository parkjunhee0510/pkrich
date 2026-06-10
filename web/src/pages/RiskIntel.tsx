import { useEffect } from 'react'
import { ErrorState } from '../components/ErrorState'
import { RiskIntelPanel } from '../components/RiskIntelPanel'
import { DashboardSkeleton } from '../components/Skeleton'
import { useRiskIntelData } from '../hooks/useRiskIntelData'

export function RiskIntel() {
  const { summary, graph, loading, error, graphError } = useRiskIntelData()

  useEffect(() => {
    document.title = '리스크 인텔리전스 · Stock Research'
  }, [])

  if (loading) return <DashboardSkeleton />

  if (error) {
    const isMissing = /(^|\s)4\d\d(\s|$)/.test(error)
    if (isMissing) {
      return (
        <div className="risk-intel-page">
          <header className="page-header">
            <div className="page-header__eyebrow">RISK INTELLIGENCE</div>
            <div className="page-header__row">
              <h1 className="page-header__headline">리스크 인텔리전스</h1>
            </div>
            <p className="page-header__meta">
              아직 네트워크 데이터가 없습니다. 다음 일일 배치가 완료되면 정책·안보·사회 이슈의 전파 경로가 표시됩니다.
            </p>
          </header>
          <p className="status">output/data/risk_intel_summary.json 파일이 없습니다.</p>
        </div>
      )
    }
    return <ErrorState message={`risk_intel_summary.json: ${error}`} />
  }

  if (!summary) return null

  return (
    <div className="risk-intel-page">
      <RiskIntelPanel summary={summary} graph={graph} />
      {graphError ? (
        <p className="risk-intel-secondary-note">
          네트워크 상세 파일을 읽지 못해 카드 요약만 표시합니다. ({graphError})
        </p>
      ) : null}
      {graph?.health_warnings?.length ? (
        <section className="risk-intel-warning-panel" aria-labelledby="risk-intel-warning-title">
          <h3 id="risk-intel-warning-title">검증 경고</h3>
          <ul>
            {graph.health_warnings.map((warning) => (
              <li key={`${warning.code}-${warning.ref_id ?? warning.message_ko}`}>
                <strong>{warning.code}</strong>
                <span>{warning.message_ko}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}
