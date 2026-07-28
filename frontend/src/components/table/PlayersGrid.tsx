import { useMemo, useRef, useState } from 'react'
import { AgGridReact } from 'ag-grid-react'
import {
  AllCommunityModule,
  ModuleRegistry,
  type ColDef,
  type RowStyle,
  type SelectionChangedEvent,
} from 'ag-grid-community'
import { useNavigate } from 'react-router-dom'
import type { PlayerRow, Tag } from '../../types/player'
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
import { assignPlayerTag } from '../../lib/tagsApi'
import { hexToRgba } from '../../lib/ratingScale'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { Button } from '../ui/Button'
import { TagSelect } from '../tags/TagSelect'

ModuleRegistry.registerModules([AllCommunityModule])

interface PlayersGridProps {
  rows: PlayerRow[]
  tags: Tag[]
  onRowRemoved: () => void
  onTagAssigned: () => void
}

function TagCellRenderer(props: { data?: PlayerRow; tags: Tag[]; onTagAssigned: () => void }) {
  if (!props.data) return null
  const player = props.data

  return (
    <TagSelect
      value={player.tag}
      tags={props.tags}
      onAssign={async (tagId) => {
        await assignPlayerTag(player.id, tagId)
        props.onTagAssigned()
      }}
      onTagCreated={() => props.onTagAssigned()}
    />
  )
}

type PendingRemoval = { players: PlayerRow[] } | null

function RemoveCellRenderer(props: { data?: PlayerRow; onRequestRemove: (player: PlayerRow) => void }) {
  if (!props.data) return null
  const player = props.data

  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        props.onRequestRemove(player)
      }}
      className="rounded-sm px-2 py-1 text-xs font-medium text-text-muted hover:bg-danger/10 hover:text-danger"
    >
      Rimuovi
    </button>
  )
}

export function PlayersGrid({ rows, tags, onRowRemoved, onTagAssigned }: PlayersGridProps) {
  const navigate = useNavigate()
  const gridRef = useRef<AgGridReact<PlayerRow>>(null)
  const [selectedRows, setSelectedRows] = useState<PlayerRow[]>([])
  const [pendingRemoval, setPendingRemoval] = useState<PendingRemoval>(null)
  const [isRemoving, setIsRemoving] = useState(false)

  function requestRemove(player: PlayerRow) {
    setPendingRemoval({ players: [player] })
  }

  function requestBulkRemove() {
    if (selectedRows.length === 0) return
    setPendingRemoval({ players: selectedRows })
  }

  async function handleConfirmRemoval() {
    if (!pendingRemoval) return
    setIsRemoving(true)
    try {
      await Promise.all(pendingRemoval.players.map((p) => removeFromWatchlist(p.id)))
      gridRef.current?.api?.deselectAll()
      setSelectedRows([])
      onRowRemoved()
    } finally {
      setIsRemoving(false)
      setPendingRemoval(null)
    }
  }

  const columnDefs = useMemo<ColDef<PlayerRow>[]>(
    () => [
      {
        headerName: 'Giocatore',
        field: 'full_name',
        cellRenderer: PlayerNameCellRenderer,
        pinned: 'left',
        minWidth: 240,
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
        headerName: 'Età',
        field: 'age',
        minWidth: 90,
        filter: 'agNumberColumnFilter',
        valueFormatter: (p) => (p.value === null || p.value === undefined ? 'N/D' : String(p.value)),
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
        headerName: 'Tag',
        colId: 'tag',
        minWidth: 150,
        sortable: false,
        filter: false,
        cellRenderer: (p: { data?: PlayerRow }) => (
          <TagCellRenderer data={p.data} tags={tags} onTagAssigned={onTagAssigned} />
        ),
      },
      {
        headerName: '',
        colId: 'actions',
        minWidth: 100,
        maxWidth: 110,
        sortable: false,
        filter: false,
        resizable: false,
        cellRenderer: (p: { data?: PlayerRow }) => (
          <RemoveCellRenderer data={p.data} onRequestRemove={requestRemove} />
        ),
      },
    ],
    [tags, onTagAssigned],
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

  const dialogCopy = useMemo(() => {
    if (!pendingRemoval) return { title: '', message: '' }
    if (pendingRemoval.players.length === 1) {
      return {
        title: 'Rimuovi giocatore',
        message: `Rimuovere ${pendingRemoval.players[0].full_name} dalla watchlist?`,
      }
    }
    return {
      title: 'Rimuovi giocatori',
      message: `Rimuovere ${pendingRemoval.players.length} giocatori selezionati dalla watchlist?`,
    }
  }, [pendingRemoval])

  return (
    <div className="flex h-full flex-col gap-3">
      {selectedRows.length > 0 && (
        <div className="flex items-center justify-between rounded-md border border-border-subtle bg-bg-surface-hover px-4 py-2">
          <span className="text-sm text-text-secondary">
            {selectedRows.length} giocator{selectedRows.length === 1 ? 'e' : 'i'} selezionat
            {selectedRows.length === 1 ? 'o' : 'i'}
          </span>
          <Button variant="danger" onClick={requestBulkRemove} className="!px-3 !py-1 text-xs">
            Rimuovi selezionati
          </Button>
        </div>
      )}

      <div style={{ flex: 1, minHeight: 0, width: '100%' }}>
        <AgGridReact<PlayerRow>
          ref={gridRef}
          theme={wikiscoutGridTheme}
          rowData={rows}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          getRowId={(p) => String(p.data.id)}
          getRowStyle={(params): RowStyle | undefined =>
            params.data?.tag
              ? {
                  borderLeft: `3px solid ${params.data.tag.color}`,
                  backgroundColor: hexToRgba(params.data.tag.color, 0.07),
                }
              : undefined
          }
          onRowClicked={(e) => {
            // AG Grid dispatches rowClicked for any click inside the row,
            // including custom cell renderers with interactive elements
            // (il select dei tag, il bottone "Rimuovi"): React's
            // stopPropagation dentro quei renderer non basta a fermarlo,
            // quindi va escluso qui in base all'elemento cliccato.
            const target = e.event?.target as HTMLElement | null
            if (target?.closest('select, button, input, a')) return
            if (e.data) navigate(`/players/${e.data.id}`)
          }}
          onSelectionChanged={(e: SelectionChangedEvent<PlayerRow>) => setSelectedRows(e.api.getSelectedRows())}
          rowSelection={{
            mode: 'multiRow',
            checkboxes: true,
            headerCheckbox: true,
            enableClickSelection: false,
          }}
          rowHeight={52}
          headerHeight={44}
          animateRows
        />
      </div>

      <ConfirmDialog
        open={pendingRemoval !== null}
        title={dialogCopy.title}
        message={dialogCopy.message}
        confirmLabel="Rimuovi"
        busy={isRemoving}
        onConfirm={handleConfirmRemoval}
        onCancel={() => setPendingRemoval(null)}
      />
    </div>
  )
}
