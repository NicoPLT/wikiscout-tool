import { api } from './api'
import type {
  MatchStatLine,
  PlayerDetail,
  PlayerRow,
  PlayerSearchResult,
  PlayerSeasonOption,
  PlayerTransfer,
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

export async function searchPlayers(query: string, signal?: AbortSignal): Promise<PlayerSearchResult[]> {
  const { data } = await api.get<PlayerSearchResult[]>('/api/players/search', { params: { q: query }, signal })
  return data
}

export async function addToWatchlist(playerId: number, notes?: string, tags?: string[]): Promise<PlayerDetail> {
  const { data } = await api.post<PlayerDetail>('/api/watchlist', { player_id: playerId, notes, tags })
  return data
}

export async function importPlayerFromTransfermarkt(candidate: PlayerSearchResult): Promise<PlayerDetail> {
  const { data } = await api.post<PlayerDetail>('/api/watchlist/import', {
    transfermarkt_id: candidate.transfermarkt_id,
    full_name: candidate.full_name,
    current_team: candidate.current_team,
    position: candidate.position,
    nationality: candidate.nationality,
    market_value_eur: candidate.market_value_eur,
    photo_url: candidate.photo_url,
  })
  return data
}

export async function fetchPlayerSeasons(playerId: number): Promise<PlayerSeasonOption[]> {
  const { data } = await api.get<PlayerSeasonOption[]>(`/api/players/${playerId}/seasons`)
  return data
}

export async function fetchPlayerTransfers(playerId: number): Promise<PlayerTransfer[]> {
  const { data } = await api.get<PlayerTransfer[]>(`/api/players/${playerId}/transfers`)
  return data
}

export async function linkSofascoreProfile(playerId: number, sofascoreUrlOrId: string): Promise<PlayerDetail> {
  const { data } = await api.post<PlayerDetail>(`/api/players/${playerId}/sofascore-link`, {
    sofascore_url_or_id: sofascoreUrlOrId,
  })
  return data
}

export async function updateWatchlistEntry(
  playerId: number,
  notes?: string,
  tags?: string[],
): Promise<PlayerDetail> {
  const { data } = await api.patch<PlayerDetail>(`/api/watchlist/${playerId}`, { notes, tags })
  return data
}

export async function removeFromWatchlist(playerId: number): Promise<void> {
  await api.delete(`/api/watchlist/${playerId}`)
}

export type { MatchStatLine }

export async function exportWatchlist(): Promise<void> {
  const { data } = await api.get('/api/watchlist/export', { responseType: 'blob' })
  const url = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = `wikiscout-${new Date().toISOString().slice(0, 10)}.json`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
