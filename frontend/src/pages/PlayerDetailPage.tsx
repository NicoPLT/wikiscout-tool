import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AppLayout } from '../components/layout/AppLayout'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { MarketValueTrend } from '../components/charts/MarketValueTrend'
import { fetchPlayerDetail, linkSofascoreProfile, updateWatchlistEntry } from '../lib/playersApi'
import type { PlayerDetail } from '../types/player'
import { formatCurrency, formatDate, formatPct, formatRelativeUpdate } from '../lib/format'

function BackIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function PlayerDetailPage() {
  const { playerId } = useParams<{ playerId: string }>()
  const navigate = useNavigate()
  const [player, setPlayer] = useState<PlayerDetail | null>(null)
  const [notes, setNotes] = useState('')
  const [tagsInput, setTagsInput] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [sofascoreInput, setSofascoreInput] = useState('')
  const [isLinkingSofascore, setIsLinkingSofascore] = useState(false)
  const [sofascoreLinkError, setSofascoreLinkError] = useState<string | null>(null)

  useEffect(() => {
    if (!playerId) return
    fetchPlayerDetail(Number(playerId)).then((data) => {
      setPlayer(data)
      setNotes(data.watchlist_notes ?? '')
      setTagsInput((data.watchlist_tags ?? []).join(', '))
    })
  }, [playerId])

  async function handleSaveNotes() {
    if (!player) return
    setIsSaving(true)
    try {
      const tags = tagsInput
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean)
      const updated = await updateWatchlistEntry(player.id, notes, tags)
      setPlayer(updated as PlayerDetail)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setIsSaving(false)
    }
  }

  async function handleLinkSofascore() {
    if (!player || !sofascoreInput.trim()) return
    setIsLinkingSofascore(true)
    setSofascoreLinkError(null)
    try {
      const updated = await linkSofascoreProfile(player.id, sofascoreInput.trim())
      setPlayer(updated as PlayerDetail)
      setSofascoreInput('')
    } catch {
      setSofascoreLinkError('URL/id non valido, o profilo senza statistiche disponibili. Controlla il link e riprova.')
    } finally {
      setIsLinkingSofascore(false)
    }
  }

  if (!player) {
    return (
      <AppLayout>
        <p className="text-text-secondary">Caricamento...</p>
      </AppLayout>
    )
  }

  const marketFreshness = formatRelativeUpdate(player.market_value_updated_at)
  const statsFreshness = formatRelativeUpdate(player.stats_updated_at)

  return (
    <AppLayout>
      <div className="flex flex-col gap-6">
        <button
          onClick={() => navigate(-1)}
          className="flex w-fit items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary"
        >
          <BackIcon /> Torna alla dashboard
        </button>

        <Card>
          <div className="flex flex-wrap items-center gap-5">
            {player.photo_url ? (
              <img src={player.photo_url} alt="" className="h-20 w-20 rounded-full object-cover" />
            ) : (
              <div className="h-20 w-20 rounded-full bg-bg-surface-hover" />
            )}
            <div className="flex-1">
              <h1 className="text-2xl text-text-primary">{player.full_name}</h1>
              <p className="mt-1 text-sm text-text-secondary">
                {player.current_team ?? 'N/D'} · {player.league ?? 'N/D'} · {player.position ?? 'N/D'}
              </p>
              <p className="mt-1 text-xs text-text-muted">
                {player.nationality ?? 'N/D'} · nato il {formatDate(player.date_of_birth)}
              </p>
            </div>
            <div className="text-right">
              <p className="metric-value text-text-primary">{formatCurrency(player.market_value_eur)}</p>
              {player.market_value_change_pct !== null && (
                <Badge tone={player.market_value_change_pct >= 0 ? 'positive' : 'negative'}>
                  {formatPct(player.market_value_change_pct)}
                </Badge>
              )}
            </div>
          </div>
        </Card>

        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Card>
            <p className="label-caption">Goal / Assist stagione</p>
            <p className="mt-2 text-xl text-text-primary">
              {player.goals_season} / {player.assists_season}
            </p>
          </Card>
          <Card>
            <p className="label-caption">Presenze / minuti</p>
            <p className="mt-2 text-xl text-text-primary">
              {player.appearances_season} / {player.minutes_season}&apos;
            </p>
          </Card>
          <Card>
            <p className="label-caption">Rating medio</p>
            <p className="mt-2 text-xl text-text-primary">{player.rating_avg?.toFixed(1) ?? 'N/D'}</p>
          </Card>
          <Card>
            <p className="label-caption">xG / xA stagione</p>
            <p className="mt-2 text-xl text-text-primary">
              {player.is_xg_covered
                ? `${player.xg_season?.toFixed(1) ?? '0.0'} / ${player.xa_season?.toFixed(1) ?? '0.0'}`
                : <span className="text-text-muted">N/D</span>}
            </p>
          </Card>
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <Card title="Trend valore di mercato" className="lg:col-span-2">
            <MarketValueTrend
              data={player.market_value_history.map((h) => ({
                recorded_at: h.recorded_at,
                total_value_eur: h.value_eur,
              }))}
            />
            <p className="mt-3 text-xs text-text-muted">
              Valore aggiornato{' '}
              <span
                className={
                  marketFreshness.freshness === 'fresh'
                    ? 'text-accent-primary'
                    : marketFreshness.freshness === 'stale'
                      ? 'text-text-muted'
                      : 'text-danger'
                }
              >
                {marketFreshness.label}
              </span>
            </p>
          </Card>

          <Card title="Note personali">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Osservazioni, punti di forza, aree di miglioramento..."
              rows={5}
              className="w-full resize-none rounded-md border border-border-subtle bg-bg-surface-hover p-3 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none"
            />
            <input
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="Tag separati da virgola (es. talento, da monitorare)"
              className="mt-3 w-full rounded-md border border-border-subtle bg-bg-surface-hover px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none"
            />
            <div className="mt-3 flex items-center gap-3">
              <Button onClick={handleSaveNotes} disabled={isSaving}>
                {isSaving ? 'Salvataggio...' : 'Salva'}
              </Button>
              {saved && <span className="text-xs text-accent-primary">Salvato</span>}
            </div>
          </Card>
        </div>

        {!player.sofascore_id && (
          <Card title="Collega profilo Sofascore">
            <p className="text-sm text-text-secondary">
              Non abbiamo trovato con certezza il profilo Sofascore di questo giocatore (nome ambiguo o
              omonimia), quindi rating/xG/xA/statistiche restano N/D. Incolla qui il link del profilo
              corretto (es. https://www.sofascore.com/player/erling-haaland/839956) per collegarlo
              manualmente.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <input
                value={sofascoreInput}
                onChange={(e) => setSofascoreInput(e.target.value)}
                placeholder="https://www.sofascore.com/player/..."
                className="min-w-[280px] flex-1 rounded-md border border-border-subtle bg-bg-surface-hover px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none"
              />
              <Button onClick={handleLinkSofascore} disabled={isLinkingSofascore || !sofascoreInput.trim()}>
                {isLinkingSofascore ? 'Collegamento...' : 'Collega'}
              </Button>
            </div>
            {sofascoreLinkError && <p className="mt-2 text-xs text-danger">{sofascoreLinkError}</p>}
          </Card>
        )}

        <Card title="Storico partite">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-subtle text-left text-text-muted">
                  <th className="pb-2 pr-4 font-medium">Data</th>
                  <th className="pb-2 pr-4 font-medium">Competizione</th>
                  <th className="pb-2 pr-4 font-medium">Avversario</th>
                  <th className="pb-2 pr-4 font-medium">Min</th>
                  <th className="pb-2 pr-4 font-medium">Goal</th>
                  <th className="pb-2 pr-4 font-medium">Assist</th>
                  <th className="pb-2 pr-4 font-medium">Rating</th>
                  <th className="pb-2 pr-4 font-medium">xG / xA</th>
                </tr>
              </thead>
              <tbody>
                {player.recent_matches.map((match) => (
                  <tr key={match.id} className="border-b border-border-subtle last:border-b-0">
                    <td className="py-2.5 pr-4 text-text-secondary">{formatDate(match.match_date)}</td>
                    <td className="py-2.5 pr-4 text-text-primary">{match.competition}</td>
                    <td className="py-2.5 pr-4 text-text-secondary">
                      {match.is_home ? 'vs' : '@'} {match.opponent ?? 'N/D'}
                    </td>
                    <td className="py-2.5 pr-4 text-text-primary">{match.minutes_played}&apos;</td>
                    <td className="py-2.5 pr-4 text-text-primary">{match.goals}</td>
                    <td className="py-2.5 pr-4 text-text-primary">{match.assists}</td>
                    <td className="py-2.5 pr-4 text-text-primary">{match.rating?.toFixed(1) ?? 'N/D'}</td>
                    <td className="py-2.5 pr-4 text-text-primary">
                      {player.is_xg_covered ? (
                        `${match.xg?.toFixed(2) ?? '0.00'} / ${match.xa?.toFixed(2) ?? '0.00'}`
                      ) : (
                        <span className="text-text-muted">N/D</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-text-muted">
            Statistiche aggiornate{' '}
            <span
              className={
                statsFreshness.freshness === 'fresh'
                  ? 'text-accent-primary'
                  : statsFreshness.freshness === 'stale'
                    ? 'text-text-muted'
                    : 'text-danger'
              }
            >
              {statsFreshness.label}
            </span>
          </p>
        </Card>
      </div>
    </AppLayout>
  )
}
