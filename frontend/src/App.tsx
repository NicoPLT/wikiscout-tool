import { lazy, Suspense } from 'react'
import { Spinner } from './components/ui/Spinner'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './hooks/useAuth'
import { ProtectedRoute } from './components/ProtectedRoute'
import { LoginPage } from './pages/LoginPage'
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const PlayerDetailPage = lazy(() => import('./pages/PlayerDetailPage').then((m) => ({ default: m.PlayerDetailPage })))
const OneToWatchPage = lazy(() => import('./pages/OneToWatchPage').then((m) => ({ default: m.OneToWatchPage })))

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<div className="flex justify-center p-12"><Spinner /></div>}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/players/:playerId"
            element={
              <ProtectedRoute>
                <PlayerDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/one-to-watch"
            element={
              <ProtectedRoute>
                <OneToWatchPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
