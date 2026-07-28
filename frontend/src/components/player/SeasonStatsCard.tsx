import type { ReactNode } from 'react'
import { Card } from '../ui/Card'
import { RatingBadge } from '../ui/RatingBadge'
import type { PlayerSeasonOption } from '../../types/player'

function TrophyIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path
        d="M8 21h8M12 17v4M7 4h10v4a5 5 0 01-10 0V4zM7 5H4a1 1 0 00-1 1v1a4 4 0 004 4M17 5h3a1 1 0 011 1v1a4 4 0 01-4 4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function CardIcon({ tone }: { tone: 'yellow' | 'red' }) {
  return (
    <span
      className={`inline-block h-4 w-3 rounded-[2px] ${tone === 'yellow' ? 'bg-[#eab308]' : 'bg-danger'}`}
      aria-hidden
    />
  )
}

function StatCell({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="metric-value text-text-primary">{children}</div>
      <p className="label-caption text-center">{label}</p>
    </div>
  )
}

interface SeasonStatsCardProps {
  competitionName: string | null
  seasonLabel: string | null
  seasonOptions: PlayerSeasonOption[]
  selectedSeasonId: number | null
  onSeasonChange: (seasonId: number) => void
  goals: number
  assists: number
  starts: number
  appearances: number
  minutesPlayed: number
  rating: number | null
  yellowCards: number
  redCards: number
  isXgCovered: boolean
  xg: number | null
  xa: number | null
}

export function SeasonStatsCard({
  competitionName,
  seasonLabel,
  seasonOptions,
  selectedSeasonId,
  onSeasonChange,
  goals,
  assists,
  starts,
  appearances,
  minutesPlayed,
  rating,
  yellowCards,
  redCards,
  isXgCovered,
  xg,
  xa,
}: SeasonStatsCardProps) {
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-bg-surface-hover text-accent-primary">
            <TrophyIcon />
          </span>
          <div>
            <p className="text-base font-medium text-text-primary">{competitionName ?? 'Campionato'}</p>
            {seasonLabel && <p className="text-xs text-text-muted">Stagione {seasonLabel}</p>}
          </div>
        </div>

        {seasonOptions.length > 0 && (
          <select
            value={selectedSeasonId ?? ''}
            onChange={(e) => onSeasonChange(Number(e.target.value))}
            className="rounded-sm border border-border-subtle bg-bg-surface-hover px-3 py-1.5 text-sm text-text-primary focus:border-accent-primary focus:outline-none"
          >
            {seasonOptions.map((o) => (
              <option key={o.season_id} value={o.season_id}>
                Stagione {o.season_label}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="mt-5 border-t border-border-subtle pt-5">
        <div className="grid grid-cols-2 gap-y-4 sm:grid-cols-4">
          <StatCell label="Goal">{goals}</StatCell>
          <StatCell label="Assist">{assists}</StatCell>
          <StatCell label="Iniziato">{starts}</StatCell>
          <StatCell label="Partite">{appearances}</StatCell>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-y-4 border-t border-border-subtle pt-4 sm:grid-cols-4">
          <StatCell label="Minuti giocati">{minutesPlayed}</StatCell>
          <StatCell label="Voto">
            <RatingBadge rating={rating} size="md" />
          </StatCell>
          <StatCell label="Ammonizioni">
            <span className="flex items-center justify-center gap-1.5">
              <CardIcon tone="yellow" />
              {yellowCards}
            </span>
          </StatCell>
          <StatCell label="Espulsioni">
            <span className="flex items-center justify-center gap-1.5">
              <CardIcon tone="red" />
              {redCards}
            </span>
          </StatCell>
        </div>
      </div>

      {isXgCovered && (
        <p className="mt-4 border-t border-border-subtle pt-3 text-xs text-text-muted">
          xG / xA stagione:{' '}
          <span className="text-text-primary">
            {xg?.toFixed(1) ?? '0.0'} / {xa?.toFixed(1) ?? '0.0'}
          </span>
        </p>
      )}
    </Card>
  )
}
