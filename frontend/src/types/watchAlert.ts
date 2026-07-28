export type WatchAlertTriggerType =
  | 'rating_streak'
  | 'goal_streak'
  | 'assist_streak'
  | 'recent_transfer'
  | 'market_value_spike'

export interface WatchAlertPlayer {
  id: number
  full_name: string
  photo_url: string | null
  current_team: string | null
  league: string | null
}

export interface WatchAlert {
  id: number
  player_id: number
  player: WatchAlertPlayer
  // null = segnalazione manuale (vedi is_manual).
  trigger_type: WatchAlertTriggerType | null
  trigger_detail: string
  detected_at: string
  is_dismissed: boolean
  is_manual: boolean
  is_seen: boolean
}
