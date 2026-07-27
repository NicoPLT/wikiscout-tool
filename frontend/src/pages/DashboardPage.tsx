import { useCallback, useEffect, useState } from 'react'
import { AppLayout } from '../components/layout/AppLayout'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { PlayersGrid } from '../components/table/PlayersGrid'
import { TagManagerModal } from '../components/tags/TagManagerModal'
import { fetchWatchlist } from '../lib/playersApi'
import { fetchTags } from '../lib/tagsApi'
import type { PlayerRow, Tag } from '../types/player'

export function DashboardPage() {
  const [rows, setRows] = useState<PlayerRow[]>([])
  const [tags, setTags] = useState<Tag[]>([])
  const [isTagManagerOpen, setIsTagManagerOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      const [watchlist, tagsData] = await Promise.all([fetchWatchlist(), fetchTags()])
      setRows(watchlist)
      setTags(tagsData)
      setError(null)
    } catch {
      setError('Impossibile caricare la watchlist. Verifica che il backend sia raggiungibile.')
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  return (
    <AppLayout onDataChanged={loadData}>
      <div className="flex h-full flex-col gap-4">
        {error && (
          <Card className="border-danger/40">
            <p className="text-sm text-danger">{error}</p>
          </Card>
        )}

        <Card className="flex flex-1 flex-col">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h1 className="text-2xl text-text-primary">Watchlist</h1>
              <p className="mt-1 text-sm text-text-secondary">
                Tutti i giocatori seguiti. Apri una scheda per rating, valore di mercato e ultimi aggiornamenti.
              </p>
            </div>
            <Button variant="secondary" onClick={() => setIsTagManagerOpen(true)} className="!px-3 !py-1.5 text-xs">
              Gestisci tag
            </Button>
          </div>
          <div className="flex-1">
            <PlayersGrid rows={rows} tags={tags} onRowRemoved={loadData} onTagAssigned={loadData} />
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
