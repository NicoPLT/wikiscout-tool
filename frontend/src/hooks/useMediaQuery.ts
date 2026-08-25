import { useEffect, useState } from 'react'

/** Specchia una media query CSS in React. Usato per scegliere tra AG Grid
 * (desktop) e la lista a card (mobile/tablet) senza montare entrambe: AG
 * Grid e' pesante e non ha senso inizializzarla su un dispositivo dove non
 * verra' mai mostrata. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => (typeof window !== 'undefined' ? window.matchMedia(query).matches : false))

  useEffect(() => {
    const mql = window.matchMedia(query)
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches)
    setMatches(mql.matches)
    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [query])

  return matches
}
