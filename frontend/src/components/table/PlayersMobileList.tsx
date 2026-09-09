import { useNavigate } from 'react-router-dom'
import type { PlayerRow, Tag } from '../../types/player'
import { Card } from '../ui/Card'
import { RatingBadge } from '../ui/RatingBadge'
import { TagSelect } from '../tags/TagSelect'
import { assignPlayerTag } from '../../lib/tagsApi'
import { formatCurrency, formatPct } from '../../lib/format'
import { hexToRgba } from '../../lib/ratingScale'

interface PlayersMobileListProps {
  rows: PlayerRow[]
  tags: Tag[]
  onTagAssigned: () => void
  onRequestRemove: (player: PlayerRow) => void
}

/** Alternativa alla griglia AG Grid per mobile/tablet (sotto il breakpoint
 * lg, vedi PlayersGrid): le 16 colonne della tabella desktop non hanno
 * senso su uno schermo stretto, quindi qui si mostra una card per
 * giocatore con solo le informazioni piu' rilevanti a colpo d'occhio
 * (le altre restano a un tap di distanza nella scheda singola). Niente
 * selezione multipla/bulk-rimuovi qui: su mobile ogni card ha la sua
 * azione "Rimuovi", piu' naturale al tocco di una checkbox minuscola. */
export function PlayersMobileList({ rows, tags, onTagAssigned, onRequestRemove }: PlayersMobileListProps) {
  const navigate = useNavigate()

  if (rows.length === 0) {
    return (
      <div className="flex h-full items-center justify-center py-12 text-center text-sm text-text-muted">
        Nessun giocatore in watchlist.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {rows.map((player) => {
        const change = player.market_value_change_pct

        return (
          <Card
            key={player.id}
            onClick={() => navigate(`/players/${player.id}`)}
            className="cursor-pointer active:bg-bg-surface-hover"
            style={
              player.tag
                ? { borderLeft: `3px solid ${player.tag.color}`, backgroundColor: hexToRgba(player.tag.color, 0.07) }
                : undefined
            }
          >
            {player.sync_status !== 'success' && <p className="mb-2 text-xs text-text-muted">
              {player.sync_status === 'pending' ? 'In attesa di aggiornamento' : 'Dati parziali: apri la scheda per lo stato'}
            </p>}

            <div className="flex items-start gap-3">
              {player.photo_url ? (
                <img loading="lazy" src={player.photo_url} alt="" className="h-11 w-11 shrink-0 rounded-full object-cover" />
              ) : (
                <div className="h-11 w-11 shrink-0 rounded-full bg-bg-surface-hover" />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-text-primary">{player.full_name}</p>
                <p className="truncate text-xs text-text-muted">
                  {player.current_team ?? 'N/D'} · {player.league ?? 'N/D'}
                  {player.age !== null && ` · ${player.age} anni`}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className="text-sm font-medium text-text-primary">{formatCurrency(player.market_value_eur)}</p>
                {change !== null && change !== undefined && change !== 0 && (
                  <span className={`text-xs font-medium ${change > 0 ? 'text-accent-primary' : 'text-danger'}`}>
                    {formatPct(change)}
                  </span>
                )}
              </div>
            </div>

            <div className="mt-3 flex items-center gap-4 text-xs text-text-secondary">
              <span className="flex items-center gap-1.5">
                Voto <RatingBadge rating={player.rating_avg} />
              </span>
              <span>
                Goal (5) <span className="text-text-primary">{player.goals_last5}</span>
              </span>
              <span>
                Assist (5) <span className="text-text-primary">{player.assists_last5}</span>
              </span>
            </div>

            <div
              className="mt-3 flex items-center justify-between gap-2 border-t border-border-subtle pt-3"
              onClick={(e) => e.stopPropagation()}
            >
              <TagSelect
                value={player.tag}
                tags={tags}
                onAssign={async (tagId) => {
                  await assignPlayerTag(player.id, tagId)
                  onTagAssigned()
                }}
                onTagCreated={() => onTagAssigned()}
              />
              <button
                onClick={() => onRequestRemove(player)}
                className="rounded-sm px-2 py-1 text-xs font-medium text-text-muted hover:bg-danger/10 hover:text-danger"
              >
                Rimuovi
              </button>
            </div>
          </Card>
        )
      })}
    </div>
  )
}
