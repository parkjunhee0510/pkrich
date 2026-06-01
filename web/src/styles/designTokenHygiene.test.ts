/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

function cssPart(file: string) {
  return readFileSync(resolve(__dirname, 'parts', file), 'utf8')
}

const tokensCss = cssPart('tokens.css')

function tokenValue(name: string) {
  const match = tokensCss.match(new RegExp(`${name}:\\s*([^;]+);`))
  if (!match) {
    throw new Error(`${name} token is missing`)
  }
  return match[1].trim()
}

describe('design token hygiene', () => {
  it('does not let pill radius tokens render as half-round surfaces', () => {
    expect(tokenValue('--radius-pill')).toBe('var(--radius-md)')
    expect(tokenValue('--cozy-pill-radius')).toBe('var(--radius-md)')

    const css = [
      cssPart('base.css'),
      cssPart('cozy.css'),
      cssPart('dashboard.css'),
      cssPart('components.css'),
      cssPart('admin.css'),
      cssPart('ui.css'),
    ].join('\n')

    expect(css).not.toMatch(/border-radius\s*:\s*999px/)
  })

  it('uses semantic tokens for repeated status colors outside token definitions', () => {
    const checks = [
      [
        'admin.css',
        /#26a69a|#ef5350|#1f8b81|#c23a37|rgba\(38,\s*166,\s*154|rgba\(239,\s*83,\s*80|rgba\(127,\s*127,\s*127/,
      ],
      [
        'cozy.css',
        /#7db991|#e0a870|#d98585|#2a7a4a|#8a5e16|#8a3e34|rgba\(63,\s*169,\s*107|rgba\(217,\s*154,\s*58|rgba\(194,\s*90,\s*78/,
      ],
      ['base.css', /#b85555|color:\s*#fff\s*!important/],
      ['dashboard.css', /#d98585|#b86464|color:\s*#fff\s*!important/],
      ['components.css', /#a8401a|#8a6820|#5a6878|#fff2c8|rgba\(168,\s*64,\s*26/],
      ['policy-impact.css', /var\(--[\w-]+,\s*#[^)]+\)/],
    ] as const

    const violations = checks
      .filter(([file, pattern]) => pattern.test(cssPart(file)))
      .map(([file]) => file)

    expect(violations).toEqual([])
  })

  it('overrides semantic soft foreground tokens in dark mode for contrast', () => {
    const darkBlock = tokensCss.match(/@media \(prefers-color-scheme: dark\) \{\s*:root \{([\s\S]*?)\n\s*\}\s*\}/)
    expect(darkBlock?.[1]).toBeTruthy()

    for (const token of [
      '--color-positive-soft-fg',
      '--color-negative-soft-fg',
      '--color-caution-soft-fg',
      '--color-info-soft-fg',
      '--color-accent-soft-fg',
    ]) {
      expect(darkBlock?.[1]).toContain(token)
    }
  })
})
