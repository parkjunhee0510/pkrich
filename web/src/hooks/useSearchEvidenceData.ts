import { useJsonResource } from './useJsonResource'
import type { SearchEvidencePayload } from '../types'

export function useSearchEvidenceData() {
  const resource = useJsonResource<SearchEvidencePayload>('output/data/search_evidence.json')

  return {
    searchEvidence: resource.data,
    loading: resource.loading,
    error: resource.error,
  }
}
