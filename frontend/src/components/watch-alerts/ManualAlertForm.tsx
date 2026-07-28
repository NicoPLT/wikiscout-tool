import { useEffect, useRef, useState } from 'react'
import { Card } from '../ui/Card'
import { Button } from '../ui/Button'
import { Spinner } from '../ui/Spinner'
import { searchPlayers, importPlayerFromTransfermarkt } from '../../lib/playersApi'
import { createManualWatchAlert } from '../../lib/watchAlertsApi'
import type { PlayerSearchResult } from '../../types/player'

interface ManualAlertFormProps {
  onCreated: () => void
}

export function ManualAlertForm({ onCreated }: ManualAlertFormProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PlayerSearchResult[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [selected, setSelected] = useState<PlayerSearchResult | null>(null)
  const [note, setNote] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([])
      setIsSearching(false)
      return
    }
    setIsSearching(true)
    const handle = setTimeout(() => {
      searchPlayers(query.trim())
        .then((data) => {
          setResults(data)
          setIsOpen(true)
        })
        .catch(() => setResults([]))
        .finally(() => setIsSearching(false))
    }, 350)
    return () => clearTimeout(handle)
  }, [query])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function handleSelect(player: PlayerSearchResult) {
    setSelected(player)
    setQuery('')
    setResults([])
    setIsOpen(false)
    setError(null)
  }

  function handleClearSelection() {
    setSelected(null)
    setNote('')
    setError(null)
  }

  async function handleSubmit() {
    if (!selected || !note.trim()) return
    setIsSubmitting(true)
    setError(null)
    try {
      let playerId = selected.id
      if (selected.source === 'transfermarkt') {
        const imported = await importPlayerFromTransfermarkt(selected)
        playerId = imported.id
      }
      if (playerId === null) return
      await createManualWatchAlert(playerId, note.trim())
      handleClearSelection()
      onCreated()
    } catch {
      setError('Impossibile aggiungere la segnalazione in questo momento. Riprova.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Card title="Aggiungi segnalazione manuale">
      <p className="mb-3 text-sm text-text-secondary">
        Segnala un giocatore indipendentemente dai criteri automatici, con una nota personale (es.
        "visto dal vivo, impressionante nell'uno contro uno").
      </p>

      {selected ? (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3 rounded-md border border-border-subtle bg-bg-surface-hover px-3 py-2">
            <div className="flex items-center gap-3 overflow-hidden">
              {selected.photo_url ? (
                <img src={selected.photo_url} alt="" className="h-8 w-8 shrink-0 rounded-full object-cover" />
              ) : (
                <div className="h-8 w-8 shrink-0 rounded-full bg-bg-surface" />
              )}
              <div className="min-w-0">
                <p className="truncate text-sm text-text-primary">{selected.full_name}</p>
                <p className="truncate text-xs text-text-muted">{selected.current_team ?? 'N/D'}</p>
              </div>
            </div>
            <button
              onClick={handleClearSelection}
              className="shrink-0 text-xs text-text-muted hover:text-text-primary"
            >
              Cambia
            </button>
          </div>

          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Nota personale..."
            rows={3}
            className="w-full resize-none rounded-md border border-border-subtle bg-bg-surface-hover p-3 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none"
          />

          <div className="flex items-center gap-3">
            <Button onClick={handleSubmit} disabled={isSubmitting || !note.trim()}>
              {isSubmitting ? 'Aggiunta...' : 'Aggiungi segnalazione'}
            </Button>
            <Button variant="ghost" onClick={handleClearSelection} disabled={isSubmitting}>
              Annulla
            </Button>
          </div>
          {error && <p className="text-xs text-danger">{error}</p>}
        </div>
      ) : (
        <div ref={containerRef} className="relative">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => results.length > 0 && setIsOpen(true)}
            placeholder="Cerca giocatore per nome..."
            className="w-full rounded-md border border-border-subtle bg-bg-surface-hover px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none"
          />

          {isOpen && (isSearching || results.length > 0) && (
            <div className="absolute left-0 right-0 top-full z-20 mt-2 max-h-72 overflow-y-auto rounded-card border border-border-subtle bg-bg-surface shadow-lg">
              {isSearching && results.length === 0 && (
                <div className="px-4 py-3 text-xs text-text-muted">
                  <Spinner size="sm" /> Ricerca in corso...
                </div>
              )}
              {results.map((player) => (
                <button
                  key={`${player.source}-${player.id ?? player.transfermarkt_id}`}
                  onClick={() => handleSelect(player)}
                  className="flex w-full items-center gap-3 border-b border-border-subtle px-4 py-2.5 text-left last:border-b-0 hover:bg-bg-surface-hover"
                >
                  {player.photo_url ? (
                    <img src={player.photo_url} alt="" className="h-8 w-8 shrink-0 rounded-full object-cover" />
                  ) : (
                    <div className="h-8 w-8 shrink-0 rounded-full bg-bg-surface-hover" />
                  )}
                  <div className="min-w-0">
                    <p className="truncate text-sm text-text-primary">{player.full_name}</p>
                    <p className="truncate text-xs text-text-muted">
                      {player.current_team ?? 'N/D'} · {player.league ?? 'N/D'}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
