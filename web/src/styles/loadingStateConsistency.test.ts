/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const targetPageFiles = [
  'src/pages/Dashboard.tsx',
  'src/pages/PriceHistory.tsx',
  'src/pages/TickerDetail.tsx',
]

const rawLoadingFallbackPatterns = [
  /Loading chart\.\.\./,
  /Loading timeline\.\.\./,
  /fallback=\{<div className="status">/,
  /<TablePageSkeleton/,
  /className="table-page-skeleton"/,
]

describe('page loading state consistency', () => {
  it('uses the shared accessible inline loading state for nested page fallbacks', () => {
    const violations = targetPageFiles.flatMap((file) => {
      const source = readFileSync(resolve(process.cwd(), file), 'utf8')
      return rawLoadingFallbackPatterns
        .filter((pattern) => pattern.test(source))
        .map((pattern) => `${file} matches ${pattern.source}`)
    })

    expect(violations).toEqual([])
  })
})
