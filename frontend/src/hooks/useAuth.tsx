import { createContext, useCallback, useContext, useEffect, useRef, useState, type PropsWithChildren } from 'react'
import { fetchMe, login as loginRequest } from '../lib/authApi'
import { clearToken, getToken, requestErrorMessage } from '../lib/api'

interface AuthState {
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  email: string | null
  retry: () => void
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | undefined>(undefined)

export function AuthProvider({ children }: PropsWithChildren) {
  const [email, setEmail] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const restoreController = useRef<AbortController | null>(null)

  const retry = useCallback(() => {
    restoreController.current?.abort()
    const controller = new AbortController()
    restoreController.current = controller
    setError(null)
    const token = getToken()
    if (!token) {
      setEmail(null)
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    fetchMe(controller.signal)
      .then((me) => {
        if (!controller.signal.aborted && getToken() === token) setEmail(me.email)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        // Only rejected credentials clear the token in the interceptor.
        if (!getToken()) setEmail(null)
        else if (getToken() === token) setError(requestErrorMessage(cause))
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false)
      })
  }, [])

  useEffect(() => {
    retry()
    return () => restoreController.current?.abort()
  }, [retry])

  async function login(emailInput: string, password: string) {
    restoreController.current?.abort()
    setIsLoading(false)
    setError(null)
    const me = await loginRequest(emailInput, password)
    setEmail(me.email)
  }

  function logout() {
    restoreController.current?.abort()
    clearToken()
    setEmail(null)
    setError(null)
    setIsLoading(false)
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!email, isLoading, error, email, retry, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve essere usato dentro AuthProvider')
  return ctx
}
