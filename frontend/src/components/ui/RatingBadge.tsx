import { getRatingColor, hexToRgba } from '../../lib/ratingScale'

interface RatingBadgeProps {
  rating: number | null | undefined
  size?: 'sm' | 'md'
}

export function RatingBadge({ rating, size = 'sm' }: RatingBadgeProps) {
  if (rating === null || rating === undefined) {
    return <span className="text-text-muted">N/D</span>
  }

  const color = getRatingColor(rating)
  const sizeClass = size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'

  return (
    <span
      className={`inline-flex items-center rounded-sm font-semibold ${sizeClass}`}
      style={{ backgroundColor: hexToRgba(color, 0.18), color }}
    >
      {rating.toFixed(1)}
    </span>
  )
}
