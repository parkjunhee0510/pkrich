import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'
import { Link, useLocation } from 'react-router-dom'
import { getRoutePathFromHref, preloadRoutePath, warmRouteChunksInIdle } from '../routes/routePreload'

const PRIMARY_NAV = [
  { to: '/', label: '워치리스트' },
  { to: '/prices', label: '시세' },
  { to: '/portfolio', label: '포트폴리오' },
  { to: '/signals', label: '시그널 통계' },
] as const

const MORE_NAV = [
  { to: '/policy', label: '정책·규제' },
  { to: '/risk-intel', label: '리스크 인텔' },
  { to: '/sectors', label: '섹터 탐색' },
  { to: '/calendar', label: '캘린더' },
  { to: '/scenario', label: '시나리오' },
  { to: '/backtest', label: '백테스트' },
  { to: '/chat', label: '리서치 채팅' },
  { to: '/api-status', label: 'API 상태' },
  { to: '/admin', label: 'Admin' },
] as const

const BASENAME = import.meta.env.BASE_URL.replace(/\/$/, '') || '/'

function isRouteActive(pathname: string, to: string) {
  if (to === '/') return pathname === '/'
  return pathname === to || pathname.startsWith(`${to}/`)
}

function formatNavDate(date: Date) {
  const weekdays = ['SUNDAY','MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY']
  const months = ['JANUARY','FEBRUARY','MARCH','APRIL','MAY','JUNE','JULY','AUGUST','SEPTEMBER','OCTOBER','NOVEMBER','DECEMBER']
  return `${weekdays[date.getDay()]} · ${months[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`
}

export function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [isNavOpen, setIsNavOpen] = useState(false)
  const [isMoreOpen, setIsMoreOpen] = useState(false)
  const [todayLabel, setTodayLabel] = useState('')
  const [moreMenuStyle, setMoreMenuStyle] = useState<CSSProperties>({})
  const moreRef = useRef<HTMLDivElement | null>(null)
  const moreTriggerRef = useRef<HTMLButtonElement | null>(null)
  const moreMenuRef = useRef<HTMLDivElement | null>(null)
  const previousPathnameRef = useRef(location.pathname)

  const isMoreActive = MORE_NAV.some((item) => isRouteActive(location.pathname, item.to))

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setTodayLabel(formatNavDate(new Date()))
    }, 0)
    return () => window.clearTimeout(timeoutId)
  }, [])

  useEffect(() => {
    warmRouteChunksInIdle(location.pathname)
  }, [location.pathname])

  useRouteIntentPrefetch()

  useEffect(() => {
    if (previousPathnameRef.current === location.pathname) return
    previousPathnameRef.current = location.pathname

    queueMicrotask(() => {
      setIsNavOpen(false)
      setIsMoreOpen(false)
    })
  }, [location.pathname])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const isTypingTarget = target instanceof HTMLInputElement
        || target instanceof HTMLTextAreaElement
        || target instanceof HTMLSelectElement
        || target?.isContentEditable

      if (event.key === '/' && !isTypingTarget) {
        event.preventDefault()
        const searchInput = document.querySelector<HTMLInputElement>('.dashboard-search')
        searchInput?.focus()
        searchInput?.select()
        return
      }

      if (event.key === 'Escape') {
        if (isMoreOpen) {
          setIsMoreOpen(false)
          return
        }
        if (isNavOpen) {
          setIsNavOpen(false)
          return
        }
        const activeElement = document.activeElement as HTMLElement | null
        activeElement?.blur()
        return
      }

      if ((event.key === 'r' || event.key === 'R') && !isTypingTarget) {
        event.preventDefault()
        window.location.reload()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isNavOpen, isMoreOpen])

  useEffect(() => {
    if (!isMoreOpen) return
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node
      if (moreRef.current?.contains(target) || moreMenuRef.current?.contains(target)) {
        return
      }
      setIsMoreOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isMoreOpen])

  useLayoutEffect(() => {
    if (!isMoreOpen) return

    const updateMenuPosition = () => {
      const trigger = moreTriggerRef.current
      if (!trigger) return

      const rect = trigger.getBoundingClientRect()
      const viewportPadding = 12
      const maxWidth = Math.max(180, window.innerWidth - viewportPadding * 2)
      const menuWidth = Math.min(240, maxWidth)
      const maxMenuHeight = Math.max(160, window.innerHeight - viewportPadding * 2)
      const menuScrollHeight = moreMenuRef.current?.scrollHeight ?? 0
      const menuHeight = Math.min(menuScrollHeight > 0 ? menuScrollHeight : maxMenuHeight, maxMenuHeight)
      const left = Math.min(
        Math.max(viewportPadding, rect.right - menuWidth),
        Math.max(viewportPadding, window.innerWidth - menuWidth - viewportPadding),
      )
      const top = Math.min(
        Math.max(viewportPadding, rect.bottom + 6),
        Math.max(viewportPadding, window.innerHeight - menuHeight - viewportPadding),
      )

      setMoreMenuStyle({
        top,
        left,
        width: menuWidth,
        maxHeight: maxMenuHeight,
      })
    }

    updateMenuPosition()
    window.addEventListener('resize', updateMenuPosition)
    window.addEventListener('scroll', updateMenuPosition, true)
    return () => {
      window.removeEventListener('resize', updateMenuPosition)
      window.removeEventListener('scroll', updateMenuPosition, true)
    }
  }, [isMoreOpen])

  const getMoreMenuItems = () => (
    Array.from(moreMenuRef.current?.querySelectorAll<HTMLAnchorElement>('[role="menuitem"]') ?? [])
  )

  const focusMoreMenuItem = (itemIndex: number) => {
    const items = getMoreMenuItems()
    if (items.length === 0) return

    const index = ((itemIndex % items.length) + items.length) % items.length
    items[index]?.focus()
  }

  const openMoreMenuAndFocus = (itemIndex: number) => {
    setIsMoreOpen(true)
    window.setTimeout(() => focusMoreMenuItem(itemIndex), 0)
  }

  const handleMoreTriggerKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      openMoreMenuAndFocus(0)
      return
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault()
      openMoreMenuAndFocus(MORE_NAV.length - 1)
    }
  }

  const handleMoreMenuKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const items = getMoreMenuItems()
    if (items.length === 0) return

    const currentIndex = items.indexOf(document.activeElement as HTMLAnchorElement)

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      focusMoreMenuItem(currentIndex < 0 ? 0 : currentIndex + 1)
      return
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault()
      focusMoreMenuItem(currentIndex < 0 ? items.length - 1 : currentIndex - 1)
      return
    }

    if (event.key === 'Home') {
      event.preventDefault()
      focusMoreMenuItem(0)
      return
    }

    if (event.key === 'End') {
      event.preventDefault()
      focusMoreMenuItem(items.length - 1)
      return
    }

    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      setIsMoreOpen(false)
      moreTriggerRef.current?.focus()
    }
  }

  const moreMenu = isMoreOpen ? (
    <div
      id="more-navigation-menu"
      ref={moreMenuRef}
      className="nav-more-menu"
      role="menu"
      aria-label="추가 탐색"
      style={moreMenuStyle}
      onKeyDown={handleMoreMenuKeyDown}
    >
      {MORE_NAV.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          role="menuitem"
          aria-current={isRouteActive(location.pathname, item.to) ? 'page' : undefined}
          className={`nav-more-item${isRouteActive(location.pathname, item.to) ? ' nav-active' : ''}`}
          onClick={() => {
            setIsMoreOpen(false)
            setIsNavOpen(false)
          }}
        >
          {item.label}
        </Link>
      ))}
    </div>
  ) : null

  return (
    <div className="layout">
      <header className="header">
        <Link to="/" className="header-title">
          준희의 포트폴리오
        </Link>
        <button
          type="button"
          className={`header-hamburger${isNavOpen ? ' is-open' : ''}`}
          aria-label={isNavOpen ? '메뉴 닫기' : '메뉴 열기'}
          aria-expanded={isNavOpen}
          aria-controls="primary-navigation"
          onClick={() => setIsNavOpen((v) => !v)}
        >
          <span className="hamburger-line" aria-hidden="true" />
          <span className="hamburger-line" aria-hidden="true" />
          <span className="hamburger-line" aria-hidden="true" />
        </button>
        <nav id="primary-navigation" className={`header-nav${isNavOpen ? ' nav-open' : ''}`} aria-label="주요 탐색">
          {PRIMARY_NAV.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              aria-current={isRouteActive(location.pathname, item.to) ? 'page' : undefined}
              className={`nav-link${isRouteActive(location.pathname, item.to) ? ' nav-active' : ''}`}
              onClick={() => setIsNavOpen(false)}
            >
              {item.label}
            </Link>
          ))}

          <div className={`nav-more${isMoreOpen ? ' nav-more-open' : ''}`} ref={moreRef}>
            <button
              type="button"
              ref={moreTriggerRef}
              className={`nav-link nav-more-trigger${isMoreActive ? ' nav-active' : ''}`}
              aria-label={isMoreOpen ? '추가 메뉴 닫기' : '추가 메뉴 열기'}
              aria-haspopup="menu"
              aria-expanded={isMoreOpen}
              aria-controls="more-navigation-menu"
              onClick={() => setIsMoreOpen((v) => !v)}
              onKeyDown={handleMoreTriggerKeyDown}
            >
              더보기
              <span className="nav-more-caret" aria-hidden="true">▾</span>
            </button>
          </div>
          {todayLabel ? <span className="cozy-nav-date" aria-hidden="true">{todayLabel}</span> : null}
        </nav>
      </header>
      <main className="main">{children}</main>
      {moreMenu ? createPortal(moreMenu, document.body) : null}
    </div>
  )
}

function useRouteIntentPrefetch() {
  useEffect(() => {
    const handleRouteIntent = (event: Event) => {
      const target = event.target
      if (!(target instanceof Element)) {
        return
      }

      const anchor = target.closest<HTMLAnchorElement>('a[href]')
      if (!anchor) {
        return
      }

      const routePath = getRoutePathFromHref(anchor.href, window.location.origin, BASENAME)
      if (!routePath) {
        return
      }

      void preloadRoutePath(routePath)
    }

    document.addEventListener('pointerover', handleRouteIntent, { passive: true })
    document.addEventListener('pointerdown', handleRouteIntent, { passive: true })
    document.addEventListener('touchstart', handleRouteIntent, { passive: true })
    document.addEventListener('focusin', handleRouteIntent)

    return () => {
      document.removeEventListener('pointerover', handleRouteIntent)
      document.removeEventListener('pointerdown', handleRouteIntent)
      document.removeEventListener('touchstart', handleRouteIntent)
      document.removeEventListener('focusin', handleRouteIntent)
    }
  }, [])
}
