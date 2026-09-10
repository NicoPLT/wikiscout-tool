import { lazy, Suspense, useState } from 'react'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import type { PlayerRow, Tag } from '../../types/player'
import { PlayersMobileList } from './PlayersMobileList'
import { removeFromWatchlist } from '../../lib/playersApi'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { LoadingStatus } from '../ui/LoadingStatus'

const DesktopPlayersGrid = lazy(() => import('./DesktopPlayersGrid').then((m) => ({ default: m.DesktopPlayersGrid })))

interface PlayersGridProps {
  rows: PlayerRow[]
  tags: Tag[]
  onRowRemoved: () => void
  onTagAssigned: () => void
}

export function PlayersGrid(props: PlayersGridProps) {
  const isDesktop = useMediaQuery('(min-width: 1024px)')
  const [pending, setPending] = useState<PlayerRow | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (isDesktop) return <Suspense fallback={<LoadingStatus message="Preparazione della tabella..." />}><DesktopPlayersGrid {...props} /></Suspense>
  async function remove() {
    if (!pending) return
    setBusy(true)
    setError(null)
    try {
      await removeFromWatchlist(pending.id)
      setPending(null)
      props.onRowRemoved()
    } catch {
      setError('Rimozione non riuscita. Riprova.')
    } finally { setBusy(false) }
  }
  return <>
    {error && <p role="alert" className="text-sm text-danger">{error}</p>}
    <PlayersMobileList rows={props.rows} tags={props.tags} onTagAssigned={props.onTagAssigned} onRequestRemove={setPending} />
    <ConfirmDialog open={pending !== null} title="Rimuovi giocatore" message={`Rimuovere ${pending?.full_name ?? ''} dalla watchlist?`}
      busy={busy} onConfirm={remove} onCancel={() => setPending(null)} />
  </>
}
