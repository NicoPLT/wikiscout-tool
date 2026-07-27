import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { MarketValueTrendPoint } from '../../types/player'
import { formatCurrency, formatDate } from '../../lib/format'

interface MarketValueTrendProps {
  data: MarketValueTrendPoint[]
}

export function MarketValueTrend({ data }: MarketValueTrendProps) {
  if (data.length === 0) {
    return <p className="text-sm text-text-muted">Nessuno storico disponibile.</p>
  }

  const chartData = data.map((point) => ({
    date: point.recorded_at,
    value: point.total_value_eur,
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="marketValueFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6bec68" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#6bec68" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="date"
          tickFormatter={(v) => formatDate(v)}
          stroke="#707070"
          tick={{ fontSize: 11, fill: '#707070' }}
          axisLine={{ stroke: '#2c2c2c' }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(v) => formatCurrency(v)}
          stroke="#707070"
          tick={{ fontSize: 11, fill: '#707070' }}
          axisLine={false}
          tickLine={false}
          width={60}
        />
        <Tooltip
          contentStyle={{
            background: '#1f1f1f',
            border: '1px solid #2c2c2c',
            borderRadius: 8,
            fontSize: 12,
          }}
          labelFormatter={(v) => formatDate(v as string)}
          formatter={(value) => [formatCurrency(Number(value)), 'Valore totale']}
        />
        <Area type="monotone" dataKey="value" stroke="#6bec68" strokeWidth={2} fill="url(#marketValueFill)" />
      </AreaChart>
    </ResponsiveContainer>
  )
}
