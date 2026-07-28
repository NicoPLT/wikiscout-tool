import { useState, type ChangeEvent } from 'react'
import { createTag } from '../../lib/tagsApi'
import { hexToRgba } from '../../lib/ratingScale'
import type { Tag } from '../../types/player'

const PALETTE = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899']
const NEW_TAG_VALUE = '__new__'

interface TagSelectProps {
  value: Tag | null
  tags: Tag[]
  onAssign: (tagId: number | null) => void | Promise<void>
  onTagCreated: (tag: Tag) => void
  className?: string
}

export function TagSelect({ value, tags, onAssign, onTagCreated, className }: TagSelectProps) {
  const [isCreating, setIsCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState(PALETTE[0])
  const [error, setError] = useState<string | null>(null)

  async function handleChange(e: ChangeEvent<HTMLSelectElement>) {
    const raw = e.target.value
    if (raw === NEW_TAG_VALUE) {
      setIsCreating(true)
      return
    }
    await onAssign(raw === '' ? null : Number(raw))
  }

  async function handleCreate() {
    if (!newName.trim()) return
    setError(null)
    try {
      const tag = await createTag(newName.trim(), newColor)
      onTagCreated(tag)
      await onAssign(tag.id)
      setIsCreating(false)
      setNewName('')
    } catch {
      setError("Esiste gia' un tag con questo nome.")
    }
  }

  function handleCancel() {
    setIsCreating(false)
    setNewName('')
    setError(null)
  }

  if (isCreating) {
    return (
      <div
        className={`flex flex-wrap items-center gap-2 ${className ?? ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        <input
          autoFocus
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Nome nuovo tag"
          className="h-7 min-w-[120px] rounded-sm border border-border-subtle bg-bg-surface-hover px-2 text-xs text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none"
        />
        <div className="flex items-center gap-1">
          {PALETTE.map((color) => (
            <button
              key={color}
              type="button"
              onClick={() => setNewColor(color)}
              className={`h-5 w-5 rounded-full ${newColor === color ? 'ring-2 ring-text-primary ring-offset-1 ring-offset-bg-surface' : ''}`}
              style={{ backgroundColor: color }}
              aria-label={`Seleziona colore ${color}`}
            />
          ))}
        </div>
        <button
          type="button"
          onClick={handleCreate}
          disabled={!newName.trim()}
          className="rounded-sm bg-accent-primary px-2 py-1 text-xs font-medium text-bg-base disabled:opacity-50"
        >
          Crea
        </button>
        <button
          type="button"
          onClick={handleCancel}
          className="text-xs text-text-muted hover:text-text-primary"
        >
          Annulla
        </button>
        {error && <span className="text-xs text-danger">{error}</span>}
      </div>
    )
  }

  return (
    <select
      value={value?.id ?? ''}
      onChange={handleChange}
      onClick={(e) => e.stopPropagation()}
      className={`h-7 rounded-sm border-0 bg-bg-surface-hover px-2 text-xs font-medium focus:outline-none ${className ?? ''}`}
      style={value ? { backgroundColor: hexToRgba(value.color, 0.2), color: value.color } : undefined}
    >
      <option value="">Nessun tag</option>
      {tags.map((tag) => (
        <option key={tag.id} value={tag.id}>
          {tag.name}
        </option>
      ))}
      <option value={NEW_TAG_VALUE}>+ Crea nuovo tag...</option>
    </select>
  )
}
