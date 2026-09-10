import { Component, type PropsWithChildren } from 'react'
import { Button } from './ui/Button'

// Lazy imports can fail on an interrupted connection or after a new deploy.
// A reload fetches the current HTML and asset URLs without losing the session.
export class AppErrorBoundary extends Component<PropsWithChildren, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (this.state.failed) {
      return <div className="flex min-h-dvh items-center justify-center bg-bg-primary px-6">
        <div className="max-w-md space-y-4">
          <h1 className="text-xl text-text-primary">Impossibile aprire la schermata</h1>
          <p role="alert" className="text-sm text-text-secondary">Il caricamento non è riuscito. Ricarica la pagina per riprovare.</p>
          <Button onClick={() => window.location.reload()}>Ricarica pagina</Button>
        </div>
      </div>
    }
    return this.props.children
  }
}
