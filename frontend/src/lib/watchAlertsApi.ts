import { api } from './api'
import type { WatchAlert } from '../types/watchAlert'

export async function fetchWatchAlerts(): Promise<WatchAlert[]> {
  const { data } = await api.get<WatchAlert[]>('/api/watch-alerts')
  return data
}

export async function dismissWatchAlert(alertId: number): Promise<void> {
  await api.post(`/api/watch-alerts/${alertId}/dismiss`)
}

export async function createManualWatchAlert(playerId: number, note: string): Promise<WatchAlert> {
  const { data } = await api.post<WatchAlert>('/api/watch-alerts', { player_id: playerId, note })
  return data
}
