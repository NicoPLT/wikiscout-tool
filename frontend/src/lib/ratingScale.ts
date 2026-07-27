/** Scala cromatica del rating in stile Sofascore: verde per le prestazioni
 * migliori, giallo/arancio per la media, rosso per le peggiori. */
export function getRatingColor(rating: number | null | undefined): string {
  if (rating === null || rating === undefined) return '#707070'
  if (rating >= 8) return '#22c55e'
  if (rating >= 7) return '#84cc16'
  if (rating >= 6.5) return '#eab308'
  if (rating >= 6) return '#f97316'
  return '#ef4444'
}

export function hexToRgba(hex: string, alpha: number): string {
  const clean = hex.replace('#', '')
  const r = parseInt(clean.substring(0, 2), 16)
  const g = parseInt(clean.substring(2, 4), 16)
  const b = parseInt(clean.substring(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}
