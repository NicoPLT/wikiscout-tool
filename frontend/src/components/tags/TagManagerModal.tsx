import { useState } from 'react'
import { Button } from '../ui/Button'
import { createTag, deleteTag, updateTag } from '../../lib/tagsApi'
import type { Tag } from '../../types/player'

const PALETTE = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899']

interface TagManagerModalProps {
  open: boolean
  tags: Tag[]
  onClose: () => void
  onTagsChanged: () => void
}

export function TagManagerModal({ open, tags, onClose, onTagsChanged }: TagManagerModalProps) {
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState(PALETTE[0])
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!open) return null

  async function handleCreate() {
    if (!newName.trim()) return
    setIsSaving(true)
    setError(null)
    try {
      await createTag(newName.trim(), newColor)
      setNewName('')
      onTagsChanged()
    } catch {
      setError('Esiste gia\' un tag con questo nome.')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleColorChange(tag: Tag, color: string) {
    await updateTag(tag.id, { color })
    onTagsChanged()
  }

  async function handleDelete(tag: Tag) {
    await deleteTag(tag.id)
    onTagsChanged()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="w-full max-w-md rounded-card border border-border-subtle bg-bg-surface p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <h3 className="text-lg text-text-primary">Gestisci tag</h3>
        <p className="mt-1 text-sm text-text-secondary">
          Crea tag colorati da assegnare ai giocatori: la riga in dashboard viene evidenziata col colore del tag.
        </p>

        <div className="mt-4 flex max-h-56 flex-col gap-2 overflow-y-auto">
          {tags.length === 0 && <p className="text-sm text-text-muted">Nessun tag ancora creato.</p>}
          {tags.map((tag) => (
            <div
              key={tag.id}
              className="flex items-center justify-between gap-2 rounded-sm border border-border-subtle px-3 py-2"
            >
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={tag.color}
                  onChange={(e) => handleColorChange(tag, e.target.value)}
                  className="h-6 w-6 cursor-pointer rounded-sm border border-border-subtle bg-transparent"
                  aria-label={`Colore per ${tag.name}`}
                />
                <span className="text-sm text-text-primary">{tag.name}</span>
              </div>
              <button
                onClick={() => handleDelete(tag)}
                className="rounded-sm px-2 py-1 text-xs font-medium text-text-muted hover:bg-danger/10 hover:text-danger"
              >
                Elimina
              </button>
            </div>
          ))}
        </div>

        <div className="mt-5 border-t border-border-subtle pt-4">
          <p className="label-caption mb-2">Nuovo tag</p>
          <div className="flex items-center gap-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Nome tag (es. Priorita alta)"
              className="flex-1 rounded-md border border-border-subtle bg-bg-surface-hover px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none"
            />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {PALETTE.map((color) => (
              <button
                key={color}
                onClick={() => setNewColor(color)}
                className={`h-6 w-6 rounded-full ${newColor === color ? 'ring-2 ring-text-primary ring-offset-2 ring-offset-bg-surface' : ''}`}
                style={{ backgroundColor: color }}
                aria-label={`Seleziona colore ${color}`}
              />
            ))}
          </div>
          {error && <p className="mt-2 text-xs text-danger">{error}</p>}
          <div className="mt-4 flex justify-end gap-3">
            <Button variant="ghost" onClick={onClose}>
              Chiudi
            </Button>
            <Button onClick={handleCreate} disabled={isSaving || !newName.trim()}>
              {isSaving ? 'Creazione...' : 'Crea tag'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
