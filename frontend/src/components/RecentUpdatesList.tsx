import { Link } from 'react-router-dom'
import type { RecentUpdateItem } from '../types/player'
import { formatPct, formatRelativeUpdate } from '../lib/format'

export function RecentUpdatesList({ items }: { items: RecentUpdateItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-text-muted">Nessun aggiornamento recente.</p>
  }

  return (
    <ul className="flex flex-col">
      {items.map((item, idx) => {
        const isPositive = (item.change_pct ?? 0) >= 0
        return (
          <li key={`${item.player_id}-${item.kind}-${idx}`}>
            <Link
              to={`/players/${item.player_id}`}
              className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0 hover:opacity-80"
            >
              {item.photo_url ? (
                <img src={item.photo_url} alt="" className="h-9 w-9 shrink-0 rounded-full object-cover" />
              ) : (
                <div className="h-9 w-9 shrink-0 rounded-full bg-bg-surface-hover" />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-text-primary">{item.full_name}</p>
                <p className="truncate text-xs text-text-muted">{item.label}</p>
              </div>
              <div className="shrink-0 text-right">
                {item.change_pct !== null && (
                  <p className={`text-sm font-medium ${isPositive ? 'text-accent-primary' : 'text-danger'}`}>
                    {formatPct(item.change_pct)}
                  </p>
                )}
                <p className="text-xs text-text-muted">{formatRelativeUpdate(item.at).label}</p>
              </div>
            </Link>
          </li>
        )
      })}
    </ul>
  )
}
