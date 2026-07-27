import type { PropsWithChildren } from 'react'

type BadgeTone = 'positive' | 'negative' | 'neutral' | 'muted'

const toneClasses: Record<BadgeTone, string> = {
  positive: 'bg-accent-primary/15 text-accent-primary',
  negative: 'bg-danger/15 text-danger',
  neutral: 'bg-bg-surface-hover text-text-secondary',
  muted: 'bg-transparent text-text-muted',
}

export function Badge({ tone = 'neutral', children }: PropsWithChildren<{ tone?: BadgeTone }>) {
  return (
    <span className={`inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium ${toneClasses[tone]}`}>
      {children}
    </span>
  )
}
