import type { ICellRendererParams } from 'ag-grid-community'
import type { PlayerRow } from '../../types/player'
import { formatCurrency, formatPct, formatRelativeUpdate } from '../../lib/format'

export function PlayerNameCellRenderer(params: ICellRendererParams<PlayerRow>) {
  const player = params.data
  if (!player) return null
  return (
    <div className="flex h-full items-center gap-2.5">
      {player.photo_url ? (
        <img src={player.photo_url} alt="" className="h-7 w-7 shrink-0 rounded-full object-cover" />
      ) : (
        <div className="h-7 w-7 shrink-0 rounded-full bg-bg-surface-hover" />
      )}
      <span className="truncate font-medium text-text-primary">{player.full_name}</span>
    </div>
  )
}

export function MarketValueCellRenderer(params: ICellRendererParams<PlayerRow>) {
  const player = params.data
  if (!player) return null
  const change = player.market_value_change_pct

  return (
    <div className="flex h-full items-center gap-2">
      <span className="text-text-primary">{formatCurrency(player.market_value_eur)}</span>
      {change !== null && change !== undefined && change !== 0 && (
        <span
          className={`rounded-sm px-1.5 py-0.5 text-xs font-medium ${
            change > 0 ? 'bg-accent-primary/15 text-accent-primary' : 'bg-danger/15 text-danger'
          }`}
        >
          {formatPct(change)}
        </span>
      )}
    </div>
  )
}

export function AppearancesCellRenderer(params: ICellRendererParams<PlayerRow>) {
  const player = params.data
  if (!player) return null
  return (
    <span className="text-text-primary">
      {player.appearances_season} <span className="text-text-muted">/ {player.minutes_season}&apos;</span>
    </span>
  )
}

export function RatingCellRenderer(params: ICellRendererParams<PlayerRow>) {
  const rating = params.data?.rating_avg
  if (rating === null || rating === undefined) {
    return <span className="text-text-muted">N/D</span>
  }
  return <span className="text-text-primary">{rating.toFixed(1)}</span>
}

export function XgXaCellRenderer(params: ICellRendererParams<PlayerRow>) {
  const player = params.data
  if (!player) return null
  if (!player.is_xg_covered) {
    return <span className="text-text-muted">N/D</span>
  }
  const xg = player.xg_season?.toFixed(1) ?? '0.0'
  const xa = player.xa_season?.toFixed(1) ?? '0.0'
  return (
    <span className="text-text-primary">
      {xg} <span className="text-text-muted">/ {xa}</span>
    </span>
  )
}

export function UpdatedAtCellRenderer(params: ICellRendererParams<PlayerRow>) {
  const { label, freshness } = formatRelativeUpdate(params.data?.last_synced_at)
  const toneClass =
    freshness === 'fresh' ? 'text-accent-primary' : freshness === 'stale' ? 'text-text-muted' : 'text-danger'
  return <span className={`text-xs font-medium ${toneClass}`}>{label}</span>
}
