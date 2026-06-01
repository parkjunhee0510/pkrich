import { useJsonResource } from './useJsonResource'
import type { QualityReliabilityLoopPayload } from '../types'

export function useQualityReliabilityLoopData() {
  const resource = useJsonResource<QualityReliabilityLoopPayload>('output/data/quality_reliability_loop.json')

  return {
    qualityLoop: resource.data,
    loading: resource.loading,
    error: resource.error,
  }
}
