import { useCallback, useEffect, useRef, useState } from 'react'
import { AppLayout } from '../components/layout/AppLayout'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { PlayersGrid } from '../components/table/PlayersGrid'
import { TagManagerModal } from '../components/tags/TagManagerModal'
import { exportWatchlist, fetchWatchlist } from '../lib/playersApi'
import { LoadingStatus } from '../components/ui/LoadingStatus'
import { requestErrorMessage } from '../lib/api'
import { fetchTags } from '../lib/tagsApi'
import type { PlayerRow, Tag } from '../types/player'

export function DashboardPage() {
  const [rows, setRows] = useState<PlayerRow[]>([])
  const [tags, setTags] = useState<Tag[]>([])
  const [isTagManagerOpen, setIsTagManagerOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tagError, setTagError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tagsLoading, setTagsLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const loadController = useRef<AbortController | null>(null)

  const loadData = useCallback(async () => {
    loadController.current?.abort()
    const controller = new AbortController()
    loadController.current = controller
    const { signal } = controller
    setLoading(true)
    setTagsLoading(true)
    setError(null)
    setTagError(null)
    // Render players as soon as they arrive; optional tags cannot block them.
    await Promise.all([
      fetchWatchlist(signal)
        .then((watchlist) => { if (!signal.aborted) setRows(watchlist) })
        .catch((cause: unknown) => {
          if (!signal.aborted) setError(`Impossibile caricare la watchlist. ${requestErrorMessage(cause)}`)
        })
        .finally(() => { if (!signal.aborted) setLoading(false) }),
      fetchTags(signal)
        .then((tagsData) => { if (!signal.aborted) setTags(tagsData) })
        .catch(() => {
          if (!signal.aborted) setTagError('Impossibile aggiornare i tag. Puoi continuare a consultare i giocatori.')
        })
        .finally(() => { if (!signal.aborted) setTagsLoading(false) }),
    ])
  }, [])

  useEffect(() => {
    loadData()
    return () => loadController.current?.abort()
  }, [loadData])

  async function downloadExport() {
    setExporting(true)
    try { await exportWatchlist() }
    catch { setError('Esportazione non riuscita. Riprova.') }
    finally { setExporting(false) }
  }

  return (
    <AppLayout onDataChanged={loadData}>
      <div className="flex h-full flex-col gap-4">
        {(error || tagError) && (
          <Card className="border-danger/40">
            {error && <p role="alert" className="text-sm text-danger">{error}</p>}
            {tagError && <p role="alert" className="text-sm text-danger">{tagError}</p>}
            <Button variant="secondary" onClick={loadData}>Riprova</Button>
          </Card>
        )}

        <Card className="flex flex-1 flex-col">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-2xl text-text-primary">Watchlist</h1>
              <p className="mt-1 text-sm text-text-secondary">
                Tutti i giocatori seguiti. Apri una scheda per rating, valore di mercato e ultimi aggiornamenti.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={downloadExport} disabled={exporting}
              className="!px-3 !py-1.5 text-xs">{exporting ? 'Esportazione…' : 'Esporta dati'}</Button>
            <Button
              variant="secondary"
              onClick={() => setIsTagManagerOpen(true)}
              disabled={tagsLoading || !!tagError}
              className="shrink-0 self-start whitespace-nowrap !px-3 !py-1.5 text-xs sm:self-auto"
            >
              Gestisci tag
            </Button>
            </div>
          </div>
          <div className="flex-1">
            {loading ? <LoadingStatus phase="data" message="Caricamento della watchlist..." />
              : <PlayersGrid rows={rows} tags={tags} onRowRemoved={loadData} onTagAssigned={loadData} />}
          </div>
        </Card>
      </div>

      <TagManagerModal
        open={isTagManagerOpen}
        tags={tags}
        onClose={() => setIsTagManagerOpen(false)}
        onTagsChanged={loadData}
      />
    </AppLayout>
  )
}
