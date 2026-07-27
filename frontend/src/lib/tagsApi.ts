import { api } from './api'
import type { Tag } from '../types/player'

export async function fetchTags(): Promise<Tag[]> {
  const { data } = await api.get<Tag[]>('/api/tags')
  return data
}

export async function createTag(name: string, color: string): Promise<Tag> {
  const { data } = await api.post<Tag>('/api/tags', { name, color })
  return data
}

export async function updateTag(tagId: number, updates: { name?: string; color?: string }): Promise<Tag> {
  const { data } = await api.patch<Tag>(`/api/tags/${tagId}`, updates)
  return data
}

export async function deleteTag(tagId: number): Promise<void> {
  await api.delete(`/api/tags/${tagId}`)
}

export async function assignPlayerTag(playerId: number, tagId: number | null): Promise<void> {
  await api.patch(`/api/players/${playerId}/tag`, { tag_id: tagId })
}
