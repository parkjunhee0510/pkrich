/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const baseCss = readFileSync(resolve(__dirname, 'parts/base.css'), 'utf8')
const componentsCss = readFileSync(resolve(__dirname, 'parts/components.css'), 'utf8')

function ruleBody(source: string, selector: string) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = source.match(new RegExp(`${escapedSelector}\\s*\\{(?<body>[\\s\\S]*?)\\}`))
  return match?.groups?.body ?? ''
}

describe('navigation layering CSS', () => {
  it('keeps the More navigation menu above page content on desktop and mobile', () => {
    expect(ruleBody(baseCss, '.header')).toMatch(/z-index\s*:\s*1000/)
    expect(ruleBody(baseCss, '.nav-more-open')).toMatch(/z-index\s*:\s*1001/)
    expect(ruleBody(baseCss, '.nav-more-menu')).toMatch(/position\s*:\s*fixed/)
    expect(ruleBody(baseCss, '.nav-more-menu')).toMatch(/z-index\s*:\s*var\(--z-popover\)/)
    expect(ruleBody(baseCss, '.nav-more-menu')).toMatch(/border-radius\s*:\s*0/)
    expect(ruleBody(baseCss, '.nav-more-menu')).toMatch(/max-height\s*:\s*calc\(100dvh - \(var\(--space-4\) \* 2\)\)/)
    expect(ruleBody(baseCss, '.nav-more-menu')).toMatch(/overflow-y\s*:\s*auto/)
    expect(ruleBody(baseCss, '.nav-more-menu')).toMatch(/overscroll-behavior\s*:\s*contain/)
    expect(ruleBody(baseCss, '.nav-more-menu')).not.toMatch(/radius-pill|cozy-pill-radius|999px/)
    expect(ruleBody(baseCss, '.nav-more-item')).toMatch(/display\s*:\s*flex/)
    expect(ruleBody(baseCss, '.nav-more-item')).toMatch(/min-height\s*:\s*var\(--touch-target\)/)
    expect(baseCss).toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*?\.nav-more-menu\s*\{[\s\S]*?position\s*:\s*fixed/)
    expect(baseCss).not.toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*?\.nav-more-menu\s*\{[\s\S]*?position\s*:\s*static/)
  })

  it('keeps the portfolio ticker picker dropdown above editor rows', () => {
    expect(ruleBody(componentsCss, '.portfolio-ticker-picker:focus-within')).toMatch(/z-index\s*:\s*var\(--z-popover\)/)
    expect(ruleBody(componentsCss, '.portfolio-ticker-picker-menu')).toMatch(/z-index\s*:\s*var\(--z-popover\)/)
    expect(ruleBody(componentsCss, '.portfolio-ticker-picker-menu')).toMatch(/border-radius\s*:\s*0/)
    expect(ruleBody(componentsCss, '.portfolio-ticker-picker-menu')).not.toMatch(/radius-pill|cozy-pill-radius|999px/)
  })
})
