/**
 * Mission Control 指挥中心 · 共享数据层（模块级单例）
 * - REST 预加载（agents / instances / trace / conflicts / messages）
 * - WebSocket 帧分发（message / node_trace / counter / agent_status / conflict）
 * - 跨 Tab 共享选中实例与跳转意图
 */
import { computed, reactive, ref } from 'vue'
import type { Component } from 'vue'
import { ElMessage } from 'element-plus'
import WorkflowIcon from '~icons/lucide/workflow'
import UserRoundIcon from '~icons/lucide/user-round'
import PackageIcon from '~icons/lucide/package'
import ShieldAlertIcon from '~icons/lucide/shield-alert'
import SearchCheckIcon from '~icons/lucide/search-check'
import MessagesSquareIcon from '~icons/lucide/messages-square'
import ClipboardListIcon from '~icons/lucide/clipboard-list'
import BadgeCheckIcon from '~icons/lucide/badge-check'
import GavelIcon from '~icons/lucide/gavel'
// 兼容旧 4 Agent 注册名的图标兜底
import PackageCheckIcon from '~icons/lucide/package-check'
import HandshakeIcon from '~icons/lucide/handshake'
import ShieldCheckIcon from '~icons/lucide/shield-check'
import BotIcon from '~icons/lucide/bot'
import { activeTheme } from '@/composables/useTheme'
import {
  getDemoStatus,
  getInstanceTrace,
  listAgents,
  listConflicts,
  listInstances,
  listMessages,
  listTraces,
  setAgentControl,
  startDemo as apiStartDemo,
  stopDemo as apiStopDemo,
} from '@/api/console'
import type {
  DemoResult,
  DemoStatus,
  DemoStatusValue,
  DemoStep,
} from '@/api/console'
import type { InstanceTrace } from '@/api/console'
import type {
  AclMessageItem,
  AgentStatusItem,
  ConflictItem,
  FlowInstance,
} from '@/api/types'

// ---------------------------------------------------------------- 元数据

export interface AgentMeta {
  icon: Component
  accent: string
  en: string
  label: string
}

/** 9 大角色元信息（与后端注册名一致） */
const AGENT_META: Record<string, AgentMeta> = {
  coordinator: { icon: WorkflowIcon, accent: '#818CF8', en: 'Coordinator', label: '协调管理' },
  user_agent: { icon: UserRoundIcon, accent: '#60A5FA', en: 'User Agent', label: '用户代理' },
  commodity: { icon: PackageIcon, accent: '#34D399', en: 'Commodity', label: '商品管理' },
  moderation: { icon: ShieldAlertIcon, accent: '#F87171', en: 'Moderation', label: '内容审核' },
  search: { icon: SearchCheckIcon, accent: '#22D3EE', en: 'Search', label: '搜索推荐' },
  negotiation: { icon: MessagesSquareIcon, accent: '#818CF8', en: 'Negotiation', label: '议价谈判' },
  order: { icon: ClipboardListIcon, accent: '#FBBF24', en: 'Order', label: '交易履约' },
  credit: { icon: BadgeCheckIcon, accent: '#F472B6', en: 'Credit', label: '信用评价' },
  arbitrator: { icon: GavelIcon, accent: '#FB923C', en: 'Arbitrator', label: '纠纷仲裁' },
  // 旧注册名兼容（后端升级前后均不写死）
  goods: { icon: PackageCheckIcon, accent: '#34D399', en: 'Goods Moderator', label: '商品审核' },
  trade: { icon: HandshakeIcon, accent: '#22D3EE', en: 'Trade Negotiator', label: '交易撮合' },
  order_credit: { icon: ShieldCheckIcon, accent: '#FBBF24', en: 'Order & Credit', label: '履约信用' },
}

const FALLBACK_META: AgentMeta = { icon: BotIcon, accent: '#818CF8', en: '', label: '' }

export function agentMeta(name: string): AgentMeta {
  const meta = AGENT_META[name]
  if (meta) return meta
  return { ...FALLBACK_META, en: name, label: name }
}

/** 9 大角色注册名（展示与筛选顺序）；旧名仅保留在 AGENT_META 中作图标兜底 */
const PRIMARY_AGENTS = [
  'coordinator',
  'user_agent',
  'commodity',
  'moderation',
  'search',
  'negotiation',
  'order',
  'credit',
  'arbitrator',
]

/** 消息总线筛选用 Agent 选项（由 9 大角色元数据驱动） */
export const AGENT_OPTIONS = PRIMARY_AGENTS.map((value) => ({
  value,
  label: AGENT_META[value].label,
}))

/** 按当前主题取色（深色用霓虹 400 色阶，浅色用 600 色阶保证对比度） */
function themed(dark: string, light: string): string {
  return activeTheme.value === 'light' ? light : dark
}

export const PERFORMATIVES = [
  'request',
  'inform',
  'propose',
  'accept',
  'reject',
  'refuse',
  'arbitrate',
  'veto',
  'interrupt',
] as const

const PERF_COLORS: Record<string, { dark: string; light: string; glow?: boolean }> = {
  request: { dark: '#60a5fa', light: '#2563eb' },
  inform: { dark: '#34d399', light: '#059669' },
  propose: { dark: '#22d3ee', light: '#0891b2' },
  accept: { dark: '#fbbf24', light: '#d97706' },
  reject: { dark: '#94a3b8', light: '#64748b' },
  refuse: { dark: '#fb7185', light: '#e11d48' },
  arbitrate: { dark: '#c084fc', light: '#7c3aed' },
  veto: { dark: '#f43f5e', light: '#e11d48', glow: true },
  interrupt: { dark: '#fb923c', light: '#ea580c' },
}

export function perfMeta(perf: string): { color: string; label: string; glow?: boolean } {
  const c = PERF_COLORS[perf]
  if (!c) return { color: themed('#8b98bd', '#64748b'), label: perf }
  return { color: themed(c.dark, c.light), label: perf, glow: c.glow }
}

const FLOW_COLORS: Record<string, { dark: string; light: string }> = {
  publish: { dark: '#34d399', light: '#059669' },
  trade: { dark: '#22d3ee', light: '#0891b2' },
  appeal: { dark: '#c084fc', light: '#7c3aed' },
  demo: { dark: '#818cf8', light: '#4f46e5' },
}

const FLOW_LABELS: Record<string, string> = {
  publish: '发布审核',
  trade: '交易支付',
  appeal: '纠纷申诉',
  demo: '演示流',
}

export function flowMeta(flow: string): { label: string; color: string } {
  const label = FLOW_LABELS[flow] ?? flow
  const c = FLOW_COLORS[flow]
  return { label, color: c ? themed(c.dark, c.light) : themed('#8b98bd', '#64748b') }
}

/** 实例筛选流类型（由 FLOW_LABELS 驱动） */
export const FLOW_FILTERS = Object.entries(FLOW_LABELS).map(([value, label]) => ({ value, label }))

interface SceneMetaDef {
  label: string
  short: string
  sub: string
  dark: string
  light: string
}

/** C1–C8 八类冲突（与 spec 8.5 处置要点对齐） */
const SCENE_DEFS: Record<string, SceneMetaDef> = {
  C1: { label: 'C1 · 目标冲突', short: '议价僵持', sub: '互让未达 / 纳什参考', dark: '#22d3ee', light: '#0891b2' },
  C2: { label: 'C2 · 资源冲突', short: '并发抢单', sub: '预占锁 · 三优先裁决', dark: '#fbbf24', light: '#d97706' },
  C3: { label: 'C3 · 决策冲突', short: '驳回申诉', sub: '解释补材料 / 规则复核', dark: '#a78bfa', light: '#7c3aed' },
  C4: { label: 'C4 · 纠纷冲突', short: '货不对板', sub: '证据链裁决 / 信用扣罚', dark: '#fb923c', light: '#ea580c' },
  C5: { label: 'C5 · 目标冲突', short: '推荐偏差', sub: '效用比较 / 要求重排', dark: '#60a5fa', light: '#2563eb' },
  C6: { label: 'C6 · 意见冲突', short: '风险投票', sub: '三方加权投票', dark: '#c084fc', light: '#9333ea' },
  C7: { label: 'C7 · 信息冲突', short: '状态纠偏', sub: 'SSOT 自动纠正', dark: '#2dd4bf', light: '#0d9488' },
  C8: { label: 'C8 · 安全冲突', short: '安全否决', sub: '欺诈违禁 / 一票否决', dark: '#fb7185', light: '#e11d48' },
  other: { label: '其他冲突', short: '其他', sub: '扩展场景', dark: '#8b98bd', light: '#64748b' },
}

export function sceneMeta(scene: string): { label: string; short: string; sub: string; color: string } {
  const def = SCENE_DEFS[scene] ?? SCENE_DEFS.other
  return { label: def.label, short: def.short, sub: def.sub, color: themed(def.dark, def.light) }
}

// ---------------------------------------------------------------- 编排图文案

export const GRAPH_NODE_LABELS: Record<string, string> = {
  goods_structure: '商品结构化',
  goods_moderate: '商品审核',
  human_review_gate: '人工复核门',
  veto_gate: '安全否决门',
  order_lock: '预占锁建单',
  risk_check: '风险评估',
  weighted_vote: '加权投票',
  risk_human_gate: '风险终裁门',
  wait_payment_gate: '等待支付门',
  sandbox_pay: '沙箱支付',
  cancel_order: '取消订单',
  appeal_evidence: '证据汇总',
  appeal_rule: '规则裁决',
  appeal_human_gate: '纠纷终裁门',
  apply_ruling: '执行裁决',
  demo_submit: '演示提交',
  demo_human_gate: '演示人工门',
}

export function nodeLabel(node: string): string {
  return GRAPH_NODE_LABELS[node] ?? node
}

const RESULT_TEXT: Record<string, string> = {
  ok: '完成',
  locked: '已锁定',
  structured: '已结构化',
  need_info: '信息不足待补充',
  approve: '通过',
  reject: '驳回',
  veto: '安全否决',
  frozen: '维持冻结',
  unfreeze: '解除冻结',
  maintain: '维持冻结',
  manual: '转人工处理',
  allow: '放行',
  block: '拦截',
  canceled: '已取消',
  paid: '支付成功',
  expired: '支付超时',
  failed: '失败',
  conflict: '锁冲突',
  agent_paused: 'Agent 已暂停',
  evidence_built: '证据已汇总',
  refund: '裁决退款',
  uphold: '维持交易',
  received: '已受理',
  pay: '完成支付',
}

export function resultText(result: unknown): string {
  if (result === null || result === undefined || result === '') return '—'
  return RESULT_TEXT[String(result)] ?? String(result)
}

/** state.decisions[].node → 图节点 id 别名（历史代码中决策名与节点名不完全一致） */
export const DECISION_NODE_ALIAS: Record<string, string> = {
  structure: 'goods_structure',
  moderate: 'goods_moderate',
  human_review: 'human_review_gate',
  submit: 'demo_submit',
  human: 'demo_human_gate',
}

export const BAD_RESULTS = new Set([
  'reject',
  'veto',
  'frozen',
  'maintain',
  'block',
  'canceled',
  'expired',
  'failed',
  'conflict',
  'agent_paused',
])

export const WARN_RESULTS = new Set(['need_info', 'manual'])

// ---------------------------------------------------------------- 时间工具

/** 后端时间戳多为 naive UTC（无 Z 后缀），统一按 UTC 解析 */
function parseDate(iso: string): Date {
  const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`
  return new Date(normalized)
}

export function fmtClock(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = parseDate(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = parseDate(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

export function fmtRelative(iso: string | null | undefined, now: number): string {
  if (!iso) return '从未活动'
  const t = parseDate(iso).getTime()
  if (Number.isNaN(t)) return '—'
  const diff = Math.max(0, now - t)
  const s = Math.floor(diff / 1000)
  if (s < 5) return '刚刚'
  if (s < 60) return `${s} 秒前`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m} 分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} 小时前`
  return `${Math.floor(h / 24)} 天前`
}

// ---------------------------------------------------------------- 帧类型

export interface BusMessage {
  id: string | number
  conversation_id: string
  performative: string
  sender: string
  receiver: string
  payload: Record<string, any>
  confidence: number
  error_code: string | null
  graph_thread_id: string | null
  created_at: string
  summary: string
  isLive: boolean
}

export interface NodeTraceEvent {
  thread_id: string
  flow: string
  node: string
  status: 'enter' | 'exit' | 'human' | 'error' | string
  summary: string
  io: Record<string, any>
  ts: string
}

interface ConsoleFrame {
  type:
    | 'message'
    | 'node_trace'
    | 'counter'
    | 'agent_status'
    | 'conflict'
    | 'demo_phase'
    | 'connected'
  data: any
  ts?: string
}

// ---------------------------------------------------------------- 单例状态

const agents = ref<AgentStatusItem[]>([])
const agentsLoading = ref(false)
const agentsBusy = ref<string | null>(null)

const instances = ref<FlowInstance[]>([])
const instancesLoading = ref(false)
const selectedThreadId = ref<string>('')

const traceLoading = ref(false)
const traceMap = ref<Record<string, InstanceTrace>>({})

const conflicts = ref<ConflictItem[]>([])
const conflictsLoading = ref(false)

const messages = ref<BusMessage[]>([])
const messagesLoading = ref(false)
const msgFilter = ref({ sender: '', receiver: '', performative: '', conversationId: '' })

const liveMessages = ref<BusMessage[]>([])
const liveTraces = ref<NodeTraceEvent[]>([])

const connected = ref(false)
const nowTick = ref(Date.now())

export function setConnected(v: boolean): void {
  connected.value = v
}
const activeTab = ref<'overview' | 'orchestration' | 'messages' | 'blackboard' | 'conflicts'>(
  'overview',
)

const LIVE_MSG_CAP = 300
const LIVE_TRACE_CAP = 40

let tickTimer: number | undefined
let instanceRefreshTimer: number | undefined
let traceRefreshTimer: number | undefined
let demoPollTimer: number | undefined
let liveSeq = 0

// ---------------------------------------------------------------- 一键演示状态

/** 剧场时间线条目（由后端 steps / demo_phase 帧归并） */
export interface DemoStepView {
  phase: string
  label: string
  /** pending 未开始 / active 进行中 / done 完成 / error 失败 */
  state: 'pending' | 'active' | 'done' | 'error'
  index: number
  summary: string
  threadId: string | null
  ts: string
}

export interface DemoStore {
  runId: string
  status: DemoStatusValue
  phase: string
  phaseIndex: number
  phaseCount: number
  steps: DemoStepView[]
  result: DemoResult | null
  message: string
  starting: boolean
  stopping: boolean
}

const demo = reactive<DemoStore>({
  runId: '',
  status: 'idle',
  phase: '',
  phaseIndex: 0,
  phaseCount: 8,
  steps: [],
  result: null,
  message: '',
  starting: false,
  stopping: false,
})

const demoRunning = computed(() => demo.status === 'running')

/** 本次运行是否已自动切换过「编排追踪」（每个 run 仅强切一次，避免打断用户回看） */
let demoAutoSwitchedRun = ''

/** 脉冲去重（历史 traces 与 WS node_trace 同源，按业务键去重） */
const traceKeySet = new Set<string>()

function traceKey(t: NodeTraceEvent): string {
  return `${t.thread_id}|${t.node}|${t.status}|${t.ts}`
}

function pushLiveTrace(t: NodeTraceEvent): void {
  const key = traceKey(t)
  if (traceKeySet.has(key)) return
  traceKeySet.add(key)
  liveTraces.value = [t, ...liveTraces.value].slice(0, LIVE_TRACE_CAP)
}

/** GET /traces 历史预填（与实时帧合并去重，按时间倒序） */
async function loadRecentTraces(): Promise<void> {
  try {
    const rows = await listTraces(40)
    if (!rows.length) return
    const merged = [...liveTraces.value]
    rows.forEach((r) => {
      const t = r as NodeTraceEvent
      const key = traceKey(t)
      if (!traceKeySet.has(key)) {
        traceKeySet.add(key)
        merged.push(t)
      }
    })
    merged.sort((a, b) => (a.ts < b.ts ? 1 : a.ts > b.ts ? -1 : 0))
    liveTraces.value = merged.slice(0, LIVE_TRACE_CAP)
  } catch {
    /* 历史预填失败不影响实时通道 */
  }
}

function emptySteps(count: number): DemoStepView[] {
  return Array.from({ length: count }, (_, i) => ({
    phase: '',
    label: `阶段 ${i + 1}`,
    state: 'pending',
    index: i + 1,
    summary: '',
    threadId: null,
    ts: '',
  }))
}

/** 后端快照 → 剧场状态（steps 中同一阶段 start/done 两条记录需归并） */
function applyDemoSnapshot(s: DemoStatus): void {
  demo.runId = s.run_id || demo.runId
  demo.status = s.status
  demo.phase = s.phase || ''
  demo.phaseIndex = s.phase_index || 0
  demo.phaseCount = s.phase_count || s.steps?.length || demo.phaseCount || 8
  demo.result = (s.result as DemoResult) ?? null
  demo.message = s.message || ''

  const steps = emptySteps(demo.phaseCount)
  const byIndex = new Map<number, DemoStep>()
  ;(s.steps || []).forEach((step) => {
    const idx = step.index ?? byIndex.size + 1
    const prev = byIndex.get(idx)
    // 同一阶段 start 后到 done：后者覆盖；error 优先
    if (!prev || step.state === 'done' || step.state === 'error') byIndex.set(idx, step)
  })
  byIndex.forEach((rec, idx) => {
    const slot = steps[idx - 1]
    if (!slot) return
    slot.phase = rec.phase
    slot.label = rec.label || slot.label
    slot.summary = rec.summary || ''
    slot.threadId = rec.thread_id ?? null
    slot.ts = rec.ts || ''
    slot.state = rec.state === 'error' ? 'error' : rec.state === 'done' ? 'done' : 'active'
  })
  // 运行中：当前阶段若无记录则呼吸高亮；补全前序阶段为完成
  if (demo.status === 'running' && demo.phaseIndex > 0) {
    steps.forEach((step, i) => {
      if (i + 1 < demo.phaseIndex && step.state === 'pending') step.state = 'done'
      if (i + 1 === demo.phaseIndex && step.state === 'pending') step.state = 'active'
    })
  }
  demo.steps = steps
  scheduleDemoPolling()
}

async function fetchDemoStatus(): Promise<void> {
  try {
    applyDemoSnapshot(await getDemoStatus())
  } catch {
    /* 状态查询失败不打扰用户，下一帧 / 下次轮询继续 */
  }
}

function scheduleDemoPolling(): void {
  if (demoPollTimer !== undefined) window.clearInterval(demoPollTimer)
  if (demo.status !== 'running') {
    demoPollTimer = undefined
    return
  }
  // WS 为主、轮询兜底：页面挂后台 / 丢帧时仍可收敛状态
  demoPollTimer = window.setInterval(() => void fetchDemoStatus(), 4000)
}

/** 演示阶段帧 → 剧场时间线 */
function applyDemoFrame(d: Record<string, any>): void {
  const runId: string = d.run_id || demo.runId
  if (runId && runId !== demo.runId) {
    demo.runId = runId
    demo.result = null
    demo.message = ''
    demoAutoSwitchedRun = ''
  }
  // 停止 / 异常后的收尾帧不回改状态（权威状态以 status 快照为准）
  if (demo.status === 'idle' || demo.status === 'running') {
    demo.status = 'running'
  }
  const count = Number(d.count) || demo.phaseCount || 8
  const index = Number(d.index) || 0
  if (!demo.steps.length || demo.phaseCount !== count) {
    demo.phaseCount = count
    demo.steps = emptySteps(count)
  }
  demo.phase = d.phase || demo.phase
  demo.phaseIndex = index
  const slot = demo.steps[index - 1]
  if (slot) {
    slot.phase = d.phase || slot.phase
    slot.label = d.label || slot.label
    slot.threadId = d.thread_id ?? slot.threadId
    if (d.ts) slot.ts = d.ts
    if (d.summary) slot.summary = d.summary
    if (d.state === 'error') slot.state = 'error'
    else if (d.state === 'done') slot.state = 'done'
    else {
      slot.state = 'active'
      // 新阶段开始时，把仍停在 active 的前序阶段收口为完成
      demo.steps.forEach((s, i) => {
        if (i < index - 1 && s.state !== 'error') s.state = 'done'
      })
    }
  }
  if (d.thread_id) followDemoThread(String(d.thread_id), runId)
  scheduleDemoPolling()
}

/** 选中演示阶段关联的编排实例；每个 run 仅自动强切一次标签 */
function followDemoThread(threadId: string, runId: string): void {
  selectedThreadId.value = threadId
  void loadTrace(threadId)
  scheduleInstanceRefresh()
  if (demoAutoSwitchedRun !== runId) {
    demoAutoSwitchedRun = runId
    activeTab.value = 'orchestration'
  }
}

async function startDemo(): Promise<void> {
  if (demo.starting || demo.status === 'running') return
  demo.starting = true
  try {
    const r = await apiStartDemo()
    demo.runId = r.run_id
    demo.status = 'running'
    demo.phase = ''
    demo.phaseIndex = 0
    demo.steps = emptySteps(demo.phaseCount)
    demo.result = null
    demo.message = ''
    demoAutoSwitchedRun = ''
    scheduleDemoPolling()
  } catch (err: any) {
    // 运行中再启动 → HTTP 409：静默读取当前进度，不视为错误
    const httpStatus = err?.response?.status
    const bizCode = err?.code
    if (httpStatus === 409 || String(bizCode) === '409') {
      await fetchDemoStatus()
    } else {
      ElMessage.error('一键演示启动失败，请确认后端服务与管理员登录状态后重试')
    }
  } finally {
    demo.starting = false
  }
}

async function stopDemo(): Promise<void> {
  if (demo.stopping || demo.status !== 'running') return
  demo.stopping = true
  try {
    await apiStopDemo()
    await fetchDemoStatus()
  } catch {
    /* 全局拦截器已提示 */
  } finally {
    demo.stopping = false
  }
}


const runningCount = computed(
  () => agents.value.filter((a) => a.runtime_status === 'running').length,
)
const totalMessages = computed(() =>
  agents.value.reduce((sum, a) => sum + (a.msg_handled || 0), 0),
)
const totalTasks = computed(() =>
  agents.value.reduce((sum, a) => sum + (a.tasks_handled || 0), 0),
)
const waitingCount = computed(
  () => instances.value.filter((i) => i.status === 'waiting').length,
)
const currentTrace = computed<InstanceTrace | null>(
  () => (selectedThreadId.value && traceMap.value[selectedThreadId.value]) || null,
)

// ---------------------------------------------------------------- 动作

async function loadAgents(): Promise<void> {
  agentsLoading.value = true
  try {
    agents.value = await listAgents()
  } finally {
    agentsLoading.value = false
  }
}

async function toggleAgent(agent: AgentStatusItem, toPause: boolean): Promise<boolean> {
  agentsBusy.value = agent.name
  try {
    agents.value = await setAgentControl(agent.name, toPause ? 'pause' : 'resume')
    return true
  } catch {
    return false
  } finally {
    agentsBusy.value = null
  }
}

async function loadInstances(): Promise<void> {
  instancesLoading.value = true
  try {
    const rows = await listInstances()
    instances.value = rows
    if (!selectedThreadId.value && rows.length) {
      const preferred = rows.find((r) => r.status === 'waiting') ?? rows[0]
      selectedThreadId.value = preferred.thread_id
    } else if (selectedThreadId.value && !rows.some((r) => r.thread_id === selectedThreadId.value)) {
      selectedThreadId.value = rows[0]?.thread_id ?? ''
    }
  } finally {
    instancesLoading.value = false
  }
}

async function loadTrace(threadId: string): Promise<void> {
  if (!threadId) return
  traceLoading.value = true
  try {
    const trace = await getInstanceTrace(threadId)
    traceMap.value = { ...traceMap.value, [threadId]: trace }
  } catch {
    /* 错误提示由 http 层处理 */
  } finally {
    traceLoading.value = false
  }
}

function selectThread(threadId: string): void {
  selectedThreadId.value = threadId
}

function jumpThread(threadId: string): void {
  selectedThreadId.value = threadId
  activeTab.value = 'orchestration'
}

async function loadConflicts(): Promise<void> {
  conflictsLoading.value = true
  try {
    conflicts.value = await listConflicts()
  } finally {
    conflictsLoading.value = false
  }
}

function messageSummary(payload: Record<string, any> | undefined | null): string {
  if (!payload) return ''
  if (typeof payload.summary === 'string') return payload.summary
  if (typeof payload.reason === 'string') return payload.reason
  if (typeof payload.action === 'string') return `action: ${payload.action}`
  if (typeof payload.text === 'string') return payload.text
  return ''
}

async function loadMessages(): Promise<void> {
  messagesLoading.value = true
  try {
    const f = msgFilter.value
    const rows = await listMessages({
      conversation_id: f.conversationId || undefined,
      sender: f.sender || undefined,
      performative: f.performative || undefined,
    })
    messages.value = rows.map((m: AclMessageItem) => ({
      ...m,
      summary: messageSummary(m.payload),
      isLive: false,
    }))
  } finally {
    messagesLoading.value = false
  }
}

function scheduleInstanceRefresh(): void {
  if (instanceRefreshTimer) window.clearTimeout(instanceRefreshTimer)
  instanceRefreshTimer = window.setTimeout(() => void loadInstances(), 800)
}

function scheduleTraceRefresh(threadId: string): void {
  if (threadId !== selectedThreadId.value) return
  if (traceRefreshTimer) window.clearTimeout(traceRefreshTimer)
  traceRefreshTimer = window.setTimeout(() => void loadTrace(threadId), 600)
}

// ---------------------------------------------------------------- WS 分发

function handleFrame(frame: ConsoleFrame): void {
  if (!frame || !frame.type) return
  const ts = frame.ts ?? new Date().toISOString()
  switch (frame.type) {
    case 'message': {
      const d = frame.data ?? {}
      liveMessages.value = [
        {
          id: `live-${(d.msg_id as string) ?? ++liveSeq}`,
          conversation_id: d.conversation_id ?? '',
          performative: d.performative ?? '',
          sender: d.sender ?? '',
          receiver: d.receiver ?? '',
          payload: d.payload ?? {},
          confidence: typeof d.confidence === 'number' ? d.confidence : 0,
          error_code: d.error_code ?? null,
          graph_thread_id: d.graph_thread_id ?? null,
          created_at: ts,
          summary: typeof d.summary === 'string' ? d.summary : messageSummary(d.payload),
          isLive: true,
        },
        ...liveMessages.value,
      ].slice(0, LIVE_MSG_CAP)
      break
    }
    case 'node_trace': {
      pushLiveTrace({ ...(frame.data ?? {}), ts } as NodeTraceEvent)
      if (frame.data?.thread_id) {
        scheduleTraceRefresh(frame.data.thread_id)
        scheduleInstanceRefresh()
      }
      break
    }
    case 'counter': {
      const d = frame.data ?? {}
      const idx = agents.value.findIndex((a) => a.name === d.agent)
      if (idx >= 0) {
        const next = agents.value.slice()
        next[idx] = {
          ...next[idx],
          msg_handled: d.msg_handled ?? next[idx].msg_handled,
          tasks_handled: d.tasks_handled ?? next[idx].tasks_handled,
          last_active_at: d.last_active_at ?? next[idx].last_active_at,
        }
        agents.value = next
      }
      break
    }
    case 'agent_status': {
      const snap = frame.data as AgentStatusItem
      if (!snap?.name) break
      const idx = agents.value.findIndex((a) => a.name === snap.name)
      if (idx >= 0) {
        const next = agents.value.slice()
        next[idx] = { ...next[idx], ...snap }
        agents.value = next
      } else {
        agents.value = [...agents.value, snap]
      }
      break
    }
    case 'conflict': {
      const item = frame.data as ConflictItem
      if (item && !conflicts.value.some((c) => c.id === item.id)) {
        conflicts.value = [item, ...conflicts.value].slice(0, 200)
      }
      break
    }
    case 'demo_phase': {
      applyDemoFrame(frame.data ?? {})
      break
    }
    case 'connected':
      break
    default:
      // 未知帧类型忽略，不报错（WS 前向兼容）
      break
  }
}

function startTicker(): void {
  if (tickTimer !== undefined) return
  tickTimer = window.setInterval(() => {
    nowTick.value = Date.now()
  }, 30_000)
}

export function useConsoleData() {
  return {
    // state
    agents,
    agentsLoading,
    agentsBusy,
    instances,
    instancesLoading,
    selectedThreadId,
    traceLoading,
    traceMap,
    currentTrace,
    conflicts,
    conflictsLoading,
    messages,
    messagesLoading,
    msgFilter,
    liveMessages,
    liveTraces,
    connected,
    nowTick,
    activeTab,
    demo,
    demoRunning,
    // derived
    runningCount,
    totalMessages,
    totalTasks,
    waitingCount,
    // actions
    loadAgents,
    toggleAgent,
    loadInstances,
    loadTrace,
    selectThread,
    jumpThread,
    loadConflicts,
    loadMessages,
    handleFrame,
    startTicker,
    loadRecentTraces,
    fetchDemoStatus,
    startDemo,
    stopDemo,
  }
}

// 模块级具名导出：子组件直接 import { agents, ... } 共享同一单例状态
export {
  agents,
  agentsLoading,
  agentsBusy,
  instances,
  instancesLoading,
  selectedThreadId,
  traceLoading,
  traceMap,
  currentTrace,
  conflicts,
  conflictsLoading,
  messages,
  messagesLoading,
  msgFilter,
  liveMessages,
  liveTraces,
  connected,
  nowTick,
  activeTab,
  demo,
  demoRunning,
  runningCount,
  totalMessages,
  totalTasks,
  waitingCount,
  loadAgents,
  toggleAgent,
  loadInstances,
  loadTrace,
  selectThread,
  jumpThread,
  loadConflicts,
  loadMessages,
  handleFrame,
  startTicker,
  loadRecentTraces,
  fetchDemoStatus,
  startDemo,
  stopDemo,
}
