<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { searchItems } from '@/api/market'
import type { MarketItem } from '@/api/types'
import SearchIcon from '~icons/lucide/search'
import RotateIcon from '~icons/lucide/rotate-ccw'
import SparklesIcon from '~icons/lucide/sparkles'
import StarIcon from '~icons/lucide/star'
import BookIcon from '~icons/lucide/book-open'
import ChipIcon from '~icons/lucide/cpu'
import HomeIcon from '~icons/lucide/lamp'
import DumbbellIcon from '~icons/lucide/dumbbell'
import ShirtIcon from '~icons/lucide/shirt'
import FlowerIcon from '~icons/lucide/flower-2'
import PackageSearchIcon from '~icons/lucide/package-search'
import SlidersIcon from '~icons/lucide/sliders-horizontal'
import WalletIcon from '~icons/lucide/wallet'
import CloudOffIcon from '~icons/lucide/cloud-off'
import ArrowRightIcon from '~icons/lucide/arrow-right'

const router = useRouter()

const CATEGORIES = [
  '教材资料',
  '数码电子',
  '生活用品',
  '运动户外',
  '服饰鞋包',
  '美妆个护',
] as const

interface CategoryMeta {
  icon: unknown
  gradient: string
  glow: string
}

const CATEGORY_META: Record<string, CategoryMeta> = {
  教材资料: {
    icon: BookIcon,
    gradient: 'linear-gradient(135deg, #6366f1 0%, #818cf8 100%)',
    glow: 'rgba(99, 102, 241, 0.32)',
  },
  数码电子: {
    icon: ChipIcon,
    gradient: 'linear-gradient(135deg, #0891b2 0%, #22d3ee 100%)',
    glow: 'rgba(34, 211, 238, 0.32)',
  },
  生活用品: {
    icon: HomeIcon,
    gradient: 'linear-gradient(135deg, #059669 0%, #34d399 100%)',
    glow: 'rgba(52, 211, 153, 0.32)',
  },
  运动户外: {
    icon: DumbbellIcon,
    gradient: 'linear-gradient(135deg, #d97706 0%, #fbbf24 100%)',
    glow: 'rgba(251, 191, 36, 0.32)',
  },
  服饰鞋包: {
    icon: ShirtIcon,
    gradient: 'linear-gradient(135deg, #db2777 0%, #f472b6 100%)',
    glow: 'rgba(244, 114, 182, 0.32)',
  },
  美妆个护: {
    icon: FlowerIcon,
    gradient: 'linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%)',
    glow: 'rgba(167, 139, 250, 0.32)',
  },
}

function metaOf(category: string): CategoryMeta {
  return (
    CATEGORY_META[category] ?? {
      icon: PackageSearchIcon,
      gradient: 'linear-gradient(135deg, #4338ca 0%, #06b6d4 100%)',
      glow: 'rgba(99, 102, 241, 0.3)',
    }
  )
}

interface RiskMeta {
  text: string
  className: string
}

function riskMeta(tag: string): RiskMeta {
  if (tag === 'high_risk') return { text: '高风险', className: 'risk-tag--danger' }
  if (tag === 'new') return { text: '新用户', className: 'risk-tag--info' }
  return { text: '信用良好', className: 'risk-tag--success' }
}

function yuan(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

const filters = reactive({
  keyword: '',
  category: '',
  minPrice: undefined as number | undefined,
  maxPrice: undefined as number | undefined,
})

const items = ref<MarketItem[]>([])
const total = ref(0)
const suggestion = ref('')
const loading = ref(true)
const errorMsg = ref('')
const searched = ref(false)
/** 图片加载失败的商品（优雅降级为类目渐变占位，杜绝破图裂图） */
const failedImgIds = ref<Set<number>>(new Set())

function onImgError(id: number): void {
  if (failedImgIds.value.has(id)) return
  const next = new Set(failedImgIds.value)
  next.add(id)
  failedImgIds.value = next
}

async function loadData(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    const result = await searchItems({
      keyword: filters.keyword.trim() || undefined,
      category: filters.category || undefined,
      min_price: filters.minPrice,
      max_price: filters.maxPrice,
    })
    items.value = result.items ?? []
    total.value = result.total ?? 0
    suggestion.value = result.suggestion ?? ''
    failedImgIds.value = new Set()
    searched.value = true
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '市场数据加载失败'
  } finally {
    loading.value = false
  }
}

function onSearch(): void {
  void loadData()
}

function onReset(): void {
  filters.keyword = ''
  filters.category = ''
  filters.minPrice = undefined
  filters.maxPrice = undefined
  void loadData()
}

function openItem(id: number): void {
  void router.push(`/items/${id}`)
}

function notifySuggestion(): void {
  if (suggestion.value) ElMessage.info(suggestion.value)
}

onMounted(loadData)
</script>

<template>
  <div class="page-container market">
    <!-- 顶部搜索区 -->
    <section class="search-hero glass-card anim-fade-in-up">
      <div class="search-hero__bg" aria-hidden="true">
        <span class="search-hero__orb search-hero__orb--a" />
        <span class="search-hero__orb search-hero__orb--b" />
      </div>
      <div class="search-hero__head">
        <span class="search-hero__chip">
          <SparklesIcon :width="13" :height="13" :stroke-width="2.2" />
          Trade Agent 语义匹配 · 每条结果附推荐理由
        </span>
        <h1 class="search-hero__title">
          发现校园里的<span class="gradient-text gradient-text--animated">高性价比闲置</span>
        </h1>
        <p class="search-hero__desc">教材、数码、生活好物 · 支持关键词、类目与价格区间组合筛选</p>
      </div>

      <div class="search-bar">
        <el-input
          v-model="filters.keyword"
          class="search-bar__keyword"
          placeholder="搜索商品标题或描述，如：高数、耳机、台灯…"
          size="large"
          clearable
          @keyup.enter="onSearch"
        >
          <template #prefix>
            <SearchIcon :width="17" :height="17" :stroke-width="2.2" />
          </template>
        </el-input>

        <el-select
          v-model="filters.category"
          class="search-bar__category"
          placeholder="全部类目"
          size="large"
          clearable
        >
          <el-option v-for="c in CATEGORIES" :key="c" :label="c" :value="c" />
        </el-select>

        <div class="search-bar__range">
          <el-input v-model.number="filters.minPrice" placeholder="最低价" size="large">
            <template #prefix>
              <span class="search-bar__unit">¥</span>
            </template>
          </el-input>
          <span class="search-bar__dash" />
          <el-input v-model.number="filters.maxPrice" placeholder="最高价" size="large">
            <template #prefix>
              <span class="search-bar__unit">¥</span>
            </template>
          </el-input>
        </div>

        <button class="btn-gradient search-bar__submit" @click="onSearch">
          <SearchIcon :width="17" :height="17" :stroke-width="2.4" />
          搜索
        </button>
        <button class="search-bar__reset" title="重置筛选" @click="onReset">
          <RotateIcon :width="16" :height="16" :stroke-width="2.2" />
        </button>
      </div>
    </section>

    <!-- 结果元信息 -->
    <div v-if="!loading && !errorMsg && searched" class="result-meta anim-fade-in">
      <span class="result-meta__count">
        <SlidersIcon :width="14" :height="14" :stroke-width="2.2" />
        共找到 <strong>{{ total }}</strong> 件在售商品
      </span>
      <button
        v-if="suggestion"
        class="result-meta__hint"
        type="button"
        @click="notifySuggestion"
      >
        <SparklesIcon :width="13" :height="13" :stroke-width="2.2" />
        {{ suggestion }}
      </button>
    </div>

    <!-- 骨架屏 -->
    <div v-if="loading" class="item-grid">
      <article v-for="n in 8" :key="n" class="item-card">
        <div class="item-card__media skeleton" style="border-radius: 16px 16px 0 0; height: 178px" />
        <div class="item-card__body">
          <div class="skeleton" style="width: 58%; height: 12px" />
          <div class="skeleton" style="width: 90%; height: 14px; margin-top: 12px" />
          <div class="skeleton" style="width: 72%; height: 14px; margin-top: 8px" />
          <div class="skeleton" style="width: 100%; height: 34px; margin-top: 12px; border-radius: 10px" />
          <div class="skeleton" style="width: 60%; height: 16px; margin-top: 12px" />
        </div>
      </article>
    </div>

    <!-- 错误态 -->
    <section v-else-if="errorMsg" class="state-card glass-card anim-fade-in-up">
      <span class="state-card__icon state-card__icon--danger"><CloudOffIcon :stroke-width="1.8" /></span>
      <h3>市场暂时无法连接</h3>
      <p>{{ errorMsg }}</p>
      <button class="btn-gradient" @click="loadData">
        <RotateIcon :width="16" :height="16" :stroke-width="2.4" />
        重新加载
      </button>
    </section>

    <!-- 空状态 -->
    <section v-else-if="searched && items.length === 0" class="state-card glass-card anim-fade-in-up">
      <span class="state-card__illu">
        <PackageSearchIcon :width="46" :height="46" :stroke-width="1.6" />
        <span class="state-card__ring" />
      </span>
      <h3>没有找到符合条件的商品</h3>
      <p>{{ suggestion || '试试减少关键词、切换类目，或放宽价格区间后重新搜索。' }}</p>
      <div class="state-card__actions">
        <button class="btn-gradient" @click="onReset">
          <RotateIcon :width="16" :height="16" :stroke-width="2.4" />
          重置筛选条件
        </button>
        <button class="state-card__ghost" @click="router.push('/seller/publish')">
          <WalletIcon :width="16" :height="16" :stroke-width="2.2" />
          我也去发布一件
        </button>
      </div>
    </section>

    <!-- 商品网格 -->
    <div v-else class="item-grid stagger">
      <article
        v-for="item in items"
        :key="item.id"
        class="item-card glass-card glass-card--hover"
        @click="openItem(item.id)"
      >
        <div class="item-card__media">
          <img
            v-if="item.image_url && !failedImgIds.has(item.id)"
            :src="item.image_url"
            :alt="item.title"
            class="item-card__img"
            loading="lazy"
            @error="onImgError(item.id)"
          />
          <div
            v-else
            class="item-card__placeholder"
            :style="{ background: metaOf(item.category).gradient }"
          >
            <component
              :is="metaOf(item.category).icon"
              :width="42"
              :height="42"
              :stroke-width="1.5"
            />
          </div>
          <span class="item-card__badge item-card__badge--category">{{ item.category }}</span>
          <span class="item-card__badge item-card__badge--condition">{{ item.condition_level }}</span>
        </div>

        <div class="item-card__body">
          <h3 class="item-card__title">{{ item.title }}</h3>

          <div v-if="item.match_reason" class="item-card__reason">
            <span class="item-card__reason-icon">
              <SparklesIcon :width="12" :height="12" :stroke-width="2.3" />
            </span>
            <span class="item-card__reason-text">{{ item.match_reason }}</span>
          </div>

          <div class="item-card__price-row">
            <span class="item-card__price">
              <span class="item-card__currency">¥</span>{{ yuan(item.price) }}
            </span>
            <ArrowRightIcon class="item-card__go" :width="16" :height="16" :stroke-width="2.4" />
          </div>

          <div class="item-card__footer">
            <span class="item-card__seller">
              <span class="item-card__avatar">{{ item.seller_nickname.slice(0, 1) }}</span>
              <span class="item-card__seller-name">{{ item.seller_nickname }}</span>
              <AiBadge v-if="item.seller_is_ai" size="sm" />
            </span>
            <span class="item-card__credit">
              <StarIcon :width="13" :height="13" :stroke-width="2.3" />
              {{ item.seller_credit }}
            </span>
            <span class="risk-tag" :class="riskMeta(item.seller_risk).className">
              {{ riskMeta(item.seller_risk).text }}
            </span>
          </div>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped lang="scss">
.market {
  padding-top: 28px;
}

// ---------- 搜索 Hero ----------
.search-hero {
  position: relative;
  padding: 30px 32px 26px;
  overflow: hidden;

  &__bg {
    position: absolute;
    inset: 0;
    pointer-events: none;
    overflow: hidden;
  }
  &__orb {
    position: absolute;
    border-radius: 50%;
    filter: blur(12px);
    opacity: 0.5;
    &--a {
      width: 220px;
      height: 220px;
      right: -60px;
      top: -110px;
      background: radial-gradient(circle, rgba(34, 211, 238, 0.5), transparent 70%);
      animation: app-float-slow 16s ease-in-out infinite;
    }
    &--b {
      width: 260px;
      height: 260px;
      left: -80px;
      bottom: -170px;
      background: radial-gradient(circle, rgba(99, 102, 241, 0.42), transparent 70%);
      animation: app-float-slower 20s ease-in-out infinite;
    }
  }

  &__head {
    position: relative;
    z-index: 1;
  }
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
    margin: 13px 0 0;
    font-size: 27px;
    font-weight: 800;
    line-height: 1.35;
    color: var(--app-text-primary);
  }
  &__desc {
    margin-top: 8px;
    font-size: 13.5px;
    color: var(--app-text-secondary);
  }
}

.search-bar {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 22px;

  &__keyword {
    flex: 1.4;
    min-width: 180px;
  }
  &__category {
    flex: 0.9;
    min-width: 150px;
  }
  &__range {
    flex: 1;
    min-width: 200px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  &__unit {
    font-size: 13px;
    font-weight: 600;
    color: var(--app-text-secondary);
  }
  &__dash {
    flex: none;
    width: 14px;
    height: 2px;
    border-radius: 2px;
    background: var(--app-card-border-strong);
  }
  &__submit {
    flex: none;
    height: 40px;
    padding: 0 22px;
    font-size: 14px;
  }
  &__reset {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: 10px;
    color: var(--app-text-secondary);
    background: var(--app-card-bg-solid);
    border: 1px solid var(--app-card-border-strong);
    cursor: pointer;
    transition: all 0.2s ease;
    &:hover {
      color: var(--app-danger);
      border-color: rgba(239, 68, 68, 0.4);
      background: var(--app-danger-soft);
      transform: translateY(-1px);
    }
  }
}

:deep(.search-bar__range .el-input__wrapper) {
  padding: 0 13px;
}

// ---------- 结果元信息 ----------
.result-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin: 22px 2px 14px;

  &__count {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-size: 13px;
    color: var(--app-text-secondary);
    strong {
      color: var(--app-brand-strong);
      font-size: 15px;
      font-variant-numeric: tabular-nums;
    }
  }
  &__hint {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 6px 14px;
    font-size: 12px;
    color: #92400e;
    background: var(--app-warning-soft);
    border: 1px solid rgba(245, 158, 11, 0.25);
    border-radius: 999px;
    cursor: pointer;
    transition: all 0.2s ease;
    &:hover {
      background: #fef0d3;
      transform: translateY(-1px);
    }
  }
}

// ---------- 商品网格 ----------
.item-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(252px, 1fr));
  gap: 20px;
}

.item-card {
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;

  &__media {
    position: relative;
    height: 178px;
    flex: none;
    background: var(--el-fill-color-light);
  }
  &__img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
  }
  &:hover &__img {
    transform: scale(1.06);
  }
  &__placeholder {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: rgba(255, 255, 255, 0.9);
    opacity: 0.92;
  }
  &__badge {
    position: absolute;
    top: 12px;
    z-index: 1;
    padding: 4px 11px;
    font-size: 11.5px;
    font-weight: 600;
    color: #fff;
    border-radius: 999px;
    backdrop-filter: blur(6px);
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.18);
    &--category {
      left: 12px;
      background: rgba(15, 23, 42, 0.55);
    }
    &--condition {
      right: 12px;
      background: var(--app-gradient-deep);
    }
  }

  &__body {
    display: flex;
    flex-direction: column;
    gap: 0;
    padding: 16px 18px 15px;
  }
  &__title {
    margin: 0;
    font-size: 15px;
    font-weight: 700;
    line-height: 1.5;
    color: var(--app-text-primary);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 45px;
  }

  &__reason {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-top: 11px;
    padding: 9px 11px;
    border-radius: 10px;
    background: var(--app-gradient-brand-soft, linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(34, 211, 238, 0.1)));
    border: 1px solid var(--app-card-border);
  }
  &__reason-icon {
    flex: none;
    display: inline-flex;
    margin-top: 1px;
    color: var(--app-brand);
  }
  &__reason-text {
    font-size: 12px;
    line-height: 1.55;
    color: var(--app-brand-strong);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  &__price-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 13px;
  }
  &__price {
    font-size: 24px;
    font-weight: 800;
    line-height: 1;
    letter-spacing: 0.3px;
    background: var(--app-gradient);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    font-variant-numeric: tabular-nums;
  }
  &__currency {
    font-size: 15px;
    font-weight: 700;
    margin-right: 1px;
  }
  &__go {
    color: var(--app-text-placeholder);
    transition: all 0.25s cubic-bezier(0.34, 1.4, 0.5, 1);
  }
  &:hover &__go {
    color: var(--app-brand);
    transform: translateX(3px);
  }

  &__footer {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 13px;
    padding-top: 12px;
    border-top: 1px dashed var(--app-divider);
  }
  &__seller {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-width: 0;
    :deep(.ai-badge) {
      flex: none;
    }
  }
  &__avatar {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    color: #fff;
    font-size: 12px;
    font-weight: 700;
    background: var(--app-gradient);
  }
  &__seller-name {
    font-size: 12.5px;
    font-weight: 600;
    color: var(--app-text-regular);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  &__credit {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 12.5px;
    font-weight: 700;
    color: #d97706;
    font-variant-numeric: tabular-nums;
  }
}

// 风险标签
.risk-tag {
  flex: none;
  padding: 2px 9px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 999px;
  white-space: nowrap;
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
}

// ---------- 状态卡片（空 / 错） ----------
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
    background: var(--app-gradient-brand-soft);
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
    max-width: 440px;
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

// ---------- 响应式 ----------
@media (max-width: 900px) {
  .search-bar {
    flex-wrap: wrap;
    &__keyword,
    &__category {
      flex: 1 1 calc(50% - 6px);
    }
    &__range {
      flex: 1 1 100%;
      order: 3;
    }
    &__submit {
      flex: 1;
    }
    &__reset {
      flex: none;
    }
  }
}
@media (max-width: 560px) {
  .search-hero {
    padding: 24px 18px 22px;
  }
  .item-grid {
    grid-template-columns: 1fr;
  }
}
</style>
