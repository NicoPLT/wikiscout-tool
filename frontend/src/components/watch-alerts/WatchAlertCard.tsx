import { useNavigate } from 'react-router-dom'
import { Card } from '../ui/Card'
import { hexToRgba } from '../../lib/ratingScale'
import { formatDate } from '../../lib/format'
import { getTriggerConfig } from './triggerConfig'
import type { WatchAlert, WatchAlertPlayer } from '../../types/watchAlert'

interface WatchAlertCardProps {
  player: WatchAlertPlayer
  alerts: WatchAlert[]
  onDismiss: (alertId: number) => void
}

export function WatchAlertCard({ player, alerts, onDismiss }: WatchAlertCardProps) {
  const navigate = useNavigate()

  return (
    <Card>
      <div className="flex items-start gap-4">
        {player.photo_url ? (
          <img src={player.photo_url} alt="" className="h-12 w-12 shrink-0 rounded-full object-cover" />
        ) : (
          <div className="h-12 w-12 shrink-0 rounded-full bg-bg-surface-hover" />
        )}
        <div className="min-w-0 flex-1">
          <button
            onClick={() => navigate(`/players/${player.id}`)}
            className="text-left hover:underline"
          >
            <p className="truncate font-medium text-text-primary">{player.full_name}</p>
          </button>
          <p className="truncate text-xs text-text-muted">
            {player.current_team ?? 'N/D'} {player.league ? `· ${player.league}` : ''}
          </p>

          <div className="mt-3 flex flex-col gap-2">
            {alerts.map((alert) => {
              const config = getTriggerConfig(alert.trigger_type)
              return (
                <div
                  key={alert.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-bg-surface-hover px-3 py-2"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <span
                      className="flex shrink-0 items-center gap-1 rounded-sm px-2 py-1 text-xs font-medium"
                      style={{ backgroundColor: hexToRgba(config.color, 0.18), color: config.color }}
                    >
                      {config.icon}
                      {config.label}
                    </span>
                    <span className="truncate text-sm text-text-secondary">{alert.trigger_detail}</span>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="text-xs text-text-muted">{formatDate(alert.detected_at)}</span>
                    <button
                      onClick={() => onDismiss(alert.id)}
                      className="rounded-sm px-2 py-1 text-xs font-medium text-text-muted hover:bg-danger/10 hover:text-danger"
                    >
                      Scarta
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </Card>
  )
}
