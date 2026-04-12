import { useEffect, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: '워치리스트' },
  { to: '/portfolio', label: '포트폴리오' },
  { to: '/signals', label: '시그널 통계' },
  { to: '/scenario', label: '시나리오' },
  { to: '/backtest', label: '백테스트' },
  { to: '/chat', label: '리서치 챗' },
  { to: '/admin', label: 'Admin' },
  { to: '/calendar', label: '캘린더' },
] as const

export function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()

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
  }, [])

  return (
    <div className="layout">
      <header className="header">
        <Link to="/" className="header-title">
          Stock Research
        </Link>
        <nav className="header-nav">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`nav-link${location.pathname === item.to || location.pathname.startsWith(`${item.to}/`) ? ' nav-active' : ''}`}
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
