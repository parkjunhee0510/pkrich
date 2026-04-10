import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: '워치리스트' },
  { to: '/portfolio', label: '포트폴리오' },
  { to: '/signals', label: '시그널 통계' },
  { to: '/calendar', label: '캘린더' },
] as const

export function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()

  return (
    <div className="layout">
      <header className="header">
        <Link to="/" className="header-title">
          Stock Research
        </Link>
        <nav className="header-nav">
          {NAV_ITEMS.map((item) => (
            <Link key={item.to} to={item.to} className={`nav-link${location.pathname === item.to ? ' nav-active' : ''}`}>
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      <main className="main">{children}</main>
    </div>
  )
}
