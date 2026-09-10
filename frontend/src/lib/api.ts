import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE_URL,
  // Allow Render's cold start, but do not leave requests pending forever.
  timeout: 120_000,
})

const TOKEN_KEY = 'wikiscout_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // A late response from an old session must not log out a newer login.
    const token = getToken()
    if (error.response?.status === 401 && token &&
        error.config?.url !== '/api/auth/login' &&
        error.config?.headers?.Authorization === `Bearer ${token}`) {
      clearToken()
      if (error.config?.url !== '/api/auth/me' && window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

export function requestErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 401) return 'Email o password errati oppure sessione scaduta.'
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      return 'Il server sta impiegando troppo tempo a rispondere. Attendi qualche secondo e riprova.'
    }
    if (!error.response) return 'Connessione al server non riuscita. Controlla la connessione e riprova.'
    if (error.response.status >= 500) return 'Il servizio è temporaneamente non disponibile. Riprova tra qualche secondo.'
  }
  return 'Operazione non riuscita. Riprova.'
}
