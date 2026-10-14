<script setup lang="ts">
/**
 * 区块 2 · 编排追踪
 * 实例选择器 + 自定义 SVG 主链路图 + 节点决策时间线 + 人工中断待办
 */
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import GitBranchIcon from '~icons/lucide/git-branch'
import WorkflowIcon from '~icons/lucide/workflow'
import HistoryIcon from '~icons/lucide/history'
import DoorOpenIcon from '~icons/lucide/door-open'
import ExternalLinkIcon from '~icons/lucide/external-link'
import ReceiptIcon from '~icons/lucide/receipt-text'
import GavelIcon from '~icons/lucide/gavel'
import CheckCircleIcon from '~icons/lucide/circle-check'
import SlashCircleIcon from '~icons/lucide/circle-slash'
import AlertTriangleIcon from '~icons/lucide/triangle-alert'
import FlagIcon from '~icons/lucide/flag'
import InstanceSelector from './InstanceSelector.vue'
import FlowGraph from './FlowGraph.vue'
import {
  BAD_RESULTS,
  WARN_RESULTS,
  currentTrace,
  flowMeta,
  instances,
  loadTrace,
  nodeLabel,
  resultText,
  selectedThreadId,
  traceLoading,
} from '@/composables/useConsoleData'

const router = useRouter()

watch(
  selectedThreadId,
  (tid) => {
    if (tid) void loadTrace(tid)
  },
  { immediate: true },
)

const selectedInstance = computed(() =>
  instances.value.find((i) => i.thread_id === selectedThreadId.value) ?? null,
)

interface Decision {
  node: string
  result?: string
  confidence?: number
  basis?: unknown
  reasons?: unknown
  [key: string]: unknown
}

const decisions = computed<Decision[]>(
  () => (currentTrace.value?.state?.decisions ?? []) as Decision[],
)

const pending = computed(() => currentTrace.value?.pending_human ?? null)

function toneOf(result: string | undefined): 'good' | 'bad' | 'warn' | 'neutral' {
  if (!result) return 'neutral'
  if (BAD_RESULTS.has(result)) return 'bad'
  if (WARN_RESULTS.has(result)) return 'warn'
  return 'good'
}

function basisList(d: Decision): string[] {
  const out: string[] = []
  if (Array.isArray(d.basis)) out.push(...d.basis.map((x) => String(x)))
  else if (typeof d.basis === 'string' && d.basis) out.push(d.basis)
  if (Array.isArray(d.reasons)) out.push(...d.reasons.map((x) => String(x)))
  return out
}

const pendingKind = computed(() => String(pending.value?.kind ?? ''))
const pendingNode = computed(() => String(pending.value?.node ?? ''))

const pendingAction = computed<{ text: string; to?: string; tip?: string } | null>(() => {
  switch (pendingKind.value) {
    case 'item_review':
    case 'veto_review':
      return { text: '前往人工复核台处理', to: '/review' }
    case 'risk_final':
    case 'appeal_final':
      return { text: '前往三级终裁台处理', to: '/appeals-admin' }
    case 'wait_pay':
      return { text: '前往订单页完成支付', to: '/orders', tip: '支付门等待买家在订单页完成沙箱支付' }
    default:
      return pendingKind.value ? { text: '等待管理员操作' } : null
  }
})

function goPending(): void {
  const action = pendingAction.value
  if (action?.to) void router.push(action.to)
  else if (action?.tip) ElMessage.info(action.tip)
}

function pendingPayloadEntries(): Array<[string, unknown]> {
  const p = pending.value?.payload
  if (!p || typeof p !== 'object') return []
  return Object.entries(p).filter(([, v]) => v !== null && v !== undefined && v !== '')
}

function formatPayloadValue(v: unknown): string {
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
</script>

<template>
  <div class="orch">
    <InstanceSelector />

    <!-- 空态 -->
    <div v-if="!selectedThreadId && !traceLoading" class="orch__empty panel">
      <WorkflowIcon :width="28" :height="28" :stroke-width="1.5" />
      <p>暂无流程实例，请先在卖家端发布商品或完成一笔交易</p>
    </div>

    <template v-else>
      <!-- 主链路图 -->
      <section class="panel graph-panel">
        <header class="panel__header">
          <div class="panel__title-wrap">
            <h2 class="panel__title">
              <GitBranchIcon :width="15" :height="15" />
              主链路编排图
            </h2>
            <span
              v-if="currentTrace"
              class="flow-badge"
              :style="{
                color: flowMeta(currentTrace.flow).color,
                background: `${flowMeta(currentTrace.flow).color}1a`,
                borderColor: `${flowMeta(currentTrace.flow).color}55`,
              }"
            >
              {{ flowMeta(currentTrace.flow).label }}流
            </span>
            <span class="thread-id" :title="selectedThreadId">{{ selectedThreadId }}</span>
          </div>
          <div class="panel__meta">
            <span v-if="selectedInstance" class="meta-chip">
              stage：<b>{{ selectedInstance.stage || '—' }}</b>
            </span>
            <span
              class="meta-chip"
              :class="currentTrace?.status === 'waiting' ? 'meta-chip--waiting' : 'meta-chip--done'"
            >
              <span class="meta-chip__dot" />
              {{ currentTrace?.status === 'waiting' ? 'WAITING' : 'DONE' }}
            </span>
            <span class="meta-chip">决策 {{ decisions.length }} 步</span>
          </div>
        </header>

        <div class="graph-panel__canvas">
          <div v-if="traceLoading && !currentTrace" class="graph-panel__loading">
            <span v-for="n in 3" :key="n" class="skeleton graph-skeleton" />
          </div>
          <FlowGraph v-else-if="currentTrace" :trace="currentTrace" />
        </div>

        <!-- 图例 -->
        <footer class="graph-legend">
          <span><i class="legend-dot legend-dot--done" />已完成</span>
          <span><i class="legend-dot legend-dot--pending" />等待中（人工 / 外部事件）</span>
          <span><i class="legend-dot legend-dot--warn" />需关注</span>
          <span><i class="legend-dot legend-dot--bad" />否决 / 异常</span>
          <span><i class="legend-dot legend-dot--idle" />未到达</span>
        </footer>
      </section>

      <!-- 人工中断待办 -->
      <section v-if="currentTrace?.status === 'waiting' && pending" class="panel pending-panel">
        <header class="pending-panel__head">
          <span class="pending-panel__icon">
            <DoorOpenIcon :width="16" :height="16" />
          </span>
          <div class="pending-panel__titles">
            <h3>{{ pending.summary || '流程等待人工操作' }}</h3>
            <p>
              中断节点 <code>{{ pendingNode }}</code>
              <template v-if="pendingKind"> · kind <code>{{ pendingKind }}</code></template>
            </p>
          </div>
          <el-button v-if="pendingAction" type="primary" round size="small" @click="goPending">
            <component
              :is="pendingKind === 'wait_pay' ? ReceiptIcon : GavelIcon"
              :width="13"
              :height="13"
              style="margin-right: 5px"
            />
            {{ pendingAction.text }}
            <ExternalLinkIcon :width="12" :height="12" style="margin-left: 5px" />
          </el-button>
        </header>
        <div v-if="pendingPayloadEntries().length" class="pending-panel__payload">
          <span v-for="[k, v] in pendingPayloadEntries()" :key="k" class="payload-chip">
            <em>{{ k }}</em>
            <b>{{ formatPayloadValue(v) }}</b>
          </span>
        </div>
      </section>

      <!-- 决策时间线 -->
      <section class="panel timeline-panel">
        <header class="panel__header">
          <h2 class="panel__title">
            <HistoryIcon :width="15" :height="15" />
            节点决策时间线
          </h2>
          <span class="panel__sub">state.decisions · 按执行顺序</span>
        </header>

        <div v-if="!decisions.length" class="timeline-empty">该实例尚无决策记录</div>
        <ol v-else class="tl">
          <li v-for="(d, i) in decisions" :key="i" class="tl__item">
            <span class="tl__rail">
              <span class="tl__node-dot" :class="`tl__node-dot--${toneOf(d.result)}`">
                <component
                  :is="toneOf(d.result) === 'bad' ? SlashCircleIcon : toneOf(d.result) === 'warn' ? AlertTriangleIcon : CheckCircleIcon"
                  :width="13"
                  :height="13"
                />
              </span>
              <span v-if="i < decisions.length - 1" class="tl__line" />
            </span>
            <div class="tl__card">
              <div class="tl__card-head">
                <span class="tl__index">#{{ i + 1 }}</span>
                <span class="tl__node">{{ nodeLabel(d.node) }}</span>
                <code class="tl__node-id">{{ d.node }}</code>
                <span class="tl__result" :class="`tl__result--${toneOf(d.result)}`">
                  {{ resultText(d.result) }}
                </span>
                <span v-if="typeof d.confidence === 'number'" class="tl__conf">
                  <span class="tl__conf-bar">
                    <span
                      class="tl__conf-fill"
                      :style="{ width: `${Math.round(d.confidence * 100)}%` }"
                    />
                  </span>
                  {{ d.confidence.toFixed(2) }}
                </span>
              </div>
              <ul v-if="basisList(d).length" class="tl__basis">
                <li v-for="(b, bi) in basisList(d)" :key="bi">
                  <FlagIcon :width="10" :height="10" class="tl__basis-icon" />
                  {{ b }}
                </li>
              </ul>
            </div>
          </li>
        </ol>
      </section>
    </template>
  </div>
</template>

<style scoped lang="scss">
@use './console.scss' as *;

.panel {
  @include panel;
}

.orch {
  display: flex;
  flex-direction: column;
  gap: 14px;

  &__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 56px 20px;
    color: var(--cc-text-muted);
    font-size: 13px;
  }
}

.panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 13px 18px;
  border-bottom: 1px solid var(--cc-divider);
}
.panel__title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.panel__title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--cc-text-1);
  svg {
    color: var(--cc-indigo);
  }
}
.panel__sub {
  font-size: 11px;
  color: var(--cc-text-faint);
  font-family: 'JetBrains Mono', ui-monospace, monospace;
}
.panel__meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.meta-chip {
  @include chip;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  b {
    color: var(--cc-link-2);
    font-weight: 600;
  }
  &--waiting {
    color: var(--cc-warning-text);
    border-color: var(--cc-warning-border);
  }
  &--done {
    color: var(--cc-success-text);
    border-color: var(--cc-success-border);
  }
  &__dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    animation: console-live-blink 1.4s ease-in-out infinite;
  }
}
.flow-badge {
  height: 22px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 700;
  border: 1px solid;
  border-radius: 999px;
}
.thread-id {
  font-size: 10.5px;
  color: var(--cc-text-muted);
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

// ---- 图面板 ----
.graph-panel {
  &__canvas {
    position: relative;
    padding: 20px 18px 8px;
    background-image:
      radial-gradient(circle at 50% 0%, var(--cc-hover-bg), transparent 70%);
  }
  &__loading {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 10px 0;
  }
}
.graph-skeleton {
  height: 110px;
  border-radius: 12px;
}
.graph-legend {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
  padding: 10px 18px 14px;
  font-size: 11px;
  color: var(--cc-text-3);
  span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
}
.legend-dot {
  width: 9px;
  height: 9px;
  border-radius: 3px;
  &--done {
    background: var(--cc-success);
    box-shadow: 0 0 7px var(--cc-success-glow);
  }
  &--pending {
    background: var(--cc-warning);
    box-shadow: 0 0 7px var(--cc-warning-glow);
  }
  &--warn {
    background: var(--cc-warning);
    opacity: 0.7;
  }
  &--bad {
    background: var(--cc-danger);
    box-shadow: 0 0 7px var(--cc-danger-glow);
  }
  &--idle {
    background: var(--cc-edge-dim);
  }
}

// ---- 人工待办 ----
.pending-panel {
  border-color: var(--cc-warning-border);
  box-shadow: 0 0 26px var(--cc-warning-soft), var(--cc-shadow-panel);
  padding: 14px 18px;

  &__head {
    display: flex;
    align-items: center;
    gap: 13px;
  }
  &__icon {
    flex: none;
    width: 38px;
    height: 38px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 11px;
    color: var(--cc-warning);
    background: var(--cc-warning-soft);
    border: 1px solid var(--cc-warning-border);
    box-shadow: 0 0 14px var(--cc-warning-soft);
  }
  &__titles {
    flex: 1;
    min-width: 0;
    h3 {
      font-size: 13.5px;
      font-weight: 600;
      color: var(--cc-warning-text);
    }
    p {
      margin-top: 3px;
      font-size: 11.5px;
      color: var(--cc-text-3);
      code {
        padding: 1px 6px;
        border-radius: 5px;
        background: var(--cc-code-bg);
        color: var(--cc-link);
        font-family: 'JetBrains Mono', ui-monospace, monospace;
        font-size: 10.5px;
      }
    }
  }
  &__payload {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 12px;
  }
}
.payload-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 8px;
  background: var(--cc-raise-2);
  border: 1px solid var(--cc-border-soft);
  font-size: 11px;
  em {
    color: var(--cc-text-muted);
    font-style: normal;
  }
  b {
    color: var(--cc-link-2);
    font-weight: 600;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
  }
}

// ---- 时间线 ----
.timeline-empty {
  padding: 28px;
  text-align: center;
  font-size: 12.5px;
  color: var(--cc-text-faint);
}
.tl {
  list-style: none;
  margin: 0;
  padding: 8px 18px 14px;

  &__item {
    display: flex;
    gap: 12px;
  }
  &__rail {
    position: relative;
    flex: none;
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 22px;
    padding-top: 12px;
  }
  &__node-dot {
    position: relative;
    z-index: 1;
    display: inline-flex;
    width: 22px;
    height: 22px;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: var(--cc-panel-solid);
    &--good {
      color: var(--cc-success);
      border: 1px solid var(--cc-success-border);
      box-shadow: 0 0 10px var(--cc-success-soft);
    }
    &--warn {
      color: var(--cc-warning);
      border: 1px solid var(--cc-warning-border);
      box-shadow: 0 0 10px var(--cc-warning-soft);
    }
    &--bad {
      color: var(--cc-danger);
      border: 1px solid var(--cc-danger-border);
      box-shadow: 0 0 10px var(--cc-danger-soft);
    }
    &--neutral {
      color: var(--cc-text-3);
      border: 1px solid var(--cc-border-strong);
    }
  }
  &__line {
    flex: 1;
    width: 1.5px;
    min-height: 18px;
    background: linear-gradient(180deg, var(--cc-border-strong), var(--cc-divider));
  }
  &__card {
    flex: 1;
    min-width: 0;
    margin-bottom: 10px;
    padding: 10px 14px;
    border-radius: 12px;
    background: var(--cc-raise-2);
    border: 1px solid var(--cc-border-soft);
  }
  &__card-head {
    display: flex;
    align-items: center;
    gap: 9px;
    flex-wrap: wrap;
  }
  &__index {
    font-size: 10.5px;
    font-weight: 700;
    color: var(--cc-text-muted);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
  }
  &__node {
    font-size: 13px;
    font-weight: 600;
    color: var(--cc-text-1);
  }
  &__node-id {
    font-size: 10px;
    color: var(--cc-text-muted);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
  }
  &__result {
    margin-left: auto;
    height: 21px;
    padding: 0 10px;
    display: inline-flex;
    align-items: center;
    font-size: 11px;
    font-weight: 600;
    border-radius: 999px;
    &--good {
      color: var(--cc-success-text);
      background: var(--cc-success-soft);
    }
    &--warn {
      color: var(--cc-warning-text);
      background: var(--cc-warning-soft);
    }
    &--bad {
      color: var(--cc-danger-text);
      background: var(--cc-danger-soft);
    }
    &--neutral {
      color: var(--cc-text-3);
      background: var(--cc-raise);
    }
  }
  &__conf {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 10.5px;
    color: var(--cc-text-3);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
  }
  &__conf-bar {
    width: 52px;
    height: 4px;
    border-radius: 999px;
    background: var(--cc-track-bg);
    overflow: hidden;
  }
  &__conf-fill {
    display: block;
    height: 100%;
    background: var(--cc-track-fill);
  }
  &__basis {
    margin: 7px 0 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 4px;
    li {
      display: flex;
      align-items: flex-start;
      gap: 6px;
      font-size: 11.5px;
      line-height: 1.6;
      color: var(--cc-text-2);
    }
  }
  &__basis-icon {
    flex: none;
    margin-top: 4px;
    color: var(--cc-indigo);
  }
}
</style>
