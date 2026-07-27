import type { PropsWithChildren } from 'react'

interface CardProps {
  className?: string
  title?: string
}

export function Card({ title, className = '', children }: PropsWithChildren<CardProps>) {
  return (
    <div
      className={`rounded-card border border-border-subtle bg-bg-surface p-5 ${className}`}
    >
      {title && <h3 className="mb-4 text-base font-medium text-text-primary">{title}</h3>}
      {children}
    </div>
  )
}
