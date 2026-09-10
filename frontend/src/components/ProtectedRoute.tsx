import type { PropsWithChildren } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { Button } from './ui/Button'
import { LoadingStatus } from './ui/LoadingStatus'

export function ProtectedRoute({ children }: PropsWithChildren) {
  const { isAuthenticated, isLoading, error, retry, logout } = useAuth()

  if (isLoading) {
    return <LoadingStatus fullScreen phase="access" message="Verifica dell'accesso in corso..." />
  }

  if (error) {
    return <div className="flex min-h-dvh items-center justify-center bg-bg-primary px-6">
      <div className="max-w-md space-y-4">
        <p role="alert" className="text-sm text-danger">{error}</p>
        <Button onClick={retry}>Riprova</Button>
        <Button variant="ghost" onClick={logout}>Torna al login</Button>
      </div>
    </div>
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
