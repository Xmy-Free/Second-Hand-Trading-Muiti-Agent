<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getMyCredit } from '@/api/social'
import type { CreditInfo } from '@/api/social'
import ShieldCheckIcon from '~icons/lucide/shield-check'
import ShieldAlertIcon from '~icons/lucide/shield-alert'
import SparklesIcon from '~icons/lucide/sparkle'
import StarIcon from '~icons/lucide/star'
import HandshakeIcon from '~icons/lucide/handshake'
import MessageSquareIcon from '~icons/lucide/message-square-heart'
import TrendingUpIcon from '~icons/lucide/trending-up'
import TrendingDownIcon from '~icons/lucide/trending-down'
import MinusIcon from '~icons/lucide/minus'
import RotateIcon from '~icons/lucide/rotate-ccw'
import CloudOffIcon from '~icons/lucide/cloud-off'
import HistoryIcon from '~icons/lucide/history'
import ScaleIcon from '~icons/lucide/scale'
import InfoIcon from '~icons/lucide/info'

interface RiskMeta {
  text: string
  desc: string
  className: string
  icon: unknown
}

function riskMeta(tag: string, score: number): RiskMeta {
  if (tag === 'high_risk' || score < 80) {
    return {
      text: '高风险',
      desc: '信用分低于安全阈值，交易与议价将触发更严格的风控校验',
      className: 'risk--danger',
      icon: ShieldAlertIcon,
    }
  }
  if (tag === 'new') {
    return {
      text: '新用户',
      desc: '账号尚无成交记录，完成履约与互评后可积累信用',
      className: 'risk--info',
      icon: SparklesIcon,
    }
  }
  return {
    text: '信用良好',
    desc: '历史履约稳定，享受更顺畅的交易与议价体验',
    className: 'risk--success',
    icon: ShieldCheckIcon,
  }
}

function fmtDateTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const info = ref<CreditInfo | null>(null)
const loading = ref(true)
const errorMsg = ref('')

const risk = computed<RiskMeta | null>(() =>
  info.value ? riskMeta(info.value.risk_tag, info.value.credit_score) : null,
)

/** 圆环按 0-120 刻度归一，分数越高弧越满，102 等高分依然保持满弧 */
const RING_R = 64
const RING_C = 2 * Math.PI * RING_R
const fraction = computed(() => {
  if (!info.value) return 0
  return Math.max(0, Math.min(1, info.value.credit_score / 120))
})
const ringOffset = computed(() => RING_C * (1 - fraction.value))

async function load(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    info.value = await getMyCredit()
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '信用信息加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-container credit">
    <header class="page-head anim-fade-in-up">
      <span class="page-head__chip">
        <ShieldCheckIcon :width="13" :height="13" :stroke-width="2.2" />
        履约信用 Agent · 双向评价聚合
      </span>
      <h1 class="page-head__title">我的信用</h1>
      <p class="page-head__desc">信用分综合支付、交付、确认收货与互评表现动态更新，全程可解释、可追溯</p>
    </header>

    <!-- 骨架 -->
    <div v-if="loading" class="credit__layout">
      <div class="glass-card skeleton" style="height: 340px; border-radius: 22px" />
      <div class="glass-card skeleton" style="height: 340px; border-radius: 22px" />
    </div>

    <!-- 错误 -->
    <section v-else-if="errorMsg || !info" class="state-card glass-card anim-fade-in-up">
      <span class="state-card__icon"><CloudOffIcon :stroke-width="1.8" /></span>
      <h3>信用信息暂时不可用</h3>
      <p>{{ errorMsg }}</p>
      <button class="btn-gradient" @click="load">
        <RotateIcon :width="16" :height="16" :stroke-width="2.4" />
        重新加载
      </button>
    </section>

    <template v-else>
      <div class="credit__layout anim-fade-in-up">
        <!-- 信用总览 -->
        <section class="hero glass-card">
          <div class="hero__ring-wrap">
            <svg class="hero__ring" width="168" height="168" viewBox="0 0 168 168">
              <defs>
                <linearGradient id="creditRingGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#6366f1" />
                  <stop offset="55%" stop-color="#22d3ee" />
                  <stop offset="100%" stop-color="#34d399" />
                </linearGradient>
              </defs>
              <circle class="hero__track" cx="84" cy="84" :r="RING_R" />
              <circle
                class="hero__bar"
                cx="84"
                cy="84"
                :r="RING_R"
                stroke="url(#creditRingGradient)"
                :stroke-dasharray="RING_C"
                :stroke-dashoffset="ringOffset"
              />
            </svg>
            <div class="hero__center">
              <span class="hero__score">{{ info.credit_score }}</span>
              <span class="hero__score-label">信用分</span>
            </div>
          </div>

          <div class="hero__meta">
            <span v-if="risk" class="risk-pill" :class="risk.className">
              <component :is="risk.icon" :width="14" :height="14" :stroke-width="2.3" />
              {{ risk.text }}
            </span>
            <h2 class="hero__title">
              {{ info.credit_score >= 80 ? '履约表现优秀' : '信用分有待提升' }}
            </h2>
            <p class="hero__desc">{{ risk?.desc }}</p>

            <div class="hero__stats">
              <div class="stat">
                <span class="stat__icon stat__icon--deal"><HandshakeIcon :width="16" :height="16" :stroke-width="2.2" /></span>
                <span class="stat__value">{{ info.deal_count }}</span>
                <span class="stat__label">成交订单</span>
              </div>
              <span class="hero__stat-divider" />
              <div class="stat">
                <span class="stat__icon stat__icon--review">
                  <MessageSquareIcon :width="16" :height="16" :stroke-width="2.2" />
                </span>
                <span class="stat__value">{{ info.review_count }}</span>
                <span class="stat__label">收到评价</span>
              </div>
            </div>

            <div class="hero__note">
              <InfoIcon :width="13" :height="13" :stroke-width="2.2" />
              信用分由履约信用 Agent 聚合互评、取消与申诉裁决结果计算
            </div>
          </div>
        </section>

        <!-- 变动时间线 -->
        <section class="timeline-panel glass-card">
          <header class="timeline-panel__head">
            <h2>
              <HistoryIcon :width="17" :height="17" :stroke-width="2.2" />
              信用变动
            </h2>
            <span class="timeline-panel__sub">每一次履约都被记录</span>
          </header>

          <div v-if="info.changes.length === 0" class="changes-empty">
            <span class="changes-empty__icon"><ScaleIcon :width="30" :height="30" :stroke-width="1.6" /></span>
            <p>暂无信用变动记录</p>
            <span>完成交易并互评后，评分变化会出现在这里</span>
          </div>

          <ol v-else class="changes">
            <li v-for="(change, idx) in info.changes" :key="idx" class="change" :class="{ 'is-first': idx === 0 }">
              <span class="change__rail">
                <span
                  class="change__dot"
                  :class="change.delta > 0 ? 'change__dot--up' : change.delta < 0 ? 'change__dot--down' : 'change__dot--flat'"
                >
                  <component
                    :is="change.delta > 0 ? TrendingUpIcon : change.delta < 0 ? TrendingDownIcon : MinusIcon"
                    :width="11"
                    :height="11"
                    :stroke-width="2.6"
                  />
                </span>
                <span v-if="idx < info.changes.length - 1" class="change__line" />
              </span>

              <div class="change__body">
                <div class="change__top">
                  <span class="change__reason">{{ change.reason }}</span>
                  <span
                    class="change__delta"
                    :class="change.delta > 0 ? 'change__delta--up' : change.delta < 0 ? 'change__delta--down' : 'change__delta--flat'"
                  >
                    {{ change.delta > 0 ? '+' : '' }}{{ change.delta }}
                  </span>
                </div>
                <div class="change__foot">
                  <span>{{ fmtDateTime(change.created_at) }}</span>
                  <span class="change__result">
                    <StarIcon :width="11" :height="11" :stroke-width="2.3" />
                    变动后 {{ change.new_score }} 分
                  </span>
                </div>
              </div>
            </li>
          </ol>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.credit {
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

.credit__layout {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
  gap: 20px;
  margin-top: 22px;
  align-items: start;
}

// ---------- 总览 ----------
.hero {
  position: relative;
  padding: 34px 30px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    width: 300px;
    height: 300px;
    top: -180px;
    right: -140px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(34, 211, 238, 0.16), transparent 68%);
    pointer-events: none;
  }

  &__ring-wrap {
    position: relative;
    width: 168px;
    height: 168px;
  }
  &__ring {
    transform: rotate(-90deg);
    filter: drop-shadow(0 8px 20px rgba(99, 102, 241, 0.18));
  }
  &__track {
    fill: none;
    stroke: var(--el-fill-color-dark);
    stroke-width: 11;
  }
  &__bar {
    fill: none;
    stroke-width: 11;
    stroke-linecap: round;
    transition: stroke-dashoffset 1.1s cubic-bezier(0.22, 1, 0.36, 1);
  }
  &__center {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
  }
  &__score {
    font-size: 52px;
    font-weight: 800;
    line-height: 1;
    letter-spacing: 1px;
    color: transparent;
    background: var(--app-gradient);
    -webkit-background-clip: text;
    background-clip: text;
    font-variant-numeric: tabular-nums;
  }
  &__score-label {
    font-size: 12.5px;
    font-weight: 600;
    color: var(--app-text-placeholder);
    letter-spacing: 3px;
  }

  &__meta {
    position: relative;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
  &__title {
    margin: 12px 0 6px;
    font-size: 18px;
    font-weight: 800;
    color: var(--app-text-primary);
  }
  &__desc {
    margin: 0;
    max-width: 320px;
    font-size: 13px;
    line-height: 1.7;
    color: var(--app-text-secondary);
  }

  &__stats {
    display: flex;
    align-items: center;
    gap: 18px;
    margin-top: 22px;
    padding: 14px 24px;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.72);
    border: 1px solid var(--app-card-border);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
  }
  &__stat-divider {
    width: 1px;
    height: 34px;
    background: var(--app-divider);
  }
  &__note {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    margin-top: 16px;
    font-size: 12px;
    line-height: 1.6;
    color: var(--app-text-placeholder);
    svg {
      color: var(--app-brand);
    }
  }
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;

  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: 12px;
    margin-bottom: 4px;
    &--deal {
      color: var(--app-brand);
      background: var(--app-brand-soft);
    }
    &--review {
      color: var(--app-success);
      background: var(--app-success-soft);
    }
  }
  &__value {
    font-size: 22px;
    font-weight: 800;
    line-height: 1;
    color: var(--app-text-primary);
    font-variant-numeric: tabular-nums;
  }
  &__label {
    font-size: 12px;
    color: var(--app-text-secondary);
  }
}

.risk-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 700;
  border-radius: 999px;
  &--success {
    color: var(--app-success);
    background: var(--app-success-soft);
    border: 1px solid rgba(16, 185, 129, 0.22);
  }
  &--danger {
    color: var(--app-danger);
    background: var(--app-danger-soft);
    border: 1px solid rgba(239, 68, 68, 0.22);
  }
  &--info {
    color: var(--app-info);
    background: var(--app-info-soft);
    border: 1px solid rgba(14, 165, 233, 0.22);
  }
}

// ---------- 时间线 ----------
.timeline-panel {
  padding: 24px 26px;

  &__head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 20px;
    h2 {
      display: inline-flex;
      align-items: center;
      gap: 9px;
      margin: 0;
      font-size: 16.5px;
      font-weight: 800;
      color: var(--app-text-primary);
      svg {
        color: var(--app-brand);
      }
    }
    &__sub {
      font-size: 12px;
      color: var(--app-text-placeholder);
    }
  }
}

.changes {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.change {
  display: flex;
  gap: 14px;

  &__rail {
    position: relative;
    flex: none;
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 28px;
  }
  &__dot {
    position: relative;
    z-index: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--app-card-bg-solid);
    border: 1px solid var(--app-card-border-strong);
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);

    &--up {
      color: var(--app-success);
      background: var(--app-success-soft);
      border-color: rgba(16, 185, 129, 0.3);
    }
    &--down {
      color: var(--app-danger);
      background: var(--app-danger-soft);
      border-color: rgba(239, 68, 68, 0.3);
    }
    &--flat {
      color: var(--app-text-secondary);
      background: var(--el-fill-color);
    }
  }
  &__line {
    flex: 1;
    width: 2px;
    margin: 5px 0;
    background: linear-gradient(180deg, var(--app-card-border-strong), var(--app-divider));
  }

  &__body {
    flex: 1;
    min-width: 0;
    padding: 2px 0 22px;
  }
  &__top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
  }
  &__reason {
    font-size: 14px;
    font-weight: 600;
    line-height: 1.6;
    color: var(--app-text-primary);
  }
  &__delta {
    flex: none;
    font-size: 16px;
    font-weight: 800;
    padding: 3px 12px;
    border-radius: 999px;
    font-variant-numeric: tabular-nums;

    &--up {
      color: var(--app-success);
      background: var(--app-success-soft);
    }
    &--down {
      color: var(--app-danger);
      background: var(--app-danger-soft);
    }
    &--flat {
      color: var(--app-text-secondary);
      background: var(--el-fill-color);
    }
  }
  &__foot {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-top: 7px;
    font-size: 12px;
    color: var(--app-text-placeholder);
    font-variant-numeric: tabular-nums;
  }
  &__result {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    svg {
      color: #f59e0b;
    }
  }
}

.changes-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 20px;
  text-align: center;

  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 64px;
    height: 64px;
    border-radius: 20px;
    color: var(--app-brand);
    background: var(--app-brand-soft);
    border: 1px solid var(--app-card-border);
  }
  p {
    margin: 4px 0 0;
    font-size: 15px;
    font-weight: 700;
    color: var(--app-text-primary);
  }
  span {
    font-size: 12.5px;
    color: var(--app-text-secondary);
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
}
.state-card .btn-gradient {
  margin-top: 22px;
  height: 40px;
  padding: 0 22px;
}

@media (max-width: 900px) {
  .credit__layout {
    grid-template-columns: 1fr;
  }
}
</style>
