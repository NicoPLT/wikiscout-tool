import type { ReactNode } from 'react'
import type { WatchAlertTriggerType } from '../../types/watchAlert'

function FlameIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path
        d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function BallIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="12" r="9" />
      <path
        d="M12 7l3.5 2.5-1.3 4.1H9.8L8.5 9.5 12 7zM12 3v4M4.2 9.2l3.3.3M19.8 9.2l-3.3.3M7 19.5l1.5-3.7M17 19.5l-1.5-3.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function BootIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path
        d="M5 3v7.5c0 1-.4 2-1.2 2.7L3 14v4a2 2 0 002 2h14a2 2 0 002-2c0-2.5-1.7-4-4-4.5l-4.5-1V3H5z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M5 7h7" strokeLinecap="round" />
    </svg>
  )
}

function TransferArrowIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 8h13M13 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M20 16H7M11 12l-4 4 4 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ChartSpikeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 19h16M4 19V6M4 15l4-4 3 3 6-7" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13 5h4v4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function PinIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path
        d="M12 22s7-6.4 7-12a7 7 0 10-14 0c0 5.6 7 12 7 12z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="10" r="2.5" />
    </svg>
  )
}

export interface TriggerConfigEntry {
  label: string
  color: string
  icon: ReactNode
}

export const TRIGGER_CONFIG: Record<WatchAlertTriggerType, TriggerConfigEntry> = {
  rating_streak: { label: 'Rating in serie', color: '#f97316', icon: <FlameIcon /> },
  goal_streak: { label: 'Serie di goal', color: '#6bec68', icon: <BallIcon /> },
  assist_streak: { label: 'Serie di assist', color: '#38bdf8', icon: <BootIcon /> },
  recent_transfer: { label: 'Trasferimento recente', color: '#a78bfa', icon: <TransferArrowIcon /> },
  market_value_spike: { label: 'Balzo di valore', color: '#fb7185', icon: <ChartSpikeIcon /> },
}

export const MANUAL_TRIGGER_CONFIG: TriggerConfigEntry = {
  label: 'Nota dello scout',
  color: '#eab308',
  icon: <PinIcon />,
}

export function getTriggerConfig(triggerType: WatchAlertTriggerType | null): TriggerConfigEntry {
  if (triggerType === null) return MANUAL_TRIGGER_CONFIG
  return TRIGGER_CONFIG[triggerType]
}
