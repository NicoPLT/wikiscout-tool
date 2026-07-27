import { api } from './api'
import type {
  MatchStatLine,
  PlayerDetail,
  PlayerRow,
  PlayerSearchResult,
  WatchlistSummary,
} from '../types/player'

export async function fetchWatchlist(): Promise<PlayerRow[]> {
  const { data } = await api.get<PlayerRow[]>('/api/watchlist')
  return data
}

export async function fetchWatchlistSummary(): Promise<WatchlistSummary> {
  const { data } = await api.get<WatchlistSummary>('/api/watchlist/summary')
  return data
}

export async function fetchPlayerDetail(playerId: number): Promise<PlayerDetail> {
  const { data } = await api.get<PlayerDetail>(`/api/players/${playerId}`)
  return data
}

export async function searchPlayers(query: string): Promise<PlayerSearchResult[]> {
  const { data } = await api.get<PlayerSearchResult[]>('/api/players/search', { params: { q: query } })
  return data
}

export async function addToWatchlist(playerId: number, notes?: string, tags?: string[]): Promise<PlayerRow> {
  const { data } = await api.post<PlayerRow>('/api/watchlist', { player_id: playerId, notes, tags })
  return data
}

export async function updateWatchlistEntry(
  playerId: number,
  notes?: string,
  tags?: string[],
): Promise<PlayerRow> {
  const { data } = await api.patch<PlayerRow>(`/api/watchlist/${playerId}`, { notes, tags })
  return data
}

export async function removeFromWatchlist(playerId: number): Promise<void> {
  await api.delete(`/api/watchlist/${playerId}`)
}

export type { MatchStatLine }
