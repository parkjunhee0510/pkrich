/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const sourceFiles = [
  'src/pages/Admin.tsx',
  'src/pages/Backtest.tsx',
  'src/pages/Chat.tsx',
  'src/pages/Portfolio.tsx',
  'src/pages/Scenario.tsx',
  'src/pages/Signals.tsx',
  'src/components/PerformanceMeasurementPanel.tsx',
  'src/components/PortfolioRiskPanel.tsx',
  'src/components/SignalQualityPanel.tsx',
]

const forbiddenInlineLayoutPatterns = [
  /\bstyle=\{\{[^}]*\bmargin(?:Top|Bottom|Left|Right)?\s*:/,
  /\bstyle=\{\{[^}]*\bpadding(?:Inline|Block|Top|Bottom|Left|Right)?\s*:/,
  /\bstyle=\{\{[^}]*\bdisplay\s*:/,
  /\bstyle=\{\{[^}]*\bgap\s*:/,
  /\bstyle=\{\{[^}]*\bfontSize\s*:/,
]

describe('inline layout styles', () => {
  it('keeps static spacing and typography in shared CSS classes', () => {
    const violations = sourceFiles.flatMap((file) => {
      const source = readFileSync(resolve(process.cwd(), file), 'utf8')
      return forbiddenInlineLayoutPatterns
        .filter((pattern) => pattern.test(source))
        .map((pattern) => `${file} matches ${pattern.source}`)
    })

    expect(violations).toEqual([])
  })
})
