<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listNegotiations } from '@/api/negotiation'
import type { NegotiationView } from '@/api/types'
import MessagesIcon from '~icons/lucide/messages-square'
import StoreIcon from '~icons/lucide/store'
import ArrowRightIcon from '~icons/lucide/arrow-right'
import ArrowLeftIcon from '~icons/lucide/arrow-left'
import ScaleIcon from '~icons/lucide/scale'
import TrophyIcon from '~icons/lucide/trophy'
import HeartCrackIcon from '~icons/lucide/heart-crack'
import CircleDashedIcon from '~icons/lucide/circle-dashed'
import RotateIcon from '~icons/lucide/rotate-ccw'
import CloudOffIcon from '~icons/lucide/cloud-off'
import PackageOpenIcon from '~icons/lucide/package-open'
import TimerIcon from '~icons/lucide/timer'

const router = useRouter()

type FilterKey = 'all' | 'ongoing' | 'deal' | 'terminated'

const FILTERS: Array<{ key: FilterKey; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'ongoing', label: '进行中' },
  { key: 'deal', label: '已成交' },
  { key: 'terminated', label: '已破裂' },
]

const STATUS_META: Record<
  NegotiationView['status'],
  { text: string; className: string; icon: unknown }
> = {
  ongoing: { text: '进行中', className: 'neg-status--ongoing', icon: CircleDashedIcon },
  deal: { text: '已成交', className: 'neg-status--deal', icon: TrophyIcon },
  terminated: { text: '已破裂', className: 'neg-status--terminated', icon: HeartCrackIcon },
}

function yuan(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function fmtTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}月${d.getDate()}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const rows = ref<NegotiationView[]>([])
const loading = ref(true)
const errorMsg = ref('')
const filter = ref<FilterKey>('all')

const filtered = computed(() =>
  filter.value === 'all' ? rows.value : rows.value.filter((r) => r.status === filter.value),
)

const counts = computed(() => ({
  all: rows.value.length,
  ongoing: rows.value.filter((r) => r.status === 'ongoing').length,
  deal: rows.value.filter((r) => r.status === 'deal').length,
  terminated: rows.value.filter((r) => r.status === 'terminated').length,
}))

async function load(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    rows.value = await listNegotiations()
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '议价列表加载失败'
  } finally {
    loading.value = false
  }
}

function counterparty(row: NegotiationView): string {
  return row_my_role(row) === 'buyer' ? row.seller_nickname : row.buyer_nickname
}

function counterpartyIsAi(row: NegotiationView): boolean {
  return row_my_role(row) === 'buyer' ? Boolean(row.seller_is_ai) : Boolean(row.buyer_is_ai)
}

function row_my_role(row: NegotiationView): 'buyer' | 'seller' | 'observer' {
  return row.my_role
}

function latestRound(row: NegotiationView): number {
  return row.offers?.length ? Math.max(...row.offers.map((o) => o.round)) : 0
}

function latestPrice(row: NegotiationView): number | null {
  if (!row.offers?.length) return null
  return row.offers[row.offers.length - 1].price
}

function openRoom(id: number): void {
  void router.push(`/negotiations/${id}`)
}

onMounted(load)
</script>

<template>
  <div class="page-container neg-list">
    <header class="page-head anim-fade-in-up">
      <div>
        <span class="page-head__chip">
          <MessagesIcon :width="13" :height="13" :stroke-width="2.2" />
          纳什议价 · 多轮让步
        </span>
        <h1 class="page-head__title">议价室</h1>
        <p class="page-head__desc">交易 Agent 提供纳什参考价与让步建议，出价顺序经 WebSocket 实时同步</p>
      </div>
      <button class="btn-gradient page-head__action" @click="router.push('/market')">
        <StoreIcon :width="16" :height="16" :stroke-width="2.3" />
        去市场逛逛
      </button>
    </header>

    <!-- 筛选 -->
    <div v-if="!loading && !errorMsg" class="filter-bar anim-fade-in">
      <button
        v-for="f in FILTERS"
        :key="f.key"
        class="filter-bar__item"
        :class="{ 'is-active': filter === f.key }"
        type="button"
        @click="filter = f.key"
      >
        {{ f.label }}
        <span class="filter-bar__num">{{ counts[f.key] }}</span>
      </button>
    </div>

    <!-- 骨架 -->
    <div v-if="loading" class="neg-stack">
      <article v-for="n in 4" :key="n" class="neg-card glass-card">
        <div class="skeleton neg-card__thumb" />
        <div class="neg-card__main">
          <div class="skeleton" style="width: 46%; height: 15px" />
          <div class="skeleton" style="width: 80%; height: 13px; margin-top: 12px" />
          <div class="skeleton" style="width: 60%; height: 13px; margin-top: 9px" />
        </div>
        <div class="skeleton" style="width: 92px; height: 30px; border-radius: 999px" />
      </article>
    </div>

    <!-- 错误 -->
    <section v-else-if="errorMsg" class="state-card glass-card anim-fade-in-up">
      <span class="state-card__icon"><CloudOffIcon :stroke-width="1.8" /></span>
      <h3>议价记录加载失败</h3>
      <p>{{ errorMsg }}</p>
      <button class="btn-gradient" @click="load">
        <RotateIcon :width="16" :height="16" :stroke-width="2.4" />
        重新加载
      </button>
    </section>

    <!-- 空状态 -->
    <section v-else-if="filtered.length === 0" class="state-card glass-card anim-fade-in-up">
      <span class="state-card__illu">
        <MessagesIcon :width="44" :height="44" :stroke-width="1.5" />
        <span class="state-card__ring" />
      </span>
      <h3>{{ filter === 'all' ? '还没有议价会话' : '当前筛选下没有会话' }}</h3>
      <p>
        {{ filter === 'all' ? '在市场中挑中心仪的商品，发起议价后可在此查看每轮出价与纳什参考价。' : '切换其他状态，或去市场发现新的闲置好物。' }}
      </p>
      <div class="state-card__actions">
        <button class="btn-gradient" @click="router.push('/market')">
          <StoreIcon :width="16" :height="16" :stroke-width="2.4" />
          前往二手市场
        </button>
        <button v-if="filter !== 'all'" class="state-card__ghost" @click="filter = 'all'">
          <ArrowLeftIcon :width="15" :height="15" :stroke-width="2.2" />
          查看全部
        </button>
      </div>
    </section>

    <!-- 列表 -->
    <div v-else class="neg-stack stagger">
      <article
        v-for="row in filtered"
        :key="row.id"
        class="neg-card glass-card glass-card--hover"
        :class="`neg-card--${row.status}`"
        @click="openRoom(row.id)"
      >
        <div class="neg-card__thumb">
          <PackageOpenIcon
            class="neg-card__thumb-fallback"
            :width="26"
            :height="26"
            :stroke-width="1.7"
            style="color: rgba(255, 255, 255, 0.92)"
          />
          <img
            v-if="row.item_image"
            :src="row.item_image"
            :alt="row.item_title"
            class="neg-card__img"
            @error="(e) => ((e.currentTarget as HTMLImageElement).style.display = 'none')"
          />
        </div>

        <div class="neg-card__main">
          <div class="neg-card__title-row">
            <h3 class="neg-card__title">{{ row.item_title }}</h3>
            <span class="neg-status" :class="STATUS_META[row.status].className">
              <component :is="STATUS_META[row.status].icon" :width="12" :height="12" :stroke-width="2.3" />
              {{ STATUS_META[row.status].text }}
            </span>
          </div>

          <div class="neg-card__sub">
            <span class="neg-card__party">
              <span class="neg-card__role">{{ row_my_role(row) === 'buyer' ? '卖家' : '买家' }}</span>
              {{ counterparty(row) }}
              <AiBadge v-if="counterpartyIsAi(row)" size="sm" />
            </span>
            <span class="neg-card__dot">·</span>
            <span class="neg-card__round">
              <TimerIcon :width="12" :height="12" :stroke-width="2.3" />
              第 {{ latestRound(row) || '—' }} / {{ row.max_rounds }} 轮
            </span>
          </div>

          <div class="neg-card__metrics">
            <span class="metric">
              <ScaleIcon :width="13" :height="13" :stroke-width="2.2" />
              纳什价
              <strong>¥{{ yuan(row.nash_price) }}</strong>
            </span>
            <span v-if="row.status === 'deal'" class="metric metric--deal">
              <TrophyIcon :width="13" :height="13" :stroke-width="2.2" />
              成交价
              <strong>¥{{ yuan(row.deal_price) }}</strong>
            </span>
            <span v-else-if="latestPrice(row) !== null" class="metric">
              <MessagesIcon :width="13" :height="13" :stroke-width="2.2" />
              最新出价
              <strong>¥{{ yuan(latestPrice(row)) }}</strong>
            </span>
            <span class="neg-card__time">{{ fmtTime(row.closed_at || row.created_at) }}</span>
          </div>
        </div>

        <span class="neg-card__enter">
          <ArrowRightIcon :width="18" :height="18" :stroke-width="2.3" />
        </span>
      </article>
    </div>
  </div>
</template>

<style scoped lang="scss">
.neg-list {
  padding-top: 28px;
}

.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;

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
  &__action {
    height: 40px;
    padding: 0 20px;
    font-size: 14px;
  }
}

// ---------- 筛选 ----------
.filter-bar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin: 22px 0 18px;

  &__item {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    height: 34px;
    padding: 0 16px;
    font-size: 13px;
    font-weight: 600;
    color: var(--app-text-secondary);
    border-radius: 999px;
    border: 1px solid var(--app-card-border);
    background: var(--app-card-bg);
    backdrop-filter: blur(10px);
    cursor: pointer;
    transition: all 0.2s ease;
    &:hover {
      color: var(--app-brand);
      border-color: var(--app-card-border-strong);
      transform: translateY(-1px);
    }
    &.is-active {
      color: #fff;
      border-color: transparent;
      background: var(--app-gradient);
      box-shadow: 0 6px 18px rgba(99, 102, 241, 0.32);
    }
  }
  &__num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    font-size: 11.5px;
    font-weight: 700;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.08);
    color: var(--app-text-placeholder);
    font-variant-numeric: tabular-nums;
  }
  &__item.is-active &__num {
    background: rgba(255, 255, 255, 0.22);
    color: #fff;
  }
}

// ---------- 列表卡片 ----------
.neg-stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.neg-card {
  position: relative;
  display: flex;
  align-items: stretch;
  gap: 18px;
  padding: 16px 20px;
  cursor: pointer;

  &__thumb {
    position: relative;
    flex: none;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 88px;
    height: 88px;
    border-radius: 16px;
    overflow: hidden;
    background: var(--app-gradient-deep);
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.16);
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

  &__main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 9px;
  }
  &__title-row {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
  &__title {
    margin: 0;
    font-size: 16px;
    font-weight: 700;
    color: var(--app-text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }
  &__sub {
    display: flex;
    align-items: center;
    gap: 9px;
    font-size: 12.5px;
    color: var(--app-text-secondary);
    flex-wrap: wrap;
  }
  &__role {
    display: inline-flex;
    align-items: center;
    padding: 2px 9px;
    font-size: 11.5px;
    font-weight: 600;
    color: var(--app-brand-strong);
    border-radius: 999px;
    background: var(--app-brand-soft);
  }
  &__dot {
    color: var(--app-text-placeholder);
  }
  &__round {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    svg {
      color: var(--app-text-placeholder);
    }
  }

  &__metrics {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }
  &__time {
    margin-left: auto;
    font-size: 12px;
    color: var(--app-text-placeholder);
    font-variant-numeric: tabular-nums;
  }
  &__enter {
    flex: none;
    align-self: center;
    display: inline-flex;
    color: var(--app-text-placeholder);
    transition: all 0.25s cubic-bezier(0.34, 1.4, 0.5, 1);
  }
  &:hover &__enter {
    color: var(--app-brand);
    transform: translateX(4px);
  }

  // 状态侧边光
  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 18px;
    bottom: 18px;
    width: 3px;
    border-radius: 3px;
    background: var(--app-brand);
    opacity: 0.65;
  }
  &--deal::before {
    background: linear-gradient(180deg, #f59e0b, #fbbf24);
  }
  &--terminated::before {
    background: var(--el-border-color-darker);
  }
}

.metric {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  font-size: 12px;
  color: var(--app-text-secondary);
  border-radius: 999px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);
  svg {
    color: var(--app-brand);
  }
  strong {
    font-size: 13.5px;
    font-weight: 800;
    color: var(--app-text-primary);
    font-variant-numeric: tabular-nums;
  }
  &--deal {
    background: var(--app-warning-soft);
    border-color: rgba(245, 158, 11, 0.3);
    svg,
    strong {
      color: #b45309;
    }
  }
}

.neg-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 11px;
  font-size: 11.5px;
  font-weight: 700;
  border-radius: 999px;
  white-space: nowrap;

  &--ongoing {
    color: var(--app-success);
    background: var(--app-success-soft);
    svg {
      animation: app-spin 5s linear infinite;
    }
  }
  &--deal {
    color: #b45309;
    background: var(--app-warning-soft);
  }
  &--terminated {
    color: var(--app-text-secondary);
    background: var(--el-fill-color-dark);
  }
}

// ---------- 状态卡 ----------
.state-card {
  margin-top: 30px;
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
    width: 54px;
    height: 54px;
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
    max-width: 460px;
    font-size: 13.5px;
    line-height: 1.8;
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

@media (max-width: 640px) {
  .page-head {
    align-items: flex-start;
  }
  .neg-card {
    flex-wrap: wrap;
  }
  .neg-card__time {
    margin-left: 0;
  }
}
</style>
