import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { DashboardSkeleton } from './components/Skeleton'
import './styles/global.css'

const Dashboard = lazy(() =>
  import('./pages/Dashboard').then((module) => ({ default: module.Dashboard })),
)
const TickerDetail = lazy(() =>
  import('./pages/TickerDetail').then((module) => ({ default: module.TickerDetail })),
)
const Portfolio = lazy(() =>
  import('./pages/Portfolio').then((module) => ({ default: module.Portfolio })),
)
const Signals = lazy(() =>
  import('./pages/Signals').then((module) => ({ default: module.Signals })),
)
const Calendar = lazy(() =>
  import('./pages/Calendar').then((module) => ({ default: module.Calendar })),
)
const NotFound = lazy(() =>
  import('./pages/NotFound').then((module) => ({ default: module.NotFound })),
)

const BASENAME = import.meta.env.BASE_URL.replace(/\/$/, '')

export default function App() {
  return (
    <BrowserRouter basename={BASENAME}>
      <Layout>
        <Suspense fallback={<DashboardSkeleton />}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/ticker/:ticker" element={<TickerDetail />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/signals" element={<Signals />} />
            <Route path="/calendar" element={<Calendar />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </Layout>
    </BrowserRouter>
  )
}

