import { DashboardSkeleton } from './Skeleton'

export function RouteSuspenseFallback({ hasResolvedRoute }: { hasResolvedRoute: boolean }) {
  if (!hasResolvedRoute) {
    return <DashboardSkeleton />
  }

  return (
    <div className="route-transition-fallback" role="status" aria-live="polite" aria-label="Loading page">
      <span className="route-transition-bar" aria-hidden="true" />
    </div>
  )
}
