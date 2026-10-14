<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getItem } from '@/api/items'
import { startNegotiation } from '@/api/negotiation'
import type { ItemOut } from '@/api/types'
import ArrowLeftIcon from '~icons/lucide/arrow-left'
import PackageOpenIcon from '~icons/lucide/package-open'
import BookIcon from '~icons/lucide/book-open'
import ChipIcon from '~icons/lucide/cpu'
import LampIcon from '~icons/lucide/lamp'
import DumbbellIcon from '~icons/lucide/dumbbell'
import ShirtIcon from '~icons/lucide/shirt'
import FlowerIcon from '~icons/lucide/flower-2'
import SparklesIcon from '~icons/lucide/sparkles'
import StarIcon from '~icons/lucide/star'
import ShieldCheckIcon from '~icons/lucide/shield-check'
import ShieldAlertIcon from '~icons/lucide/shield-alert'
import ShieldIcon from '~icons/lucide/shield'
import MessagesIcon from '~icons/lucide/messages-square'
import RotateIcon from '~icons/lucide/rotate-ccw'
import CloudOffIcon from '~icons/lucide/cloud-off'
import FileTextIcon from '~icons/lucide/file-text'
import TagIcon from '~icons/lucide/tag'
import InfoIcon from '~icons/lucide/info'

const route = useRoute()
const router = useRouter()
const itemId = Number(route.params.id)

interface CategoryMeta {
  icon: unknown
  gradient: string
}

const CATEGORY_META: Record<string, CategoryMeta> = {
  教材资料: { icon: BookIcon, gradient: 'linear-gradient(135deg, #6366f1 0%, #818cf8 100%)' },
  数码电子: { icon: ChipIcon, gradient: 'linear-gradient(135deg, #0891b2 0%, #22d3ee 100%)' },
  生活用品: { icon: LampIcon, gradient: 'linear-gradient(135deg, #059669 0%, #34d399 100%)' },
  运动户外: { icon: DumbbellIcon, gradient: 'linear-gradient(135deg, #d97706 0%, #fbbf24 100%)' },
  服饰鞋包: { icon: ShirtIcon, gradient: 'linear-gradient(135deg, #db2777 0%, #f472b6 100%)' },
  美妆个护: { icon: FlowerIcon, gradient: 'linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%)' },
}

function metaOf(category: string): CategoryMeta {
  return (
    CATEGORY_META[category] ?? {
      icon: PackageOpenIcon,
      gradient: 'linear-gradient(135deg, #4338ca 0%, #06b6d4 100%)',
    }
  )
}

function yuan(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

const item = ref<ItemOut | null>(null)
const loading = ref(true)
const errorMsg = ref('')
/** 主图加载失败时降级为类目渐变占位（零破图） */
const imgFailed = ref(false)

const isOnSale = computed(() => item.value?.status === 'on_sale')
const INTERNAL_ATTR_KEYS = new Set(['source', 'index', 'seed'])
const attrEntries = computed<Array<[string, unknown]>>(() => {
  const attrs = item.value?.attrs
  if (!attrs || typeof attrs !== 'object') return []
  return Object.entries(attrs).filter(
    ([k, v]) => v !== null && v !== '' && !INTERNAL_ATTR_KEYS.has(k),
  )
})

type RiskTag = 'high_risk' | 'normal' | 'new'
interface RiskMeta {
  tag: RiskTag
  text: string
  className: string
}

/** 详情接口未返回 risk_tag，依据履约 Agent 的信用阈值（80）推导展示。 */
const sellerRisk = computed<RiskMeta>(() => {
  const score = item.value?.seller_credit ?? 0
  if (score < 80) return { tag: 'high_risk', text: '高风险卖家', className: 'seller-risk--danger' }
  return { tag: 'normal', text: '信用良好', className: 'seller-risk--success' }
})

const reservePrice = ref<number | undefined>()
const firstOffer = ref<number | undefined>()
const submitting = ref(false)

async function load(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    item.value = await getItem(itemId)
    imgFailed.value = false
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '商品加载失败'
  } finally {
    loading.value = false
  }
}

async function onStartNegotiation(): Promise<void> {
  if (!item.value || submitting.value) return
  const reserve = Number(reservePrice.value)
  if (!reserve || reserve <= 0) {
    ElMessage.warning('请填写有效的保留价（你愿意接受的最高价）')
    return
  }
  const first = firstOffer.value === undefined || (firstOffer.value as number) <= 0
    ? null
    : Number(firstOffer.value)
  if (first !== null && first > reserve) {
    ElMessage.warning('首次出价不能高于保留价，议价需要从低往高让步')
    return
  }
  submitting.value = true
  try {
    const neg = await startNegotiation({
      item_id: itemId,
      buyer_reserve: reserve,
      first_offer: first,
    })
    ElMessage.success('议价会话已发起，等待卖家回应')
    void router.replace(`/negotiations/${neg.id}`)
  } catch {
    /* 全局拦截器已提示 */
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-container detail">
    <!-- 顶部返回 -->
    <div class="detail__back anim-fade-in">
      <button class="back-btn" type="button" @click="router.push('/market')">
        <ArrowLeftIcon :width="16" :height="16" :stroke-width="2.2" />
        返回市场
      </button>
    </div>

    <!-- 骨架屏 -->
    <div v-if="loading" class="detail__layout">
      <div class="glass-card skeleton detail__media-skeleton" />
      <div class="detail__main">
        <div class="glass-card skeleton" style="height: 420px" />
        <div class="glass-card skeleton" style="height: 150px" />
      </div>
    </div>

    <!-- 错误态 -->
    <section v-else-if="errorMsg || !item" class="state-card glass-card anim-fade-in-up">
      <span class="state-card__icon state-card__icon--danger"><CloudOffIcon :stroke-width="1.8" /></span>
      <h3>商品信息加载失败</h3>
      <p>{{ errorMsg || '该商品不存在或已被下架' }}</p>
      <div class="state-card__actions">
        <button class="btn-gradient" @click="load">
          <RotateIcon :width="16" :height="16" :stroke-width="2.4" />
          重新加载
        </button>
        <button class="state-card__ghost" @click="router.push('/market')">返回市场</button>
      </div>
    </section>

    <!-- 正常内容 -->
    <template v-else>
      <div class="detail__layout anim-fade-in-up">
        <!-- 左：图片 -->
        <section class="media glass-card">
          <div class="media__stage" :style="{ background: metaOf(item.category).gradient }">
            <img
              v-if="item.image_url && !imgFailed"
              :src="item.image_url"
              :alt="item.title"
              class="media__img"
              @error="imgFailed = true"
            />
            <template v-else>
              <span class="media__halo" />
              <component
                :is="metaOf(item.category).icon"
                class="media__icon"
                :width="92"
                :height="92"
                :stroke-width="1.3"
              />
              <PackageOpenIcon
                v-if="!item.image_url"
                class="media__watermark"
                :width="20"
                :height="20"
                :stroke-width="2"
              />
            </template>
            <span class="media__badge">{{ item.category }}</span>
            <span class="media__badge media__badge--cond">{{ item.condition_level }}</span>
          </div>

          <div class="media__thumbs">
            <span class="media__thumb media__thumb--active">
              <img
                v-if="item.image_url && !imgFailed"
                :src="item.image_url"
                :alt="item.title"
                class="media__thumb-img"
                @error="imgFailed = true"
              />
              <component
                v-else
                :is="metaOf(item.category).icon"
                :width="18"
                :height="18"
                :stroke-width="2"
              />
              {{ item.image_url && !imgFailed ? '实物图' : '实物图待补' }}
            </span>
          </div>
        </section>

        <!-- 右：内容 -->
        <div class="detail__main">
          <article class="panel glass-card">
            <div class="panel__tags">
              <span class="chip chip--brand"><TagIcon :width="12" :height="12" :stroke-width="2.3" />{{ item.category }}</span>
              <span class="chip">{{ item.condition_level }}</span>
              <span v-if="!isOnSale" class="chip chip--status">{{ item.status_text }}</span>
            </div>

            <h1 class="panel__title">{{ item.title }}</h1>

            <div class="price-box">
              <div class="price-box__main">
                <span class="price-box__label">卖家标价</span>
                <span class="price-box__price">
                  <span class="price-box__unit">¥</span>{{ yuan(item.price) }}
                </span>
              </div>
              <div v-if="item.price_suggest_min != null && item.price_suggest_max != null" class="price-box__suggest">
                <span class="price-box__suggest-icon"><SparklesIcon :width="14" :height="14" :stroke-width="2.2" /></span>
                <div>
                  <div class="price-box__suggest-label">审核 Agent 建议价区间</div>
                  <div class="price-box__suggest-range">
                    ¥{{ yuan(item.price_suggest_min) }} – ¥{{ yuan(item.price_suggest_max) }}
                  </div>
                </div>
              </div>
            </div>

            <!-- 描述 -->
            <div class="info-block">
              <h3 class="info-block__title">
                <FileTextIcon :width="15" :height="15" :stroke-width="2.2" />
                商品描述
              </h3>
              <p class="info-block__text">{{ item.description || '卖家暂未填写详细描述。' }}</p>
            </div>

            <div v-if="attrEntries.length" class="info-block">
              <h3 class="info-block__title">
                <InfoIcon :width="15" :height="15" :stroke-width="2.2" />
                规格属性
              </h3>
              <div class="attr-grid">
                <div v-for="[k, v] in attrEntries" :key="k" class="attr-item">
                  <span class="attr-item__key">{{ k }}</span>
                  <span class="attr-item__val">{{ String(v) }}</span>
                </div>
              </div>
            </div>

            <!-- 卖家信息 -->
            <div class="seller-card">
              <span class="seller-card__avatar">{{ item.seller_nickname.slice(0, 1) }}</span>
              <div class="seller-card__meta">
                <div class="seller-card__name-row">
                  <span class="seller-card__name">{{ item.seller_nickname }}</span>
                  <AiBadge v-if="item.seller_is_ai" size="sm" />
                  <span class="seller-risk" :class="sellerRisk.className">
                    <component
                      :is="sellerRisk.tag === 'high_risk' ? ShieldAlertIcon : sellerRisk.tag === 'new' ? ShieldIcon : ShieldCheckIcon"
                      :width="12"
                      :height="12"
                      :stroke-width="2.2"
                    />
                    {{ sellerRisk.text }}
                  </span>
                </div>
                <div class="seller-card__credit">
                  <StarIcon :width="13" :height="13" :stroke-width="2.3" />
                  信用分 <strong>{{ item.seller_credit }}</strong>
                  <span class="seller-card__credit-hint">· 履约 Agent 评估</span>
                </div>
              </div>
            </div>
          </article>

          <!-- 发起议价 -->
          <article class="panel glass-card launch">
            <div class="launch__head">
              <span class="launch__icon"><MessagesIcon :width="18" :height="18" :stroke-width="2" /></span>
              <div>
                <h2>发起议价</h2>
                <p>纳什参考价由议价 Agent 计算，保留价仅你可见，卖家无法获知</p>
              </div>
            </div>

            <template v-if="isOnSale">
              <div class="launch__form">
                <div class="field">
                  <label class="field__label">保留价（最高可接受价）<em>*</em></label>
                  <el-input v-model.number="reservePrice" placeholder="如：150">
                    <template #prefix><span class="field__unit">¥</span></template>
                  </el-input>
                </div>
                <div class="field">
                  <label class="field__label">首次出价<span>（可选，默认由 Agent 引导）</span></label>
                  <el-input v-model.number="firstOffer" placeholder="如：120">
                    <template #prefix><span class="field__unit">¥</span></template>
                  </el-input>
                </div>
              </div>
              <ul class="launch__tips">
                <li>双方各有最多 5 轮让步机会，全程 120 秒倒计时</li>
                <li>出价须逐轮提高（单调让步），越过保留价需二次确认</li>
              </ul>
              <button
                class="btn-gradient launch__submit"
                :disabled="submitting"
                @click="onStartNegotiation"
              >
                <MessagesIcon :width="17" :height="17" :stroke-width="2.4" />
                {{ submitting ? '正在发起…' : '发起议价' }}
              </button>
            </template>

            <div v-else class="launch__closed">
              <component
                :is="item.status === 'dealed' ? ShieldCheckIcon : ShieldAlertIcon"
                :width="20"
                :height="20"
                :stroke-width="2"
              />
              <div>
                <strong>当前不可发起议价</strong>
                <p>商品状态为「{{ item.status_text }}」，仅在售商品支持议价交易。</p>
              </div>
              <button class="state-card__ghost" @click="router.push('/market')">看看其他商品</button>
            </div>
          </article>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.detail {
  padding-top: 20px;

  &__back {
    margin-bottom: 16px;
  }
  &__layout {
    display: grid;
    grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
    gap: 22px;
    align-items: start;
  }
  &__main {
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  &__media-skeleton {
    height: 460px;
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

// ---------- 左侧媒体 ----------
.media {
  position: sticky;
  top: 84px;
  padding: 14px;

  &__stage {
    position: relative;
    height: 420px;
    border-radius: 14px;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.14);
  }
  &__img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  &__halo {
    position: absolute;
    width: 300px;
    height: 300px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(255, 255, 255, 0.28), transparent 68%);
    filter: blur(8px);
  }
  &__icon {
    position: relative;
    color: rgba(255, 255, 255, 0.94);
    filter: drop-shadow(0 10px 26px rgba(15, 23, 42, 0.22));
  }
  &__watermark {
    position: absolute;
    right: 14px;
    bottom: 14px;
    padding: 4px 9px;
    gap: 4px;
    display: inline-flex;
    align-items: center;
    color: rgba(255, 255, 255, 0.85);
    background: rgba(15, 23, 42, 0.22);
    border-radius: 999px;
  }
  &__badge {
    position: absolute;
    top: 14px;
    left: 14px;
    padding: 5px 13px;
    font-size: 12px;
    font-weight: 600;
    color: #fff;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.5);
    backdrop-filter: blur(6px);
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.2);
    &--cond {
      left: auto;
      right: 14px;
      background: rgba(255, 255, 255, 0.18);
    }
  }
  &__thumbs {
    display: flex;
    gap: 10px;
    margin-top: 12px;
  }
  &__thumb {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 13px;
    font-size: 12px;
    font-weight: 500;
    color: var(--app-text-secondary);
    border-radius: 10px;
    border: 1px dashed var(--app-card-border-strong);
    background: var(--el-fill-color-lighter);
  }
  &__thumb-img {
    width: 26px;
    height: 26px;
    border-radius: 7px;
    object-fit: cover;
    flex: none;
  }
}

// ---------- 右侧面板 ----------
.panel {
  padding: 26px 28px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-secondary);
  border-radius: 999px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);
  &--brand {
    color: var(--app-brand-strong);
    background: var(--app-brand-soft);
  }
  &--status {
    color: var(--app-warning);
    background: var(--app-warning-soft);
    border-color: rgba(245, 158, 11, 0.3);
  }
}

.panel__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
}
.panel__title {
  margin: 14px 0 0;
  font-size: 23px;
  font-weight: 800;
  line-height: 1.45;
  color: var(--app-text-primary);
}

.price-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 18px;
  padding: 18px 20px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(34, 211, 238, 0.08));
  border: 1px solid var(--app-card-border);

  &__main {
    display: flex;
    align-items: baseline;
    gap: 12px;
  }
  &__label {
    font-size: 13px;
    font-weight: 600;
    color: var(--app-text-secondary);
  }
  &__price {
    font-size: 36px;
    font-weight: 800;
    line-height: 1;
    color: transparent;
    background: var(--app-gradient);
    -webkit-background-clip: text;
    background-clip: text;
    font-variant-numeric: tabular-nums;
  }
  &__unit {
    font-size: 19px;
    font-weight: 700;
    margin-right: 2px;
  }
  &__suggest {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 8px 14px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid var(--app-card-border);
  }
  &__suggest-icon {
    display: inline-flex;
    color: var(--app-brand);
  }
  &__suggest-label {
    font-size: 11px;
    color: var(--app-text-placeholder);
  }
  &__suggest-range {
    margin-top: 2px;
    font-size: 14px;
    font-weight: 700;
    color: var(--app-brand-strong);
    font-variant-numeric: tabular-nums;
  }
}

.info-block {
  margin-top: 24px;

  &__title {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 0 10px;
    font-size: 14px;
    font-weight: 700;
    color: var(--app-text-primary);
    svg {
      color: var(--app-brand);
    }
  }
  &__text {
    margin: 0;
    font-size: 13.5px;
    line-height: 1.9;
    color: var(--app-text-regular);
    white-space: pre-wrap;
  }
}

.attr-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
}
.attr-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 11px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--app-card-border);
  &__key {
    font-size: 12px;
    color: var(--app-text-secondary);
  }
  &__val {
    font-size: 13px;
    font-weight: 600;
    color: var(--app-text-primary);
  }
}

// 卖家卡
.seller-card {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 24px;
  padding: 16px 18px;
  border-radius: 14px;
  background: var(--app-card-bg-solid);
  border: 1px solid var(--app-card-border);

  &__avatar {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 46px;
    height: 46px;
    border-radius: 14px;
    color: #fff;
    font-size: 18px;
    font-weight: 700;
    background: var(--app-gradient);
    box-shadow: 0 6px 18px rgba(99, 102, 241, 0.3);
  }
  &__name-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  &__name {
    font-size: 15.5px;
    font-weight: 700;
    color: var(--app-text-primary);
  }
  &__credit {
    display: flex;
    align-items: center;
    gap: 5px;
    margin-top: 5px;
    font-size: 12.5px;
    color: var(--app-text-secondary);
    strong {
      color: var(--app-text-primary);
      font-variant-numeric: tabular-nums;
    }
  }
  &__credit-hint {
    color: var(--app-text-placeholder);
  }
}

.seller-risk {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  font-size: 11.5px;
  font-weight: 600;
  border-radius: 999px;
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

// ---------- 发起议价 ----------
.launch {
  padding: 22px 24px;

  &__head {
    display: flex;
    align-items: center;
    gap: 12px;
    h2 {
      margin: 0;
      font-size: 16px;
      font-weight: 700;
      color: var(--app-text-primary);
    }
    p {
      margin: 3px 0 0;
      font-size: 12.5px;
      color: var(--app-text-secondary);
    }
  }
  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: none;
    width: 42px;
    height: 42px;
    border-radius: 13px;
    color: #fff;
    background: var(--app-gradient);
    box-shadow: var(--app-shadow-glow);
  }
  &__form {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-top: 18px;
  }
  &__tips {
    margin: 14px 0 0;
    padding: 0;
    list-style: none;
    li {
      position: relative;
      padding-left: 16px;
      margin-top: 6px;
      font-size: 12.5px;
      color: var(--app-text-secondary);
      &::before {
        content: '';
        position: absolute;
        left: 2px;
        top: 7px;
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: var(--app-brand);
        opacity: 0.7;
      }
    }
  }
  &__submit {
    width: 100%;
    height: 44px;
    margin-top: 18px;
    font-size: 15px;
  }
  &__closed {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-top: 20px;
    padding: 18px;
    border-radius: 14px;
    color: var(--app-text-secondary);
    background: var(--el-fill-color-lighter);
    border: 1px dashed var(--app-card-border-strong);
    svg {
      flex: none;
      color: var(--app-warning);
    }
    strong {
      font-size: 14.5px;
      color: var(--app-text-primary);
    }
    p {
      margin: 3px 0 0;
      font-size: 12.5px;
    }
  }
}

.field {
  &__label {
    display: block;
    margin-bottom: 7px;
    font-size: 13px;
    font-weight: 600;
    color: var(--app-text-regular);
    em {
      color: var(--app-danger);
      font-style: normal;
      margin-left: 2px;
    }
    span {
      margin-left: 7px;
      font-size: 12px;
      font-weight: 400;
      color: var(--app-text-placeholder);
    }
  }
  &__unit {
    font-size: 13px;
    font-weight: 700;
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
    &--danger {
      color: var(--app-danger);
      background: var(--app-danger-soft);
    }
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
    justify-content: center;
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
@media (max-width: 960px) {
  .detail__layout {
    grid-template-columns: 1fr;
  }
  .media {
    position: static;
  }
  .media__stage {
    height: 320px;
  }
}
@media (max-width: 560px) {
  .panel {
    padding: 20px 18px;
  }
  .launch__form {
    grid-template-columns: 1fr;
  }
}
</style>
