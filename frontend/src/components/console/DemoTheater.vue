<script setup lang="ts">
/**
 * 一键全自动演示 · 演示剧场浮层（FR-103）
 * 8 阶段竖向时间线 + 总进度 + 结束结果卡；数据来自 useConsoleData 单例 demo store
 * 视觉：浅色白玻璃 + 靛蓝描边，深色沿用 --cc-* 科技感 token
 */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElNotification } from 'element-plus'
import ClapperboardIcon from '~icons/lucide/clapperboard'
import SquareIcon from '~icons/lucide/square'
import XIcon from '~icons/lucide/x'
import ChevronUpIcon from '~icons/lucide/chevron-up'
import CheckIcon from '~icons/lucide/circle-check'
import CircleSlashIcon from '~icons/lucide/circle-slash'
import PackageIcon from '~icons/lucide/package'
import ReceiptIcon from '~icons/lucide/receipt-text'
import ShieldAlertIcon from '~icons/lucide/shield-alert'
import ArrowUpRightIcon from '~icons/lucide/arrow-up-right'
import BanIcon from '~icons/lucide/ban'
import AlertTriangleIcon from '~icons/lucide/triangle-alert'
import { demo, stopDemo } from '@/composables/useConsoleData'

const router = useRouter()
const minimized = ref(false)

const visible = computed(() => demo.status !== 'idle')
const running = computed(() => demo.status === 'running')
const percent = computed(() => {
  if (!demo.phaseCount) return 0
  const done = demo.steps.filter((s) => s.state === 'done').length
  return Math.round((done / demo.phaseCount) * 100)
})
const currentLabel = computed(
  () => demo.steps[demo.phaseIndex - 1]?.label || demo.steps.find((s) => s.state === 'active')?.label || '',
)

const statusMeta = computed(() => {
  switch (demo.status) {
    case 'running':
      return { text: '直播中', cls: 'theater__pill--running' }
    case 'completed':
      return { text: '演示完成', cls: 'theater__pill--done' }
    case 'stopped':
      return { text: '已停止', cls: 'theater__pill--stopped' }
    case 'error':
      return { text: '异常中止', cls: 'theater__pill--error' }
    default:
      return { text: '待机', cls: '' }
  }
})

function close(): void {
  minimized.value = true
}

function goItem(): void {
  if (demo.result?.item_id) void router.push(`/items/${demo.result.item_id}`)
  else void router.push('/market')
}
function goOrders(): void {
  void router.push('/orders')
}

// 状态终态通知（每个 run + 状态只通知一次）
let notifiedKey = ''
watch(
  () => demo.status,
  (s, prev) => {
    if (s === prev || s === 'idle' || s === 'running') return
    const key = `${demo.runId}:${s}`
    if (key === notifiedKey) return
    notifiedKey = key
    if (s === 'completed') {
      minimized.value = false
      ElNotification.success({
        title: '全自动演示完成',
        message: demo.result?.item_title
          ? `新商品《${demo.result?.item_title}》已上架，订单已走完支付与履约全链路`
          : '9 Agent 协作全链路已走完，可在剧场中查看结果',
        duration: 5200,
      })
    } else if (s === 'stopped') {
      ElNotification.warning({ title: '演示已停止', message: '此前阶段产生的商品与订单数据均已保留', duration: 4000 })
    } else if (s === 'error') {
      ElNotification.error({
        title: '演示异常中止',
        message: demo.message || '请查看服务端日志后重试',
        duration: 5200,
      })
    }
  },
)

// 新一轮运行自动展开
watch(
  () => demo.runId,
  () => {
    if (demo.status === 'running') minimized.value = false
  },
)
</script>

<template>
  <!-- 收起态：迷你轨道胶囊 -->
  <Transition name="theater-pop">
    <button
      v-if="visible && minimized"
      type="button"
      class="theater-chip"
      :class="{ 'theater-chip--running': running }"
      @click="minimized = false"
    >
      <ClapperboardIcon :width="15" :height="15" :stroke-width="2.2" />
      <span>演示剧场</span>
      <strong v-if="running">{{ demo.phaseIndex }}/{{ demo.phaseCount }}</strong>
      <span v-else-if="demo.status === 'completed'" class="theater-chip__done">
        <CheckIcon :width="13" :height="13" :stroke-width="2.6" />
      </span>
      <ChevronUpIcon :width="14" :height="14" :stroke-width="2.4" />
    </button>
  </Transition>

  <!-- 展开态：剧场主卡 -->
  <Transition name="theater-pop">
    <aside v-if="visible && !minimized" class="theater" :class="`theater--${demo.status}`">
      <span class="theater__beam" aria-hidden="true" />

      <header class="theater__head">
        <span class="theater__icon">
          <ClapperboardIcon :width="18" :height="18" :stroke-width="2.1" />
        </span>
        <div class="theater__heading">
          <h3>全自动演示剧场</h3>
          <p>9 Agent 协作全链路 · 真实落库</p>
        </div>
        <span class="theater__pill" :class="statusMeta.cls">
          <i v-if="running" />
          {{ statusMeta.text }}
        </span>
        <button
          v-if="running"
          type="button"
          class="theater__stop"
          title="停止演示"
          :disabled="demo.stopping"
          @click="stopDemo()"
        >
          <SquareIcon :width="12" :height="12" :stroke-width="2.4" />
        </button>
        <button type="button" class="theater__close" title="收起（后台继续运行）" @click="close">
          <XIcon :width="14" :height="14" :stroke-width="2.3" />
        </button>
      </header>

      <!-- 总进度 -->
      <div class="theater__progress">
        <div class="theater__progress-meta">
          <span>阶段进度</span>
          <strong>{{ demo.phaseIndex }} / {{ demo.phaseCount }}</strong>
          <em>{{ percent }}%</em>
        </div>
        <div class="theater__track">
          <span class="theater__track-fill" :style="{ width: `${percent}%` }" />
        </div>
        <p v-if="running && currentLabel" class="theater__current">
          <span class="theater__current-dot" />
          {{ currentLabel }}
        </p>
      </div>

      <!-- 阶段时间线 -->
      <ol class="theater__timeline">
        <li
          v-for="step in demo.steps"
          :key="`${step.index}-${step.phase}`"
          class="stage"
          :class="`stage--${step.state}`"
        >
          <span class="stage__rail" aria-hidden="true" />
          <span class="stage__node">
            <span v-if="step.state === 'done'" class="stage__check"><CheckIcon :width="13" :height="13" :stroke-width="2.8" /></span>
            <span v-else-if="step.state === 'error'" class="stage__error"><CircleSlashIcon :width="13" :height="13" :stroke-width="2.6" /></span>
            <span v-else-if="step.state === 'active'" class="stage__spin" />
            <span v-else class="stage__idle">{{ step.index }}</span>
          </span>
          <div class="stage__body">
            <div class="stage__label-row">
              <span class="stage__label">{{ step.label }}</span>
              <span v-if="step.state === 'active'" class="stage__tag">进行中</span>
            </div>
            <p v-if="step.summary" class="stage__summary">{{ step.summary }}</p>
          </div>
        </li>
      </ol>

      <!-- 结果卡：完成 -->
      <div v-if="demo.status === 'completed' && demo.result" class="theater__result result-card">
        <div class="result-card__head">
          <span class="result-card__icon result-card__icon--done"><CheckIcon :width="17" :height="17" :stroke-width="2.5" /></span>
          <div>
            <h4>演示完成</h4>
            <p v-if="demo.result.item_title">《{{ demo.result.item_title }}》</p>
          </div>
        </div>
        <div class="result-card__rows">
          <button type="button" class="result-row" @click="goItem">
            <span class="result-row__icon"><PackageIcon :width="14" :height="14" :stroke-width="2.2" /></span>
            <span class="result-row__text">
              <strong>新商品已上架</strong>
              <em>点击跳转市场查看</em>
            </span>
            <ArrowUpRightIcon :width="14" :height="14" :stroke-width="2.3" />
          </button>
          <button type="button" class="result-row" @click="goOrders">
            <span class="result-row__icon result-row__icon--order"><ReceiptIcon :width="14" :height="14" :stroke-width="2.2" /></span>
            <span class="result-row__text">
              <strong>订单 #{{ demo.result.order_id ?? '—' }}</strong>
              <em>支付 · 交付 · 评价已闭环</em>
            </span>
            <ArrowUpRightIcon :width="14" :height="14" :stroke-width="2.3" />
          </button>
          <div v-if="demo.result.veto_thread_id" class="result-row result-row--static">
            <span class="result-row__icon result-row__icon--veto"><ShieldAlertIcon :width="14" :height="14" :stroke-width="2.2" /></span>
            <span class="result-row__text">
              <strong>安全拦截支线</strong>
              <em>违禁品触发 veto，已冻结待人工终裁</em>
            </span>
          </div>
        </div>
      </div>

      <!-- 结果卡：停止 -->
      <div v-else-if="demo.status === 'stopped'" class="theater__result end-strip end-strip--stopped">
        <BanIcon :width="16" :height="16" :stroke-width="2.2" />
        <div>
          <h4>演示已停止</h4>
          <p>{{ demo.message || '此前阶段产生的全部数据均已保留' }}</p>
        </div>
      </div>

      <!-- 结果卡：异常 -->
      <div v-else-if="demo.status === 'error'" class="theater__result end-strip end-strip--error">
        <AlertTriangleIcon :width="16" :height="16" :stroke-width="2.2" />
        <div>
          <h4>演示异常中止</h4>
          <p>{{ demo.message || '服务端已安全捕获异常，可重新发起演示' }}</p>
        </div>
      </div>
    </aside>
  </Transition>
</template>

<style scoped lang="scss">
@use './console.scss' as *;

.theater-chip {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 40;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 42px;
  padding: 0 16px;
  font-size: 13px;
  font-weight: 700;
  color: var(--cc-text-1);
  border-radius: 999px;
  background: var(--cc-panel-solid);
  border: 1px solid var(--cc-border-strong);
  box-shadow: var(--cc-shadow-pop);
  backdrop-filter: blur(16px);
  cursor: pointer;
  transition: transform 0.22s ease, border-color 0.22s ease;

  svg {
    color: var(--cc-indigo);
  }
  strong {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 12px;
    color: var(--cc-cyan-text);
  }
  &:hover {
    transform: translateY(-2px);
    border-color: var(--cc-indigo);
  }
  &--running {
    border-color: var(--cc-border-strong);
    &::before {
      content: '';
      position: absolute;
      inset: -1px;
      border-radius: inherit;
      border: 1px solid var(--cc-indigo);
      opacity: 0.5;
      animation: chip-breathe 2.4s ease-in-out infinite;
      pointer-events: none;
    }
  }
}

@keyframes chip-breathe {
  0%, 100% { opacity: 0.25; }
  50% { opacity: 0.7; }
}

.theater {
  position: fixed;
  right: 24px;
  bottom: 24px;
  top: 152px;
  z-index: 40;
  width: 364px;
  max-width: calc(100vw - 24px);
  max-height: calc(100vh - 176px);
  display: flex;
  flex-direction: column;
  border-radius: 20px;
  background: var(--cc-panel-solid);
  border: 1px solid var(--cc-border-strong);
  box-shadow: var(--cc-shadow-pop);
  backdrop-filter: blur(20px) saturate(1.4);
  -webkit-backdrop-filter: blur(20px) saturate(1.4);
  overflow: hidden;

  &__beam {
    position: absolute;
    top: 0;
    left: 12%;
    right: 12%;
    height: 2px;
    border-radius: 2px;
    background: var(--cc-track-fill);
    opacity: 0;
    transition: opacity 0.3s ease;
  }
  &--running &__beam {
    opacity: 1;
    background-size: 200% 100%;
    animation: app-gradient-pan 2.6s linear infinite;
  }

  &__head {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 15px 16px 13px;
    border-bottom: 1px solid var(--cc-divider);
  }
  &__icon {
    flex: none;
    display: grid;
    place-items: center;
    width: 36px;
    height: 36px;
    border-radius: 11px;
    color: var(--cc-indigo);
    background: color-mix(in srgb, var(--cc-indigo) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--cc-indigo) 34%, transparent);
  }
  &__heading {
    flex: 1;
    min-width: 0;
    h3 {
      margin: 0;
      font-size: 14px;
      font-weight: 800;
      color: var(--cc-text-1);
      letter-spacing: 0.2px;
    }
    p {
      margin: 2px 0 0;
      font-size: 11px;
      color: var(--cc-text-muted);
    }
  }
  &__pill {
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 24px;
    padding: 0 10px;
    font-size: 11px;
    font-weight: 700;
    border-radius: 999px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    i {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: currentColor;
    }
    &--running {
      color: var(--cc-success-text);
      background: var(--cc-success-soft);
      border: 1px solid var(--cc-success-border);
      i {
        animation: console-live-blink 1.3s ease-in-out infinite;
      }
    }
    &--done {
      color: var(--cc-success-text);
      background: var(--cc-success-soft);
      border: 1px solid var(--cc-success-border);
    }
    &--stopped {
      color: var(--cc-warning-text);
      background: var(--cc-warning-soft);
      border: 1px solid var(--cc-warning-border);
    }
    &--error {
      color: var(--cc-danger-text);
      background: var(--cc-danger-soft);
      border: 1px solid var(--cc-danger-border);
    }
  }
  &__stop,
  &__close {
    flex: none;
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    color: var(--cc-text-3);
    background: transparent;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.18s ease;
  }
  &__stop:hover {
    color: var(--cc-danger-text);
    background: var(--cc-danger-soft);
    border-color: var(--cc-danger-border);
  }
  &__close:hover {
    color: var(--cc-text-1);
    background: var(--cc-hover-bg);
    border-color: var(--cc-border);
  }

  // -------- 总进度 --------
  &__progress {
    padding: 13px 16px 11px;
    border-bottom: 1px solid var(--cc-divider);
  }
  &__progress-meta {
    display: flex;
    align-items: baseline;
    gap: 8px;
    font-size: 11.5px;
    color: var(--cc-text-muted);
    strong {
      font-size: 13px;
      font-weight: 800;
      color: var(--cc-text-1);
      font-family: 'JetBrains Mono', ui-monospace, monospace;
    }
    em {
      margin-left: auto;
      font-style: normal;
      font-size: 11px;
      font-weight: 700;
      color: var(--cc-cyan-text);
      font-family: 'JetBrains Mono', ui-monospace, monospace;
    }
  }
  &__track {
    position: relative;
    height: 5px;
    margin-top: 9px;
    border-radius: 999px;
    background: var(--cc-track-bg);
    overflow: hidden;
  }
  &__track-fill {
    position: absolute;
    inset: 0 auto 0 0;
    border-radius: inherit;
    background: var(--cc-track-fill);
    box-shadow: 0 0 10px var(--cc-edge-glow-flow);
    transition: width 0.5s cubic-bezier(0.22, 1, 0.36, 1);
  }
  &__current {
    display: flex;
    align-items: center;
    gap: 7px;
    margin: 9px 0 0;
    font-size: 12px;
    font-weight: 600;
    color: var(--cc-text-2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  &__current-dot {
    flex: none;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--cc-indigo);
    box-shadow: 0 0 8px var(--cc-indigo);
    animation: console-live-blink 1.4s ease-in-out infinite;
  }

  // -------- 时间线 --------
  &__timeline {
    list-style: none;
    margin: 0;
    padding: 10px 16px 12px;
    flex: 1 1 auto;
    min-height: 120px;
    overflow-y: auto;
    @include thin-scroll;
  }
}

.stage {
  position: relative;
  display: flex;
  gap: 11px;
  padding-bottom: 13px;
  &:last-child {
    padding-bottom: 2px;
  }
  &__rail {
    position: absolute;
    left: 12px;
    top: 24px;
    bottom: -1px;
    width: 2px;
    border-radius: 2px;
    background: var(--cc-border);
  }
  &:last-child &__rail {
    display: none;
  }
  &__node {
    position: relative;
    z-index: 1;
    flex: none;
    width: 26px;
    height: 26px;
    display: grid;
    place-items: center;
    border-radius: 50%;
    font-size: 11px;
    font-weight: 800;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: var(--cc-text-muted);
    background: var(--cc-panel-solid);
    border: 2px solid var(--cc-border);
    transition: all 0.3s ease;
  }
  &__idle {
    line-height: 1;
  }
  &__body {
    flex: 1;
    min-width: 0;
    padding-top: 2px;
  }
  &__label-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  &__label {
    font-size: 12.5px;
    font-weight: 600;
    line-height: 1.4;
    color: var(--cc-text-3);
    transition: color 0.25s ease;
  }
  &__tag {
    flex: none;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.4px;
    color: var(--cc-indigo);
    padding: 1px 7px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--cc-indigo) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--cc-indigo) 30%, transparent);
  }
  &__summary {
    margin: 3px 0 0;
    font-size: 11.5px;
    line-height: 1.55;
    color: var(--cc-text-muted);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  // 状态着色
  &--active {
    .stage__node {
      color: var(--cc-indigo);
      border-color: var(--cc-indigo);
      background: color-mix(in srgb, var(--cc-indigo) 12%, transparent);
      box-shadow: 0 0 0 4px color-mix(in srgb, var(--cc-indigo) 12%, transparent);
      animation: stage-breathe 2s ease-in-out infinite;
    }
    .stage__label {
      color: var(--cc-text-1);
      font-weight: 700;
    }
  }
  &--done {
    .stage__node {
      color: #fff;
      border-color: transparent;
      background: linear-gradient(135deg, #059669, #10b981);
      box-shadow: 0 4px 12px var(--cc-success-glow);
    }
    .stage__label {
      color: var(--cc-text-2);
    }
    .stage__rail {
      background: linear-gradient(180deg, var(--cc-success), var(--cc-border));
      opacity: 0.55;
    }
  }
  &--error {
    .stage__node {
      color: #fff;
      border-color: transparent;
      background: linear-gradient(135deg, #e11d48, #f43f5e);
      box-shadow: 0 4px 12px var(--cc-danger-glow);
    }
    .stage__label {
      color: var(--cc-danger-text);
      font-weight: 700;
    }
  }
  &__spin {
    width: 13px;
    height: 13px;
    border-radius: 50%;
    border: 2px solid color-mix(in srgb, var(--cc-indigo) 25%, transparent);
    border-top-color: var(--cc-indigo);
    animation: app-spin 0.8s linear infinite;
  }
}

@keyframes stage-breathe {
  0%, 100% {
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--cc-indigo) 10%, transparent);
  }
  50% {
    box-shadow: 0 0 0 6px color-mix(in srgb, var(--cc-indigo) 16%, transparent);
  }
}

// -------- 结果区 --------
.theater__result {
  border-top: 1px solid var(--cc-divider);
}

.result-card {
  padding: 14px 16px 16px;
  background: color-mix(in srgb, var(--cc-success) 7%, transparent);

  &__head {
    display: flex;
    align-items: center;
    gap: 11px;
    margin-bottom: 11px;
    h4 {
      margin: 0;
      font-size: 13.5px;
      font-weight: 800;
      color: var(--cc-success-text);
    }
    p {
      margin: 2px 0 0;
      font-size: 12px;
      color: var(--cc-text-3);
      max-width: 260px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
  &__icon {
    flex: none;
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border-radius: 11px;
    color: #fff;
    background: linear-gradient(135deg, #059669, #10b981);
    box-shadow: 0 6px 16px var(--cc-success-glow);
  }
  &__rows {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
}

.result-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 11px;
  text-align: left;
  border-radius: 12px;
  background: var(--cc-panel);
  border: 1px solid var(--cc-border);
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    border-color: var(--cc-border-strong);
    background: var(--cc-hover-bg);
    transform: translateY(-1px);
  }
  &--static {
    cursor: default;
    &:hover {
      transform: none;
      background: var(--cc-panel);
      border-color: var(--cc-border);
    }
  }
  &__icon {
    flex: none;
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border-radius: 9px;
    color: var(--cc-indigo);
    background: color-mix(in srgb, var(--cc-indigo) 13%, transparent);
    &--order {
      color: #b45309;
      background: var(--cc-warning-soft);
    }
    &--veto {
      color: var(--cc-danger-text);
      background: var(--cc-danger-soft);
    }
  }
  &__text {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
    strong {
      font-size: 12.5px;
      font-weight: 700;
      color: var(--cc-text-1);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    em {
      font-style: normal;
      font-size: 11px;
      color: var(--cc-text-muted);
    }
  }
  svg {
    flex: none;
    color: var(--cc-text-muted);
  }
}

.end-strip {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 14px 16px;
  h4 {
    margin: 0;
    font-size: 13px;
    font-weight: 800;
  }
  p {
    margin: 3px 0 0;
    font-size: 11.5px;
    line-height: 1.55;
    color: var(--cc-text-3);
  }
  &--stopped {
    background: var(--cc-warning-soft);
    h4 { color: var(--cc-warning-text); }
    svg { color: var(--cc-warning); flex: none; margin-top: 2px; }
  }
  &--error {
    background: var(--cc-danger-soft);
    h4 { color: var(--cc-danger-text); }
    svg { color: var(--cc-danger); flex: none; margin-top: 2px; }
    p { word-break: break-word; }
  }
}

// -------- 浮层进出场 --------
.theater-pop-enter-active {
  transition: opacity 0.3s cubic-bezier(0.22, 1, 0.36, 1), transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.theater-pop-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.theater-pop-enter-from {
  opacity: 0;
  transform: translateY(18px) scale(0.97);
}
.theater-pop-leave-to {
  opacity: 0;
  transform: translateY(14px) scale(0.98);
}

@media (max-width: 720px) {
  .theater {
    right: 12px;
    bottom: 12px;
    width: calc(100vw - 24px);
  }
  .theater-chip {
    right: 12px;
    bottom: 12px;
  }
}
</style>
