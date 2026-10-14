<script setup lang="ts">
/**
 * 编排主链路自定义 SVG 节点图
 * - publish / trade / appeal / demo 四套固定布局
 * - 已完成节点依据 state.decisions 点亮，等待节点呼吸，连线流光
 */
import { computed, ref } from 'vue'
import type { InstanceTrace } from '@/api/console'
import {
  BAD_RESULTS,
  DECISION_NODE_ALIAS,
  WARN_RESULTS,
  nodeLabel,
  resultText,
} from '@/composables/useConsoleData'

const props = defineProps<{
  trace: InstanceTrace | null
}>()

// ---- 布局常量（viewBox 用户单位） ----
const W = 150
const H = 52
const XG = 184
const PAD_X = 26
const ROW_Y = [20, 118, 216]

interface GNodeDef {
  id: string
  col: number
  row: number
}
interface GEdgeDef {
  from: string
  to: string
  label?: string
  lane?: boolean
}
interface FlowLayout {
  nodes: GNodeDef[]
  edges: GEdgeDef[]
}

const LAYOUTS: Record<string, FlowLayout> = {
  publish: {
    nodes: [
      { id: 'goods_structure', col: 0, row: 1 },
      { id: 'goods_moderate', col: 1, row: 1 },
      { id: 'human_review_gate', col: 2, row: 0 },
      { id: 'veto_gate', col: 2, row: 2 },
    ],
    edges: [
      { from: 'goods_structure', to: 'goods_moderate' },
      { from: 'goods_moderate', to: 'human_review_gate', label: 'manual' },
      { from: 'goods_moderate', to: 'veto_gate', label: 'veto' },
    ],
  },
  trade: {
    nodes: [
      { id: 'order_lock', col: 0, row: 1 },
      { id: 'risk_check', col: 1, row: 1 },
      { id: 'weighted_vote', col: 2, row: 1 },
      { id: 'risk_human_gate', col: 3, row: 0 },
      { id: 'wait_payment_gate', col: 4, row: 1 },
      { id: 'sandbox_pay', col: 5, row: 0 },
      { id: 'cancel_order', col: 5, row: 2 },
    ],
    edges: [
      { from: 'order_lock', to: 'risk_check' },
      { from: 'risk_check', to: 'weighted_vote', label: '高风险' },
      { from: 'weighted_vote', to: 'risk_human_gate', label: 'manual' },
      { from: 'weighted_vote', to: 'wait_payment_gate', label: 'allow' },
      { from: 'risk_human_gate', to: 'wait_payment_gate' },
      { from: 'wait_payment_gate', to: 'sandbox_pay', label: 'pay' },
      { from: 'wait_payment_gate', to: 'cancel_order', label: 'cancel' },
      { from: 'weighted_vote', to: 'cancel_order', label: 'block', lane: true },
    ],
  },
  appeal: {
    nodes: [
      { id: 'appeal_evidence', col: 0, row: 1 },
      { id: 'appeal_rule', col: 1, row: 1 },
      { id: 'appeal_human_gate', col: 2, row: 0 },
      { id: 'apply_ruling', col: 3, row: 1 },
    ],
    edges: [
      { from: 'appeal_evidence', to: 'appeal_rule' },
      { from: 'appeal_rule', to: 'appeal_human_gate', label: '人工' },
      { from: 'appeal_rule', to: 'apply_ruling', label: '直裁' },
      { from: 'appeal_human_gate', to: 'apply_ruling' },
    ],
  },
  demo: {
    nodes: [
      { id: 'demo_submit', col: 0, row: 0 },
      { id: 'demo_human_gate', col: 1, row: 0 },
    ],
    edges: [{ from: 'demo_submit', to: 'demo_human_gate' }],
  },
}

interface PositionedNode extends GNodeDef {
  x: number
  y: number
  cx: number
  cy: number
}

const layout = computed(() => {
  const flow = props.trace?.flow ?? ''
  const def = LAYOUTS[flow]
  if (!def) return null
  const nodes: PositionedNode[] = def.nodes.map((n) => {
    const x = PAD_X + n.col * (W + XG)
    const y = ROW_Y[n.row]
    return { ...n, x, y, cx: x + W / 2, cy: y + H / 2 }
  })
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  const maxCol = Math.max(...def.nodes.map((n) => n.col))
  const maxRow = Math.max(...def.nodes.map((n) => n.row))
  const laneY = maxRow === 2 ? ROW_Y[2] + H + 14 : 0
  const width = PAD_X * 2 + maxCol * (W + XG) + W
  const height = maxRow === 2 ? laneY + 18 : ROW_Y[maxRow] + H + 26

  const edges = def.edges.map((e) => {
    const a = nodeMap.get(e.from)!
    const b = nodeMap.get(e.to)!
    let d = ''
    let lx = 0
    let ly = 0
    if (e.lane) {
      d = `M ${a.cx} ${a.y + H} V ${laneY} H ${b.cx} V ${b.y + H}`
      lx = (a.cx + b.cx) / 2
      ly = laneY - 7
    } else {
      const x1 = a.x + W
      const y1 = a.cy
      const x2 = b.x
      const y2 = b.cy
      d = `M ${x1} ${y1} C ${x1 + 52} ${y1}, ${x2 - 52} ${y2}, ${x2} ${y2}`
      lx = (x1 + x2) / 2
      ly = (y1 + y2) / 2 - 7
    }
    return { ...e, d, lx, ly }
  })
  return { nodes, edges, width, height }
})

// ---- 决策 / 状态推断 ----
interface Decision {
  node: string
  result?: string
  confidence?: number
  basis?: unknown
  reasons?: unknown
  score?: number
  missing?: unknown
  error?: string
  [key: string]: unknown
}

const decisionMap = computed(() => {
  const map = new Map<string, Decision>()
  const list = (props.trace?.state?.decisions ?? []) as Decision[]
  for (const d of list) {
    if (!d?.node) continue
    const id = DECISION_NODE_ALIAS[d.node] ?? d.node
    if (!map.has(id)) map.set(id, d)
  }
  return map
})

const pendingNodeId = computed(() => {
  const ph = props.trace?.pending_human
  if (ph && typeof ph.node === 'string') return ph.node
  return ''
})

type NodeVisual = 'idle' | 'pending' | 'done' | 'warn' | 'bad'

function visualOf(id: string): NodeVisual {
  if (id === pendingNodeId.value) return 'pending'
  if (props.trace?.next?.includes(id)) return 'pending'
  const d = decisionMap.value.get(id)
  if (!d) return 'idle'
  const r = String(d.result ?? '')
  if (BAD_RESULTS.has(r)) return 'bad'
  if (WARN_RESULTS.has(r)) return 'warn'
  return 'done'
}

type EdgeTone = 'dim' | 'flow' | 'amber' | 'red'

function edgeTone(from: string, to: string): EdgeTone {
  const tv = visualOf(to)
  const fv = visualOf(from)
  if (tv === 'idle' && fv !== 'pending') return 'dim'
  if (tv === 'pending') return 'amber'
  if (tv === 'bad') return 'red'
  if (tv === 'idle') return 'dim'
  return 'flow'
}

// ---- hover 悬浮卡 ----
interface HoverState {
  id: string
  x: number
  y: number
}
const hover = ref<HoverState | null>(null)

function onEnter(id: string, ev: MouseEvent): void {
  hover.value = { id, x: ev.clientX, y: ev.clientY }
}
function onMove(ev: MouseEvent): void {
  if (hover.value) hover.value = { ...hover.value, x: ev.clientX, y: ev.clientY }
}
function onLeave(): void {
  hover.value = null
}

const hoverNode = computed(() => {
  if (!hover.value || !layout.value) return null
  return layout.value.nodes.find((n) => n.id === hover.value!.id) ?? null
})

const popStyle = computed(() => {
  if (!hover.value) return {}
  const maxLeft = Math.max(12, window.innerWidth - 280)
  const maxTop = Math.max(12, window.innerHeight - 240)
  return {
    left: `${Math.min(hover.value.x + 16, maxLeft)}px`,
    top: `${Math.min(hover.value.y + 16, maxTop)}px`,
  }
})
const hoverDecision = computed(() =>
  hover.value ? decisionMap.value.get(hover.value.id) ?? null : null,
)

function basisText(d: Decision | null): string[] {
  if (!d) return []
  const out: string[] = []
  if (Array.isArray(d.basis)) out.push(...d.basis.map((b) => String(b)))
  else if (typeof d.basis === 'string' && d.basis) out.push(d.basis)
  if (Array.isArray(d.reasons)) out.push(...d.reasons.map((b) => String(b)))
  return out
}
</script>

<template>
  <div class="flowgraph">
    <svg
      v-if="layout"
      :viewBox="`0 0 ${layout.width} ${layout.height}`"
      class="flowgraph__svg"
      role="img"
      aria-label="编排主链路图"
    >
      <defs>
        <linearGradient id="fg-edge-flow" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" class="fg-stop fg-stop--start" />
          <stop offset="100%" class="fg-stop fg-stop--end" />
        </linearGradient>
        <marker id="fg-arrow-flow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
          <path d="M0,0 L7,3.5 L0,7 Z" class="fg-arrow fg-arrow--flow" />
        </marker>
        <marker id="fg-arrow-amber" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
          <path d="M0,0 L7,3.5 L0,7 Z" class="fg-arrow fg-arrow--amber" />
        </marker>
        <marker id="fg-arrow-red" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
          <path d="M0,0 L7,3.5 L0,7 Z" class="fg-arrow fg-arrow--red" />
        </marker>
        <marker id="fg-arrow-dim" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
          <path d="M0,0 L7,3.5 L0,7 Z" class="fg-arrow fg-arrow--dim" />
        </marker>
      </defs>

      <!-- 连线 -->
      <g class="flowgraph__edges">
        <template v-for="e in layout.edges" :key="`${e.from}-${e.to}`">
          <path
            :d="e.d"
            fill="none"
            :class="['edge', `edge--${edgeTone(e.from, e.to)}`]"
            :marker-end="`url(#fg-arrow-${edgeTone(e.from, e.to) === 'dim' ? 'dim' : edgeTone(e.from, e.to) === 'amber' ? 'amber' : edgeTone(e.from, e.to) === 'red' ? 'red' : 'flow'})`"
          />
          <text
            v-if="e.label"
            :x="e.lx"
            :y="e.ly"
            text-anchor="middle"
            :class="['edge-label', `edge-label--${edgeTone(e.from, e.to)}`]"
          >
            {{ e.label }}
          </text>
        </template>
      </g>

      <!-- 节点 -->
      <g
        v-for="n in layout.nodes"
        :key="n.id"
        class="node"
        @mouseenter="onEnter(n.id, $event)"
        @mousemove="onMove"
        @mouseleave="onLeave"
      >
        <rect
          v-if="visualOf(n.id) === 'pending'"
          :x="n.x - 5"
          :y="n.y - 5"
          :width="W + 10"
          :height="H + 10"
          rx="15"
          class="node__ping"
        />
        <rect
          :x="n.x"
          :y="n.y"
          :width="W"
          :height="H"
          rx="13"
          :class="['node__box', `node__box--${visualOf(n.id)}`]"
        />
        <text :x="n.x + 14" :y="n.y + 22" :class="['node__title', `node__title--${visualOf(n.id)}`]">
          {{ nodeLabel(n.id) }}
        </text>
        <text :x="n.x + 14" :y="n.y + 40" class="node__sub">{{ n.id }}</text>
        <!-- 状态角标 -->
        <circle
          :cx="n.x + W - 17"
          :cy="n.y + 16"
          r="7"
          :class="['node__badge', `node__badge--${visualOf(n.id)}`]"
        />
        <path
          v-if="visualOf(n.id) === 'done'"
          :d="`M ${n.x + W - 20.5} ${n.y + 16} l 2.4 2.6 l 4.8 -5.4`"
          class="node__check"
          fill="none"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <path
          v-else-if="visualOf(n.id) === 'bad'"
          :d="`M ${n.x + W - 20} ${n.y + 12.5} l 6 7 M ${n.x + W - 14} ${n.y + 12.5} l -6 7`"
          class="node__cross"
          fill="none"
          stroke-width="1.8"
          stroke-linecap="round"
        />
        <path
          v-else-if="visualOf(n.id) === 'warn'"
          :d="`M ${n.x + W - 17} ${n.y + 12.6} v 4.2 M ${n.x + W - 17} ${n.y + 19.4} v 0.6`"
          class="node__warn"
          fill="none"
          stroke-width="1.9"
          stroke-linecap="round"
        />
        <circle v-else-if="visualOf(n.id) === 'pending'" :cx="n.x + W - 17" :cy="n.y + 16" r="2.6" class="node__hour" />
      </g>
    </svg>

    <!-- hover 悬浮玻璃卡 -->
    <Teleport to="body">
      <div
        v-if="hover && hoverNode"
        class="fg-pop"
        :style="popStyle"
      >
        <div class="fg-pop__head">
          <span class="fg-pop__title">{{ nodeLabel(hoverNode.id) }}</span>
          <span :class="['fg-pop__state', `fg-pop__state--${visualOf(hoverNode.id)}`]">
            {{
              { idle: '未到达', pending: '等待中', done: '已完成', warn: '需关注', bad: '异常/否决' }[
                visualOf(hoverNode.id)
              ]
            }}
          </span>
        </div>
        <div class="fg-pop__id">{{ hoverNode.id }}</div>
        <template v-if="hoverDecision">
          <div class="fg-pop__row">
            <span class="fg-pop__k">结果</span>
            <span class="fg-pop__v">{{ resultText(hoverDecision.result) }}</span>
          </div>
          <div v-if="typeof hoverDecision.confidence === 'number'" class="fg-pop__row">
            <span class="fg-pop__k">置信度</span>
            <span class="fg-pop__conf">
              <span class="fg-pop__conf-bar">
                <span
                  class="fg-pop__conf-fill"
                  :style="{ width: `${Math.round(hoverDecision.confidence * 100)}%` }"
                />
              </span>
              {{ hoverDecision.confidence.toFixed(2) }}
            </span>
          </div>
          <div v-if="typeof hoverDecision.score === 'number'" class="fg-pop__row">
            <span class="fg-pop__k">加权分</span>
            <span class="fg-pop__v fg-pop__v--mono">{{ hoverDecision.score.toFixed(2) }}</span>
          </div>
          <ul v-if="basisText(hoverDecision).length" class="fg-pop__basis">
            <li v-for="(b, i) in basisText(hoverDecision)" :key="i">{{ b }}</li>
          </ul>
          <div v-if="hoverDecision.error" class="fg-pop__error">{{ hoverDecision.error }}</div>
        </template>
        <div v-else-if="visualOf(hoverNode.id) === 'pending'" class="fg-pop__hint">
          流程已在此节点中断，等待人工 / 外部事件恢复
        </div>
        <div v-else-if="visualOf(hoverNode.id) === 'idle'" class="fg-pop__hint">该节点尚未到达</div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped lang="scss">
@use './console.scss' as *;

.flowgraph {
  width: 100%;
  overflow-x: auto;
  @include thin-scroll;
}
.flowgraph__svg {
  display: block;
  width: 100%;
  min-width: 560px;
  height: auto;
}

// ---- 渐变 / 箭头（随主题换色） ----
.fg-stop--start {
  stop-color: var(--cc-indigo);
}
.fg-stop--end {
  stop-color: var(--cc-cyan);
}
.fg-arrow {
  &--flow { fill: var(--cc-arrow-flow); }
  &--amber { fill: var(--cc-arrow-amber); }
  &--red { fill: var(--cc-arrow-red); }
  &--dim { fill: var(--cc-arrow-dim); }
}

// ---- 连线 ----
.edge {
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
  &--dim {
    stroke: var(--cc-edge-dim);
    stroke-dasharray: 4 7;
  }
  &--flow {
    stroke: url(#fg-edge-flow);
    stroke-dasharray: 7 7;
    animation: console-dash-flow 1.1s linear infinite;
    filter: drop-shadow(0 0 5px var(--cc-edge-glow-flow));
  }
  &--amber {
    stroke: var(--cc-warning);
    stroke-dasharray: 7 7;
    animation: console-dash-flow 1.1s linear infinite;
    filter: drop-shadow(0 0 5px var(--cc-edge-glow-amber));
  }
  &--red {
    stroke: var(--cc-danger);
    filter: drop-shadow(0 0 5px var(--cc-edge-glow-red));
  }
}
.edge-label {
  font-size: 10px;
  letter-spacing: 0.3px;
  paint-order: stroke;
  stroke: var(--cc-label-halo);
  stroke-width: 4px;
  stroke-linejoin: round;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  pointer-events: none;
  &--dim {
    fill: var(--cc-edge-label-dim);
  }
  &--flow {
    fill: var(--cc-edge-label-flow);
  }
  &--amber {
    fill: var(--cc-edge-label-amber);
  }
  &--red {
    fill: var(--cc-edge-label-red);
  }
}

// ---- 节点 ----
.node {
  cursor: pointer;
}
.node__ping {
  fill: none;
  stroke: var(--cc-warning);
  stroke-width: 1.4;
  transform-box: fill-box;
  transform-origin: center;
  animation: console-node-ring 2s ease-out infinite;
}
.node__box {
  fill: var(--cc-node-fill);
  stroke-width: 1.2;
  transition: all 0.25s ease;
  &--idle {
    stroke: var(--cc-node-stroke-idle);
    opacity: 0.7;
  }
  &--done {
    stroke: var(--cc-node-stroke-done);
    filter: drop-shadow(0 0 7px var(--cc-success-soft));
  }
  &--warn {
    stroke: var(--cc-node-stroke-warn);
    filter: drop-shadow(0 0 7px var(--cc-warning-soft));
  }
  &--bad {
    stroke: var(--cc-node-stroke-bad);
    filter: drop-shadow(0 0 8px var(--cc-danger-soft));
  }
  &--pending {
    stroke: var(--cc-node-stroke-pending);
    stroke-width: 1.8;
    animation: console-node-breathe 1.6s ease-in-out infinite;
    filter: drop-shadow(0 0 12px var(--cc-warning-soft));
  }
}
.node:hover .node__box {
  stroke-width: 2;
}
.node__title {
  font-size: 12.5px;
  font-weight: 600;
  font-family:
    'Inter', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
  paint-order: stroke;
  stroke: var(--cc-label-halo);
  stroke-width: 3px;
  &--idle {
    fill: var(--cc-node-title-idle);
  }
  &--done {
    fill: var(--cc-node-title-done);
  }
  &--warn,
  &--pending {
    fill: var(--cc-node-title-warn);
  }
  &--bad {
    fill: var(--cc-node-title-bad);
  }
}
.node__sub {
  font-size: 8.5px;
  fill: var(--cc-text-muted);
  font-family: 'JetBrains Mono', ui-monospace, monospace;
}
.node__badge {
  &--idle {
    fill: var(--cc-node-badge-idle);
  }
  &--done {
    fill: var(--cc-node-badge-done);
  }
  &--warn,
  &--pending {
    fill: var(--cc-node-badge-warn);
  }
  &--bad {
    fill: var(--cc-node-badge-bad);
  }
}
.node__check {
  stroke: var(--cc-success);
}
.node__cross {
  stroke: var(--cc-danger);
}
.node__warn,
.node__hour {
  stroke: var(--cc-warning);
}
.node__hour {
  fill: var(--cc-warning);
  stroke: none;
  animation: console-live-blink 1.2s ease-in-out infinite;
}

// ---- hover 卡 ----
.fg-pop {
  position: fixed;
  z-index: 3200;
  width: 256px;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--cc-fg-pop-bg);
  border: 1px solid var(--cc-fg-pop-border);
  box-shadow: var(--cc-shadow-pop);
  backdrop-filter: blur(16px);
  pointer-events: none;
  animation: app-scale-in 0.16s ease both;
  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  &__title {
    font-size: 13px;
    font-weight: 700;
    color: var(--cc-text-1);
  }
  &__state {
    font-size: 10.5px;
    padding: 2px 8px;
    border-radius: 999px;
    font-weight: 600;
    &--done {
      color: var(--cc-success-text);
      background: var(--cc-success-soft);
    }
    &--pending,
    &--warn {
      color: var(--cc-warning-text);
      background: var(--cc-warning-soft);
    }
    &--bad {
      color: var(--cc-danger-text);
      background: var(--cc-danger-soft);
    }
    &--idle {
      color: var(--cc-text-3);
      background: var(--cc-raise);
    }
  }
  &__id {
    margin-top: 3px;
    font-size: 10.5px;
    color: var(--cc-text-muted);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
  }
  &__row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-top: 9px;
    font-size: 12px;
  }
  &__k {
    color: var(--cc-text-3);
    flex: none;
  }
  &__v {
    color: var(--cc-text-1);
    font-weight: 600;
    text-align: right;
    &--mono {
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      color: var(--cc-cyan-text);
    }
  }
  &__conf {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    color: var(--cc-text-2);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 11px;
  }
  &__conf-bar {
    width: 72px;
    height: 4px;
    border-radius: 999px;
    background: var(--cc-track-bg);
    overflow: hidden;
  }
  &__conf-fill {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: var(--cc-track-fill);
  }
  &__basis {
    margin: 9px 0 0;
    padding-left: 16px;
    color: var(--cc-text-2);
    font-size: 11.5px;
    line-height: 1.7;
  }
  &__error {
    margin-top: 8px;
    font-size: 11.5px;
    color: var(--cc-danger-text);
  }
  &__hint {
    margin-top: 8px;
    font-size: 11.5px;
    color: var(--cc-text-3);
  }
}
</style>
