import type { CSSProperties, PropsWithChildren } from 'react'

interface CardProps {
  className?: string
  title?: string
  style?: CSSProperties
  onClick?: () => void
}

export function Card({ title, className = '', style, onClick, children }: PropsWithChildren<CardProps>) {
  return (
    <div
      className={`rounded-card border border-border-subtle bg-bg-surface p-4 sm:p-5 ${className}`}
      style={style}
      onClick={onClick}
    >
      {title && <h3 className="mb-4 text-base font-medium text-text-primary">{title}</h3>}
      {children}
    </div>
  )
}
