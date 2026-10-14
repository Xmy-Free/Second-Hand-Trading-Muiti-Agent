import { httpGet, httpPost } from './http'
import type { ItemOut } from './types'

export function publishItem(body: {
  title?: string
  description: string
  price?: number | null
  image_url?: string | null
}): Promise<ItemOut> {
  return httpPost<ItemOut>('/items', body)
}

export function getItem(id: number): Promise<ItemOut> {
  return httpGet<ItemOut>(`/items/${id}`)
}

export function getMyItems(status?: string): Promise<ItemOut[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : ''
  return httpGet<ItemOut[]>(`/my/items${qs}`)
}

export function resubmitItem(
  id: number,
  body: { title?: string; description: string; price?: number | null },
): Promise<ItemOut> {
  return httpPost<ItemOut>(`/items/${id}/resubmit`, body)
}

export function offShelfItem(id: number): Promise<ItemOut> {
  return httpPost<ItemOut>(`/items/${id}/off-shelf`)
}
