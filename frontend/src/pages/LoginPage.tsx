import { useEffect, useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Logo } from '../components/Logo'
import { Button } from '../components/ui/Button'
import { useAuth } from '../hooks/useAuth'
import { api, requestErrorMessage } from '../lib/api'
import { LoadingStatus } from '../components/ui/LoadingStatus'

export function LoginPage() {
  const { login, isAuthenticated, isLoading, error: sessionError, retry } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    // Start waking the service while the user enters their credentials.
    const controller = new AbortController()
    void api.get('/api/health', { signal: controller.signal }).catch(() => {})
    return () => controller.abort()
  }, [])

  if (isAuthenticated && !isLoading) return <Navigate to="/" replace />
  if (isSubmitting) return <LoadingStatus fullScreen phase="access" message="Accesso a WikiScout in corso..." />

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (cause) {
      setError(requestErrorMessage(cause))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex h-dvh items-center justify-center bg-bg-primary px-4">
      <div className="w-full max-w-sm rounded-card border border-border-subtle bg-bg-surface p-6 sm:p-8">
        <div className="mb-6 flex justify-center">
          <Logo />
        </div>
        <h1 className="text-center text-xl text-text-primary">Accedi alla tua watchlist</h1>
        <p className="mt-1 text-center text-sm text-text-secondary">Area riservata scout</p>

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <div>
            <label htmlFor="email" className="label-caption mb-1.5 block">Email</label>
            <input
              id="email"
              autoComplete="username"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full rounded-md border border-border-subtle bg-bg-surface-hover px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="password" className="label-caption mb-1.5 block">Password</label>
            <input
              id="password"
              autoComplete="current-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded-md border border-border-subtle bg-bg-surface-hover px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none"
            />
          </div>

          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
          {sessionError && <div>
            <p role="alert" className="text-sm text-danger">{sessionError}</p>
            <Button type="button" variant="secondary" onClick={retry}>Riprova accesso salvato</Button>
          </div>}
          {isLoading && <LoadingStatus phase="access" message="Verifica dell'accesso salvato..." />}

          <Button type="submit" disabled={isSubmitting} className="mt-2 w-full">
            {isSubmitting ? 'Accesso in corso...' : 'Accedi'}
          </Button>
        </form>
      </div>
    </div>
  )
}
