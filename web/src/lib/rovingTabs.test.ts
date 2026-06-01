import { describe, expect, it } from 'vitest'
import { getRovingTabIndex } from './rovingTabs'

describe('getRovingTabIndex', () => {
  it('moves to the next tab with ArrowRight and wraps at the end', () => {
    expect(getRovingTabIndex('ArrowRight', 1, 3)).toBe(2)
    expect(getRovingTabIndex('ArrowRight', 2, 3)).toBe(0)
  })

  it('moves to the previous tab with ArrowLeft and wraps at the start', () => {
    expect(getRovingTabIndex('ArrowLeft', 1, 3)).toBe(0)
    expect(getRovingTabIndex('ArrowLeft', 0, 3)).toBe(2)
  })

  it('supports vertical arrow keys for wrapped tab rows', () => {
    expect(getRovingTabIndex('ArrowDown', 0, 4)).toBe(1)
    expect(getRovingTabIndex('ArrowUp', 0, 4)).toBe(3)
  })

  it('jumps to first and last tab with Home and End', () => {
    expect(getRovingTabIndex('Home', 2, 4)).toBe(0)
    expect(getRovingTabIndex('End', 1, 4)).toBe(3)
  })

  it('returns null for keys that should not be handled by tab roving', () => {
    expect(getRovingTabIndex('Enter', 1, 3)).toBeNull()
    expect(getRovingTabIndex('Tab', 1, 3)).toBeNull()
  })

  it('returns null when there are no tabs', () => {
    expect(getRovingTabIndex('ArrowRight', 0, 0)).toBeNull()
  })
})
