import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

const variantClasses: Record<Variant, string> = {
  primary: 'bg-accent-primary text-text-onaccent hover:bg-accent-hover hover:text-text-primary',
  secondary: 'bg-bg-surface-hover text-text-primary hover:bg-border-subtle',
  ghost: 'bg-transparent text-text-secondary hover:bg-bg-surface-hover',
  danger: 'bg-transparent text-danger hover:bg-danger/10',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

export function Button({ variant = 'primary', className = '', ...props }: ButtonProps) {
  return (
    <button
      className={`rounded-sm px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${variantClasses[variant]} ${className}`}
      {...props}
    />
  )
}
