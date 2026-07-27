import { useCallback, useEffect, useState } from 'react'
import { AppLayout } from '../components/layout/AppLayout'
import { Card } from '../components/ui/Card'
import { Gauge } from '../components/charts/Gauge'
import { MarketValueTrend } from '../components/charts/MarketValueTrend'
import { RecentUpdatesList } from '../components/RecentUpdatesList'
import { PlayersGrid } from '../components/table/PlayersGrid'
import { fetchWatchlist, fetchWatchlistSummary } from '../lib/playersApi'
import type { PlayerRow, WatchlistSummary } from '../types/player'
import { formatCurrency } from '../lib/format'

export function DashboardPage() {
  const [rows, setRows] = useState<PlayerRow[]>([])
  const [summary, setSummary] = useState<WatchlistSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      const [watchlist, summaryData] = await Promise.all([fetchWatchlist(), fetchWatchlistSummary()])
      setRows(watchlist)
      setSummary(summaryData)
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
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl text-text-primary">Dashboard scout</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Panoramica della tua watchlist, aggiornata a fine giornata di campionato.
          </p>
        </div>

        {error && (
          <Card className="border-danger/40">
            <p className="text-sm text-danger">{error}</p>
          </Card>
        )}

        {summary && (
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
            <Card title="Rating medio watchlist">
              <div className="flex items-center justify-center py-2">
                <Gauge value={summary.avg_rating ?? 0} label={`${summary.players_count} giocatori`} />
              </div>
            </Card>

            <Card title="Trend valore di mercato aggregato" className="lg:col-span-2">
              <p className="metric-value mb-3 text-text-primary">
                {formatCurrency(summary.total_market_value_eur)}
              </p>
              <MarketValueTrend data={summary.market_value_trend} />
            </Card>
          </div>
        )}

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <Card title="Watchlist" className="lg:col-span-2 flex flex-col" >
            <div style={{ height: 560 }}>
              <PlayersGrid rows={rows} onRowRemoved={loadData} />
            </div>
          </Card>

          <Card title="Ultimi aggiornamenti">
            {summary && <RecentUpdatesList items={summary.recent_updates} />}
          </Card>
        </div>
      </div>
    </AppLayout>
  )
}
