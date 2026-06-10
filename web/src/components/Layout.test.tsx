import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Layout } from './Layout'

vi.mock('../routes/routePreload', () => ({
  getRoutePathFromHref: vi.fn(() => null),
  preloadRoutePath: vi.fn(),
  warmRouteChunksInIdle: vi.fn(),
}))

const originalInnerHeight = window.innerHeight
const originalInnerWidth = window.innerWidth

describe('Layout navigation', () => {
  afterEach(() => {
    Object.defineProperty(window, 'innerHeight', {
      configurable: true,
      writable: true,
      value: originalInnerHeight,
    })
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      writable: true,
      value: originalInnerWidth,
    })
    vi.restoreAllMocks()
  })

  it('renders the More menu through a body portal so page content cannot cover it', () => {
    const { container } = render(
      <MemoryRouter>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter>,
    )

    const trigger = container.querySelector<HTMLButtonElement>('.nav-more-trigger')
    expect(trigger).not.toBeNull()

    fireEvent.click(trigger!)

    const menu = document.body.querySelector('#more-navigation-menu')
    expect(menu).not.toBeNull()
    expect(menu?.parentElement).toBe(document.body)
  })

  it.each(['Enter', ' '])('opens the More menu from the %s key', async (key) => {
    const { container } = render(
      <MemoryRouter>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter>,
    )

    const trigger = container.querySelector<HTMLButtonElement>('.nav-more-trigger')
    expect(trigger).not.toBeNull()

    fireEvent.keyDown(trigger!, { key })

    expect(await screen.findByRole('menu')).toBeInTheDocument()
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
  })

  it('clamps the More menu inside a short viewport and makes it scrollable', async () => {
    Object.defineProperty(window, 'innerHeight', {
      configurable: true,
      writable: true,
      value: 220,
    })
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      writable: true,
      value: 360,
    })

    const { container } = render(
      <MemoryRouter>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter>,
    )

    const trigger = container.querySelector<HTMLButtonElement>('.nav-more-trigger')
    expect(trigger).not.toBeNull()
    vi.spyOn(trigger!, 'getBoundingClientRect').mockReturnValue({
      bottom: 210,
      height: 36,
      left: 260,
      right: 344,
      top: 174,
      width: 84,
      x: 260,
      y: 174,
      toJSON: () => ({}),
    })

    fireEvent.click(trigger!)

    const menu = await screen.findByRole('menu')
    await waitFor(() => {
      expect(menu).toHaveStyle({ top: '12px', maxHeight: '196px' })
    })
  })

  it('marks the active primary nav link with aria-current="page"', () => {
    render(
      <MemoryRouter initialEntries={['/prices']}>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: '시세' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: '워치리스트' })).not.toHaveAttribute('aria-current')
  })

  it('marks the active More menu item with aria-current="page"', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/backtest']}>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter>,
    )

    fireEvent.click(container.querySelector<HTMLButtonElement>('.nav-more-trigger')!)
    const menu = await screen.findByRole('menu')

    expect(within(menu).getByRole('menuitem', { name: '백테스트' })).toHaveAttribute('aria-current', 'page')
    expect(within(menu).getByRole('menuitem', { name: '캘린더' })).not.toHaveAttribute('aria-current')
  })

  it('supports keyboard navigation inside the More menu', async () => {
    const { container } = render(
      <MemoryRouter>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter>,
    )

    const trigger = container.querySelector<HTMLButtonElement>('.nav-more-trigger')
    expect(trigger).not.toBeNull()

    fireEvent.keyDown(trigger!, { key: 'ArrowDown' })

    const menu = await screen.findByRole('menu')
    const items = within(menu).getAllByRole('menuitem')
    expect(items[0]).toHaveClass('nav-more-item')
    expect(items.length).toBeGreaterThan(1)

    await waitFor(() => expect(items[0]).toHaveFocus())

    fireEvent.keyDown(menu, { key: 'ArrowDown' })
    expect(items[1]).toHaveFocus()

    fireEvent.keyDown(menu, { key: 'End' })
    expect(items[items.length - 1]).toHaveFocus()

    fireEvent.keyDown(menu, { key: 'Home' })
    expect(items[0]).toHaveFocus()

    fireEvent.keyDown(menu, { key: 'ArrowUp' })
    expect(items[items.length - 1]).toHaveFocus()

    fireEvent.keyDown(menu, { key: 'Escape' })
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })
})
