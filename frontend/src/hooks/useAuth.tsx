import { createContext, useContext, useEffect, useState, type PropsWithChildren } from 'react'
import { fetchMe, login as loginRequest } from '../lib/authApi'
import { clearToken, getToken } from '../lib/api'

interface AuthState {
  isAuthenticated: boolean
  isLoading: boolean
  email: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | undefined>(undefined)

export function AuthProvider({ children }: PropsWithChildren) {
  const [email, setEmail] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const token = getToken()
    if (!token) {
      setIsLoading(false)
      return
    }
    fetchMe()
      .then((me) => setEmail(me.email))
      .catch(() => clearToken())
      .finally(() => setIsLoading(false))
  }, [])

  async function login(emailInput: string, password: string) {
    await loginRequest(emailInput, password)
    const me = await fetchMe()
    setEmail(me.email)
  }

  function logout() {
    clearToken()
    setEmail(null)
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!email, isLoading, email, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve essere usato dentro AuthProvider')
  return ctx
}
