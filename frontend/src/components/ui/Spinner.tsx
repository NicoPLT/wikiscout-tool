interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  /** 'default': verde lime su sfondo scuro/card. 'onaccent': per spinner sopra
   * un bottone gia' verde lime (bg-accent-primary), dove il tono di default
   * sparirebbe per mancanza di contrasto. */
  tone?: 'default' | 'onaccent'
  className?: string
}

const sizeClasses: Record<NonNullable<SpinnerProps['size']>, string> = {
  sm: 'h-3.5 w-3.5 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-10 w-10 border-[3px]',
}

const toneClasses: Record<NonNullable<SpinnerProps['tone']>, string> = {
  default: 'border-border-subtle border-t-accent-primary',
  onaccent: 'border-text-onaccent/30 border-t-text-onaccent',
}

export function Spinner({ size = 'md', tone = 'default', className = '' }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label="Caricamento"
      className={`inline-block animate-spin rounded-full ${sizeClasses[size]} ${toneClasses[tone]} ${className}`}
    />
  )
}
