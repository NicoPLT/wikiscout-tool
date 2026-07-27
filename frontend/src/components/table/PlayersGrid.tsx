import { useMemo, useState } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry, type ColDef } from 'ag-grid-community'
import { useNavigate } from 'react-router-dom'
import type { PlayerRow } from '../../types/player'
import { wikiscoutGridTheme } from '../../lib/agGridTheme'
import {
  AppearancesCellRenderer,
  MarketValueCellRenderer,
  PlayerNameCellRenderer,
  RatingCellRenderer,
  UpdatedAtCellRenderer,
  XgXaCellRenderer,
} from './cellRenderers'
import { removeFromWatchlist } from '../../lib/playersApi'

ModuleRegistry.registerModules([AllCommunityModule])

interface PlayersGridProps {
  rows: PlayerRow[]
  onRowRemoved: () => void
}

function RemoveCellRenderer(props: { data?: PlayerRow; onRemoved: () => void }) {
  const [busy, setBusy] = useState(false)
  if (!props.data) return null

  async function handleRemove(e: React.MouseEvent) {
    e.stopPropagation()
    if (!props.data) return
    if (!window.confirm(`Rimuovere ${props.data.full_name} dalla watchlist?`)) return
    setBusy(true)
    try {
      await removeFromWatchlist(props.data.id)
      props.onRemoved()
    } finally {
      setBusy(false)
    }
  }

  return (
    <button
      onClick={handleRemove}
      disabled={busy}
      className="rounded-sm px-2 py-1 text-xs font-medium text-text-muted hover:bg-danger/10 hover:text-danger disabled:opacity-50"
    >
      {busy ? '...' : 'Rimuovi'}
    </button>
  )
}

export function PlayersGrid({ rows, onRowRemoved }: PlayersGridProps) {
  const navigate = useNavigate()

  const columnDefs = useMemo<ColDef<PlayerRow>[]>(
    () => [
      {
        headerName: 'Giocatore',
        field: 'full_name',
        cellRenderer: PlayerNameCellRenderer,
        pinned: 'left',
        minWidth: 220,
        filter: 'agTextColumnFilter',
      },
      {
        headerName: 'Squadra',
        field: 'current_team',
        minWidth: 150,
        filter: 'agTextColumnFilter',
      },
      {
        headerName: 'Campionato',
        field: 'league',
        minWidth: 150,
        filter: 'agTextColumnFilter',
      },
      {
        headerName: 'Ruolo',
        field: 'position',
        minWidth: 130,
        filter: 'agTextColumnFilter',
      },
      {
        headerName: 'Valore di mercato',
        field: 'market_value_eur',
        cellRenderer: MarketValueCellRenderer,
        minWidth: 190,
        sort: 'desc',
        filter: 'agNumberColumnFilter',
      },
      {
        headerName: 'Goal (5)',
        field: 'goals_last5',
        minWidth: 100,
        filter: 'agNumberColumnFilter',
      },
      {
        headerName: 'Assist (5)',
        field: 'assists_last5',
        minWidth: 100,
        filter: 'agNumberColumnFilter',
      },
      {
        headerName: 'Goal stagione',
        field: 'goals_season',
        minWidth: 120,
        filter: 'agNumberColumnFilter',
      },
      {
        headerName: 'Assist stagione',
        field: 'assists_season',
        minWidth: 130,
        filter: 'agNumberColumnFilter',
      },
      {
        headerName: 'Presenze / min',
        field: 'appearances_season',
        cellRenderer: AppearancesCellRenderer,
        minWidth: 140,
        filter: 'agNumberColumnFilter',
      },
      {
        headerName: 'Rating',
        field: 'rating_avg',
        cellRenderer: RatingCellRenderer,
        minWidth: 100,
        filter: 'agNumberColumnFilter',
      },
      {
        headerName: 'xG / xA',
        field: 'xg_season',
        cellRenderer: XgXaCellRenderer,
        minWidth: 110,
        sortable: false,
        filter: false,
      },
      {
        headerName: 'Aggiornato',
        field: 'last_synced_at',
        cellRenderer: UpdatedAtCellRenderer,
        minWidth: 130,
        filter: 'agDateColumnFilter',
      },
      {
        headerName: '',
        colId: 'actions',
        minWidth: 100,
        maxWidth: 110,
        sortable: false,
        filter: false,
        resizable: false,
        cellRenderer: (p: { data?: PlayerRow }) => <RemoveCellRenderer data={p.data} onRemoved={onRowRemoved} />,
      },
    ],
    [onRowRemoved],
  )

  const defaultColDef = useMemo<ColDef>(
    () => ({
      sortable: true,
      resizable: true,
      filter: true,
      floatingFilter: true,
    }),
    [],
  )

  return (
    <div style={{ height: '100%', width: '100%' }}>
      <AgGridReact<PlayerRow>
        theme={wikiscoutGridTheme}
        rowData={rows}
        columnDefs={columnDefs}
        defaultColDef={defaultColDef}
        getRowId={(p) => String(p.data.id)}
        onRowClicked={(e) => e.data && navigate(`/players/${e.data.id}`)}
        rowHeight={52}
        headerHeight={44}
        animateRows
      />
    </div>
  )
}
