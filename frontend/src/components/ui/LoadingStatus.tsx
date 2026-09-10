import { useEffect, useState } from 'react'
import { Logo } from '../Logo'
import { Button } from './Button'
import { Spinner } from './Spinner'

interface LoadingStatusProps {
  message: string
  phase?: 'access' | 'data' | 'screen'
  fullScreen?: boolean
}

export function LoadingStatus({ message, phase = 'screen', fullScreen = false }: LoadingStatusProps) {
  const [startedAt] = useState(() => Date.now())
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    // Use wall-clock time so switching tabs does not make the timer fall behind.
    const tick = () => setElapsed(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)))
    const timer = setInterval(tick, 1_000)
    document.addEventListener('visibilitychange', tick)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', tick)
    }
  }, [startedAt])

  const duration = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, '0')}`
  const explanation = phase === 'access'
    ? elapsed >= 60
      ? 'L’accesso sta richiedendo più tempo del solito. Stiamo ancora aspettando la risposta: se non arriva, potrai riprovare.'
      : 'Dopo un periodo di inattività il servizio deve riavviarsi. In quel caso l’attesa è di circa un minuto; può variare.'
    : phase === 'data'
      ? elapsed >= 8
        ? 'I dati stanno impiegando più tempo del solito. La watchlist apparirà appena il caricamento sarà completato.'
        : 'Accesso effettuato. Stiamo recuperando i tuoi giocatori.'
      : elapsed >= 8
        ? 'La schermata sta impiegando più tempo del solito a caricarsi. Attendi ancora qualche secondo.'
        : 'Stiamo preparando la schermata. Si aprirà automaticamente.'

  const panel = <div className="mx-auto w-full max-w-md rounded-card border border-border-subtle bg-bg-surface p-6 text-center sm:p-8">
    {fullScreen && <Logo className="mb-8 justify-center" />}
    <div aria-hidden="true" className="mb-5 flex justify-center"><Spinner size="lg" className="motion-reduce:animate-none" /></div>
    <div role="status" aria-live="polite" aria-atomic="true">
      <h2 className="text-xl text-text-primary">{message}</h2>
      <p className="mt-3 text-sm leading-relaxed text-text-secondary">{explanation}</p>
    </div>
    <div className="mt-6 rounded-md bg-bg-primary px-4 py-4">
      <p className="text-xs text-text-secondary">Tempo trascorso in questa fase</p>
      <p role="timer" aria-live="off" aria-label="Tempo trascorso in questa fase" className="mt-1 text-3xl font-medium tabular-nums text-accent-primary">{duration}</p>
    </div>
    {phase === 'screen' && elapsed >= 30 &&
      <Button variant="secondary" className="mt-5" onClick={() => window.location.reload()}>Ricarica pagina</Button>}
  </div>

  return fullScreen
    ? <div className="flex min-h-dvh items-center justify-center bg-bg-primary px-4 py-8">{panel}</div>
    : <div className="py-6">{panel}</div>
}
