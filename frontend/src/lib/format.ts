export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'N/D'
  if (value >= 1_000_000) return `€${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `€${(value / 1_000).toFixed(0)}k`
  return `€${value.toFixed(0)}`
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return ''
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return 'N/D'
  return new Date(value).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })
}

/** Ritorna { label, freshness } dove freshness guida il colore (fresh/stale/old). */
export function formatRelativeUpdate(value: string | null | undefined): {
  label: string
  freshness: 'fresh' | 'stale' | 'old'
} {
  if (!value) return { label: 'N/D', freshness: 'old' }

  const now = new Date().getTime()
  const then = new Date(value).getTime()
  const diffMs = now - then
  const diffHours = diffMs / (1000 * 60 * 60)
  const diffDays = diffHours / 24

  let label: string
  if (diffHours < 1) label = 'meno di 1 ora fa'
  else if (diffHours < 24) label = `${Math.floor(diffHours)} ore fa`
  else if (diffDays < 30) label = `${Math.floor(diffDays)} giorni fa`
  else label = new Date(value).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })

  let freshness: 'fresh' | 'stale' | 'old' = 'fresh'
  if (diffHours >= 24 && diffDays < 3) freshness = 'stale'
  else if (diffDays >= 3) freshness = 'old'

  return { label, freshness }
}
