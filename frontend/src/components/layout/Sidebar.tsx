import { NavLink } from 'react-router-dom'
import { Logo } from '../Logo'

function GridIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  )
}

function LogoutIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M16 17l5-5-5-5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M21 12H9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

interface SidebarProps {
  onLogout: () => void
}

export function Sidebar({ onLogout }: SidebarProps) {
  return (
    <aside className="flex h-full w-18 flex-col items-center justify-between border-r border-border-subtle bg-bg-surface py-5">
      <div className="flex flex-col items-center gap-8">
        <Logo iconOnly />
        <nav className="flex flex-col gap-2">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `flex h-10 w-10 items-center justify-center rounded-md transition-colors ${
                isActive
                  ? 'bg-accent-primary text-text-onaccent'
                  : 'text-text-secondary hover:bg-bg-surface-hover hover:text-text-primary'
              }`
            }
            title="Dashboard"
          >
            <GridIcon />
          </NavLink>
        </nav>
      </div>

      <button
        onClick={onLogout}
        title="Esci"
        className="flex h-10 w-10 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-bg-surface-hover hover:text-danger"
      >
        <LogoutIcon />
      </button>
    </aside>
  )
}
