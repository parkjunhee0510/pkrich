import type { ReactNode } from 'react'
import { cn } from '../lib/utils'

type SkeletonProps = {
  width?: string
  height?: string
  className?: string
}

function Skeleton({ width = '100%', height = '1rem', className }: SkeletonProps) {
  return <div className={cn('skeleton', className)} aria-hidden="true" style={{ width, height }} />
}

function SkeletonFrame({ className, label, children }: { className: string; label: string; children: ReactNode }) {
  return (
    <div className={cn('skeleton-frame', className)} role="status" aria-busy="true" aria-label={label}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  )
}

export function DashboardSkeleton() {
  return (
    <SkeletonFrame className="dashboard" label="대시보드 데이터를 불러오는 중">
      <div className="skeleton-stack skeleton-stack-lg">
        <Skeleton width="35%" height="1.8rem" />
        <Skeleton width="100%" height="3rem" />
        <div className="skeleton-row skeleton-row-cards skeleton-row-dashboard">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} height="96px" />
          ))}
        </div>
        <div className="skeleton-row skeleton-row-cards">
          {[1, 2].map((i) => (
            <Skeleton key={i} height="112px" />
          ))}
        </div>
      </div>
    </SkeletonFrame>
  )
}

export function TickerDetailSkeleton() {
  return (
    <SkeletonFrame className="ticker-detail" label="종목 상세 데이터를 불러오는 중">
      <div className="skeleton-stack skeleton-stack-lg">
        <Skeleton width="80px" height="1rem" />
        <div className="skeleton-header-row">
          <div className="skeleton-copy-block skeleton-stack skeleton-stack-sm">
            <Skeleton width="55%" height="2rem" />
            <Skeleton width="25%" height="0.9rem" />
          </div>
          <Skeleton width="120px" height="2rem" />
        </div>
        <Skeleton width="100%" height="200px" />
        <div className="skeleton-row skeleton-row-cards">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} height="140px" />
          ))}
        </div>
        <Skeleton width="100%" height="280px" />
        <Skeleton width="100%" height="160px" />
      </div>
    </SkeletonFrame>
  )
}

export function TablePageSkeleton({ title }: { title: string }) {
  return (
    <SkeletonFrame className="table-page-skeleton" label={`${title} 데이터를 불러오는 중`}>
      <div className="skeleton-page-shell skeleton-stack skeleton-stack-lg">
        <Skeleton width="30%" height="1.6rem" />
        <div className="skeleton-row skeleton-row-cards">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} height="100px" />
          ))}
        </div>
        <div className="skeleton-list">
          <Skeleton width="100%" height="40px" />
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} width="100%" height="48px" />
          ))}
        </div>
      </div>
    </SkeletonFrame>
  )
}

export function InlineLoadingState({ label, className }: { label: string; className?: string }) {
  return (
    <div className={cn('inline-loading-state', className)} role="status" aria-live="polite" aria-busy="true" aria-label={label}>
      <span className="inline-loading-state-mark" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}
