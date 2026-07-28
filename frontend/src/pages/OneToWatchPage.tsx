import { useCallback, useEffect, useMemo, useState } from 'react'
import { AppLayout } from '../components/layout/AppLayout'
import { Card } from '../components/ui/Card'
import { Spinner } from '../components/ui/Spinner'
import { WatchAlertCard } from '../components/watch-alerts/WatchAlertCard'
import { ManualAlertForm } from '../components/watch-alerts/ManualAlertForm'
import { dismissWatchAlert, fetchWatchAlerts, markWatchAlertsSeen } from '../lib/watchAlertsApi'
import type { WatchAlert, WatchAlertPlayer } from '../types/watchAlert'

interface PlayerAlertGroup {
  player: WatchAlertPlayer
  alerts: WatchAlert[]
  latestDetectedAt: string
}

function groupByPlayer(alerts: WatchAlert[]): PlayerAlertGroup[] {
  const groups = new Map<number, PlayerAlertGroup>()

  for (const alert of alerts) {
    const existing = groups.get(alert.player_id)
    if (existing) {
      existing.alerts.push(alert)
      if (alert.detected_at > existing.latestDetectedAt) {
        existing.latestDetectedAt = alert.detected_at
      }
    } else {
      groups.set(alert.player_id, {
        player: alert.player,
        alerts: [alert],
        latestDetectedAt: alert.detected_at,
      })
    }
  }

  for (const group of groups.values()) {
    group.alerts.sort((a, b) => (a.detected_at < b.detected_at ? 1 : -1))
  }

  return Array.from(groups.values()).sort((a, b) => (a.latestDetectedAt < b.latestDetectedAt ? 1 : -1))
}

export function OneToWatchPage() {
  const [alerts, setAlerts] = useState<WatchAlert[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      const data = await fetchWatchAlerts()
      setAlerts(data)
      setError(null)
      // Aprire la sezione conta come "visto": azzera il badge sidebar
      // senza scartare gli alert (restano visibili finche' lo scout non
      // li scarta esplicitamente). L'evento fa aggiornare subito il badge
      // sulla sidebar di QUESTA stessa pagina, non solo alla prossima
      // navigazione.
      markWatchAlertsSeen()
        .then(() => window.dispatchEvent(new Event('watch-alerts-seen')))
        .catch(() => {})
    } catch {
      setError('Impossibile caricare le segnalazioni. Verifica che il backend sia raggiungibile.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  async function handleDismiss(alertId: number) {
    setAlerts((prev) => prev.filter((a) => a.id !== alertId))
    try {
      await dismissWatchAlert(alertId)
    } catch {
      loadData()
    }
  }

  const groups = useMemo(() => groupByPlayer(alerts), [alerts])

  return (
    <AppLayout>
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-2xl text-text-primary">One to Watch</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Segnalazioni automatiche dalla tua watchlist: giocatori che segui gia' e che stanno
            performando meglio del solito. Non e' una scoperta di nuovi giocatori nel mondo.
          </p>
        </div>

        {error && (
          <Card className="border-danger/40">
            <p className="text-sm text-danger">{error}</p>
          </Card>
        )}

        <ManualAlertForm onCreated={loadData} />

        {isLoading ? (
          <div className="flex items-center gap-2 py-12 text-sm text-text-muted">
            <Spinner size="sm" />
            Caricamento segnalazioni...
          </div>
        ) : groups.length === 0 ? (
          <Card>
            <p className="text-sm text-text-secondary">
              Nessuna segnalazione attiva al momento. Il controllo gira ogni notte sui giocatori
              gia' in watchlist.
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {groups.map((group) => (
              <WatchAlertCard
                key={group.player.id}
                player={group.player}
                alerts={group.alerts}
                onDismiss={handleDismiss}
              />
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  )
}
