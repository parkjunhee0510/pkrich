/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const uiCss = readFileSync(resolve(__dirname, 'parts', 'ui.css'), 'utf8')

function ruleBody(selector: string) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = uiCss.match(new RegExp(`${escapedSelector}\\s*\\{(?<body>[\\s\\S]*?)\\}`))
  return match?.groups?.body ?? ''
}

describe('news desk layout CSS', () => {
  it('keeps the Dashboard news desk as a structured card grid instead of raw document flow', () => {
    expect(ruleBody('.news-desk')).toMatch(/display\s*:\s*grid/)
    expect(uiCss).toMatch(/\.news-desk-first-grid\s*\{[\s\S]*?grid-template-columns/)
    expect(uiCss).toMatch(/\.news-desk-main-grid\s*\{[\s\S]*?grid-template-columns/)
    expect(uiCss).toMatch(/\.news-desk-situation-list,\s*\.news-desk-market-grid,\s*\.news-desk-impact-grid\s*\{[\s\S]*?grid-template-columns/)
    expect(uiCss).toMatch(/\.news-desk-headline-list,\s*\.news-desk-situation-list,\s*\.news-desk-feed-list,\s*\.news-desk-impact-list\s*\{[\s\S]*?list-style\s*:\s*none/)
    expect(ruleBody('.news-desk-headline-list')).toMatch(/counter-reset\s*:\s*news-desk-headline/)
    expect(ruleBody('.news-desk-more-button')).toMatch(/min-height\s*:\s*var\(--touch-target\)/)
  })
})
