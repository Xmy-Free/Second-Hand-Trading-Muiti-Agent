import { httpGet, httpPost } from './http'
import type {
  AclMessageItem,
  AgentStatusItem,
  ConflictItem,
  FlowInstance,
} from './types'

// ---------------- 一键全自动演示（FR-101/102/103） ----------------

export type DemoStatusValue = 'idle' | 'running' | 'completed' | 'stopped' | 'error'
export type DemoStepState = 'start' | 'done' | 'error' | string

export interface DemoStep {
  phase: string
  label: string
  state: DemoStepState
  index?: number
  count?: number
  ts: string
  thread_id?: string | null
  summary?: string
}

export interface DemoResult {
  item_id?: number | null
  item_title?: string | null
  negotiation_id?: number | null
  order_id?: number | null
  veto_thread_id?: string | null
  conflict_ids?: number[]
}

export interface DemoStatus {
  run_id: string
  status: DemoStatusValue
  phase: string
  phase_index: number
  phase_count: number
  steps: DemoStep[]
  result?: DemoResult | null
  message?: string
}

export function startDemo(): Promise<{ run_id: string; status: string }> {
  // 运行中重复启动会返回 409（信封 code=409 / HTTP 409），调用方静默改走 status
  return httpPost<{ run_id: string; status: string }>('/console/demo/start', undefined, {
    hideErrorToast: true,
  })
}

export function getDemoStatus(): Promise<DemoStatus> {
  return httpGet<DemoStatus>('/console/demo/status')
}

export function stopDemo(): Promise<{ status: string }> {
  return httpPost<{ status: string }>('/console/demo/stop')
}

/** 节点脉冲历史（环形缓冲，FR-104） */
export interface ConsoleTraceRow {
  thread_id: string
  flow: string
  node: string
  status: 'enter' | 'exit' | 'human' | 'error' | string
  summary: string
  io: Record<string, any>
  ts: string
}

export function listTraces(limit = 40): Promise<ConsoleTraceRow[]> {
  return httpGet<ConsoleTraceRow[]>(`/console/traces?limit=${limit}`)
}

export function listAgents(): Promise<AgentStatusItem[]> {
  return httpGet<AgentStatusItem[]>('/console/agents')
}

export function setAgentControl(
  name: string,
  action: 'pause' | 'resume',
): Promise<AgentStatusItem[]> {
  return httpPost<AgentStatusItem[]>(`/console/agents/${name}/${action}`)
}

export function listInstances(flow?: string): Promise<FlowInstance[]> {
  const qs = flow ? `?flow=${encodeURIComponent(flow)}` : ''
  return httpGet<FlowInstance[]>(`/console/instances${qs}`)
}

export interface InstanceTrace {
  thread_id: string
  flow: string
  status: 'waiting' | 'done'
  next: string[]
  pending_human: Record<string, any> | null
  state: Record<string, any>
}

export function getInstanceTrace(threadId: string): Promise<InstanceTrace> {
  return httpGet<InstanceTrace>(`/console/instances/${encodeURIComponent(threadId)}/trace`)
}

export function listConflicts(scene?: string): Promise<ConflictItem[]> {
  const qs = scene ? `?scene=${encodeURIComponent(scene)}` : ''
  return httpGet<ConflictItem[]>(`/console/conflicts${qs}`)
}

export function listMessages(filter: {
  conversation_id?: string
  sender?: string
  performative?: string
}): Promise<AclMessageItem[]> {
  const qs = new URLSearchParams()
  Object.entries(filter).forEach(([k, v]) => {
    if (v) qs.set(k, v)
  })
  return httpGet<AclMessageItem[]>(`/console/messages?${qs.toString()}`)
}
