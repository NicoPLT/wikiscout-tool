interface GaugeProps {
  /** Valore corrente, es. rating medio 0-10 */
  value: number
  min?: number
  max?: number
  label: string
}

const SIZE = 160
const STROKE = 14
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = Math.PI * RADIUS // semicirconferenza

export function Gauge({ value, min = 0, max = 10, label }: GaugeProps) {
  const clamped = Math.min(Math.max(value, min), max)
  const ratio = (clamped - min) / (max - min)
  const dashOffset = CIRCUMFERENCE * (1 - ratio)
  const gradientId = 'gauge-gradient'

  return (
    <div className="flex flex-col items-center">
      <svg width={SIZE} height={SIZE / 2 + STROKE} viewBox={`0 0 ${SIZE} ${SIZE / 2 + STROKE}`}>
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#3a8f38" />
            <stop offset="100%" stopColor="#6bec68" />
          </linearGradient>
        </defs>
        <path
          d={`M ${STROKE / 2} ${SIZE / 2} A ${RADIUS} ${RADIUS} 0 0 1 ${SIZE - STROKE / 2} ${SIZE / 2}`}
          fill="none"
          stroke="#2c2c2c"
          strokeWidth={STROKE}
          strokeLinecap="round"
        />
        <path
          d={`M ${STROKE / 2} ${SIZE / 2} A ${RADIUS} ${RADIUS} 0 0 1 ${SIZE - STROKE / 2} ${SIZE / 2}`}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={dashOffset}
        />
      </svg>
      <div className="-mt-8 text-center">
        <p className="metric-value text-text-primary">{clamped.toFixed(1)}</p>
        <p className="label-caption mt-1">{label}</p>
      </div>
    </div>
  )
}
