import { useEffect, useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: '워치리스트' },
  { to: '/prices', label: '시세' },
  { to: '/portfolio', label: '포트폴리오' },
  { to: '/signals', label: '시그널 통계' },
  { to: '/sectors', label: '섹터 탐색' },
  { to: '/scenario', label: '시나리오' },
  { to: '/backtest', label: '백테스트' },
  { to: '/chat', label: '리서치 채팅' },
  { to: '/admin', label: 'Admin' },
  { to: '/calendar', label: '캘린더' },
  { to: '/api-status', label: 'API 상태' },
] as const

export function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [isNavOpen, setIsNavOpen] = useState(false)

  useEffect(() => { setIsNavOpen(false) }, [location.pathname])

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
  }, [isNavOpen])

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
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`nav-link${location.pathname === item.to || location.pathname.startsWith(`${item.to}/`) ? ' nav-active' : ''}`}
              onClick={() => setIsNavOpen(false)}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      <main className="main">{children}</main>
    </div>
  )
}
