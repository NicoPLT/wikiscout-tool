export interface PlayerRow {
  id: number
  full_name: string
  photo_url: string | null
  current_team: string | null
  league: string | null
  position: string | null

  market_value_eur: number | null
  market_value_change_eur: number | null
  market_value_change_pct: number | null

  goals_last5: number
  assists_last5: number
  goals_season: number
  assists_season: number
  appearances_season: number
  minutes_season: number
  rating_avg: number | null

  is_xg_covered: boolean
  xg_season: number | null
  xa_season: number | null

  watchlist_notes: string | null
  watchlist_tags: string[] | null

  last_synced_at: string | null
}

export interface MatchStatLine {
  id: number
  match_date: string
  competition: string
  opponent: string | null
  is_home: boolean | null
  minutes_played: number
  goals: number
  assists: number
  rating: number | null
  xg: number | null
  xa: number | null
}

export interface MarketValuePoint {
  recorded_at: string
  value_eur: number
}

export interface PlayerDetail extends PlayerRow {
  date_of_birth: string | null
  nationality: string | null
  transfermarkt_id: string | null
  api_football_id: string | null
  sofascore_id: string | null

  stats_updated_at: string | null
  market_value_updated_at: string | null
  rating_updated_at: string | null

  recent_matches: MatchStatLine[]
  market_value_history: MarketValuePoint[]
}

export interface PlayerSearchResult {
  source: 'local' | 'api_football'
  id: number | null
  api_football_id: string | null
  full_name: string
  current_team: string | null
  league: string | null
  photo_url: string | null
  in_watchlist: boolean
}

export interface MarketValueTrendPoint {
  recorded_at: string
  total_value_eur: number
}

export interface RecentUpdateItem {
  player_id: number
  full_name: string
  photo_url: string | null
  kind: 'market_value' | 'rating' | 'stats'
  label: string
  change_pct: number | null
  at: string
}

export interface WatchlistSummary {
  players_count: number
  avg_rating: number | null
  total_market_value_eur: number
  market_value_trend: MarketValueTrendPoint[]
  recent_updates: RecentUpdateItem[]
}
