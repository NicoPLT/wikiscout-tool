import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AppLayout } from '../components/layout/AppLayout'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { RatingBadge } from '../components/ui/RatingBadge'
import { MarketValueTrend } from '../components/charts/MarketValueTrend'
import { TagSelect } from '../components/tags/TagSelect'
import { SeasonStatsCard } from '../components/player/SeasonStatsCard'
import {
  fetchPlayerDetail,
  fetchPlayerSeasons,
  fetchPlayerTransfers,
  linkSofascoreProfile,
  updateWatchlistEntry,
} from '../lib/playersApi'
import { assignPlayerTag, fetchTags } from '../lib/tagsApi'
import type { PlayerDetail, PlayerSeasonOption, PlayerTransfer, Tag } from '../types/player'
import { formatCurrency, formatDate, formatPct, formatRelativeUpdate } from '../lib/format'
import { linkifyText } from '../lib/linkify'

function BackIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ExternalLinkIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path
        d="M18 13v6a2 2 0 01-2 2H6a2 2 0 01-2-2V9a2 2 0 012-2h6M15 3h6v6M10 14L21 3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

interface ExternalProfileLinkProps {
  href: string
  label: string
}

function ExternalProfileLink({ href, label }: ExternalProfileLinkProps) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-1.5 rounded-sm bg-bg-surface-hover px-3 py-1.5 text-xs font-medium text-text-primary hover:bg-border-subtle"
    >
      {label}
      <ExternalLinkIcon />
    </a>
  )
}

export function PlayerDetailPage() {
  const { playerId } = useParams<{ playerId: string }>()
  const navigate = useNavigate()
  const [player, setPlayer] = useState<PlayerDetail | null>(null)
  const [notes, setNotes] = useState('')
  const [isEditingNotes, setIsEditingNotes] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [sofascoreInput, setSofascoreInput] = useState('')
  const [isLinkingSofascore, setIsLinkingSofascore] = useState(false)
  const [sofascoreLinkError, setSofascoreLinkError] = useState<string | null>(null)
  const [seasonOptions, setSeasonOptions] = useState<PlayerSeasonOption[]>([])
  const [selectedSeasonId, setSelectedSeasonId] = useState<number | null>(null)
  const [isLoadingSeasons, setIsLoadingSeasons] = useState(true)
  const [transfers, setTransfers] = useState<PlayerTransfer[]>([])
  const [isLoadingTransfers, setIsLoadingTransfers] = useState(true)
  const [tags, setTags] = useState<Tag[]>([])

  useEffect(() => {
    if (!playerId) return
    setPlayer(null)
    fetchPlayerDetail(Number(playerId)).then((data) => {
      setPlayer(data)
      setNotes(data.watchlist_notes ?? '')
    })
    fetchTags().then(setTags)
    setIsLoadingSeasons(true)
    fetchPlayerSeasons(Number(playerId))
      .then((options) => {
        setSeasonOptions(options)
        if (options.length > 0) setSelectedSeasonId(options[0].season_id)
      })
      .finally(() => setIsLoadingSeasons(false))
    setIsLoadingTransfers(true)
    fetchPlayerTransfers(Number(playerId))
      .then(setTransfers)
      .finally(() => setIsLoadingTransfers(false))
  }, [playerId])

  async function handleSaveNotes() {
    if (!player) return
    setIsSaving(true)
    try {
      const updated = await updateWatchlistEntry(player.id, notes)
      setPlayer(updated)
      setSaved(true)
      setIsEditingNotes(false)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setIsSaving(false)
    }
  }

  async function handleAssignTag(tagId: number | null) {
    if (!player) return
    await assignPlayerTag(player.id, tagId)
    const assigned = tagId === null ? null : tags.find((t) => t.id === tagId) ?? null
    setPlayer({ ...player, tag: assigned })
  }

  async function handleLinkSofascore() {
    if (!player || !sofascoreInput.trim()) return
    setIsLinkingSofascore(true)
    setSofascoreLinkError(null)
    try {
      const updated = await linkSofascoreProfile(player.id, sofascoreInput.trim())
      setPlayer(updated)
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
        <div className="flex flex-col items-center justify-center gap-3 py-24">
          <Spinner size="lg" />
          <p className="text-sm text-text-secondary">Caricamento scheda giocatore...</p>
        </div>
      </AppLayout>
    )
  }

  const marketFreshness = formatRelativeUpdate(player.market_value_updated_at)
  const statsFreshness = formatRelativeUpdate(player.stats_updated_at)

  const displayedSeason = seasonOptions.find((o) => o.season_id === selectedSeasonId) ?? null
  const seasonGoals = displayedSeason ? displayedSeason.goals : player.goals_season
  const seasonAssists = displayedSeason ? displayedSeason.assists : player.assists_season
  const seasonAppearances = displayedSeason ? displayedSeason.appearances : player.appearances_season
  const seasonMinutes = displayedSeason ? displayedSeason.minutes_played : player.minutes_season
  const seasonLabel = displayedSeason ? displayedSeason.season_label : player.season_label
  const seasonCompetition = displayedSeason ? displayedSeason.competition_name : player.league
  const seasonStarts = displayedSeason ? displayedSeason.starts : player.starts_season
  const seasonYellowCards = displayedSeason ? displayedSeason.yellow_cards : player.yellow_cards_season
  const seasonRedCards = displayedSeason ? displayedSeason.red_cards : player.red_cards_season

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
                {player.age !== null && ` (${player.age} anni)`}
              </p>
              <div className="mt-3 flex items-center gap-2">
                <span className="label-caption">Tag</span>
                <TagSelect
                  value={player.tag}
                  tags={tags}
                  onAssign={handleAssignTag}
                  onTagCreated={(tag) => setTags((prev) => [...prev, tag])}
                />
              </div>
              {(player.transfermarkt_id || player.sofascore_id || player.fotmob_id) && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {player.transfermarkt_id && (
                    <ExternalProfileLink
                      href={`https://www.transfermarkt.com/-/profil/spieler/${player.transfermarkt_id}`}
                      label="Transfermarkt"
                    />
                  )}
                  {player.sofascore_id && (
                    <ExternalProfileLink
                      href={`https://www.sofascore.com/player/-/${player.sofascore_id}`}
                      label="Sofascore"
                    />
                  )}
                  {player.fotmob_id && (
                    <ExternalProfileLink
                      href={`https://www.fotmob.com/players/${player.fotmob_id}/-`}
                      label="Fotmob"
                    />
                  )}
                </div>
              )}
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

        {isLoadingSeasons ? (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Spinner size="sm" />
            Caricamento statistiche stagionali...
          </div>
        ) : (
          <SeasonStatsCard
            competitionName={seasonCompetition}
            seasonLabel={seasonLabel}
            seasonOptions={seasonOptions}
            selectedSeasonId={selectedSeasonId}
            onSeasonChange={setSelectedSeasonId}
            goals={seasonGoals}
            assists={seasonAssists}
            starts={seasonStarts}
            appearances={seasonAppearances}
            minutesPlayed={seasonMinutes}
            rating={player.rating_avg}
            yellowCards={seasonYellowCards}
            redCards={seasonRedCards}
            isXgCovered={player.is_xg_covered}
            xg={player.xg_season}
            xa={player.xa_season}
          />
        )}

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
            {isEditingNotes ? (
              <>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Osservazioni, punti di forza, aree di miglioramento... (i link vengono resi cliccabili)"
                  rows={5}
                  autoFocus
                  className="w-full resize-none rounded-md border border-border-subtle bg-bg-surface-hover p-3 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none"
                />
                <div className="mt-3 flex items-center gap-3">
                  <Button onClick={handleSaveNotes} disabled={isSaving}>
                    {isSaving ? 'Salvataggio...' : 'Salva'}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setNotes(player.watchlist_notes ?? '')
                      setIsEditingNotes(false)
                    }}
                  >
                    Annulla
                  </Button>
                  {saved && <span className="text-xs text-accent-primary">Salvato</span>}
                </div>
              </>
            ) : (
              <>
                {notes ? (
                  <p className="whitespace-pre-wrap break-words text-sm text-text-primary">{linkifyText(notes)}</p>
                ) : (
                  <p className="text-sm text-text-muted">Nessuna nota.</p>
                )}
                <div className="mt-3">
                  <Button variant="secondary" onClick={() => setIsEditingNotes(true)} className="!px-3 !py-1.5 text-xs">
                    {notes ? 'Modifica' : 'Aggiungi nota'}
                  </Button>
                </div>
              </>
            )}
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
                    <td className="py-2.5 pr-4">
                      <RatingBadge rating={match.rating} />
                    </td>
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

        <Card title="Trasferimenti">
          {isLoadingTransfers ? (
            <div className="flex items-center gap-2 py-4 text-xs text-text-muted">
              <Spinner size="sm" />
              Caricamento storico trasferimenti...
            </div>
          ) : transfers.length === 0 ? (
            <p className="text-sm text-text-muted">Nessun trasferimento disponibile.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-subtle text-left text-text-muted">
                    <th className="pb-2 pr-4 font-medium">Data</th>
                    <th className="pb-2 pr-4 font-medium">Da</th>
                    <th className="pb-2 pr-4 font-medium">A</th>
                    <th className="pb-2 pr-4 font-medium">Tipo</th>
                    <th className="pb-2 pr-4 font-medium">Costo</th>
                    <th className="pb-2 pr-4 font-medium">Valore all'epoca</th>
                  </tr>
                </thead>
                <tbody>
                  {transfers.map((t) => (
                    <tr key={t.transfer_id} className="border-b border-border-subtle last:border-b-0">
                      <td className="py-2.5 pr-4 text-text-secondary">{formatDate(t.transfer_date)}</td>
                      <td className="py-2.5 pr-4 text-text-primary">{t.club_from_name ?? 'N/D'}</td>
                      <td className="py-2.5 pr-4 text-text-primary">{t.club_to_name ?? 'N/D'}</td>
                      <td className="py-2.5 pr-4">
                        {t.is_loan ? (
                          <Badge tone="neutral">Prestito</Badge>
                        ) : t.is_free_transfer ? (
                          <Badge tone="neutral">A parametro zero</Badge>
                        ) : (
                          <Badge tone="neutral">Trasferimento</Badge>
                        )}
                      </td>
                      <td className="py-2.5 pr-4 text-text-primary">
                        {t.is_free_transfer ? 'Free' : formatCurrency(t.fee_eur)}
                      </td>
                      <td className="py-2.5 pr-4 text-text-secondary">{formatCurrency(t.market_value_eur)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </AppLayout>
  )
}
