<script setup lang="ts">
/**
 * 区块 3 · ACL 消息总线
 * 实时流 + 历史预加载 + 过滤 + payload 抽屉
 */
import { computed, onMounted, ref, watch } from 'vue'
import {
  AGENT_OPTIONS,
  connected,
  fmtClock,
  liveMessages,
  loadMessages,
  messages,
  msgFilter,
  PERFORMATIVES,
  perfMeta,
} from '@/composables/useConsoleData'
import JsonBlock from './JsonBlock.vue'
import SearchIcon from '~icons/lucide/search'
import RadioIcon from '~icons/lucide/radio'
import InboxIcon from '~icons/lucide/inbox'
import ArrowRightIcon from '~icons/lucide/arrow-right'
import WifiOffIcon from '~icons/lucide/wifi-off'

const loading = ref(false)
const autoScroll = ref(true)
const drawer = ref(false)
const current = ref<Record<string, any> | null>(null)

const merged = computed(() => {
  const liveIds = new Set(liveMessages.value.map((m) => m.id))
  const hist = messages.value
    .filter((m) => !liveIds.has(m.id))
    .map((m) => ({ ...m, isLive: false }))
  return [...liveMessages.value, ...hist].slice(0, 200)
})

const filtered = computed(() => {
  const f = msgFilter.value
  return merged.value.filter((m) => {
    if (f.sender && m.sender !== f.sender && m.receiver !== f.sender) return false
    if (f.performative && m.performative !== f.performative) return false
    if (f.conversationId && !m.conversation_id.includes(f.conversationId)) return false
    return true
  })
})

async function reload() {
  loading.value = true
  try {
    await loadMessages()
  } finally {
    loading.value = false
  }
}

watch(() => [msgFilter.value.sender, msgFilter.value.performative, msgFilter.value.conversationId], () => void reload())
onMounted(() => void reload())

function openDetail(m: Record<string, any>) {
  current.value = m
  drawer.value = true
}

function agentLabel(name: string): string {
  return AGENT_OPTIONS.find((a) => a.value === name)?.label ?? name
}
</script>

<template>
  <section class="mc-panel bus">
    <header class="mc-panel__head">
      <div class="mc-panel__title">
        <RadioIcon class="mc-icon" />
        ACL 消息总线
        <span class="mc-live-dot" :class="{ 'is-off': !connected }">
          {{ connected ? 'LIVE' : '离线重连' }}
        </span>
      </div>
      <div class="bus__filters">
        <el-select v-model="msgFilter.sender" placeholder="全部 Agent" clearable size="small"
          class="bus__select" filterable>
          <el-option v-for="a in AGENT_OPTIONS" :key="a.value" :label="agentLabel(a.value)" :value="a.value" />
        </el-select>
        <el-select v-model="msgFilter.performative" placeholder="全部原语" clearable size="small"
          class="bus__select">
          <el-option v-for="p in PERFORMATIVES" :key="p" :label="p" :value="p" />
        </el-select>
        <el-input v-model="msgFilter.conversationId" size="small" placeholder="会话 ID 过滤" clearable
          class="bus__conv" :prefix-icon="SearchIcon" />
        <el-button size="small" round @click="autoScroll = !autoScroll">
          {{ autoScroll ? '自动滚动 开' : '自动滚动 关' }}
        </el-button>
        <el-button size="small" type="primary" round :loading="loading" @click="reload">刷新历史</el-button>
      </div>
    </header>

    <div v-if="!connected" class="bus__offline">
      <WifiOffIcon /> WebSocket 断开，正在指数退避重连…（历史消息仍可查看）
    </div>

    <div class="bus__stream">
      <TransitionGroup v-if="filtered.length" name="bus-row" tag="div">
        <article v-for="m in filtered" :key="m.id" class="bus-row" :class="{ 'bus-row--live': m.isLive }"
          @click="openDetail(m)">
          <span class="bus-row__time">{{ fmtClock(m.created_at) }}</span>
          <span class="bus-row__perf" :style="{
            color: perfMeta(m.performative).color,
            borderColor: perfMeta(m.performative).color + '66',
            boxShadow: perfMeta(m.performative).glow ? `0 0 10px ${perfMeta(m.performative).color}55` : 'none',
          }">{{ m.performative }}</span>
          <span class="bus-row__agents">
            <b>{{ agentLabel(m.sender) }}</b>
            <ArrowRightIcon class="bus-row__arrow" />
            <b>{{ agentLabel(m.receiver) }}</b>
          </span>
          <span class="bus-row__summary">{{ m.summary || '—' }}</span>
          <span class="bus-row__conf">
            <i :style="{ width: `${Math.round(m.confidence * 100)}%` }" />
            <em>{{ m.confidence?.toFixed?.(2) ?? m.confidence }}</em>
          </span>
        </article>
      </TransitionGroup>
      <div v-else class="bus__empty" v-loading="loading">
        <InboxIcon />
        <p>暂无消息，去业务页面发起一次交易，这里会实时滚动 Agent 间 ACL 通信</p>
      </div>
    </div>

    <el-drawer v-model="drawer" title="ACL 消息详情" size="460px"
      :append-to-body="false" direction="rtl" class="mc-drawer">
      <template v-if="current">
        <div class="bus-detail__grid">
          <div><label>消息 ID</label><span>{{ current.id }}</span></div>
          <div><label>会话</label><span class="mono">{{ current.conversation_id }}</span></div>
          <div><label>原语</label><span>{{ current.performative }}</span></div>
          <div><label>方向</label><span class="mono">{{ current.sender }} → {{ current.receiver }}</span></div>
          <div><label>置信度</label><span>{{ current.confidence }}</span></div>
          <div><label>错误码</label><span>{{ current.error_code ?? '—' }}</span></div>
          <div><label>流程实例</label><span class="mono">{{ current.graph_thread_id ?? '—' }}</span></div>
          <div><label>时间</label><span>{{ current.created_at }}</span></div>
        </div>
        <h4 class="bus-detail__pay">Payload</h4>
        <JsonBlock :data="current.payload" />
      </template>
    </el-drawer>
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
    padding: 14px 18px;
    border-bottom: 1px solid var(--cc-divider);
    flex-wrap: wrap;
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

.mc-live-dot {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  color: var(--cc-danger-text);
  letter-spacing: 0.5px;

  &:not(.is-off) {
    color: var(--cc-success-text);
  }
}

.bus__filters {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;

  :deep(.el-select) {
    width: 132px;
  }
  :deep(.el-input__wrapper),
  :deep(.el-select__wrapper) {
    background: var(--cc-input-bg) !important;
    box-shadow: 0 0 0 1px var(--cc-border) inset !important;
  }
  :deep(.el-input__inner) {
    color: var(--cc-input-text);
    font-size: 12px;
  }
  .bus__conv {
    width: 190px;
  }
  :deep(.el-button) {
    font-size: 11.5px;
  }
}

.bus__offline {
  padding: 8px 18px;
  font-size: 12px;
  color: var(--cc-danger-text);
  background: var(--cc-danger-soft);
  border-bottom: 1px solid var(--cc-danger-border);
  display: flex;
  align-items: center;
  gap: 8px;
}

.bus__stream {
  max-height: calc(100vh - 300px);
  min-height: 320px;
  overflow-y: auto;
  padding: 8px 10px;
  @include thin-scroll;
}

.bus-row {
  display: grid;
  grid-template-columns: 64px 92px minmax(90px, 1fr) minmax(150px, 1.6fr) 76px;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  margin: 4px 0;
  border-radius: 10px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.18s, border-color 0.18s;
  animation: console-row-in 0.3s ease;

  &:hover {
    background: var(--cc-hover-bg);
    border-color: var(--cc-hover-border);
  }

  &--live {
    background: linear-gradient(90deg, color-mix(in srgb, var(--cc-cyan) 8%, transparent), transparent 70%);
  }

  &__time {
    font-family: Consolas, monospace;
    font-size: 11px;
    color: var(--cc-text-muted);
  }

  &__perf {
    justify-self: start;
    font-family: Consolas, monospace;
    font-size: 10.5px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
    border: 1px solid;
    background: var(--cc-raise-2);
  }

  &__agents {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--cc-text-2);
    min-width: 0;

    b {
      font-weight: 600;
      color: var(--cc-link);
      white-space: nowrap;
    }
    em {
      font-style: normal;
    }
  }

  &__arrow {
    width: 13px;
    height: 13px;
    color: var(--cc-text-muted);
    flex: none;
  }

  &__summary {
    font-size: 12px;
    color: var(--cc-text-3);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__conf {
    position: relative;
    height: 4px;
    background: var(--cc-track-bg);
    border-radius: 999px;
    align-self: center;

    i {
      position: absolute;
      inset: 0 auto 0 0;
      background: var(--cc-track-fill);
      border-radius: 999px;
    }
    em {
      position: absolute;
      top: -17px;
      right: 0;
      font-style: normal;
      font-size: 10px;
      color: var(--cc-text-muted);
      font-family: Consolas, monospace;
    }
  }
}

.bus__empty {
  min-height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--cc-text-faint);
  font-size: 13px;

  svg {
    width: 42px;
    height: 42px;
    opacity: 0.5;
  }
}

.bus-detail__grid {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 10px 14px;
  font-size: 12.5px;
  margin-bottom: 16px;

  label {
    color: var(--cc-text-muted);
  }
  span {
    color: var(--cc-text-2);
    word-break: break-all;
  }
}
.bus-detail__pay {
  font-size: 13px;
  margin: 14px 0 8px;
  color: var(--cc-link);
}
:deep(.mc-drawer) {
  .el-drawer {
    background: var(--cc-drawer-bg);
  }
  .el-drawer__header {
    color: var(--cc-text-1);
  }
}
</style>
