import type { ReactNode } from 'react'
import { Card } from '../ui/Card'
import { RatingBadge } from '../ui/RatingBadge'
import type { CompetitionStint, PlayerSeasonOption } from '../../types/player'

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
  competitions: CompetitionStint[]
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
  competitions,
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

      {competitions.length > 1 && (
        <div className="mt-4 border-t border-border-subtle pt-4">
          <p className="label-caption mb-2">Dettaglio per competizione</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-subtle text-left text-text-muted">
                  <th className="pb-2 pr-4 font-medium">Squadra</th>
                  <th className="pb-2 pr-4 font-medium">Competizione</th>
                  <th className="pb-2 pr-4 font-medium">Partite</th>
                  <th className="pb-2 pr-4 font-medium">Goal</th>
                  <th className="pb-2 pr-4 font-medium">Assist</th>
                  <th className="pb-2 pr-4 font-medium">Minuti</th>
                </tr>
              </thead>
              <tbody>
                {competitions.map((c) => (
                  <tr key={`${c.club_id}-${c.competition_id}`} className="border-b border-border-subtle last:border-b-0">
                    <td className="py-2 pr-4 text-text-primary">{c.club_name ?? 'N/D'}</td>
                    <td className="py-2 pr-4 text-text-secondary">{c.competition_name ?? 'N/D'}</td>
                    <td className="py-2 pr-4 text-text-primary">{c.appearances}</td>
                    <td className="py-2 pr-4 text-text-primary">{c.goals}</td>
                    <td className="py-2 pr-4 text-text-primary">{c.assists}</td>
                    <td className="py-2 pr-4 text-text-primary">{c.minutes_played}&apos;</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

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
