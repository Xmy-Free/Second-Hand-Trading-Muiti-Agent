import { httpGet, httpPost } from './http'
import type { OrderView } from './types'

export function listOrders(role?: 'buyer' | 'seller'): Promise<OrderView[]> {
  const qs = role ? `?role=${role}` : ''
  return httpGet<OrderView[]>(`/orders${qs}`)
}

export function getOrder(id: number): Promise<OrderView> {
  return httpGet<OrderView>(`/orders/${id}`)
}

export function payOrder(id: number): Promise<OrderView> {
  return httpPost<OrderView>(`/orders/${id}/pay`)
}

export function cancelOrder(id: number): Promise<OrderView> {
  return httpPost<OrderView>(`/orders/${id}/cancel`)
}

export function deliverOrder(id: number): Promise<OrderView> {
  return httpPost<OrderView>(`/orders/${id}/deliver`)
}

export function receiveOrder(id: number): Promise<OrderView> {
  return httpPost<OrderView>(`/orders/${id}/receive`)
}

export interface OrderTimeline {
  order_id: number
  thread_id: string | null
  node_decisions: Array<Record<string, any>>
  offers: Array<{ round: number; from_role: string; price: number; basis: string }>
  audits: Array<{ actor_type: string; actor_id: string; action: string; detail: Record<string, any>; created_at: string }>
  conflicts: Array<{ scene: string; type: string; level: number; payload: Record<string, any>; result: string; created_at: string }>
}

export function getOrderTimeline(id: number): Promise<OrderTimeline> {
  return httpGet<OrderTimeline>(`/audit/orders/${id}`)
}
