import type { PropsWithChildren } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useAuth } from '../../hooks/useAuth'

interface AppLayoutProps {
  onDataChanged?: () => void
}

export function AppLayout({ children, onDataChanged }: PropsWithChildren<AppLayoutProps>) {
  const { email, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-bg-primary text-text-primary">
      <Sidebar onLogout={handleLogout} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header userEmail={email} onPlayerAdded={() => onDataChanged?.()} />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  )
}
