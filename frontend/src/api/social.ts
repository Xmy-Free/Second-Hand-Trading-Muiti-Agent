import { httpGet, httpPost } from './http'
import type { MyAppeal } from './types'

export interface ReviewPayload {
  order_id: number
  score: number
  content?: string
}

export function submitReview(body: ReviewPayload): Promise<{
  ok?: boolean
  summary: string
  credit_delta: number
}> {
  return httpPost('/reviews', body)
}

export interface ReceivedReview {
  id: number
  order_id: number
  item_title: string
  score: number
  content: string
  from_nickname: string
  created_at: string
}

export function getReceivedReviews(): Promise<ReceivedReview[]> {
  return httpGet<ReceivedReview[]>('/reviews/received')
}

export interface CreditInfo {
  credit_score: number
  risk_tag: string
  deal_count: number
  review_count: number
  changes: Array<{ delta: number; reason: string; new_score: number; created_at: string }>
}

export function getMyCredit(): Promise<CreditInfo> {
  return httpGet<CreditInfo>('/credit/me')
}

export interface AppealSubmitResult {
  appeal_id: number
  thread_id: string
  status: string
  pending_human: Record<string, any> | null
  stage: string
  rule?: {
    suggestion: 'uphold' | 'refund' | 'manual'
    direct: boolean
    confidence: number
    basis: string[]
  }
}

export function submitAppeal(body: { order_id: number; reason: string }): Promise<AppealSubmitResult> {
  return httpPost('/appeals', body)
}

export function listMyAppeals(): Promise<MyAppeal[]> {
  return httpGet<MyAppeal[]>('/appeals/mine')
}
