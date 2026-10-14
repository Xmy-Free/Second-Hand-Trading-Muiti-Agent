import { httpGet, httpPost } from './http'
import type { NegotiationMessage, NegotiationView } from './types'

export function startNegotiation(body: {
  item_id: number
  buyer_reserve: number
  first_offer?: number | null
}): Promise<NegotiationView> {
  return httpPost<NegotiationView>('/negotiations', body)
}

export function listNegotiations(): Promise<NegotiationView[]> {
  return httpGet<NegotiationView[]>('/negotiations')
}

export function getNegotiation(id: number): Promise<NegotiationView> {
  return httpGet<NegotiationView>(`/negotiations/${id}`)
}

export function makeOffer(
  id: number,
  body: { price: number; confirm?: boolean; basis?: string | null },
): Promise<NegotiationView> {
  return httpPost<NegotiationView>(`/negotiations/${id}/offers`, body)
}

/** 议价室聊天消息（FR-202） */
export function listNegotiationMessages(id: number): Promise<NegotiationMessage[]> {
  return httpGet<NegotiationMessage[]>(`/negotiations/${id}/messages`)
}

export function sendNegotiationMessage(id: number, content: string): Promise<NegotiationMessage> {
  return httpPost<NegotiationMessage>(`/negotiations/${id}/messages`, { content })
}
