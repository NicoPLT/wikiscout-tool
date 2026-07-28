import { api } from './api'
import type { WatchAlert } from '../types/watchAlert'

export async function fetchWatchAlerts(): Promise<WatchAlert[]> {
  const { data } = await api.get<WatchAlert[]>('/api/watch-alerts')
  return data
}

export async function dismissWatchAlert(alertId: number): Promise<void> {
  await api.post(`/api/watch-alerts/${alertId}/dismiss`)
}
