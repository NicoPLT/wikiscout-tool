import { useEffect, useRef, useState } from 'react'
import { addToWatchlist, importPlayerFromApiFootball, searchPlayers } from '../../lib/playersApi'
import type { PlayerSearchResult } from '../../types/player'

interface HeaderProps {
  userEmail: string | null
  onPlayerAdded: () => void
}

function resultKey(player: PlayerSearchResult): string {
  return `${player.source}-${player.id ?? player.api_football_id}`
}

export function Header({ userEmail, onPlayerAdded }: HeaderProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PlayerSearchResult[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [addingKey, setAddingKey] = useState<string | null>(null)
  const [importError, setImportError] = useState<string | null>(null)
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

  async function handleAdd(player: PlayerSearchResult) {
    const key = resultKey(player)
    setAddingKey(key)
    setImportError(null)
    try {
      if (player.source === 'local' && player.id !== null) {
        await addToWatchlist(player.id)
      } else if (player.api_football_id) {
        await importPlayerFromApiFootball(player.api_football_id)
      }
      setResults((prev) => prev.map((r) => (resultKey(r) === key ? { ...r, in_watchlist: true } : r)))
      onPlayerAdded()
    } catch {
      setImportError('Impossibile importare questo giocatore in questo momento. Riprova.')
    } finally {
      setAddingKey(null)
    }
  }

  return (
    <header className="flex items-center justify-between gap-4 border-b border-border-subtle bg-bg-primary px-6 py-4">
      <div ref={containerRef} className="relative w-full max-w-md">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length > 0 && setIsOpen(true)}
          placeholder="Cerca giocatore per nome (es. Bellandi)..."
          className="w-full rounded-md border border-border-subtle bg-bg-surface px-4 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none"
        />

        {isOpen && (isSearching || results.length > 0) && (
          <div className="absolute left-0 right-0 top-full z-20 mt-2 max-h-80 overflow-y-auto rounded-card border border-border-subtle bg-bg-surface shadow-lg">
            {isSearching && results.length === 0 && (
              <div className="px-4 py-3 text-xs text-text-muted">Ricerca in corso...</div>
            )}
            {results.map((player) => {
              const key = resultKey(player)
              return (
                <div
                  key={key}
                  className="flex items-center justify-between gap-3 border-b border-border-subtle px-4 py-2.5 last:border-b-0 hover:bg-bg-surface-hover"
                >
                  <div className="flex items-center gap-3 overflow-hidden">
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
                  </div>
                  <button
                    onClick={() => handleAdd(player)}
                    disabled={player.in_watchlist || addingKey === key}
                    className="shrink-0 rounded-sm bg-accent-primary px-3 py-1 text-xs font-medium text-text-onaccent hover:bg-accent-hover hover:text-text-primary disabled:cursor-not-allowed disabled:bg-bg-surface-hover disabled:text-text-muted"
                  >
                    {player.in_watchlist
                      ? 'In watchlist'
                      : addingKey === key
                        ? 'Importazione...'
                        : '+ Aggiungi'}
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {importError && <span className="text-xs text-danger">{importError}</span>}

      {userEmail && (
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <span className="label-caption">Scout</span>
          <span className="text-text-primary">{userEmail}</span>
        </div>
      )}
    </header>
  )
}
