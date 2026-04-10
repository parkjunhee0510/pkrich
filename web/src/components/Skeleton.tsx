import type { CSSProperties } from 'react'

function Skeleton({ width = '100%', height = '1rem', style }: { width?: string; height?: string; style?: CSSProperties }) {
  return <div className="skeleton" style={{ width, height, ...style }} />
}

export function DashboardSkeleton() {
  return (
    <div className="dashboard" style={{ animation: 'fadeInPage 0.35s ease' }}>
      <Skeleton width="35%" height="1.8rem" />
      <div style={{ marginTop: '1.25rem' }} />
      <Skeleton width="100%" height="3.5rem" style={{ borderRadius: '12px' }} />
      <div style={{ marginTop: '1.25rem' }} />
      <div className="skeleton-row">
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} height="180px" />
        ))}
      </div>
      <div style={{ marginTop: '1rem' }} />
      <div className="skeleton-row">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} height="120px" />
        ))}
      </div>
      <div style={{ marginTop: '1.25rem' }} />
      {[1, 2, 3].map((i) => (
        <Skeleton key={i} height="160px" style={{ marginBottom: '0.85rem' }} />
      ))}
    </div>
  )
}

export function TickerDetailSkeleton() {
  return (
    <div className="ticker-detail" style={{ animation: 'fadeInPage 0.35s ease' }}>
      <Skeleton width="80px" height="1rem" />
      <div style={{ marginTop: '1rem' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          <Skeleton width="55%" height="2rem" />
          <div style={{ marginTop: '0.5rem' }} />
          <Skeleton width="25%" height="0.9rem" />
        </div>
        <Skeleton width="120px" height="2rem" />
      </div>
      <div style={{ marginTop: '1.5rem' }} />
      <Skeleton width="100%" height="200px" />
      <div style={{ marginTop: '1.25rem' }} />
      <div className="skeleton-row">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} height="140px" />
        ))}
      </div>
      <div style={{ marginTop: '1.25rem' }} />
      <Skeleton width="100%" height="280px" />
      <div style={{ marginTop: '1rem' }} />
      <Skeleton width="100%" height="160px" />
    </div>
  )
}

export function TablePageSkeleton({ title }: { title: string }) {
  return (
    <div style={{ maxWidth: 1100, animation: 'fadeInPage 0.35s ease' }} aria-label={`${title} loading`}>
      <Skeleton width="30%" height="1.6rem" />
      <div style={{ marginTop: '1.25rem' }} />
      <div className="skeleton-row">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} height="100px" />
        ))}
      </div>
      <div style={{ marginTop: '1.25rem' }} />
      <Skeleton width="100%" height="40px" />
      {[1, 2, 3, 4, 5].map((i) => (
        <Skeleton key={i} width="100%" height="48px" style={{ marginTop: '0.35rem' }} />
      ))}
    </div>
  )
}
