import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DashboardSkeleton, InlineLoadingState, TablePageSkeleton, TickerDetailSkeleton } from './Skeleton'

const forbiddenLayoutStyles = /animation|border-radius|display|flex|margin|max-width|align-items|justify-content/

function collectInlineStyles(container: HTMLElement) {
  return [...container.querySelectorAll<HTMLElement>('[style]')].map(
    (element) => element.getAttribute('style') ?? '',
  )
}

describe('Skeleton layouts', () => {
  it('renders a compact first-load dashboard skeleton', () => {
    const { container } = render(<DashboardSkeleton />)

    expect(screen.getByRole('status', { name: '대시보드 데이터를 불러오는 중' })).toHaveAttribute('aria-busy', 'true')
    expect(container.querySelectorAll('.skeleton')).toHaveLength(7)
    expect(container.querySelectorAll('.skeleton-row-dashboard .skeleton')).toHaveLength(3)
    expect(container.querySelector('.skeleton-list')).toBeNull()
  })

  it('uses tokenized classes for skeleton layout instead of inline spacing or radius', () => {
    const { container, rerender } = render(<DashboardSkeleton />)

    expect(screen.getByRole('status')).toHaveClass('skeleton-frame')

    for (const style of collectInlineStyles(container)) {
      expect(style).not.toMatch(forbiddenLayoutStyles)
    }

    rerender(<TickerDetailSkeleton />)

    expect(screen.getByRole('status')).toHaveClass('skeleton-frame')

    for (const style of collectInlineStyles(container)) {
      expect(style).not.toMatch(forbiddenLayoutStyles)
    }

    rerender(<TablePageSkeleton title="Signals" />)

    expect(screen.getByRole('status')).toHaveClass('skeleton-frame')

    for (const style of collectInlineStyles(container)) {
      expect(style).not.toMatch(forbiddenLayoutStyles)
    }
  })

  it('uses an accessible inline loading state for nested chart and timeline fallbacks', () => {
    const { container } = render(<InlineLoadingState label="가격 차트를 불러오는 중" />)

    expect(screen.getByRole('status', { name: '가격 차트를 불러오는 중' })).toHaveAttribute('aria-busy', 'true')
    expect(container.querySelector('.inline-loading-state-mark')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByText('가격 차트를 불러오는 중')).toBeInTheDocument()

    for (const style of collectInlineStyles(container)) {
      expect(style).not.toMatch(forbiddenLayoutStyles)
    }
  })
})
