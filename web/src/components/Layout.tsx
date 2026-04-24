import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

const PRIMARY_NAV = [
  { to: '/', label: '워치리스트' },
  { to: '/prices', label: '시세' },
  { to: '/portfolio', label: '포트폴리오' },
  { to: '/signals', label: '시그널 통계' },
] as const

const MORE_NAV = [
  { to: '/sectors', label: '섹터 탐색' },
  { to: '/calendar', label: '캘린더' },
  { to: '/scenario', label: '시나리오' },
  { to: '/backtest', label: '백테스트' },
  { to: '/chat', label: '리서치 채팅' },
  { to: '/api-status', label: 'API 상태' },
  { to: '/admin', label: 'Admin' },
] as const

function isRouteActive(pathname: string, to: string) {
  if (to === '/') return pathname === '/'
  return pathname === to || pathname.startsWith(`${to}/`)
}

export function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [isNavOpen, setIsNavOpen] = useState(false)
  const [isMoreOpen, setIsMoreOpen] = useState(false)
  const moreRef = useRef<HTMLDivElement | null>(null)

  const isMoreActive = MORE_NAV.some((item) => isRouteActive(location.pathname, item.to))

  const today = new Date()
  const weekdays = ['SUNDAY','MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY']
  const months = ['JANUARY','FEBRUARY','MARCH','APRIL','MAY','JUNE','JULY','AUGUST','SEPTEMBER','OCTOBER','NOVEMBER','DECEMBER']
  const todayLabel = `${weekdays[today.getDay()]} · ${months[today.getMonth()]} ${today.getDate()}, ${today.getFullYear()}`

  useEffect(() => {
    setIsNavOpen(false)
    setIsMoreOpen(false)
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
      if (moreRef.current && !moreRef.current.contains(event.target as Node)) {
        setIsMoreOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isMoreOpen])

  return (
    <div className="layout">
      <header className="header">
        <Link to="/" className="header-title">
          준희의 포트폴리오
        </Link>
        <button
          className={`header-hamburger${isNavOpen ? ' is-open' : ''}`}
          aria-label={isNavOpen ? '메뉴 닫기' : '메뉴 열기'}
          aria-expanded={isNavOpen}
          onClick={() => setIsNavOpen((v) => !v)}
        >
          <span className="hamburger-line" />
          <span className="hamburger-line" />
          <span className="hamburger-line" />
        </button>
        <nav className={`header-nav${isNavOpen ? ' nav-open' : ''}`}>
          {PRIMARY_NAV.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`nav-link${isRouteActive(location.pathname, item.to) ? ' nav-active' : ''}`}
              onClick={() => setIsNavOpen(false)}
            >
              {item.label}
            </Link>
          ))}

          <div className={`nav-more${isMoreOpen ? ' nav-more-open' : ''}`} ref={moreRef}>
            <button
              type="button"
              className={`nav-link nav-more-trigger${isMoreActive ? ' nav-active' : ''}`}
              aria-haspopup="menu"
              aria-expanded={isMoreOpen}
              onClick={() => setIsMoreOpen((v) => !v)}
            >
              더보기
              <span className="nav-more-caret" aria-hidden="true">▾</span>
            </button>
            {isMoreOpen && (
              <div className="nav-more-menu" role="menu">
                {MORE_NAV.map((item) => (
                  <Link
                    key={item.to}
                    to={item.to}
                    role="menuitem"
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
            )}
          </div>
          <span className="cozy-nav-date" aria-hidden="true">{todayLabel}</span>
        </nav>
      </header>
      <main className="main">{children}</main>
    </div>
  )
}
