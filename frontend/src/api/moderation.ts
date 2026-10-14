import { httpGet, httpPost } from './http'
import type { ItemOut } from './types'

export interface ReviewQueueItem {
  thread_id: string
  kind: string
  summary: string
  item: ItemOut
  reasons: Array<{ rule?: string; detail?: string }>
  confidence: number
  created_at: string
}

export function getReviewQueue(): Promise<ReviewQueueItem[]> {
  return httpGet<ReviewQueueItem[]>('/moderation/queue')
}

export function resumeFlow(
  threadId: string,
  body: { action: string; basis?: string },
): Promise<{ status: string; stage: string; item?: ItemOut }> {
  return httpPost(`/moderation/flows/${encodeURIComponent(threadId)}/resume`, body)
}

export interface AppealQueueItem {
  thread_id: string
  appeal_id: number
  reason: string
  appellant_nickname: string
  order_id: number
  order_no: string
  deal_price: number
  item_title: string
  rule_suggestion: {
    suggestion: 'uphold' | 'refund' | 'manual'
    direct: boolean
    confidence: number
    basis: string[]
  }
  evidence: Record<string, any>
  created_at: string
}

export function getAppealQueue(): Promise<AppealQueueItem[]> {
  return httpGet<AppealQueueItem[]>('/appeals/queue')
}
