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

function FlameIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path
        d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
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
  unseenWatchAlertCount?: number
}

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `relative flex h-11 w-11 shrink-0 items-center justify-center rounded-md transition-colors lg:h-10 lg:w-10 ${
    isActive
      ? 'bg-accent-primary text-text-onaccent'
      : 'text-text-secondary hover:bg-bg-surface-hover hover:text-text-primary'
  }`

export function Sidebar({ onLogout, unseenWatchAlertCount = 0 }: SidebarProps) {
  return (
    <aside
      className="fixed inset-x-0 bottom-0 z-40 flex h-16 flex-row items-center justify-around border-t border-border-subtle bg-bg-surface px-2 pb-[env(safe-area-inset-bottom)] lg:static lg:inset-auto lg:h-full lg:w-18 lg:flex-col lg:items-center lg:justify-between lg:border-r lg:border-t-0 lg:px-0 lg:py-5 lg:pb-5"
    >
      <div className="flex w-full flex-1 flex-row items-center justify-around gap-1 lg:w-auto lg:flex-none lg:flex-col lg:items-center lg:justify-start lg:gap-8">
        <Logo iconOnly className="hidden lg:flex" />

        <nav className="flex w-full flex-row items-center justify-around gap-1 lg:w-auto lg:flex-col lg:justify-start lg:gap-2">
          <NavLink to="/" end className={navLinkClass} title="Dashboard">
            <GridIcon />
          </NavLink>
          <NavLink to="/one-to-watch" className={navLinkClass} title="One to Watch">
            <FlameIcon />
            {unseenWatchAlertCount > 0 && (
              <span className="absolute right-1 top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold text-text-primary lg:-right-1 lg:-top-1">
                {unseenWatchAlertCount > 9 ? '9+' : unseenWatchAlertCount}
              </span>
            )}
          </NavLink>
          <button onClick={onLogout} title="Esci" className={`${navLinkClass({ isActive: false })} lg:hidden`}>
            <LogoutIcon />
          </button>
        </nav>
      </div>

      <button
        onClick={onLogout}
        title="Esci"
        className="hidden h-10 w-10 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-bg-surface-hover hover:text-danger lg:flex"
      >
        <LogoutIcon />
      </button>
    </aside>
  )
}
