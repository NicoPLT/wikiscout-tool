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

export async function searchPlayers(query: string): Promise<PlayerSearchResult[]> {
  const { data } = await api.get<PlayerSearchResult[]>('/api/players/search', { params: { q: query } })
  return data
}

export async function addToWatchlist(playerId: number, notes?: string, tags?: string[]): Promise<PlayerRow> {
  const { data } = await api.post<PlayerRow>('/api/watchlist', { player_id: playerId, notes, tags })
  return data
}

export async function importPlayerFromTransfermarkt(candidate: PlayerSearchResult): Promise<PlayerRow> {
  const { data } = await api.post<PlayerRow>('/api/watchlist/import', {
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

export async function linkSofascoreProfile(playerId: number, sofascoreUrlOrId: string): Promise<PlayerRow> {
  const { data } = await api.post<PlayerRow>(`/api/players/${playerId}/sofascore-link`, {
    sofascore_url_or_id: sofascoreUrlOrId,
  })
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
