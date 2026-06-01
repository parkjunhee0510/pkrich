import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'

import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Dashboard } from './Dashboard'

const originalFetch = globalThis.fetch

function publicFileFromUrl(input: RequestInfo | URL) {
  const rawUrl = typeof input === 'string'
    ? input
    : input instanceof URL
      ? input.toString()
      : input.url
  const pathname = rawUrl.startsWith('http')
    ? new URL(rawUrl).pathname
    : rawUrl.split('?')[0]
  return pathname.replace(/^\//, '')
}

describe('Dashboard real data rendering', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const relativePath = publicFileFromUrl(input)
      const filePath = resolve(process.cwd(), 'public', relativePath)

      try {
        const body = await readFile(filePath, 'utf8')
        return new Response(body, {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      } catch {
        return new Response(null, { status: 404 })
      }
    })
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('renders the Dashboard with generated output instead of a blank screen', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /부자 되고 싶어요/ })).toBeInTheDocument()
    })

    expect(screen.getByRole('region', { name: '오늘의 뉴스 데스크' })).toBeInTheDocument()
  })
})
