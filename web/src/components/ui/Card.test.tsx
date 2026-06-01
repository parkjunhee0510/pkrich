import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from './Card'
import { EmptyState } from './EmptyState'

describe('Card primitive', () => {
  it('renders square shadcn-style card sections with composed classes', () => {
    render(
      <Card as="article" className="custom-surface" aria-label="Research card">
        <CardHeader>
          <CardTitle>Title</CardTitle>
          <CardDescription>Description</CardDescription>
        </CardHeader>
        <CardContent>Body</CardContent>
        <CardFooter>Footer</CardFooter>
      </Card>,
    )

    const card = screen.getByRole('article', { name: 'Research card' })
    expect(card).toHaveClass('ui-card')
    expect(card).toHaveClass('custom-surface')
    expect(screen.getByText('Title')).toHaveClass('ui-card-title')
    expect(screen.getByText('Description')).toHaveClass('ui-card-description')
    expect(screen.getByText('Body')).toHaveClass('ui-card-content')
    expect(screen.getByText('Footer')).toHaveClass('ui-card-footer')
  })

  it('uses Card as the EmptyState surface without changing EmptyState props', () => {
    render(<EmptyState title="No signals" description="Try another filter." tone="warning" />)

    const status = screen.getByText('No signals').closest('section')
    expect(status).toHaveClass('ui-card')
    expect(status).toHaveClass('ui-empty-state')
    expect(status).toHaveClass('ui-empty-state-warning')
  })
})
