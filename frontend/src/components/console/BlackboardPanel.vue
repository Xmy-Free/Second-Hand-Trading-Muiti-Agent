<script setup lang="ts">
/**
 * 区块 4 · 黑板快照：State 树形 / JSON 双视图 + 中断载荷
 */
import { computed, ref } from 'vue'
import {
  currentTrace,
  nodeLabel,
  resultText,
  selectedThreadId,
} from '@/composables/useConsoleData'
import JsonBlock from './JsonBlock.vue'
import JsonTree from './JsonTree.vue'
import DatabaseIcon from '~icons/lucide/database'
import GitBranchIcon from '~icons/lucide/git-branch'
import HandIcon from '~icons/lucide/hand'

type Tab = 'tree' | 'json'
const tab = ref<Tab>('tree')

const state = computed<Record<string, any>>(() => currentTrace.value?.state ?? {})
const pending = computed(() => currentTrace.value?.pending_human ?? null)

const decisions = computed(() => state.value.decisions ?? [])
const nextNodes = computed(() => currentTrace.value?.next ?? [])
</script>

<template>
  <section class="mc-panel board">
    <header class="mc-panel__head">
      <div class="mc-panel__title">
        <DatabaseIcon class="mc-icon" />
        黑板 SSOT 快照
        <span class="mc-thread mono">{{ selectedThreadId || '未选择流程实例' }}</span>
      </div>
      <el-radio-group v-model="tab" size="small">
        <el-radio-button value="tree">树形视图</el-radio-button>
        <el-radio-button value="json">JSON</el-radio-button>
      </el-radio-group>
    </header>

    <div v-if="!selectedThreadId" class="board__placeholder">
      请先在「编排追踪」选择一个流程实例
    </div>

    <template v-else>
      <div class="board__interrupt" v-if="pending">
        <HandIcon class="board__interrupt-icon" />
        <div>
          <strong>LangGraph interrupt · 等待人工</strong>
          <p>{{ pending.summary }}</p>
          <span class="mono">node: {{ pending.node }} · kind: {{ pending.kind }}</span>
        </div>
      </div>
      <div class="board__next" v-else-if="nextNodes.length">
        <GitBranchIcon /> 下一节点：
        <b v-for="n in nextNodes" :key="n">{{ nodeLabel(n) }}</b>
      </div>

      <div class="board__body">
        <JsonTree v-if="tab === 'tree'" :data="state" name="blackboard.state" />
        <JsonBlock v-else :data="state" />
      </div>

      <div class="board__decisions">
        <h4>本实例决策轨迹（{{ decisions.length }}）</h4>
        <ol>
          <li v-for="(d, i) in decisions" :key="i">
            <span class="board__node">{{ nodeLabel(d.node) }}</span>
            <span class="board__result">{{ resultText(d.result) }}</span>
            <small v-if="d.basis">{{ Array.isArray(d.basis) ? d.basis.join('；') : d.basis }}</small>
          </li>
        </ol>
      </div>
    </template>
  </section>
</template>

<style scoped lang="scss">
@use './console.scss' as *;

$border: var(--cc-border);

.mc-panel {
  background: var(--cc-panel);
  border: 1px solid $border;
  border-radius: 16px;
  box-shadow: var(--cc-shadow-panel);
  backdrop-filter: blur(14px);
  overflow: hidden;

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    padding: 14px 18px;
    border-bottom: 1px solid var(--cc-divider);
  }

  &__title {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    font-size: 14px;
    font-weight: 700;
    color: var(--cc-text-1);

    .mc-icon {
      width: 17px;
      height: 17px;
      color: var(--cc-cyan);
    }
  }
}

.mc-thread {
  font-family: Consolas, monospace;
  font-size: 11px;
  color: var(--cc-text-muted);
  font-weight: 400;
  margin-left: 8px;
}

.board__placeholder {
  padding: 60px 20px;
  text-align: center;
  color: var(--cc-text-faint);
  font-size: 13px;
}

.board__interrupt {
  display: flex;
  gap: 12px;
  margin: 16px 18px 0;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--cc-orange-soft);
  border: 1px solid var(--cc-orange-border);

  &-icon {
    width: 22px;
    height: 22px;
    color: var(--cc-orange);
    flex: none;
    margin-top: 2px;
  }
  strong {
    color: var(--cc-orange-text);
    font-size: 13.5px;
  }
  p {
    margin: 4px 0;
    font-size: 12.5px;
    color: var(--cc-text-2);
  }
  span {
    font-size: 11px;
    color: var(--cc-text-3);
  }
}

.board__next {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 16px 18px 0;
  padding: 10px 14px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--cc-cyan) 9%, transparent);
  border: 1px solid color-mix(in srgb, var(--cc-cyan) 28%, transparent);
  font-size: 12.5px;
  color: var(--cc-cyan-text);

  svg {
    width: 15px;
    height: 15px;
  }
  b {
    color: var(--cc-cyan-text);
  }
}

.board__body {
  margin: 16px 18px;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--cc-inset);
  border: 1px solid $border;
  max-height: 46vh;
  overflow: auto;
  @include thin-scroll;
}

.board__decisions {
  margin: 0 18px 18px;

  h4 {
    font-size: 13px;
    color: var(--cc-link);
    margin: 14px 0 10px;
  }
  ol {
    margin: 0;
    padding-left: 0;
    list-style: none;
  }
  li {
    position: relative;
    padding: 10px 12px 10px 30px;
    margin-bottom: 6px;
    border-radius: 9px;
    background: var(--cc-raise-2);
    border: 1px solid var(--cc-border-soft);
    font-size: 12.5px;

    &::before {
      content: '';
      position: absolute;
      left: 13px;
      top: 16px;
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--cc-indigo);
      box-shadow: 0 0 8px color-mix(in srgb, var(--cc-indigo) 55%, transparent);
    }
  }
  .board__node {
    font-weight: 700;
    color: var(--cc-link-2);
    margin-right: 10px;
  }
  .board__result {
    color: var(--cc-success-text);
    font-weight: 600;
  }
  small {
    display: block;
    margin-top: 3px;
    color: var(--cc-text-muted);
    line-height: 1.5;
  }
}

:deep(.el-radio-button__inner) {
  background: var(--cc-raise);
  color: var(--cc-text-3);
  border-color: var(--cc-border);
}
:deep(.el-radio-button.is-active .el-radio-button__inner) {
  background: var(--cc-track-fill);
  border-color: transparent;
  color: #fff;
}
</style>
