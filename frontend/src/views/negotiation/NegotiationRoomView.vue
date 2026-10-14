<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getNegotiation, listNegotiationMessages, makeOffer, sendNegotiationMessage } from '@/api/negotiation'
import type { NegotiationMessage, NegotiationView, OfferView } from '@/api/types'
import { useNegotiationSocket } from '@/ws'
import { useAuthStore } from '@/stores/auth'
import AiBadge from '@/components/common/AiBadge.vue'
import ArrowLeftIcon from '~icons/lucide/arrow-left'
import ScaleIcon from '~icons/lucide/scale'
import TimerIcon from '~icons/lucide/timer'
import WifiOffIcon from '~icons/lucide/wifi-off'
import ShieldAlertIcon from '~icons/lucide/shield-alert'
import SparklesIcon from '~icons/lucide/sparkles'
import BotIcon from '~icons/lucide/bot'
import SendIcon from '~icons/lucide/send-horizontal'
import TrophyIcon from '~icons/lucide/trophy'
import CreditCardIcon from '~icons/lucide/credit-card'
import HeartCrackIcon from '~icons/lucide/heart-crack'
import RotateIcon from '~icons/lucide/rotate-ccw'
import CloudOffIcon from '~icons/lucide/cloud-off'
import ChevronRightIcon from '~icons/lucide/chevron-right'
import UserIcon from '~icons/lucide/user'
import StoreIcon from '~icons/lucide/store'
import PackageOpenIcon from '~icons/lucide/package-open'
import CheckIcon from '~icons/lucide/check'
import ListChecksIcon from '~icons/lucide/list-checks'
import MessagesIcon from '~icons/lucide/messages-square'

const route = useRoute()
const router = useRouter()
const negotiationId = Number(route.params.id)

/** makeOffer 业务返回：成功时为 NegotiationView；规则拒绝时为 Agent 数据负载 */
type OfferResult = Partial<NegotiationView> & {
  ok?: boolean
  need_confirm?: boolean
  error?: string
  status?: string
}

function yuan(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function fmtClock(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const detail = ref<NegotiationView | null>(null)
const loading = ref(true)
const errorMsg = ref('')

const offerPrice = ref<number | undefined>()
const submitting = ref(false)
const remaining = ref(0)
const timedOut = ref(false)
const scrollRef = ref<HTMLElement | null>(null)
const chatScrollRef = ref<HTMLElement | null>(null)

// ---------- 洽谈消息（FR-202 / FR-203） ----------
const authStore = useAuthStore()
const myUserId = computed(() => authStore.user?.id ?? null)

const messages = ref<NegotiationMessage[]>([])
const chatLoading = ref(false)
const chatSending = ref(false)
const chatDraft = ref('')
/** 对方「正在输入…」指示 */
const typingVisible = ref(false)
let typingTimer: number | undefined

const counterpartIsAi = computed(() => Boolean(detail.value?.counterpart_is_ai))
const counterpartPersona = computed(() => detail.value?.counterpart_ai_persona || '')
const chatClosedReason = computed(() => {
  if (isDeal.value) return '议价已成交，洽谈通道已关闭'
  if (isTerminated.value) return detail.value?.terminate_reason || '议价已破裂，洽谈通道已关闭'
  return ''
})

function isMyMessage(m: NegotiationMessage): boolean {
  return m.from_user_id !== null && myUserId.value !== null && m.from_user_id === myUserId.value
}

function scrollChatToBottom(smooth = true): void {
  void nextTick(() => {
    const el = chatScrollRef.value
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
  })
}

async function fetchMessages(): Promise<void> {
  chatLoading.value = true
  try {
    const rows = await listNegotiationMessages(negotiationId)
    messages.value = rows
    scrollChatToBottom(false)
  } catch {
    /* 全局拦截器已提示 */
  } finally {
    chatLoading.value = false
  }
}

function appendChatMessage(m: NegotiationMessage): void {
  if (messages.value.some((x) => x.id === m.id)) return
  messages.value = [...messages.value, m]
  scrollChatToBottom()
}

function showTyping(): void {
  typingVisible.value = true
  scrollChatToBottom()
  if (typingTimer !== undefined) window.clearTimeout(typingTimer)
  // 兜底超时（AI 正常回复帧会立即关闭指示）
  typingTimer = window.setTimeout(() => {
    typingVisible.value = false
  }, 6500)
}

function hideTyping(): void {
  typingVisible.value = false
  if (typingTimer !== undefined) {
    window.clearTimeout(typingTimer)
    typingTimer = undefined
  }
}

async function onSendChat(): Promise<void> {
  const content = chatDraft.value.trim()
  if (!content || chatSending.value || !isOngoing.value) return
  chatSending.value = true
  try {
    const m = await sendNegotiationMessage(negotiationId, content)
    appendChatMessage(m)
    chatDraft.value = ''
  } catch {
    /* 全局拦截器已提示（如会话已结束 409） */
  } finally {
    chatSending.value = false
  }
}

function onChatKeydown(e: Event | KeyboardEvent): void {
  const ev = e as KeyboardEvent
  if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing) {
    ev.preventDefault()
    void onSendChat()
  }
}

let tickTimer: number | undefined
let socketEverOpened = false

const isBuyer = computed(() => detail.value?.my_role === 'buyer')
const isOngoing = computed(() => detail.value?.status === 'ongoing')
const isDeal = computed(() => detail.value?.status === 'deal')
const isTerminated = computed(() => detail.value?.status === 'terminated')
const highRisk = computed(() => detail.value?.seller_risk?.tag === 'high_risk')
const latestRound = computed(() =>
  detail.value?.offers?.length ? detail.value.offers[detail.value.offers.length - 1].round : 0,
)

const countdownFraction = computed(() => {
  const d = detail.value
  if (!d || d.deadline_seconds <= 0) return 0
  return Math.max(0, Math.min(1, remaining.value / d.deadline_seconds))
})
const countdownColor = computed(() => {
  if (remaining.value <= 30) return '#ef4444'
  if (remaining.value <= 60) return '#f59e0b'
  return 'url(#negCountdownGradient)'
})
const countdownText = computed(() => {
  const s = Math.max(0, remaining.value)
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}:${String(r).padStart(2, '0')}`
})

const partyName = computed(() => {
  const d = detail.value
  if (!d) return ''
  return d.my_role === 'buyer' ? d.seller_nickname : d.buyer_nickname
})
const partyRoleText = computed(() => (isBuyer.value ? '卖家' : '买家'))

// 环形倒计时参数
const RING_R = 21
const RING_C = 2 * Math.PI * RING_R
const ringOffset = computed(() => RING_C * (1 - countdownFraction.value))

function scrollToBottom(smooth = true): void {
  void nextTick(() => {
    const el = scrollRef.value
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
  })
}

function applyDetail(d: NegotiationView): void {
  detail.value = d
  remaining.value = Math.max(0, d.remaining_seconds ?? 0)
  if (d.status !== 'ongoing') timedOut.value = false
  scrollToBottom()
}

async function fetchDetail(showLoading = false): Promise<void> {
  if (showLoading) loading.value = true
  errorMsg.value = ''
  try {
    const d = await getNegotiation(negotiationId)
    applyDetail(d)
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '议价会话加载失败'
  } finally {
    loading.value = false
  }
}

const { connected } = useNegotiationSocket(
  negotiationId,
  (msg: {
    type?: string
    detail?: NegotiationView
    id?: number
    negotiation_id?: number
    from_user_id?: number | null
    from_nickname?: string
    from_is_ai?: boolean
    kind?: string
    content?: string
    created_at?: string
  }) => {
    if ((msg.type === 'update' || msg.type === 'started') && msg.detail) {
      applyDetail(msg.detail)
      if (msg.type === 'update') {
        ElMessage.success({
          message: msg.detail.status === 'deal' ? '双方达成一致，议价成交' : '收到对方新出价',
          duration: 1800,
        })
      }
      return
    }
    // FR-202：洽谈消息实时帧（REST 回填 / 跨标签页广播均按 id 去重）
    if (msg.type === 'chat' && typeof msg.id === 'number' && msg.content !== undefined) {
      hideTyping()
      appendChatMessage({
        id: msg.id,
        negotiation_id: msg.negotiation_id ?? negotiationId,
        from_user_id: msg.from_user_id ?? null,
        from_nickname: msg.from_nickname ?? '',
        from_is_ai: Boolean(msg.from_is_ai),
        kind: msg.kind === 'system' ? 'system' : 'chat',
        content: msg.content,
        created_at: msg.created_at ?? new Date().toISOString(),
      })
      return
    }
    // FR-203：对方正在输入（自身动作的回显不显示）
    if (
      msg.type === 'typing' &&
      msg.from_user_id !== undefined &&
      msg.from_user_id !== myUserId.value
    ) {
      showTyping()
    }
  },
)

watch(
  () => detail.value?.remaining_seconds,
  (v) => {
    if (typeof v === 'number' && isOngoing.value) remaining.value = Math.max(0, v)
  },
)

async function doOffer(confirm: boolean): Promise<void> {
  if (!detail.value || submitting.value) return
  const price = Number(offerPrice.value)
  if (!price || price <= 0) {
    ElMessage.warning('请输入有效的出价金额')
    return
  }

  submitting.value = true
  try {
    const resp = (await makeOffer(negotiationId, {
      price,
      confirm,
    })) as OfferResult

    // Agent 规则拒绝 / need_confirm（HTTP 信封 code=0，业务数据原样返回）
    if (resp && resp.ok === false) {
      if (resp.need_confirm) {
        try {
          await ElMessageBox.confirm(
            resp.error || `该价格越过你的保留价，仍要以 ¥${yuan(price)} 出价吗？`,
            '越过保留价 · 二次确认',
            {
              confirmButtonText: '确认出价',
              cancelButtonText: '再想想',
              type: 'warning',
              roundButton: true,
            },
          )
          await doOffer(true)
        } catch {
          /* 用户取消二次确认 */
        }
        return
      }
      ElMessage.error(resp.error || '出价未被接受，请调整后重试')
      if (resp.status === 'deal' || resp.status === 'terminated') await fetchDetail()
      return
    }

    applyDetail(resp as NegotiationView)
    offerPrice.value = undefined
  } catch {
    /* 全局拦截器已提示（如 Agent 熔断 409） */
  } finally {
    submitting.value = false
  }
}

function onSubmit(): void {
  void doOffer(false)
}

function adoptSuggestion(): void {
  const p = detail.value?.server_note?.price
  if (p) offerPrice.value = p
}

function openItem(id: number): void {
  void router.push(`/items/${id}`)
}

// ---------- 气泡角色样式 ----------
function bubbleAlign(offer: OfferView): 'left' | 'right' | 'center' {
  if (offer.from_role === 'agent') return 'center'
  return offer.mine ? 'right' : 'left'
}

function roleLabel(offer: OfferView): string {
  if (offer.from_role === 'agent') return 'Agent 提示'
  const mine = offer.from_role === detail.value?.my_role
  if (offer.from_role === 'buyer') return mine ? '我（买家）' : '买家'
  return mine ? '我（卖家）' : '卖家'
}

onMounted(async () => {
  await fetchDetail(true)
  scrollToBottom(false)
  void fetchMessages()
  tickTimer = window.setInterval(() => {
    if (!isOngoing.value) return
    if (remaining.value > 0) {
      remaining.value -= 1
      if (remaining.value === 0 && !timedOut.value) {
        timedOut.value = true
        ElMessage.warning('议价倒计时已结束，正在刷新最新状态…')
        void fetchDetail()
      }
    }
  }, 1000)
})

onBeforeUnmount(() => {
  if (tickTimer) window.clearInterval(tickTimer)
  hideTyping()
})

// WS 重连后静默兜底，防止丢帧（首次连接不重复拉取）
watch(connected, (val) => {
  if (val && socketEverOpened && detail.value && isOngoing.value) {
    void fetchDetail()
    void fetchMessages()
  }
  if (val) socketEverOpened = true
})

// 议价成交 / 破裂：拉取最后一条系统提示（如「AI 接受了 ¥42.2，议价达成」）
watch(
  () => detail.value?.status,
  (s, prev) => {
    if (prev === 'ongoing' && s && s !== 'ongoing') {
      hideTyping()
      void fetchMessages()
    }
  },
)
</script>

<template>
  <div class="page-container page-container--tight room">
    <!-- 返回 -->
    <div class="room__back anim-fade-in">
      <button class="back-btn" type="button" @click="router.push('/negotiations')">
        <ArrowLeftIcon :width="16" :height="16" :stroke-width="2.2" />
        议价室
      </button>
      <span v-if="!loading && detail" class="room__reconnect" :class="{ 'is-on': connected }">
        <WifiOffIcon v-if="!connected" :width="13" :height="13" :stroke-width="2.3" />
        <span class="status-dot" :class="connected ? 'status-dot--live' : 'status-dot--warning'" />
        {{ connected ? '实时已连接' : '断线重连中…' }}
      </span>
    </div>

    <!-- 骨架 -->
    <div v-if="loading" class="room__shell">
      <div class="glass-card skeleton" style="height: 96px; border-radius: 18px" />
      <div class="glass-card skeleton room__stream-skeleton" />
      <div class="glass-card skeleton" style="height: 132px; border-radius: 18px" />
    </div>

    <!-- 错误 -->
    <section v-else-if="errorMsg || !detail" class="state-card glass-card anim-fade-in-up">
      <span class="state-card__icon"><CloudOffIcon :stroke-width="1.8" /></span>
      <h3>议价会话不可用</h3>
      <p>{{ errorMsg || '会话不存在或你无权访问' }}</p>
      <div class="state-card__actions">
        <button class="btn-gradient" @click="fetchDetail(true)">
          <RotateIcon :width="16" :height="16" :stroke-width="2.4" />
          重新加载
        </button>
        <button class="state-card__ghost" @click="router.push('/negotiations')">返回列表</button>
      </div>
    </section>

    <template v-else>
      <!-- 顶部信息条 -->
      <header class="info-bar glass-card anim-fade-in-up">
        <div class="info-bar__main">
          <button class="info-bar__item" type="button" @click="openItem(detail.item_id)">
            <PackageOpenIcon :width="18" :height="18" :stroke-width="2" />
            <span class="info-bar__title">{{ detail.item_title }}</span>
            <ChevronRightIcon :width="15" :height="15" :stroke-width="2.3" />
          </button>

          <div class="info-bar__chips">
            <span class="nash-badge">
              <ScaleIcon :width="13" :height="13" :stroke-width="2.3" />
              纳什参考价
              <strong>¥{{ yuan(detail.nash_price) }}</strong>
            </span>
            <span class="info-chip">
              <ListChecksIcon :width="13" :height="13" :stroke-width="2.2" />
              第 <strong>{{ latestRound }}</strong> / {{ detail.max_rounds }} 轮
            </span>
            <span class="party-chip">
              <span class="party-chip__avatar"><UserIcon :width="13" :height="13" :stroke-width="2.2" /></span>
              {{ partyRoleText }} · {{ partyName }}
              <AiBadge v-if="counterpartIsAi" size="sm" :persona="counterpartPersona" />
            </span>
          </div>
        </div>

        <!-- 倒计时环 -->
        <div v-if="isOngoing" class="timer-ring" :class="{ 'timer-ring--danger': remaining <= 30 }">
          <svg width="52" height="52" viewBox="0 0 52 52">
            <defs>
              <linearGradient id="negCountdownGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#6366f1" />
                <stop offset="100%" stop-color="#22d3ee" />
              </linearGradient>
            </defs>
            <circle class="timer-ring__track" cx="26" cy="26" :r="21" />
            <circle
              class="timer-ring__bar"
              cx="26"
              cy="26"
              :r="RING_R"
              :stroke="countdownColor"
              :stroke-dasharray="RING_C"
              :stroke-dashoffset="ringOffset"
            />
          </svg>
          <span class="timer-ring__text">
            <TimerIcon :width="11" :height="11" :stroke-width="2.4" />
            {{ countdownText }}
          </span>
        </div>
        <div v-else class="status-seal" :class="{ 'status-seal--deal': isDeal, 'status-seal--dead': isTerminated }">
          <TrophyIcon v-if="isDeal" :width="18" :height="18" :stroke-width="2.2" />
          <HeartCrackIcon v-else :width="18" :height="18" :stroke-width="2.2" />
          {{ isDeal ? '已成交' : '已破裂' }}
        </div>
      </header>

      <!-- 高风险警告 -->
      <div v-if="isBuyer && highRisk" class="risk-strip anim-fade-in">
        <ShieldAlertIcon :width="16" :height="16" :stroke-width="2.3" />
        <span>
          对方为<strong>高风险卖家</strong>（信用分 {{ detail.seller_risk?.credit }}，低于安全阈值），
          履约 Agent 已加强交易监控，请谨慎确认价格与交付信息。
        </span>
      </div>

      <!-- 超时提示 -->
      <div v-if="isOngoing && timedOut" class="timeout-strip anim-fade-in">
        <TimerIcon :width="15" :height="15" :stroke-width="2.3" />
        <span>本轮倒计时已结束</span>
        <button type="button" @click="fetchDetail()">
          <RotateIcon :width="13" :height="13" :stroke-width="2.4" />
          刷新状态
        </button>
      </div>

      <!-- 成交横幅 -->
      <div v-if="isDeal" class="banner banner--deal anim-scale-in">
        <span class="banner__icon"><TrophyIcon :width="20" :height="20" :stroke-width="2.1" /></span>
        <div class="banner__text">
          <strong>议价成交！</strong>
          <span>双方在纳什参考价附近达成一致，成交价 <em>¥{{ yuan(detail.deal_price) }}</em>，订单已自动创建。</span>
        </div>
        <button v-if="detail.order_id" class="banner__action" @click="router.push('/orders')">
          <CreditCardIcon :width="15" :height="15" :stroke-width="2.3" />
          去支付
        </button>
      </div>

      <!-- 破裂横幅 -->
      <div v-if="isTerminated" class="banner banner--dead anim-scale-in">
        <span class="banner__icon"><HeartCrackIcon :width="20" :height="20" :stroke-width="2.1" /></span>
        <div class="banner__text">
          <strong>议价已破裂</strong>
          <span>{{ detail.terminate_reason || '双方未能在最大轮次内达成一致' }}</span>
        </div>
      </div>

      <!-- 对话流 -->
      <section class="stream glass-card">
        <div class="stream__tip">
          <SparklesIcon :width="13" :height="13" :stroke-width="2.2" />
          出价须逐轮{{ isBuyer ? '提高' : '降低' }}（单调让步）·纳什参考价 ¥{{ yuan(detail.nash_price) }}
        </div>

        <div ref="scrollRef" class="stream__scroll">
          <p v-if="!detail.offers || detail.offers.length === 0" class="stream__empty">
            <BotIcon :width="26" :height="26" :stroke-width="1.7" />
            议价已发起，等待对方第一轮回应…
          </p>

          <template v-for="offer in detail.offers" :key="offer.id">
            <div
              class="bubble-row"
              :class="[
                bubbleAlign(offer) === 'right' ? 'bubble-row--right' : bubbleAlign(offer) === 'left' ? '' : 'bubble-row--center',
              ]"
            >
              <div
                v-if="bubbleAlign(offer) !== 'center'"
                class="bubble"
                :class="offer.mine ? 'bubble--mine' : 'bubble--other'"
              >
                <div class="bubble__meta">
                  <span>{{ roleLabel(offer) }}</span>
                  <span>第 {{ offer.round }} 轮</span>
                  <span>{{ fmtClock(offer.created_at) }}</span>
                </div>
                <div class="bubble__price">¥{{ yuan(offer.price) }}</div>
                <div v-if="offer.basis" class="bubble__basis">
                  <SparklesIcon :width="11" :height="11" :stroke-width="2.3" />
                  {{ offer.basis }}
                </div>
              </div>

              <div v-else class="agent-note anim-message-in">
                <span class="agent-note__icon"><BotIcon :width="14" :height="14" :stroke-width="2.2" /></span>
                <div class="agent-note__body">
                  <div class="agent-note__title">Agent 建议</div>
                  <div class="agent-note__text">{{ offer.basis }}</div>
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- Agent 建议 -->
        <div v-if="isOngoing && detail.server_note" class="server-note anim-fade-in">
          <span class="server-note__icon"><BotIcon :width="15" :height="15" :stroke-width="2.2" /></span>
          <div class="server-note__body">
            <div class="server-note__title">
              Agent 建议
              <span v-if="detail.server_note.would_deal" class="server-note__deal">
                <CheckIcon :width="11" :height="11" :stroke-width="2.6" />
                此价可成交
              </span>
            </div>
            <div class="server-note__text">{{ detail.server_note.text }}</div>
          </div>
          <button class="server-note__adopt" type="button" @click="adoptSuggestion">
            <SparklesIcon :width="13" :height="13" :stroke-width="2.3" />
            采纳建议价 ¥{{ yuan(detail.server_note.price) }}
          </button>
        </div>
      </section>

      <!-- 洽谈消息（FR-202：与出价气泡清晰分层，不含价格大数字） -->
      <section class="chat glass-card" v-loading="chatLoading && !messages.length">
        <header class="chat__head">
          <div class="chat__title">
            <MessagesIcon :width="15" :height="15" :stroke-width="2.2" />
            <h3>洽谈消息</h3>
            <span v-if="counterpartIsAi" class="chat__ai-online">
              <span class="chat__ai-dot" />
              AI 在线
              <AiBadge size="sm" :persona="counterpartPersona" />
            </span>
          </div>
          <p v-if="counterpartIsAi && counterpartPersona" class="chat__persona">
            <SparklesIcon :width="12" :height="12" :stroke-width="2.3" />
            {{ counterpartPersona }}
          </p>
        </header>

        <div ref="chatScrollRef" class="chat__scroll">
          <p v-if="!messages.length && !chatLoading" class="chat__empty">
            <MessagesIcon :width="22" :height="22" :stroke-width="1.7" />
            还没有洽谈消息，主动打个招呼吧～
          </p>

          <template v-for="m in messages" :key="m.id">
            <!-- 系统提示：居中胶囊 -->
            <div v-if="m.kind === 'system'" :key="m.id" class="chat-sys anim-fade-in">
              <BotIcon :width="12" :height="12" :stroke-width="2.2" />
              <span>{{ m.content }}</span>
            </div>

            <!-- 聊天气泡：本人右 / 对方左 -->
            <div
              v-else
              :key="m.id"
              class="chat-row"
              :class="isMyMessage(m) ? 'chat-row--right' : ''"
            >
              <div class="chat-bubble" :class="isMyMessage(m) ? 'chat-bubble--mine' : 'chat-bubble--other'">
                <div v-if="!isMyMessage(m)" class="chat-bubble__name">
                  <span>{{ m.from_nickname || partyName }}</span>
                  <AiBadge v-if="m.from_is_ai" size="sm" />
                </div>
                <div class="chat-bubble__text">{{ m.content }}</div>
                <div class="chat-bubble__time">{{ fmtClock(m.created_at) }}</div>
              </div>
            </div>
          </template>

          <!-- 对方正在输入 -->
          <div v-if="typingVisible" class="chat-row chat-row--typing anim-fade-in">
            <div class="chat-bubble chat-bubble--other chat-bubble--typing">
              <span class="chat-bubble__name">
                <span>{{ counterpartIsAi ? (detail.counterpart_nickname || partyName) : '对方' }}</span>
                <AiBadge v-if="counterpartIsAi" size="sm" />
              </span>
              <span class="typing-dots"><i /><i /><i /></span>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div v-if="isOngoing" class="chat__composer">
          <el-input
            v-model="chatDraft"
            type="textarea"
            class="chat__input"
            :autosize="{ minRows: 1, maxRows: 4 }"
            placeholder="和对方说点什么… Enter 发送，Shift+Enter 换行"
            resize="none"
            @keydown="onChatKeydown"
          />
          <button
            class="btn-gradient chat__send"
            :disabled="chatSending || !chatDraft.trim() || !connected"
            @click="onSendChat"
          >
            <SendIcon :width="15" :height="15" :stroke-width="2.3" />
            {{ chatSending ? '发送中' : '发送' }}
          </button>
        </div>
        <div v-else class="chat__closed">
          <CheckIcon :width="13" :height="13" :stroke-width="2.4" />
          {{ chatClosedReason }}
        </div>
      </section>

      <!-- 同类推荐（破裂后） -->
      <section v-if="isTerminated && detail.recommendations && detail.recommendations.length" class="recs">
        <h3 class="recs__title">
          <StoreIcon :width="15" :height="15" :stroke-width="2.2" />
          别灰心，交易 Agent 为你找到同类好物
        </h3>
        <div class="recs__rail">
          <article
            v-for="rec in detail.recommendations"
            :key="rec.id"
            class="rec-card glass-card glass-card--hover"
            @click="openItem(rec.id)"
          >
            <div class="rec-card__media">
              <PackageOpenIcon class="rec-card__fallback" :width="22" :height="22" :stroke-width="1.7" />
              <img
                v-if="rec.image_url"
                :src="rec.image_url"
                :alt="rec.title"
                class="rec-card__img"
                @error="(e) => ((e.currentTarget as HTMLImageElement).style.display = 'none')"
              />
            </div>
            <div class="rec-card__body">
              <h4>{{ rec.title }}</h4>
              <div class="rec-card__meta">
                <span>{{ rec.category }}</span>
                <span>·</span>
                <span>{{ rec.condition_level }}</span>
              </div>
              <div class="rec-card__price">¥{{ yuan(rec.price) }}</div>
              <div v-if="rec.match_reason" class="rec-card__reason">
                <SparklesIcon :width="11" :height="11" :stroke-width="2.3" />
                {{ rec.match_reason }}
              </div>
            </div>
          </article>
        </div>
      </section>

      <!-- 底部出价区 -->
      <footer class="composer glass-card">
        <template v-if="isOngoing">
          <div class="composer__row">
            <el-input
              v-model.number="offerPrice"
              class="composer__input"
              :placeholder="isBuyer ? '输入本轮出价（需高于上轮）' : '输入本轮要价（需低于上轮）'"
              size="large"
              @keyup.enter="onSubmit"
            >
              <template #prefix>
                <span class="composer__unit">¥</span>
              </template>
            </el-input>
            <button
              class="btn-gradient composer__send"
              :disabled="submitting || !connected"
              @click="onSubmit"
            >
              <SendIcon :width="16" :height="16" :stroke-width="2.3" />
              {{ submitting ? '发送中…' : '出价' }}
            </button>
          </div>
          <div class="composer__foot">
            <span v-if="isBuyer && detail.my_reserve != null" class="composer__reserve">
              我的保留价：<strong>¥{{ yuan(detail.my_reserve) }}</strong>（对卖家保密）
            </span>
            <span v-else-if="detail.my_reserve != null" class="composer__reserve">
              我的保留价：<strong>¥{{ yuan(detail.my_reserve) }}</strong>（对买家保密）
            </span>
            <span v-if="!connected" class="composer__offline">
              <WifiOffIcon :width="12" :height="12" :stroke-width="2.3" />
              当前未连接，重连后自动恢复
            </span>
            <span class="composer__hint">Enter 快速发送 · 越过保留价需二次确认</span>
          </div>
        </template>

        <div v-else class="composer__closed">
          <component
            :is="isDeal ? TrophyIcon : HeartCrackIcon"
            :width="17"
            :height="17"
            :stroke-width="2.1"
            :style="{ color: isDeal ? '#b45309' : 'var(--app-text-placeholder)' }"
          />
          <span>会话已{{ isDeal ? '成交' : '破裂' }}，出价通道已关闭</span>
          <button v-if="isDeal && detail.order_id" class="btn-gradient composer__pay" @click="router.push('/orders')">
            <CreditCardIcon :width="15" :height="15" :stroke-width="2.3" />
            前往支付
          </button>
          <button v-else class="state-card__ghost" @click="router.push('/market')">
            <StoreIcon :width="15" :height="15" :stroke-width="2.2" />
            再逛市场
          </button>
        </div>
      </footer>
    </template>
  </div>
</template>

<style scoped lang="scss">
.room {
  padding-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;

  &__back {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  &__reconnect {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 13px;
    font-size: 12px;
    font-weight: 600;
    color: var(--app-warning);
    border-radius: 999px;
    background: var(--app-warning-soft);
    border: 1px solid rgba(245, 158, 11, 0.25);
    &.is-on {
      color: var(--app-success);
      background: var(--app-success-soft);
      border-color: rgba(16, 185, 129, 0.25);
    }
  }
  &__shell {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  &__stream-skeleton {
    flex: 1;
    min-height: 420px;
  }
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 36px;
  padding: 0 15px;
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text-secondary);
  border-radius: 10px;
  border: 1px solid var(--app-card-border);
  background: var(--app-card-bg);
  backdrop-filter: blur(12px);
  cursor: pointer;
  transition: all 0.2s ease;
  &:hover {
    color: var(--app-brand);
    border-color: var(--app-card-border-strong);
    transform: translateX(-2px);
  }
}

// ---------- 顶部信息条 ----------
.info-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 14px 20px;

  &__main {
    min-width: 0;
    flex: 1;
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }
  &__item {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 0;
    border: none;
    background: transparent;
    cursor: pointer;
    max-width: 100%;
    &:hover &__title {
      color: var(--app-brand);
    }
  }
  &__title {
    margin: 0;
    font-size: 16px;
    font-weight: 700;
    color: var(--app-text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: color 0.2s ease;
  }
  &__chips {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
}

.nash-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  border-radius: 999px;
  background: var(--app-gradient-deep);
  box-shadow: 0 6px 18px rgba(67, 56, 202, 0.3);
  strong {
    font-size: 13.5px;
    font-variant-numeric: tabular-nums;
  }
}
.info-chip,
.party-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 13px;
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-secondary);
  border-radius: 999px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);
  strong {
    color: var(--app-text-primary);
    font-variant-numeric: tabular-nums;
  }
}
.party-chip__avatar {
  display: inline-flex;
  color: var(--app-brand);
}

// 倒计时环
.timer-ring {
  position: relative;
  flex: none;
  width: 52px;
  height: 52px;

  svg {
    transform: rotate(-90deg);
  }
  &__track {
    fill: none;
    stroke: var(--el-fill-color-dark);
    stroke-width: 4.5;
  }
  &__bar {
    fill: none;
    stroke-width: 4.5;
    stroke-linecap: round;
    transition: stroke-dashoffset 1s linear, stroke 0.4s ease;
  }
  &__text {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1px;
    font-size: 12px;
    font-weight: 700;
    color: var(--app-brand-strong);
    font-variant-numeric: tabular-nums;
  }
  &--danger &__text {
    color: var(--app-danger);
  }
}

.status-seal {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 40px;
  padding: 0 18px;
  font-size: 13.5px;
  font-weight: 700;
  border-radius: 999px;
  color: var(--app-text-secondary);
  background: var(--el-fill-color-dark);
  border: 1px solid var(--app-card-border);
  &--deal {
    color: #b45309;
    background: var(--app-warning-soft);
    border-color: rgba(245, 158, 11, 0.35);
  }
  &--dead {
    color: var(--app-text-placeholder);
  }
}

// ---------- 警示条 ----------
.risk-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  font-size: 13px;
  line-height: 1.6;
  color: #991b1b;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(254, 226, 226, 0.9), rgba(254, 242, 242, 0.72));
  border: 1px solid rgba(239, 68, 68, 0.28);
  strong {
    font-weight: 800;
  }
  svg {
    flex: none;
    color: var(--app-danger);
  }
}

.timeout-strip {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 600;
  color: #92400e;
  border-radius: 14px;
  background: var(--app-warning-soft);
  border: 1px solid rgba(245, 158, 11, 0.3);
  button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-left: auto;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 700;
    color: #b45309;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(245, 158, 11, 0.35);
    cursor: pointer;
    transition: all 0.2s ease;
    &:hover {
      background: #fff;
      transform: translateY(-1px);
    }
  }
}

// ---------- 横幅 ----------
.banner {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 15px 20px;
  border-radius: 16px;

  &__icon {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 42px;
    height: 42px;
    border-radius: 13px;
  }
  &__text {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 13px;
    color: var(--app-text-secondary);
    strong {
      font-size: 15px;
      font-weight: 800;
    }
    em {
      font-style: normal;
      font-weight: 800;
      color: #b45309;
      font-variant-numeric: tabular-nums;
    }
  }
  &__action {
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    height: 38px;
    padding: 0 18px;
    font-size: 13.5px;
    font-weight: 700;
    color: #fff;
    border: none;
    border-radius: 11px;
    background: linear-gradient(135deg, #d97706, #f59e0b);
    box-shadow: 0 8px 22px rgba(245, 158, 11, 0.4);
    cursor: pointer;
    transition: all 0.22s ease;
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 12px 28px rgba(245, 158, 11, 0.5);
    }
  }

  &--deal {
    color: #78350f;
    background: linear-gradient(120deg, #fff7e6 0%, #fef3c7 60%, #fde68a 100%);
    border: 1px solid rgba(245, 158, 11, 0.4);
    box-shadow: 0 10px 30px rgba(245, 158, 11, 0.18);
    .banner__icon {
      color: #fff;
      background: linear-gradient(135deg, #f59e0b, #fbbf24);
      box-shadow: 0 6px 18px rgba(245, 158, 11, 0.4);
    }
  }
  &--dead {
    background: linear-gradient(135deg, #f1f5f9, #e8edf6);
    border-color: var(--app-card-border-strong);
    color: var(--app-text-secondary);
    .banner__icon {
      color: #94a3b8;
      background: rgba(255, 255, 255, 0.85);
      border: 1px solid var(--app-card-border);
    }
    strong {
      color: var(--app-text-regular);
    }
  }
}

// ---------- 对话流 ----------
.stream {
  display: flex;
  flex-direction: column;
  padding: 16px;

  &__tip {
    align-self: center;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    margin: 0 0 14px;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 500;
    color: var(--app-text-secondary);
    border-radius: 999px;
    background: var(--el-fill-color-light);
    border: 1px solid var(--app-card-border);
    svg {
      color: var(--app-brand);
    }
  }
  &__scroll {
    flex: 1;
    min-height: 360px;
    max-height: 52vh;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 4px 6px 8px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  &__empty {
    margin: auto;
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--app-text-placeholder);
    font-size: 13.5px;
    svg {
      color: var(--app-brand);
      opacity: 0.6;
    }
  }
}

.bubble-row {
  display: flex;
  width: 100%;

  &--right {
    justify-content: flex-end;
  }
  &--center {
    justify-content: center;
  }
}

.bubble {
  position: relative;
  max-width: min(72%, 460px);
  padding: 11px 15px 12px;
  border-radius: 16px;
  animation: app-message-in 0.28s cubic-bezier(0.22, 1, 0.36, 1) both;

  &__meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    font-weight: 600;
    opacity: 0.72;
    & span:nth-child(2) {
      padding: 2px 8px;
      border-radius: 999px;
      background: rgba(15, 23, 42, 0.06);
    }
  }
  &__price {
    margin-top: 6px;
    font-size: 21px;
    font-weight: 800;
    line-height: 1.15;
    font-variant-numeric: tabular-nums;
  }
  &__basis {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    margin-top: 8px;
    padding-top: 8px;
    font-size: 12px;
    line-height: 1.6;
    border-top: 1px solid currentColor;
    opacity: 0.82;
  }

  &--mine {
    color: #fff;
    background: var(--app-gradient-deep);
    border-bottom-right-radius: 5px;
    box-shadow: 0 10px 26px rgba(67, 56, 202, 0.28);
    animation-name: app-message-in-right;
    .bubble__basis {
      border-color: rgba(255, 255, 255, 0.28);
    }
    .bubble__meta span:nth-child(2) {
      background: rgba(255, 255, 255, 0.18);
    }
  }
  &--other {
    color: var(--app-text-regular);
    background: var(--app-card-bg-solid);
    border: 1px solid var(--app-card-border);
    border-bottom-left-radius: 5px;
    box-shadow: var(--app-shadow-card);
  }
}

.agent-note {
  display: inline-flex;
  align-items: flex-start;
  gap: 9px;
  max-width: min(80%, 520px);
  padding: 10px 14px;
  border-radius: 14px;
  background: var(--app-gradient-brand-soft, linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(34, 211, 238, 0.08)));
  border: 1px dashed var(--app-card-border-strong);

  &__icon {
    flex: none;
    margin-top: 2px;
    display: inline-flex;
    color: var(--app-brand);
  }
  &__title {
    font-size: 11.5px;
    font-weight: 800;
    color: var(--app-brand-strong);
  }
  &__text {
    margin-top: 2px;
    font-size: 12.5px;
    line-height: 1.6;
    color: var(--app-text-secondary);
  }
}

// Agent 建议条
.server-note {
  display: flex;
  align-items: center;
  gap: 13px;
  margin-top: 14px;
  padding: 13px 16px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.09), rgba(34, 211, 238, 0.09));
  border: 1px solid var(--app-card-border-strong);

  &__icon {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border-radius: 11px;
    color: #fff;
    background: var(--app-gradient);
    box-shadow: var(--app-shadow-glow);
  }
  &__body {
    flex: 1;
    min-width: 0;
  }
  &__title {
    display: flex;
    align-items: center;
    gap: 9px;
    font-size: 12.5px;
    font-weight: 800;
    color: var(--app-brand-strong);
  }
  &__deal {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11.5px;
    font-weight: 700;
    color: var(--app-success);
  }
  &__text {
    margin-top: 3px;
    font-size: 13px;
    line-height: 1.6;
    color: var(--app-text-regular);
  }
  &__adopt {
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 34px;
    padding: 0 15px;
    font-size: 12.5px;
    font-weight: 700;
    color: #fff;
    border: none;
    border-radius: 10px;
    background: var(--app-gradient);
    box-shadow: 0 6px 18px rgba(99, 102, 241, 0.32);
    cursor: pointer;
    transition: all 0.2s ease;
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 10px 24px rgba(99, 102, 241, 0.4);
    }
  }
}

// ---------- 洽谈消息 ----------
.chat {
  display: flex;
  flex-direction: column;
  padding: 16px 18px 15px;

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
  }
  &__title {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    h3 {
      margin: 0;
      font-size: 14.5px;
      font-weight: 700;
      color: var(--app-text-primary);
    }
    svg {
      color: var(--app-brand);
    }
  }
  &__ai-online {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px 3px 9px;
    font-size: 11.5px;
    font-weight: 700;
    color: var(--app-success);
    border-radius: 999px;
    background: var(--app-success-soft);
    border: 1px solid rgba(16, 185, 129, 0.28);
  }
  &__ai-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--app-success);
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.16);
    animation: app-pulse 2s ease-in-out infinite;
  }
  &__persona {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 9px 0 0;
    padding: 7px 11px;
    font-size: 12px;
    line-height: 1.5;
    color: var(--app-brand-strong);
    border-radius: 10px;
    background: var(--app-brand-soft);
    border: 1px solid var(--app-card-border);
    svg {
      flex: none;
      color: var(--app-brand);
    }
  }
  &__scroll {
    margin-top: 13px;
    min-height: 168px;
    max-height: 38vh;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 2px 4px 4px;
    display: flex;
    flex-direction: column;
    gap: 11px;
  }
  &__empty {
    margin: auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 9px;
    padding: 22px 0;
    font-size: 13px;
    color: var(--app-text-placeholder);
    svg {
      color: var(--app-brand);
      opacity: 0.55;
    }
  }
  &__composer {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    margin-top: 13px;
    padding-top: 13px;
    border-top: 1px dashed var(--app-divider, var(--app-card-border));
  }
  &__input {
    flex: 1;
  }
  &__send {
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    height: 38px;
    padding: 0 18px;
    font-size: 13.5px;
    white-space: nowrap;
  }
  &__closed {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-top: 13px;
    padding: 11px 14px;
    font-size: 12.5px;
    font-weight: 600;
    color: var(--app-text-secondary);
    border-radius: 12px;
    background: var(--el-fill-color-light);
    border: 1px solid var(--app-card-border);
    svg {
      color: var(--app-success);
    }
  }
}

:deep(.chat__input .el-textarea__inner) {
  border-radius: 12px;
  padding: 9px 13px;
  font-size: 13.5px;
  line-height: 1.55;
  box-shadow: none;
  background: var(--app-card-bg-solid);
  border-color: var(--app-card-border);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  &:focus {
    border-color: var(--app-card-border-strong);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
  }
}

.chat-row {
  display: flex;
  width: 100%;
  &--right {
    justify-content: flex-end;
  }
  &--typing {
    margin-top: -2px;
  }
}

.chat-bubble {
  position: relative;
  max-width: min(74%, 440px);
  padding: 9px 14px 8px;
  border-radius: 15px;
  animation: app-message-in 0.26s cubic-bezier(0.22, 1, 0.36, 1) both;

  &__name {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
    font-size: 11.5px;
    font-weight: 700;
    color: var(--app-brand-strong);
  }
  &__text {
    font-size: 13.5px;
    line-height: 1.65;
    white-space: pre-wrap;
    word-break: break-word;
  }
  &__time {
    margin-top: 4px;
    font-size: 10.5px;
    line-height: 1;
    text-align: right;
    font-variant-numeric: tabular-nums;
    opacity: 0.62;
  }

  &--mine {
    color: #fff;
    background: var(--app-gradient-deep);
    border-bottom-right-radius: 5px;
    box-shadow: 0 8px 22px rgba(67, 56, 202, 0.24);
    animation-name: app-message-in-right;
    .chat-bubble__time {
      color: rgba(255, 255, 255, 0.78);
    }
  }
  &--other {
    color: var(--app-text-regular);
    background: var(--app-card-bg-solid);
    border: 1px solid var(--app-card-border);
    border-bottom-left-radius: 5px;
    box-shadow: var(--app-shadow-card);
  }
  &--typing {
    padding: 10px 15px;
  }
}

.typing-dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 1px;
  i {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--app-text-placeholder);
    animation: typing-bounce 1.35s ease-in-out infinite;
  }
  i:nth-child(2) { animation-delay: 0.16s; }
  i:nth-child(3) { animation-delay: 0.32s; }
}

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.45; }
  30% { transform: translateY(-4px); opacity: 1; }
}

.chat-sys {
  align-self: center;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  max-width: min(86%, 520px);
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
  text-align: center;
  color: var(--app-brand-strong);
  border-radius: 999px;
  background: var(--app-brand-soft);
  border: 1px solid var(--app-card-border);
  svg {
    flex: none;
    color: var(--app-brand);
  }
}

// ---------- 推荐横滑 ----------
.recs {
  &__title {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 2px 12px;
    font-size: 14.5px;
    font-weight: 700;
    color: var(--app-text-primary);
    svg {
      color: var(--app-brand);
    }
  }
  &__rail {
    display: flex;
    gap: 14px;
    overflow-x: auto;
    padding: 2px 2px 10px;
    scroll-snap-type: x mandatory;
  }
}

.rec-card {
  flex: 0 0 218px;
  scroll-snap-align: start;
  padding: 0;
  overflow: hidden;

  &__media {
    position: relative;
    height: 112px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: rgba(255, 255, 255, 0.9);
    background: var(--app-gradient-deep);
  }
  &__fallback {
    position: absolute;
    inset: 0;
    margin: auto;
  }
  &__img {
    position: relative;
    z-index: 1;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  &__body {
    padding: 13px 15px 14px;
  }
  h4 {
    margin: 0;
    font-size: 13.5px;
    font-weight: 700;
    line-height: 1.45;
    color: var(--app-text-primary);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 39px;
  }
  &__meta {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 7px;
    font-size: 11.5px;
    color: var(--app-text-secondary);
  }
  &__price {
    margin-top: 7px;
    font-size: 19px;
    font-weight: 800;
    background: var(--app-gradient);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    font-variant-numeric: tabular-nums;
  }
  &__reason {
    display: flex;
    align-items: flex-start;
    gap: 5px;
    margin-top: 7px;
    font-size: 11.5px;
    line-height: 1.5;
    color: var(--app-brand-strong);
    svg {
      flex: none;
      margin-top: 1px;
      color: var(--app-brand);
    }
  }
}

// ---------- 底部出价区 ----------
.composer {
  padding: 15px 18px;
  position: sticky;
  bottom: 16px;

  &__row {
    display: flex;
    gap: 12px;
    align-items: center;
  }
  &__input {
    flex: 1;
  }
  &__send {
    flex: none;
    height: 40px;
    padding: 0 22px;
    font-size: 14px;
  }
  &__foot {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-top: 10px;
    flex-wrap: wrap;
  }
  &__reserve {
    font-size: 12px;
    color: var(--app-text-secondary);
    strong {
      color: var(--app-text-primary);
      font-variant-numeric: tabular-nums;
    }
  }
  &__offline {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--app-warning);
  }
  &__hint {
    margin-left: auto;
    font-size: 11.5px;
    color: var(--app-text-placeholder);
  }
  &__unit {
    font-size: 14px;
    font-weight: 700;
    color: var(--app-text-secondary);
  }
  &__pay {
    height: 36px;
    padding: 0 18px;
  }
  &__closed {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13.5px;
    font-weight: 600;
    color: var(--app-text-secondary);
  }
}

// ---------- 状态卡 ----------
.state-card {
  padding: 56px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 72px;
    height: 72px;
    border-radius: 22px;
    color: var(--app-danger);
    background: var(--app-danger-soft);
  }
  h3 {
    margin: 18px 0 8px;
    font-size: 17px;
    font-weight: 700;
    color: var(--app-text-primary);
  }
  p {
    margin: 0;
    font-size: 13.5px;
    color: var(--app-text-secondary);
  }
  &__actions {
    display: flex;
    gap: 12px;
    margin-top: 22px;
  }
  &__ghost {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    height: 40px;
    padding: 0 20px;
    font-size: 14px;
    font-weight: 600;
    color: var(--app-brand);
    border-radius: 10px;
    border: 1px solid var(--app-card-border-strong);
    background: var(--app-card-bg-solid);
    cursor: pointer;
    transition: all 0.22s ease;
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 22px rgba(99, 102, 241, 0.14);
    }
  }
}
.state-card .btn-gradient {
  height: 40px;
  padding: 0 22px;
}

@media (max-width: 720px) {
  .info-bar {
    align-items: flex-start;
    flex-direction: column;
  }
  .timer-ring,
  .status-seal {
    align-self: flex-end;
    margin-top: -66px;
  }
  .composer__hint {
    margin-left: 0;
    width: 100%;
  }
  .bubble {
    max-width: 86%;
  }
  .chat-bubble {
    max-width: 88%;
  }
  .chat__composer {
    flex-wrap: wrap;
  }
  .chat__input {
    flex: 1 1 200px;
  }
  .chat__send {
    flex: 0 0 auto;
  }
}
</style>
