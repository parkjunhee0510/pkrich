import { Suspense, lazy, useCallback, useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { RouteSuspenseFallback } from './components/RouteSuspenseFallback'
import { routeModuleLoaders } from './routes/routePreload'

const Dashboard = lazy(routeModuleLoaders.dashboard)
const TickerDetail = lazy(routeModuleLoaders.tickerDetail)
const Portfolio = lazy(routeModuleLoaders.portfolio)
const PriceHistory = lazy(routeModuleLoaders.priceHistory)
const Signals = lazy(routeModuleLoaders.signals)
const Chat = lazy(routeModuleLoaders.chat)
const Scenario = lazy(routeModuleLoaders.scenario)
const Backtest = lazy(routeModuleLoaders.backtest)
const Admin = lazy(routeModuleLoaders.admin)
const Calendar = lazy(routeModuleLoaders.calendar)
const Sectors = lazy(routeModuleLoaders.sectors)
const SectorDetail = lazy(routeModuleLoaders.sectorDetail)
const ApiStatus = lazy(routeModuleLoaders.apiStatus)
const PolicyImpact = lazy(routeModuleLoaders.policyImpact)
const RiskIntel = lazy(routeModuleLoaders.riskIntel)
const NotFound = lazy(routeModuleLoaders.notFound)

const BASENAME = import.meta.env.BASE_URL.replace(/\/$/, '')

export default function App() {
  return (
    <BrowserRouter basename={BASENAME}>
      <Layout>
        <AppRoutes />
      </Layout>
    </BrowserRouter>
  )
}

function AppRoutes() {
  const location = useLocation()
  const [hasResolvedRoute, setHasResolvedRoute] = useState(false)
  const handleResolvedRoute = useCallback(() => {
    setHasResolvedRoute(true)
  }, [])

  return (
    <Suspense fallback={<RouteSuspenseFallback hasResolvedRoute={hasResolvedRoute} />}>
      <RouteResolvedMarker pathname={location.pathname} onResolvedRoute={handleResolvedRoute} />
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
        <Route path="/policy" element={<PolicyImpact />} />
        <Route path="/risk-intel" element={<RiskIntel />} />
        <Route path="/api-status" element={<ApiStatus />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}

function RouteResolvedMarker({
  pathname,
  onResolvedRoute,
}: {
  pathname: string
  onResolvedRoute: () => void
}) {
  useEffect(() => {
    onResolvedRoute()
  }, [onResolvedRoute, pathname])

  return null
}

