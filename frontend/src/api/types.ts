/** 后端接口共享类型 */

export interface ItemOut {
  id: number
  seller_id: number
  seller_nickname: string
  seller_credit: number
  title: string
  category: string
  condition_level: string
  attrs: Record<string, unknown>
  description: string
  image_url: string
  price: number
  price_suggest_min?: number | null
  price_suggest_max?: number | null
  status: string
  status_text: string
  reject_count: number
  audit_reason: Array<{ rule?: string; detail?: string } | string>
  graph_thread_id?: string | null
  reason_text: string
  flow_status?: string
  missing?: string[]
  pending_human?: PendingHuman | null
  /** V5：AI 虚拟卖家标识（后端透传时展示 AI 徽章） */
  seller_is_ai?: boolean
}

/** 议价室自由文本 / 系统消息（FR-202） */
export interface NegotiationMessage {
  id: number
  negotiation_id: number
  from_user_id: number | null
  from_nickname: string
  from_is_ai: boolean
  kind: 'chat' | 'system' | string
  content: string
  created_at: string
}

export interface MarketItem {
  id: number
  title: string
  category: string
  condition_level: string
  price: number
  image_url: string
  seller_id: number
  seller_nickname: string
  seller_credit: number
  seller_risk: string
  match_reason: string
  /** V5：AI 虚拟卖家标识（后端透传时展示 AI 徽章） */
  seller_is_ai?: boolean
}

export interface OfferView {
  id: number
  round: number
  from_role: 'buyer' | 'seller' | 'agent'
  price: number
  basis: string
  mine: boolean
  created_at: string
}

export interface PendingHuman {
  kind: string
  node: string
  summary: string
  payload: Record<string, any>
  thread_id: string
}

export interface NegotiationView {
  id: number
  item_id: number
  item_title: string
  item_image: string
  item_price: number
  buyer_id: number
  buyer_nickname: string
  buyer_is_ai?: boolean
  seller_id: number
  seller_nickname: string
  seller_is_ai?: boolean
  /** 对方信息（FR-201，AI 徽章 / 在线态 / 人设简介） */
  counterpart_user_id?: number | null
  counterpart_nickname?: string
  counterpart_is_ai?: boolean
  counterpart_ai_persona?: string
  nash_price: number
  max_rounds: number
  deadline_seconds: number
  remaining_seconds: number
  status: 'ongoing' | 'deal' | 'terminated'
  deal_price: number | null
  order_id: number | null
  order_status: string | null
  my_role: 'buyer' | 'seller' | 'observer'
  my_reserve: number | null
  seller_risk: { tag: string; credit: number } | null
  offers: OfferView[]
  created_at: string
  closed_at: string | null
  server_note?: { price: number; would_deal: boolean; text: string }
  recommendations?: MarketItem[]
  terminate_reason?: string
  conflict_id?: number
  error?: string
  need_confirm?: boolean
}

export interface OrderView {
  id: number
  order_no: string
  item_id: number
  item_title: string
  item_image: string
  negotiation_id: number | null
  buyer_id: number
  seller_id: number
  my_role: 'buyer' | 'seller'
  counterparty_nickname: string
  counterparty_id: number
  deal_price: number
  status: string
  status_text: string
  lock_token: string | null
  graph_thread_id: string | null
  i_reviewed: boolean
  review_count: number
  pay_deadline: string | null
  created_at: string
  updated_at: string
}

export interface AgentStatusItem {
  name: string
  display_name: string
  avatar: string
  accent: string
  capabilities: string[]
  description: string
  runtime_status: 'running' | 'paused' | 'error'
  llm_mode: 'llm' | 'rule'
  msg_handled: number
  tasks_handled: number
  last_active_at: string | null
}

export interface ConflictItem {
  id: number
  scene: 'C1' | 'C2' | 'C3' | 'C4' | 'C5' | 'C6' | 'C7' | 'C8' | 'other' | string
  type: string
  level: number
  participants: string[]
  payload: Record<string, any>
  result: string
  graph_thread_id: string | null
  created_at: string
}

export interface AclMessageItem {
  id: number
  conversation_id: string
  performative: string
  sender: string
  receiver: string
  payload: Record<string, any>
  confidence: number
  error_code: string | null
  graph_thread_id: string | null
  created_at: string
}

export interface FlowInstance {
  thread_id: string
  flow: string
  stage: string
  status: 'waiting' | 'done'
  user_id: number
  business: Record<string, any>
  pending_human: PendingHuman | null
  decision_count: number
  created_at: string
}

export interface VoteDetail {
  agent: string
  agent_name: string
  weight: number
  confidence: number
  vote: number
  weighted: number
  basis: string[]
}

export interface MyAppeal {
  id: number
  order_id: number
  item_title: string
  reason: string
  status: string
  ruling: string | null
  ruling_basis: string
  judged_by: string | null
  created_at: string
  ruled_at: string | null
}
