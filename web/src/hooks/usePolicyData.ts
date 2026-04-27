import type { PolicyImpactReport } from '../types'
import { useJsonResource } from './useJsonResource'

/**
 * Fetches the daily policy/regulation impact report.
 *
 * Backend: src/output/policy_json.py writes `output/data/policy_impact.json`
 * which is synced to `web/public/data/` by the existing pipeline export step.
 *
 * The pipeline degrades gracefully — if the policy stage failed or no events
 * were extracted, the file may be missing. Consumers should treat
 * `error !== null` as "no policy data today" and render an empty state.
 */
export function usePolicyData() {
  return useJsonResource<PolicyImpactReport>('data/policy_impact.json')
}
