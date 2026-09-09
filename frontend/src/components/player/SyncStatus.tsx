import type { PlayerDetail } from '../../types/player'
import { formatRelativeUpdate } from '../../lib/format'
import { Card } from '../ui/Card'

const sources: Record<string, string> = {
  stats: 'Statistiche', market: 'Valore di mercato', ratings: 'Rating e xG/xA',
  links: 'Anagrafica e profili', transfers: 'Trasferimenti',
}

export function SyncStatus({ player }: { player: PlayerDetail }) {
  return <Card>
    <p className="text-sm text-text-secondary">
      {player.sync_status === 'pending'
        ? 'Dati in attesa del prossimo aggiornamento notturno. Il giocatore e le tue note sono già salvati.'
        : player.sync_status === 'success'
          ? 'Aggiornamento completato. Qui puoi verificare quando ogni fonte è stata controllata.'
          : 'Alcuni dati non sono disponibili. Conserviamo gli ultimi dati validi e riproviamo automaticamente.'}
    </p>
    <details className="mt-2 text-xs text-text-muted">
      <summary className="cursor-pointer">Stato delle fonti</summary>
      <ul className="mt-2 space-y-2">
        {Object.entries(sources).map(([key, label]) => {
          const state = player.sync_state?.[key]
          return <li key={key}>
            <span className="font-medium text-text-secondary">{label}</span>: ultimo successo {formatRelativeUpdate(state?.last_success_at).label}
            {state?.last_attempt_at && <> · ultimo tentativo {formatRelativeUpdate(state.last_attempt_at).label}</>}
            {state?.error && <span className="text-danger"> · Dati non disponibili, nuovo tentativo programmato</span>}
          </li>
        })}
      </ul>
    </details>
  </Card>
}
