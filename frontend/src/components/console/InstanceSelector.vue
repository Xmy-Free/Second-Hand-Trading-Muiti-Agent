<script setup lang="ts">
/**
 * 编排实例选择器：流类型筛选 + 横向滑动实例卡
 * Orchestration 与 Blackboard 两个区块共用（共享 composable 选中态）
 */
import { computed, ref } from 'vue'
import RefreshIcon from '~icons/lucide/refresh-cw'
import InboxIcon from '~icons/lucide/inbox'
import {
  FLOW_FILTERS,
  flowMeta,
  fmtDateTime,
  selectThread,
  selectedThreadId,
  instances,
  instancesLoading,
  loadInstances,
} from '@/composables/useConsoleData'
import type { FlowInstance } from '@/api/types'

const flowFilter = ref('')

const flowTabs = computed(() => [{ value: '', label: '全部' }, ...FLOW_FILTERS])

const filtered = computed(() =>
  flowFilter.value
    ? instances.value.filter((i) => i.flow === flowFilter.value)
    : instances.value,
)

const BUSINESS_LABELS: Record<string, string> = {
  item_id: '商品',
  order_id: '订单',
  negotiation_id: '议价',
  appeal_id: '申诉',
}

function businessText(inst: FlowInstance): string {
  const entries = Object.entries(inst.business ?? {}).filter(([, v]) => v !== null && v !== undefined)
  if (!entries.length) return '—'
  return entries
    .map(([k, v]) => `${BUSINESS_LABELS[k] ?? k} #${v}`)
    .join(' · ')
}

function shortThread(tid: string): string {
  if (tid.length <= 18) return tid
  return `${tid.slice(0, 8)}…${tid.slice(-6)}`
}
</script>

<template>
  <div class="inst-select">
    <div class="inst-select__bar">
      <div class="inst-select__tabs">
        <button
          v-for="t in flowTabs"
          :key="t.value"
          type="button"
          class="flow-tab"
          :class="{ 'flow-tab--active': flowFilter === t.value }"
          @click="flowFilter = t.value"
        >
          {{ t.label }}
        </button>
      </div>
      <button
        type="button"
        class="inst-refresh"
        :disabled="instancesLoading"
        title="刷新实例列表"
        @click="loadInstances"
      >
        <RefreshIcon :width="14" :height="14" :class="{ 'anim-spin': instancesLoading }" />
      </button>
    </div>

    <div v-if="instancesLoading && !instances.length" class="inst-select__loading">
      <span v-for="n in 3" :key="n" class="skeleton inst-skeleton" />
    </div>

    <div v-else-if="!filtered.length" class="inst-select__empty">
      <InboxIcon :width="20" :height="20" :stroke-width="1.6" />
      <span>暂无{{ flowFilter ? flowMeta(flowFilter).label : '' }}流程实例</span>
    </div>

    <div v-else class="inst-select__list">
      <button
        v-for="inst in filtered"
        :key="inst.thread_id"
        type="button"
        class="inst-card"
        :class="{
          'inst-card--active': inst.thread_id === selectedThreadId,
          'inst-card--waiting': inst.status === 'waiting',
        }"
        @click="selectThread(inst.thread_id)"
      >
        <span
          class="inst-card__flow"
          :style="{
            color: flowMeta(inst.flow).color,
            background: `${flowMeta(inst.flow).color}1f`,
            borderColor: `${flowMeta(inst.flow).color}55`,
          }"
        >
          {{ flowMeta(inst.flow).label }}
        </span>
        <span class="inst-card__status">
          <span
            class="inst-card__dot"
            :class="inst.status === 'waiting' ? 'inst-card__dot--waiting' : 'inst-card__dot--done'"
          />
          {{ inst.status === 'waiting' ? '等待中' : '已完成' }}
        </span>
        <span class="inst-card__tid" :title="inst.thread_id">{{ shortThread(inst.thread_id) }}</span>
        <span class="inst-card__biz">{{ businessText(inst) }}</span>
        <span class="inst-card__foot">
          <span>{{ inst.stage || '—' }}</span>
          <span>{{ fmtDateTime(inst.created_at) }}</span>
        </span>
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use './console.scss' as *;

.inst-select {
  &__bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 12px;
  }
  &__tabs {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  &__list {
    display: flex;
    gap: 10px;
    overflow-x: auto;
    padding-bottom: 6px;
    @include thin-scroll;
  }
  &__loading {
    display: flex;
    gap: 10px;
  }
  &__empty {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 34px 0;
    font-size: 13px;
    color: var(--cc-text-faint, var(--cc-text-muted));
    border: 1px dashed var(--cc-border-strong);
    border-radius: 14px;
  }
}

.inst-skeleton {
  width: 210px;
  height: 96px;
  border-radius: 14px;
}

.flow-tab {
  height: 26px;
  padding: 0 13px;
  font-size: 12px;
  color: var(--cc-text-3);
  background: var(--cc-raise);
  border: 1px solid var(--cc-border);
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.18s ease;
  &:hover {
    color: var(--cc-text-1);
    border-color: var(--cc-border-strong);
  }
  &--active {
    color: #fff;
    background: var(--cc-track-fill);
    border-color: transparent;
    box-shadow: 0 4px 14px var(--cc-edge-glow-flow);
  }
}

.inst-refresh {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  color: var(--cc-text-3);
  background: var(--cc-raise);
  border: 1px solid var(--cc-border);
  border-radius: 9px;
  cursor: pointer;
  transition: all 0.18s ease;
  &:hover {
    color: var(--cc-link);
    border-color: var(--cc-border-strong);
  }
}

.inst-card {
  position: relative;
  flex: 0 0 214px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 11px 13px;
  text-align: left;
  background: var(--cc-panel);
  border: 1px solid var(--cc-border);
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.22, 1, 0.36, 1);

  &:hover {
    transform: translateY(-2px);
    border-color: var(--cc-border-strong);
    background: var(--cc-hover-bg);
  }
  &--active {
    border-color: var(--cc-border-strong);
    background: linear-gradient(
      150deg,
      color-mix(in srgb, var(--cc-indigo) 14%, transparent),
      color-mix(in srgb, var(--cc-cyan) 8%, transparent)
    );
    box-shadow: 0 0 20px var(--cc-edge-glow-flow);
  }
  &--waiting::before {
    content: '';
    position: absolute;
    top: 0;
    left: 14px;
    right: 14px;
    height: 2px;
    border-radius: 2px;
    background: linear-gradient(90deg, var(--cc-warning), color-mix(in srgb, var(--cc-warning) 60%, var(--cc-warning)));
    box-shadow: 0 0 8px var(--cc-warning-glow);
  }
  &__flow {
    align-self: flex-start;
    height: 20px;
    padding: 0 9px;
    display: inline-flex;
    align-items: center;
    font-size: 10.5px;
    font-weight: 600;
    border: 1px solid;
    border-radius: 999px;
  }
  &__status {
    position: absolute;
    top: 11px;
    right: 12px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 10.5px;
    color: var(--cc-text-3);
  }
  &__dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    &--waiting {
      background: var(--cc-warning);
      animation: console-live-blink 1.4s ease-in-out infinite;
      box-shadow: 0 0 8px var(--cc-warning-glow);
    }
    &--done {
      background: var(--cc-success);
    }
  }
  &__tid {
    font-size: 10.5px;
    color: var(--cc-text-muted);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  &__biz {
    font-size: 12.5px;
    font-weight: 600;
    color: var(--cc-text-1);
  }
  &__foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    font-size: 10.5px;
    color: var(--cc-text-muted);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    span:first-child {
      color: var(--cc-text-3);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}
</style>
