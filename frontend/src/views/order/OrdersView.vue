<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  cancelOrder,
  deliverOrder,
  listOrders,
  payOrder,
  receiveOrder,
} from '@/api/orders'
import { listMyAppeals, submitAppeal, submitReview } from '@/api/social'
import type { MyAppeal, OrderView } from '@/api/types'
import ReceiptIcon from '~icons/lucide/receipt-text'
import PackageOpenIcon from '~icons/lucide/package-open'
import WalletIcon from '~icons/lucide/wallet'
import BanIcon from '~icons/lucide/ban'
import TruckIcon from '~icons/lucide/truck'
import PackageCheckIcon from '~icons/lucide/package-check'
import StarIcon from '~icons/lucide/star'
import GavelIcon from '~icons/lucide/gavel'
import RotateIcon from '~icons/lucide/rotate-ccw'
import CloudOffIcon from '~icons/lucide/cloud-off'
import StoreIcon from '~icons/lucide/store'
import ChevronRightIcon from '~icons/lucide/chevron-right'
import CircleCheckIcon from '~icons/lucide/circle-check'
import ClockIcon from '~icons/lucide/clock'

// ---------- 常量映射 ----------
type RoleFilter = 'all' | 'buyer' | 'seller'
type TabKey = 'all' | 'active' | 'done' | 'closed'

const ROLE_TABS: Array<{ key: RoleFilter; label: string }> = [
  { key: 'all', label: '全部角色' },
  { key: 'buyer', label: '我买到的' },
  { key: 'seller', label: '我卖出的' },
]

const STATUS_TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'active', label: '进行中' },
  { key: 'done', label: '已完成' },
  { key: 'closed', label: '已终止' },
]

const TAB_OF: Record<string, TabKey> = {
  created: 'active',
  unpaid: 'active',
  paid: 'active',
  receiving: 'active',
  appealing: 'active',
  completed: 'done',
  reviewed: 'done',
  canceled: 'closed',
  refunded: 'closed',
}

const STATUS_TAG: Record<string, { text: string; className: string }> = {
  created: { text: '已创建', className: 'tag--info' },
  unpaid: { text: '待支付', className: 'tag--warning' },
  paid: { text: '已支付', className: 'tag--brand' },
  receiving: { text: '待收货', className: 'tag--brand' },
  completed: { text: '已完成', className: 'tag--success' },
  appealing: { text: '申诉中', className: 'tag--danger' },
  refunded: { text: '已退款', className: 'tag--info' },
  canceled: { text: '已取消', className: 'tag--muted' },
  reviewed: { text: '已评价', className: 'tag--success' },
}

const APPEAL_STATUS_TEXT: Record<string, string> = {
  pending: '处理中 · 正在裁决',
  uphold: '申诉驳回 · 维持原裁决',
  upheld: '申诉驳回 · 维持原裁决',
  refund: '裁定支持 · 发起退款',
  manual: '已升级 · 人工复核中',
  closed: '申诉已关闭',
}

const STEP_TITLES = ['待支付', '待收货', '已完成', '已评价']

function stepActive(order: OrderView): number {
  switch (order.status) {
    case 'created':
    case 'unpaid':
      return 0
    case 'paid':
    case 'receiving':
      return 1
    case 'completed':
      return 2
    case 'reviewed':
      return 4
    default:
      return 0
  }
}

function yuan(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function fmtDateTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function payDeadlineText(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `请于 ${d.getMonth() + 1}月${d.getDate()}日 ${pad(d.getHours())}:${pad(d.getMinutes())} 前完成支付`
}

// ---------- 状态 ----------
const orders = ref<OrderView[]>([])
const appeals = ref<MyAppeal[]>([])
const loading = ref(true)
const errorMsg = ref('')
const roleFilter = ref<RoleFilter>('all')
const activeTab = ref<TabKey>('all')

const actingId = ref<number | null>(null)
const appealVisible = ref(false)
const appealOrder = ref<OrderView | null>(null)
const appealReason = ref('')
const appealSubmitting = ref(false)

const reviewVisible = ref(false)
const reviewOrder = ref<OrderView | null>(null)
const reviewScore = ref(5)
const reviewContent = ref('')
const reviewSubmitting = ref(false)

const filtered = computed(() =>
  orders.value.filter((o) => {
    if (roleFilter.value !== 'all' && o.my_role !== roleFilter.value) return false
    if (activeTab.value !== 'all' && (TAB_OF[o.status] ?? 'active') !== activeTab.value) return false
    return true
  }),
)

const counts = computed(() => {
  const c = { all: 0, active: 0, done: 0, closed: 0, buy: 0, sell: 0 }
  for (const o of orders.value) {
    c.all += 1
    const tab = TAB_OF[o.status] ?? 'active'
    if (tab === 'active') c.active += 1
    else if (tab === 'done') c.done += 1
    else if (tab === 'closed') c.closed += 1
    if (o.my_role === 'buyer') c.buy += 1
    else c.sell += 1
  }
  return c
})

function appealOf(orderId: number): MyAppeal | undefined {
  return appeals.value.find((a) => a.order_id === orderId)
}

// ---------- 数据加载 ----------
async function load(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    const [rows, appealRows] = await Promise.all([
      listOrders(),
      listMyAppeals().catch(() => [] as MyAppeal[]),
    ])
    orders.value = rows
    appeals.value = appealRows
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '订单加载失败'
  } finally {
    loading.value = false
  }
}

async function runAction(
  order: OrderView,
  action: () => Promise<OrderView>,
  pendingText: string,
  successText: string,
): Promise<void> {
  actingId.value = order.id
  try {
    const updated = await action()
    Object.assign(order, updated)
    ElMessage.success(successText || pendingText)
  } catch {
    /* 全局拦截器已提示；若后端状态已变更则做一次静默同步 */
    await load()
  } finally {
    actingId.value = null
  }
}

async function onPay(order: OrderView): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `将通过沙箱支付向卖家支付 ¥${yuan(order.deal_price)}，支付后卖家将确认交付。是否继续？`,
      '模拟支付确认',
      {
        confirmButtonText: '确认支付',
        cancelButtonText: '再想想',
        type: 'info',
        roundButton: true,
      },
    )
  } catch {
    return
  }
  await runAction(order, () => payOrder(order.id), '支付中…', '支付成功（沙箱模拟），等待卖家交付')
}

async function onCancel(order: OrderView): Promise<void> {
  try {
    await ElMessageBox.confirm('取消后预占锁将释放，且可能影响信用记录。确认取消该订单？', '取消订单', {
      confirmButtonText: '确认取消',
      cancelButtonText: '再等等',
      type: 'warning',
      roundButton: true,
    })
  } catch {
    return
  }
  await runAction(order, () => cancelOrder(order.id), '取消中…', '订单已取消')
}

async function onDeliver(order: OrderView): Promise<void> {
  try {
    await ElMessageBox.confirm('请确认已与买家完成校内面交或交付，提交后买家将可确认收货。', '卖家确认交付', {
      confirmButtonText: '已交付',
      cancelButtonText: '取消',
      type: 'success',
      roundButton: true,
    })
  } catch {
    return
  }
  await runAction(order, () => deliverOrder(order.id), '提交中…', '交付已确认，等待买家收货')
}

async function onReceive(order: OrderView): Promise<void> {
  try {
    await ElMessageBox.confirm('确认已收到商品且验货无误？确认后交易完成，可对本次交易进行评价。', '确认收货', {
      confirmButtonText: '确认收货',
      cancelButtonText: '还没收到',
      type: 'success',
      roundButton: true,
    })
  } catch {
    return
  }
  await runAction(order, () => receiveOrder(order.id), '确认中…', '交易完成，感谢使用校园集市')
}

// ---------- 申诉 ----------
function openAppeal(order: OrderView): void {
  appealOrder.value = order
  appealReason.value = ''
  appealVisible.value = true
}

async function submitAppealForm(): Promise<void> {
  if (!appealOrder.value || appealSubmitting.value) return
  const reason = appealReason.value.trim()
  if (reason.length < 5) {
    ElMessage.warning('申诉理由至少 5 个字，请描述具体问题')
    return
  }
  appealSubmitting.value = true
  try {
    await submitAppeal({ order_id: appealOrder.value.id, reason })
    appealVisible.value = false
    ElMessage.success('已提交，等待处理')
    await load()
  } catch {
    /* 全局提示 */
  } finally {
    appealSubmitting.value = false
  }
}

// ---------- 评价 ----------
function openReview(order: OrderView): void {
  reviewOrder.value = order
  reviewScore.value = 5
  reviewContent.value = ''
  reviewVisible.value = true
}

async function submitReviewForm(): Promise<void> {
  if (!reviewOrder.value || reviewSubmitting.value) return
  if (!reviewScore.value) {
    ElMessage.warning('请先选择评分星级')
    return
  }
  reviewSubmitting.value = true
  try {
    const result = await submitReview({
      order_id: reviewOrder.value.id,
      score: reviewScore.value,
      content: reviewContent.value.trim() || undefined,
    })
    reviewVisible.value = false
    ElMessage.success(`${result.summary}（信用 ${result.credit_delta >= 0 ? '+' : ''}${result.credit_delta}）`)
    await load()
  } catch {
    /* 全局提示 */
  } finally {
    reviewSubmitting.value = false
  }
}

function statusHint(order: OrderView): string {
  if (order.my_role === 'buyer') {
    if (order.status === 'paid') return '已支付，等待卖家确认交付'
    if (order.status === 'receiving') return '卖家已确认交付，请收货验货后确认'
  } else {
    if (order.status === 'paid') return '买家已付款，请尽快确认交付'
    if (order.status === 'receiving') return '已交付，等待买家确认收货'
    if (order.status === 'unpaid' || order.status === 'created') return '订单已创建，等待买家支付'
  }
  return ''
}

onMounted(load)
</script>

<template>
  <div class="page-container orders">
    <header class="page-head anim-fade-in-up">
      <div>
        <span class="page-head__chip">
          <ReceiptIcon :width="13" :height="13" :stroke-width="2.2" />
          订单状态机 · 预占锁 · 履约信用
        </span>
        <h1 class="page-head__title">我的订单</h1>
        <p class="page-head__desc">支付、校内面交交付、确认收货、双向评价与申诉全流程追踪</p>
      </div>
    </header>

    <!-- 筛选 -->
    <div v-if="!loading && !errorMsg" class="filters anim-fade-in">
      <div class="seg">
        <button
          v-for="t in ROLE_TABS"
          :key="t.key"
          class="seg__item"
          :class="{ 'is-active': roleFilter === t.key }"
          type="button"
          @click="roleFilter = t.key"
        >
          {{ t.label }}
          <span class="seg__num">{{ t.key === 'buyer' ? counts.buy : t.key === 'seller' ? counts.sell : counts.all }}</span>
        </button>
      </div>
      <div class="tabs">
        <button
          v-for="t in STATUS_TABS"
          :key="t.key"
          class="tabs__item"
          :class="{ 'is-active': activeTab === t.key }"
          type="button"
          @click="activeTab = t.key"
        >
          {{ t.label }}
          <span class="tabs__num">{{ counts[t.key] }}</span>
        </button>
      </div>
    </div>

    <!-- 骨架 -->
    <div v-if="loading" class="order-stack">
      <article v-for="n in 3" :key="n" class="order-card glass-card">
        <div class="skeleton order-card__thumb" />
        <div class="order-card__body">
          <div class="skeleton" style="width: 40%; height: 15px" />
          <div class="skeleton" style="width: 70%; height: 13px; margin-top: 12px" />
          <div class="skeleton" style="width: 92%; height: 26px; margin-top: 18px; border-radius: 8px" />
          <div class="skeleton" style="width: 50%; height: 12px; margin-top: 14px" />
        </div>
      </article>
    </div>

    <!-- 错误 -->
    <section v-else-if="errorMsg" class="state-card glass-card anim-fade-in-up">
      <span class="state-card__icon"><CloudOffIcon :stroke-width="1.8" /></span>
      <h3>订单加载失败</h3>
      <p>{{ errorMsg }}</p>
      <button class="btn-gradient" @click="load">
        <RotateIcon :width="16" :height="16" :stroke-width="2.4" />
        重新加载
      </button>
    </section>

    <!-- 空状态 -->
    <section v-else-if="filtered.length === 0" class="state-card glass-card anim-fade-in-up">
      <span class="state-card__illu">
        <ReceiptIcon :width="44" :height="44" :stroke-width="1.5" />
        <span class="state-card__ring" />
      </span>
      <h3>暂无相关订单</h3>
      <p>
        {{ activeTab === 'all' && roleFilter === 'all'
          ? '完成第一笔议价成交后，订单会出现在这里。'
          : '切换筛选条件看看，或去市场淘一件心仪好物。' }}
      </p>
      <div class="state-card__actions">
        <button class="btn-gradient" @click="$router.push('/market')">
          <StoreIcon :width="16" :height="16" :stroke-width="2.4" />
          去市场逛逛
        </button>
      </div>
    </section>

    <!-- 订单列表 -->
    <div v-else class="order-stack stagger">
      <article
        v-for="order in filtered"
        :key="order.id"
        class="order-card glass-card"
        :class="[`order-card--${order.status}`, { 'order-card--appealing': order.status === 'appealing' }]"
      >
        <!-- 头部 -->
        <header class="order-card__head">
          <div class="order-card__id">
            <span class="order-card__no">订单号 {{ order.order_no }}</span>
            <span class="order-card__time">
              <ClockIcon :width="11" :height="11" :stroke-width="2.3" />
              {{ fmtDateTime(order.created_at) }}
            </span>
          </div>
          <span class="tag" :class="STATUS_TAG[order.status]?.className ?? 'tag--info'">
            {{ order.status_text }}
          </span>
        </header>

        <div class="order-card__content">
          <!-- 商品 -->
          <div class="order-card__thumb">
            <PackageOpenIcon
              class="order-card__thumb-fallback"
              :width="26"
              :height="26"
              :stroke-width="1.7"
            />
            <img
              v-if="order.item_image"
              :src="order.item_image"
              :alt="order.item_title"
              class="order-card__img"
              @error="(e) => ((e.currentTarget as HTMLImageElement).style.display = 'none')"
            />
          </div>

          <div class="order-card__body">
            <h3 class="order-card__title">{{ order.item_title }}</h3>

            <div class="order-card__parties">
              <span class="party-chip">
                <component
                  :is="order.my_role === 'buyer' ? WalletIcon : StoreIcon"
                  :width="12"
                  :height="12"
                  :stroke-width="2.2"
                />
                我是{{ order.my_role === 'buyer' ? '买家' : '卖家' }}
              </span>
              <ChevronRightIcon class="party-arrow" :width="13" :height="13" :stroke-width="2.4" />
              <span class="party-chip party-chip--other">{{ order.counterparty_nickname }}</span>
            </div>

            <div class="order-card__deal">
              <span class="order-card__deal-label">成交价</span>
              <span class="order-card__deal-price">¥{{ yuan(order.deal_price) }}</span>
            </div>
          </div>
        </div>

        <!-- 申诉提示条 -->
        <div v-if="order.status === 'appealing'" class="appeal-strip">
          <GavelIcon :width="15" :height="15" :stroke-width="2.2" />
          <div class="appeal-strip__body">
            <strong>申诉处理中</strong>
            <span v-if="appealOf(order.id)">
              {{ APPEAL_STATUS_TEXT[appealOf(order.id)!.status] ?? '纠纷三级终裁流程进行中' }}
            </span>
            <span v-else>纠纷仲裁 Agent 正在核验证据包，请保持订单信息畅通</span>
          </div>
        </div>

        <!-- 异常状态展示 -->
        <div v-else-if="order.status === 'canceled' || order.status === 'refunded'" class="terminal-strip">
          <component
            :is="order.status === 'refunded' ? CircleCheckIcon : BanIcon"
            :width="15"
            :height="15"
            :stroke-width="2.2"
          />
          <span>
            {{ order.status === 'refunded' ? '已按终裁结果完成退款，订单关闭' : '订单已取消，商品预占锁已释放' }}
          </span>
          <span class="terminal-strip__time">{{ fmtDateTime(order.updated_at) }}</span>
        </div>

        <!-- 时间线 -->
        <div v-else class="order-card__steps">
          <el-steps :active="stepActive(order)" align-center finish-status="success">
            <el-step v-for="(title, idx) in STEP_TITLES" :key="title" :title="title">
              <template #description>
                <span v-if="idx === 0 && (order.status === 'unpaid' || order.status === 'created')" class="step-desc">
                  {{ payDeadlineText(order.pay_deadline) }}
                </span>
                <span v-else-if="idx === 1 && statusHint(order)" class="step-desc">
                  {{ statusHint(order) }}
                </span>
                <span v-else-if="idx === 2 && order.status === 'reviewed'" class="step-desc">交易完成</span>
                <span v-else-if="idx === 3" class="step-desc">双方互评</span>
              </template>
            </el-step>
          </el-steps>
        </div>

        <!-- 操作按钮 -->
        <footer class="order-card__actions">
          <template v-if="order.my_role === 'buyer'">
            <template v-if="order.status === 'unpaid' || order.status === 'created'">
              <el-button type="primary" :loading="actingId === order.id" @click="onPay(order)">
                <WalletIcon :width="15" :height="15" :stroke-width="2.3" />
                模拟支付
              </el-button>
              <el-button :disabled="actingId === order.id" @click="onCancel(order)">
                <BanIcon :width="15" :height="15" :stroke-width="2.2" />
                取消订单
              </el-button>
            </template>
            <template v-else-if="order.status === 'receiving'">
              <el-button type="primary" :loading="actingId === order.id" @click="onReceive(order)">
                <PackageCheckIcon :width="15" :height="15" :stroke-width="2.3" />
                确认收货
              </el-button>
              <el-button :disabled="actingId === order.id" @click="openAppeal(order)">
                <GavelIcon :width="15" :height="15" :stroke-width="2.2" />
                申诉
              </el-button>
            </template>
            <template v-else-if="order.status === 'completed' && !order.i_reviewed">
              <el-button type="primary" @click="openReview(order)">
                <StarIcon :width="15" :height="15" :stroke-width="2.3" />
                评价交易
              </el-button>
            </template>
          </template>

          <template v-else>
            <el-button
              v-if="order.status === 'paid'"
              type="primary"
              :loading="actingId === order.id"
              @click="onDeliver(order)"
            >
              <TruckIcon :width="15" :height="15" :stroke-width="2.3" />
              确认交付
            </el-button>
          </template>

          <span v-if="order.status === 'completed' && order.i_reviewed" class="actions-note">
            <CircleCheckIcon :width="14" :height="14" :stroke-width="2.3" />
            已完成评价
          </span>
          <span v-else-if="order.status === 'reviewed'" class="actions-note">
            <StarIcon :width="14" :height="14" :stroke-width="2.3" />
            双方已互评（{{ order.review_count }} 条）
          </span>
        </footer>
      </article>
    </div>

    <!-- 申诉弹框 -->
    <el-dialog v-model="appealVisible" title="发起申诉" width="520px" class="action-dialog" append-to-body>
      <div class="dialog-banner">
        <GavelIcon :width="16" :height="16" :stroke-width="2.2" />
        <p>申诉将按「协调仲裁 → 规则裁决 → 人工兜底」三级处理；证据包与裁决书全程留痕。</p>
      </div>
      <div v-if="appealOrder" class="dialog-order">
        <PackageOpenIcon :width="15" :height="15" :stroke-width="2.1" />
        <span class="dialog-order__title">{{ appealOrder.item_title }}</span>
        <span class="dialog-order__price">¥{{ yuan(appealOrder.deal_price) }}</span>
      </div>
      <el-input
        v-model="appealReason"
        type="textarea"
        :rows="4"
        maxlength="500"
        show-word-limit
        placeholder="请描述申诉理由（至少 5 个字），如：与描述不符、未收到货、卖家拒绝沟通…"
      />
      <template #footer>
        <el-button @click="appealVisible = false">取消</el-button>
        <el-button type="primary" :loading="appealSubmitting" @click="submitAppealForm">
          <GavelIcon :width="15" :height="15" :stroke-width="2.3" />
          提交申诉
        </el-button>
      </template>
    </el-dialog>

    <!-- 评价弹框 -->
    <el-dialog v-model="reviewVisible" title="评价本次交易" width="520px" class="action-dialog" append-to-body>
      <div v-if="reviewOrder" class="dialog-order">
        <PackageOpenIcon :width="15" :height="15" :stroke-width="2.1" />
        <span class="dialog-order__title">{{ reviewOrder.item_title }}</span>
        <span class="dialog-order__price">¥{{ yuan(reviewOrder.deal_price) }}</span>
      </div>
      <div class="review-box">
        <div class="review-box__label">综合评分</div>
        <el-rate
          v-model="reviewScore"
          :max="5"
          size="large"
          :colors="['#fbbf24', '#f59e0b', '#f59e0b']"
        />
        <div class="review-box__hint">评价将计入双方信用分，评分由履约信用 Agent 聚合</div>
      </div>
      <el-input
        v-model="reviewContent"
        type="textarea"
        :rows="4"
        maxlength="300"
        show-word-limit
        placeholder="说说商品成色、沟通与交付体验（选填）"
      />
      <template #footer>
        <el-button @click="reviewVisible = false">取消</el-button>
        <el-button type="primary" :loading="reviewSubmitting" @click="submitReviewForm">
          <StarIcon :width="15" :height="15" :stroke-width="2.3" />
          提交评价
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.orders {
  padding-top: 28px;
}

.page-head {
  &__chip {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 13px;
    font-size: 12px;
    font-weight: 500;
    color: var(--app-brand-strong);
    border-radius: 999px;
    background: var(--app-brand-soft);
    border: 1px solid var(--app-card-border);
  }
  &__title {
    margin: 12px 0 0;
    font-size: 26px;
    font-weight: 800;
    color: var(--app-text-primary);
  }
  &__desc {
    margin: 8px 0 0;
    font-size: 13.5px;
    color: var(--app-text-secondary);
  }
}

// ---------- 筛选 ----------
.filters {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  margin: 22px 0 18px;
}

.seg,
.tabs {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border-radius: 999px;
  background: var(--app-card-bg);
  border: 1px solid var(--app-card-border);
  backdrop-filter: blur(12px);
}

.seg__item,
.tabs__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 15px;
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text-secondary);
  border: none;
  border-radius: 999px;
  background: transparent;
  cursor: pointer;
  transition: all 0.2s ease;
  &:hover {
    color: var(--app-brand);
    background: var(--app-nav-item-hover);
  }
  &.is-active {
    color: #fff;
    background: var(--app-gradient);
    box-shadow: 0 5px 15px rgba(99, 102, 241, 0.3);
  }
}
.seg__num,
.tabs__num {
  min-width: 19px;
  height: 19px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.07);
  color: var(--app-text-placeholder);
  font-variant-numeric: tabular-nums;
}
.seg__item.is-active .seg__num,
.tabs__item.is-active .tabs__num {
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
}

// ---------- 订单卡片 ----------
.order-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.order-card {
  padding: 18px 22px 16px;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    background: var(--app-brand);
    opacity: 0.7;
  }
  &--completed::before,
  &--reviewed::before {
    background: var(--app-success);
  }
  &--canceled::before,
  &--refunded::before {
    background: var(--el-border-color-darker);
  }
  &--appealing::before {
    background: var(--app-danger);
  }

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }
  &__id {
    display: inline-flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
  }
  &__no {
    font-size: 12.5px;
    font-weight: 600;
    color: var(--app-text-placeholder);
    font-variant-numeric: tabular-nums;
  }
  &__time {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
    color: var(--app-text-placeholder);
    font-variant-numeric: tabular-nums;
  }

  &__content {
    display: flex;
    gap: 16px;
    margin-top: 14px;
  }
  &__thumb {
    position: relative;
    flex: none;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 84px;
    height: 84px;
    border-radius: 15px;
    overflow: hidden;
    color: rgba(255, 255, 255, 0.92);
    background: var(--app-gradient-deep);
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.14);
  }
  &__thumb-fallback {
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
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  &__title {
    margin: 0;
    font-size: 16px;
    font-weight: 700;
    line-height: 1.45;
    color: var(--app-text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  &__parties {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12.5px;
    color: var(--app-text-secondary);
  }
  &__deal {
    display: inline-flex;
    align-items: baseline;
    gap: 7px;
    margin-top: auto;
  }
  &__deal-label {
    font-size: 12px;
    color: var(--app-text-placeholder);
  }
  &__deal-price {
    font-size: 22px;
    font-weight: 800;
    line-height: 1;
    color: transparent;
    background: var(--app-gradient);
    -webkit-background-clip: text;
    background-clip: text;
    font-variant-numeric: tabular-nums;
  }

  &__steps {
    margin-top: 16px;
    padding: 14px 10px 4px;
    border-radius: 13px;
    background: var(--el-fill-color-lighter);
    border: 1px solid var(--app-card-border);
  }
  &__actions {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 14px;
    flex-wrap: wrap;
    .el-button {
      margin-left: 0;
    }
  }
}

.party-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 11px;
  font-size: 11.5px;
  font-weight: 600;
  border-radius: 999px;
  color: var(--app-brand-strong);
  background: var(--app-brand-soft);
  &--other {
    color: var(--app-text-regular);
    background: var(--el-fill-color);
  }
}
.party-arrow {
  color: var(--app-text-placeholder);
}

.actions-note {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--app-success);
  svg {
    color: var(--app-success);
  }
}

.step-desc {
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--app-text-secondary);
}

:deep(.el-steps) {
  .el-step__icon.is-text {
    background: var(--app-gradient);
    color: #fff;
    border: none;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.28);
  }
  .el-step__head.is-process .el-step__icon.is-text {
    box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.12);
  }
}

// ---------- 标签 ----------
.tag {
  flex: none;
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 700;
  border-radius: 999px;
  &--warning {
    color: #b45309;
    background: var(--app-warning-soft);
  }
  &--brand {
    color: var(--app-brand-strong);
    background: var(--app-brand-soft);
  }
  &--success {
    color: var(--app-success);
    background: var(--app-success-soft);
  }
  &--danger {
    color: var(--app-danger);
    background: var(--app-danger-soft);
  }
  &--info {
    color: var(--app-info);
    background: var(--app-info-soft);
  }
  &--muted {
    color: var(--app-text-secondary);
    background: var(--el-fill-color-dark);
  }
}

// ---------- 申诉 / 终止条 ----------
.appeal-strip,
.terminal-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 15px;
  padding: 11px 15px;
  border-radius: 12px;
  font-size: 12.5px;
}
.appeal-strip {
  color: #991b1b;
  background: linear-gradient(135deg, rgba(254, 226, 226, 0.9), rgba(254, 242, 242, 0.6));
  border: 1px solid rgba(239, 68, 68, 0.28);
  svg {
    flex: none;
    color: var(--app-danger);
  }
  strong {
    font-weight: 800;
    margin-right: 6px;
  }
}
.terminal-strip {
  color: var(--app-text-secondary);
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);
  svg {
    flex: none;
  }
  &__time {
    margin-left: auto;
    font-size: 12px;
    color: var(--app-text-placeholder);
  }
}

// ---------- 弹框 ----------
.action-dialog {
  :deep(.el-dialog__body) {
    padding-top: 8px;
  }
}
.dialog-banner {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  margin-bottom: 16px;
  border-radius: 12px;
  background: var(--app-gradient-brand-soft, linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(34, 211, 238, 0.08)));
  border: 1px solid var(--app-card-border);
  svg {
    flex: none;
    margin-top: 2px;
    color: var(--app-brand);
  }
  p {
    margin: 0;
    font-size: 12.5px;
    line-height: 1.7;
    color: var(--app-text-secondary);
  }
}
.dialog-order {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  margin-bottom: 16px;
  border-radius: 12px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--app-card-border);
  svg {
    color: var(--app-brand);
  }
  &__title {
    flex: 1;
    min-width: 0;
    font-size: 13.5px;
    font-weight: 700;
    color: var(--app-text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  &__price {
    flex: none;
    font-size: 17px;
    font-weight: 800;
    background: var(--app-gradient);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    font-variant-numeric: tabular-nums;
  }
}
.review-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 13px 15px;
  margin-bottom: 14px;
  border-radius: 12px;
  background: var(--app-warning-soft);
  border: 1px solid rgba(245, 158, 11, 0.25);
  &__label {
    font-size: 12.5px;
    font-weight: 700;
    color: #92400e;
  }
  &__hint {
    font-size: 12px;
    color: #a16207;
  }
}

// ---------- 状态卡 ----------
.state-card {
  margin-top: 26px;
  padding: 56px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;

  &__illu {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 108px;
    height: 108px;
    border-radius: 32px;
    color: var(--app-brand);
    background: var(--app-gradient-brand-soft, linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(34, 211, 238, 0.1)));
    border: 1px solid var(--app-card-border);
  }
  &__ring {
    position: absolute;
    inset: -9px;
    border-radius: 38px;
    border: 1.5px dashed var(--app-card-border-strong);
    animation: app-spin 26s linear infinite;
  }
  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 52px;
    height: 52px;
    color: var(--app-danger);
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
    margin-top: 22px;
  }
}
.state-card .btn-gradient {
  height: 40px;
  padding: 0 22px;
}

// ---------- el-steps 微调 ----------
@media (max-width: 640px) {
  .order-card {
    padding: 16px 16px 14px;
  }
  .step-desc {
    display: none;
  }
  .terminal-strip__time {
    display: none;
  }
}
</style>
