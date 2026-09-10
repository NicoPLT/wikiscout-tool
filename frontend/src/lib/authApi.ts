import { api, setToken } from './api'

export interface MeResponse {
  email: string
}

export async function login(email: string, password: string): Promise<MeResponse> {
  const { data } = await api.post<{ access_token: string; email?: string }>('/api/auth/login', { email, password })
  setToken(data.access_token)
  // Keep compatibility while frontend and backend deploy independently.
  return data.email ? { email: data.email } : fetchMe(undefined, 30_000)
}

export async function fetchMe(signal?: AbortSignal, timeout = 120_000): Promise<MeResponse> {
  const { data } = await api.get<MeResponse>('/api/auth/me', { signal, timeout })
  return data
}
