import { useCallback, useEffect, useState } from 'react'
import { AppLayout } from '../components/layout/AppLayout'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { PlayersGrid } from '../components/table/PlayersGrid'
import { TagManagerModal } from '../components/tags/TagManagerModal'
import { exportWatchlist, fetchWatchlist } from '../lib/playersApi'
import { Spinner } from '../components/ui/Spinner'
import { fetchTags } from '../lib/tagsApi'
import type { PlayerRow, Tag } from '../types/player'

export function DashboardPage() {
  const [rows, setRows] = useState<PlayerRow[]>([])
  const [tags, setTags] = useState<Tag[]>([])
  const [isTagManagerOpen, setIsTagManagerOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)

  const loadData = useCallback(async () => {
    try {
      const [watchlist, tagsData] = await Promise.all([fetchWatchlist(), fetchTags()])
      setRows(watchlist)
      setTags(tagsData)
      setError(null)
    } catch {
      setError('Impossibile caricare la watchlist. Verifica che il backend sia raggiungibile.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
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
        {error && (
          <Card className="border-danger/40">
            <p className="text-sm text-danger">{error}</p>
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
              className="shrink-0 self-start whitespace-nowrap !px-3 !py-1.5 text-xs sm:self-auto"
            >
              Gestisci tag
            </Button>
            </div>
          </div>
          <div className="flex-1">
            {loading ? <div className="flex items-center gap-3 py-8"><Spinner /><span className="text-sm text-text-muted">Caricamento… al primo accesso il servizio può impiegare circa un minuto.</span></div>
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
