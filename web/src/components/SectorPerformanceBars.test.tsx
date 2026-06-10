import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { SectorPerformanceBars } from './SectorPerformanceBars'
import type { SectorsSector } from '../hooks/useSectorsData'

const SECTORS = [
  { id: 'tech', name: '기술', tickers: [] },
  { id: 'energy', name: '에너지', tickers: [] },
] as unknown as SectorsSector[]

function renderBars() {
  return render(
    <MemoryRouter>
      <SectorPerformanceBars sectors={SECTORS} />
    </MemoryRouter>,
  )
}

describe('SectorPerformanceBars accessibility', () => {
  it('exposes the selected window toggle via aria-pressed', () => {
    renderBars()

    expect(screen.getByRole('button', { name: '1M' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '3M' })).toHaveAttribute('aria-pressed', 'false')

    fireEvent.click(screen.getByRole('button', { name: '3M' }))

    expect(screen.getByRole('button', { name: '3M' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '1M' })).toHaveAttribute('aria-pressed', 'false')
  })
})
