import { httpGet } from './http'
import type { MarketItem } from './types'

export interface SearchResult {
  items: MarketItem[]
  total: number
  suggestion: string
}

export function searchItems(params: {
  keyword?: string
  category?: string
  min_price?: number
  max_price?: number
}): Promise<SearchResult> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
  })
  return httpGet<SearchResult>(`/market/items?${qs.toString()}`)
}

export function getRecommendations(itemId: number, category?: string): Promise<SearchResult> {
  const qs = new URLSearchParams()
  if (category) qs.set('category', category)
  return httpGet<SearchResult>(`/market/recommend/${itemId}?${qs.toString()}`)
}
