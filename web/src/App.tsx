import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import './styles/global.css'

const Dashboard = lazy(() =>
  import('./pages/Dashboard').then((module) => ({ default: module.Dashboard })),
)
const TickerDetail = lazy(() =>
  import('./pages/TickerDetail').then((module) => ({ default: module.TickerDetail })),
)

const BASENAME = import.meta.env.BASE_URL.replace(/\/$/, '')

export default function App() {
  return (
    <BrowserRouter basename={BASENAME}>
      <Layout>
        <Suspense fallback={<p className="status">Loading...</p>}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/ticker/:ticker" element={<TickerDetail />} />
          </Routes>
        </Suspense>
      </Layout>
    </BrowserRouter>
  )
}
