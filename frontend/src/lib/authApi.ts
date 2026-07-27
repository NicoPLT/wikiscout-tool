import { api, setToken } from './api'

export interface MeResponse {
  email: string
}

export async function login(email: string, password: string): Promise<void> {
  const { data } = await api.post<{ access_token: string }>('/api/auth/login', { email, password })
  setToken(data.access_token)
}

export async function fetchMe(): Promise<MeResponse> {
  const { data } = await api.get<MeResponse>('/api/auth/me')
  return data
}
