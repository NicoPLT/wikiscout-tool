import { useEffect, useState, type PropsWithChildren } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useAuth } from '../../hooks/useAuth'
import { fetchUnseenWatchAlertCount } from '../../lib/watchAlertsApi'

interface AppLayoutProps {
  onDataChanged?: () => void
}

// Nessun sistema di notifiche push: un poll leggero basta a tenere il
// badge ragionevolmente aggiornato senza dover coordinare stato tra le
// pagine (ognuna monta un proprio AppLayout/Sidebar alla navigazione,
// che gia' rifa' il fetch da zero).
const UNSEEN_COUNT_POLL_MS = 5 * 60 * 1000

export function AppLayout({ children, onDataChanged }: PropsWithChildren<AppLayoutProps>) {
  const { email, logout } = useAuth()
  const navigate = useNavigate()
  const [unseenCount, setUnseenCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    function loadCount() {
      fetchUnseenWatchAlertCount()
        .then((count) => {
          if (!cancelled) setUnseenCount(count)
        })
        .catch(() => {})
    }
    loadCount()
    const interval = setInterval(loadCount, UNSEEN_COUNT_POLL_MS)
    // OneToWatchPage lo dispatcha dopo aver marcato tutto come visto: senza
    // questo, il badge resterebbe con il conteggio vecchio finche' non si
    // naviga altrove (AppLayout viene rimontato ad ogni pagina) o non scatta
    // il prossimo poll.
    window.addEventListener('watch-alerts-seen', loadCount)
    return () => {
      cancelled = true
      clearInterval(interval)
      window.removeEventListener('watch-alerts-seen', loadCount)
    }
  }, [])

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-bg-primary text-text-primary">
      <Sidebar onLogout={handleLogout} unseenWatchAlertCount={unseenCount} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header userEmail={email} onPlayerAdded={() => onDataChanged?.()} />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  )
}
