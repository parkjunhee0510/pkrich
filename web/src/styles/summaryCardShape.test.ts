/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const uiCss = readFileSync(resolve(__dirname, 'parts/ui.css'), 'utf8')

const rectangularSurfaceSelectors = [
  '.page-header',
  '.dashboard-header',
  '.header',
  '.nav-more-menu',
  '.error-state',
  '.error-state-detail',
  '.empty',
  '.inline-loading-state',
  '.inline-loading-state-mark',
  '.skeleton',
  '.skeleton-row',
  '.dashboard-controls',
  '.dashboard-quick-bar',
  '.news-desk',
  '.news-desk-headlines-card',
  '.news-desk-situation-card',
  '.news-desk-market-card',
  '.news-desk-feed-card',
  '.news-desk-impact-card',
  '.news-desk-alert',
  '.news-desk-market-move',
  '.news-desk-market-item',
  '.news-desk-situation-item',
  '.news-desk-feed-item',
  '.news-desk-impact-item',
  '.news-desk-more-button',
  '.filing-toolbar',
  '.filing-controls',
  '.price-chart-toolbar',
  '.watchlist-dnd-toolbar',
  '.market-regime-banner.cozy-premium-banner',
  '.ticker-detail-section-shell',
  '.ticker-detail-collapsible',
  '.ticker-header',
  '.ticker-price-group',
  '.chart-container',
  '.price-chart-wrapper',
  '.equity-curve-wrapper',
  '.price-history-chip',
  '.today-priority-score-block strong',
  '.action-change-risk-note',
]

const rectangularSurfacePatternSelectors = [
  ":where(div, section, article, li, a)[class*='-card']",
  ":where(div, section, article, li, a)[class*='-panel']",
  ":where(div, section, article, li, a)[class*='-surface']",
  ":where(div, section, article, li, a)[class*='-summary']",
  ":where(div, section, article, li, a)[class*='-empty']",
  ":where(div, section, article, li, a)[class*='-row']",
]

function readContentSurfaceShapeGuard() {
  const match = uiCss.match(
    /\/\* Content surface shape guard: square information DIVs\. \*\/\s*([\s\S]*?)\{\s*([\s\S]*?)\}/,
  )

  if (!match) {
    throw new Error('Content surface shape guard is missing')
  }

  return {
    selectors: match[1],
    body: match[2],
  }
}

function readContentSurfacePatternGuard() {
  const match = uiCss.match(
    /\/\* Content surface pattern guard: square future div-like surfaces\. \*\/\s*([\s\S]*?)\{\s*([\s\S]*?)\}/,
  )

  if (!match) {
    throw new Error('Content surface pattern guard is missing')
  }

  return {
    selectors: match[1],
    body: match[2],
  }
}

describe('summary card shape rules', () => {
  it('keeps dashboard information cards and rows rectangular', () => {
    const { selectors, body } = readContentSurfaceShapeGuard()

    for (const selector of rectangularSurfaceSelectors) {
      expect(selectors).toContain(selector)
    }

    expect(body).toMatch(/border-radius\s*:\s*0\s*!important/)
    expect(body).not.toMatch(/999px|radius-pill|cozy-pill-radius|cozy-card-radius|radius-card/)
  })

  it('keeps future div-like surface classes rectangular by pattern', () => {
    const { selectors, body } = readContentSurfacePatternGuard()

    for (const selector of rectangularSurfacePatternSelectors) {
      expect(selectors).toContain(selector)
    }

    expect(body).toMatch(/border-radius\s*:\s*0\s*!important/)
    expect(body).not.toMatch(/999px|radius-pill|cozy-pill-radius|cozy-card-radius|radius-card/)
  })
})
