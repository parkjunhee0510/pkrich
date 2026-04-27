import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { DashboardSkeleton } from './components/Skeleton'

const Dashboard = lazy(() =>
  import('./pages/Dashboard').then((module) => ({ default: module.Dashboard })),
)
const TickerDetail = lazy(() =>
  import('./pages/TickerDetail').then((module) => ({ default: module.TickerDetail })),
)
const Portfolio = lazy(() =>
  import('./pages/Portfolio').then((module) => ({ default: module.Portfolio })),
)
const PriceHistory = lazy(() =>
  import('./pages/PriceHistory').then((module) => ({ default: module.PriceHistory })),
)
const Signals = lazy(() =>
  import('./pages/Signals').then((module) => ({ default: module.Signals })),
)
const Chat = lazy(() =>
  import('./pages/Chat').then((module) => ({ default: module.Chat })),
)
const Scenario = lazy(() =>
  import('./pages/Scenario').then((module) => ({ default: module.Scenario })),
)
const Backtest = lazy(() =>
  import('./pages/Backtest').then((module) => ({ default: module.Backtest })),
)
const Admin = lazy(() =>
  import('./pages/Admin').then((module) => ({ default: module.Admin })),
)
const Calendar = lazy(() =>
  import('./pages/Calendar').then((module) => ({ default: module.Calendar })),
)
const Sectors = lazy(() =>
  import('./pages/Sectors').then((module) => ({ default: module.Sectors })),
)
const SectorDetail = lazy(() =>
  import('./pages/SectorDetail').then((module) => ({ default: module.SectorDetail })),
)
const ApiStatus = lazy(() =>
  import('./pages/ApiStatus').then((module) => ({ default: module.ApiStatus })),
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
            <Route path="/prices" element={<PriceHistory />} />
            <Route path="/signals" element={<Signals />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/scenario" element={<Scenario />} />
            <Route path="/backtest" element={<Backtest />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="/calendar" element={<Calendar />} />
            <Route path="/sectors" element={<Sectors />} />
            <Route path="/sectors/:sectorId" element={<SectorDetail />} />
            <Route path="/api-status" element={<ApiStatus />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </Layout>
    </BrowserRouter>
  )
}

