import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RouteSuspenseFallback } from './RouteSuspenseFallback'

describe('RouteSuspenseFallback', () => {
  it('uses the full dashboard skeleton only before the first route is ready', () => {
    const { container } = render(<RouteSuspenseFallback hasResolvedRoute={false} />)

    expect(container.querySelector('.dashboard')).not.toBeNull()
    expect(container.querySelector('.route-transition-fallback')).toBeNull()
  })

  it('uses a lightweight transition indicator after the first route is ready', () => {
    const { container } = render(<RouteSuspenseFallback hasResolvedRoute />)

    expect(container.querySelector('.dashboard')).toBeNull()
    expect(container.querySelector('.skeleton-row-dashboard')).toBeNull()
    expect(container.querySelector('.table-page-skeleton')).toBeNull()
    expect(container.querySelector('.route-transition-fallback')).not.toBeNull()
    expect(screen.getByRole('status', { name: 'Loading page' })).toBeInTheDocument()
  })
})
