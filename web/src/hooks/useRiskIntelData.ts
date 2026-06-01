import { useJsonResource } from './useJsonResource'
import type { RiskIntelGraphPayload, RiskIntelSummaryPayload } from '../types'

export function useRiskIntelData() {
  const summary = useJsonResource<RiskIntelSummaryPayload>('output/data/risk_intel_summary.json')
  const graph = useJsonResource<RiskIntelGraphPayload>('output/data/risk_intel_graph.json')

  return {
    summary: summary.data,
    graph: graph.data,
    loading: summary.loading,
    error: summary.error,
    graphError: graph.error,
  }
}
