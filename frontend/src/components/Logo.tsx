import logoMark from '../assets/logo-mark.png'

interface LogoProps {
  /** Se true mostra solo il simbolo (icona), utile per la sidebar compatta */
  iconOnly?: boolean
  className?: string
}

/**
 * Componente logo isolato: oggi punta a logo-mark.png (asset ufficiale
 * WikiScout), ma basta sostituire il file in src/assets/logo-mark.png (o
 * questo componente) per aggiornare il brand ovunque nell'app.
 */
export function Logo({ iconOnly = false, className = '' }: LogoProps) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <img src={logoMark} alt="WikiScout" className="h-8 w-8 rounded-full" />
      {!iconOnly && (
        <span className="text-lg font-medium tracking-tighter2 text-text-primary">WikiScout</span>
      )}
    </div>
  )
}
