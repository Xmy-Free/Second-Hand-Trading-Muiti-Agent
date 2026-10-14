<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { Component } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import WorkflowIcon from '~icons/lucide/workflow'
import UserRoundIcon from '~icons/lucide/user-round'
import PackageIcon from '~icons/lucide/package'
import ShieldAlertIcon from '~icons/lucide/shield-alert'
import SearchCheckIcon from '~icons/lucide/search-check'
import MessagesSquareIcon from '~icons/lucide/messages-square'
import ClipboardListIcon from '~icons/lucide/clipboard-list'
import BadgeCheckIcon from '~icons/lucide/badge-check'
import GavelIcon from '~icons/lucide/gavel'
import ArrowRightIcon from '~icons/lucide/arrow-right'
import StoreIcon from '~icons/lucide/store'
import PackagePlusIcon from '~icons/lucide/package-plus'
import RadarIcon from '~icons/lucide/radar'
import SearchIcon from '~icons/lucide/search'
import CreditCardIcon from '~icons/lucide/credit-card'
import MapPinIcon from '~icons/lucide/map-pin'
import StarIcon from '~icons/lucide/star'
import SparklesIcon from '~icons/lucide/sparkles'
import NetworkIcon from '~icons/lucide/network'

interface AgentCard {
  index: string
  name: string
  role: string
  icon: Component
  t1: string
  t2: string
  desc: string
  points: string[]
}

const router = useRouter()
const auth = useAuthStore()
const { isAdmin } = storeToRefs(auth)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

/** 1 个协调者 · 全局中枢 */
const coordinator: AgentCard = {
  index: '00',
  name: '协调管理 Agent',
  role: 'Coordinator · 全局中枢',
  icon: WorkflowIcon,
  t1: '#6366f1',
  t2: '#22d3ee',
  desc: '基于全局状态黑板 SSOT 统一注册与编排 9 大角色，路由 ACL 消息、主持加权投票，冲突按「对等协商 → 加权仲裁 → 人工终裁」三级升级，每一步决策均可解释、可回放。',
  points: ['ACL 消息路由', '黑板 SSOT 编排', '加权投票 · 冲突升级'],
}

/** 8 个专家 Agent · 各司其职 */
const specialists: AgentCard[] = [
  {
    index: '01',
    name: '用户代理 Agent',
    role: 'User Agent · 用户数字分身',
    icon: UserRoundIcon,
    t1: '#60a5fa',
    t2: '#3b82f6',
    desc: '作为用户的数字分身理解交易意图，沉淀画像与保留价，在授权区间内代客议价，越界请求立即人工确认。',
    points: ['意图理解与画像', '保留价授权区间', '越界人工确认'],
  },
  {
    index: '02',
    name: '商品管理 Agent',
    role: 'Commodity Agent · 上架管家',
    icon: PackageIcon,
    t1: '#34d399',
    t2: '#10b981',
    desc: '自然语言描述秒级结构化，自动分类与成色评级，给出建议价区间，并统一管理库存上下架。',
    points: ['描述结构化建档', '分类成色 · 建议价', '库存上下架'],
  },
  {
    index: '03',
    name: '内容审核 Agent',
    role: 'Moderation Agent · 安检员',
    icon: ShieldAlertIcon,
    t1: '#f87171',
    t2: '#ef4444',
    desc: '违禁品与欺诈识别的安全闸门，命中规则即行使安全一票否决，并输出置信度与逐条审核依据。',
    points: ['违禁 / 欺诈识别', '安全一票否决', '置信度与依据'],
  },
  {
    index: '04',
    name: '搜索推荐 Agent',
    role: 'Search Agent · 导购员',
    icon: SearchCheckIcon,
    t1: '#22d3ee',
    t2: '#06b6d4',
    desc: '多条件检索与意向匹配，给出带理由的排序结果，并进行目标相容性检查，防止推荐跑偏。',
    points: ['多条件检索', '带理由排序', '目标相容性检查'],
  },
  {
    index: '05',
    name: '议价谈判 Agent',
    role: 'Negotiation Agent · 中立主持人',
    icon: MessagesSquareIcon,
    t1: '#818cf8',
    t2: '#6366f1',
    desc: '主持多轮出价与单调让步，给出纳什均衡参考价，僵局破裂时为双方推荐同类商品。',
    points: ['多轮出价主持', '纳什参考价', '僵局推荐同类'],
  },
  {
    index: '06',
    name: '交易履约 Agent',
    role: 'Order Agent · 账房调度',
    icon: ClipboardListIcon,
    t1: '#fbbf24',
    t2: '#f59e0b',
    desc: '预占锁加乐观版本号防止抢单，驱动订单状态机与模拟支付，超时自动回滚释放资源。',
    points: ['预占锁防抢单', '订单状态机', '模拟支付 · 超时回滚'],
  },
  {
    index: '07',
    name: '信用评价 Agent',
    role: 'Credit Agent · 信用局',
    icon: BadgeCheckIcon,
    t1: '#f472b6',
    t2: '#ec4899',
    desc: '聚合买卖双向评价动态计算信用分，输出风险画像与置信度意见，联动信用奖励与处罚。',
    points: ['双向评价聚合', '信用分动态计算', '风险画像意见'],
  },
  {
    index: '08',
    name: '纠纷仲裁 Agent',
    role: 'Arbitrator Agent · 线上小法官',
    icon: GavelIcon,
    t1: '#fb923c',
    t2: '#f97316',
    desc: '汇总双方证据链生成结构化裁决书，超阈值自动升级人工终裁，并联动信用处罚闭环。',
    points: ['证据链汇总', '结构化裁决书', '升级人工 · 信用处罚'],
  },
]

/** 中枢轨道装饰：8 个专家围绕协调者的节点坐标 */
const orbitDots = Array.from({ length: 8 }, (_, i) => {
  const angle = (Math.PI * 2 * i) / 8 - Math.PI / 2
  return { x: 60 + 46 * Math.cos(angle), y: 60 + 46 * Math.sin(angle) }
})

const pipeline = [
  { title: '自然语言发布', icon: SparklesIcon },
  { title: 'Agent 审核', icon: ShieldAlertIcon },
  { title: '搜索推荐', icon: SearchIcon },
  { title: '多轮议价', icon: MessagesSquareIcon },
  { title: '下单支付', icon: CreditCardIcon },
  { title: '校内面交', icon: MapPinIcon },
  { title: '双向评价', icon: StarIcon },
]
</script>

<template>
  <div class="page-container home-page">
    <!-- ================= Hero 品牌欢迎区 ================= -->
    <section class="hero glass-card anim-fade-in-up">
      <div class="hero__bg" aria-hidden="true">
        <span class="hero__blob hero__blob--indigo anim-float-slow" />
        <span class="hero__blob hero__blob--cyan anim-float-slower" />
        <span class="hero__grid" />
      </div>

      <div class="hero__inner">
        <span class="hero__chip">
          <span class="status-dot status-dot--live" />
          Multi-Agent 黑板协同在线
          <span class="hero__chip-sep">·</span>
          {{ greeting }}，{{ auth.nickname }}
        </span>

        <h1 class="hero__title">
          <span class="gradient-text gradient-text--animated">校园二手交易</span>
          <span class="hero__title-sub gradient-text gradient-text--animated">
            Multi-Agent 智能体协作平台
          </span>
        </h1>

        <p class="hero__desc">
          <strong>1 个协调者 Agent + 8 个专家 Agent</strong>
          围绕全局状态黑板协同工作，以标准
          <em>ACL 消息</em>相互协作；交易冲突按
          <em>「对等协商 → 加权仲裁 → 人工终裁」三级决策</em>
          升级，安全底线由审核 Agent
          <em class="hero__desc-veto">一票否决</em>
          ，每一步决策均可解释、可回放。
        </p>

        <div class="hero__actions">
          <button class="btn-gradient hero__btn-primary" @click="router.push('/market')">
            <StoreIcon :width="17" :height="17" :stroke-width="2.3" />
            去市场逛逛
            <ArrowRightIcon :width="16" :height="16" :stroke-width="2.4" />
          </button>
          <button class="hero__btn-ghost" @click="router.push('/seller/publish')">
            <PackagePlusIcon :width="16" :height="16" :stroke-width="2.2" />
            发布闲置商品
          </button>
          <button v-if="isAdmin" class="hero__btn-ghost hero__btn-ghost--amber" @click="router.push('/console')">
            <RadarIcon :width="16" :height="16" :stroke-width="2.2" />
            Agent 控制台
            <ArrowRightIcon :width="14" :height="14" :stroke-width="2.4" />
          </button>
        </div>
      </div>
    </section>

    <!-- ================= 1 协调者 + 8 专家 Agent 矩阵 ================= -->
    <section class="agents">
      <header class="section-head anim-fade-in-up">
        <div>
          <h2>
            <NetworkIcon :width="19" :height="19" :stroke-width="2.2" />
            智能体编排矩阵
          </h2>
          <p>1 个协调者统筹调度，8 个专家 Agent 各司其职</p>
        </div>
        <span class="section-head__rule">COORDINATOR + 8 SPECIALISTS</span>
      </header>

      <!-- 协调者：跨列中枢高亮卡 -->
      <article class="coordinator-card glass-card anim-fade-in-up">
        <div class="coordinator-card__main">
          <span class="coordinator-card__icon">
            <component :is="coordinator.icon" :width="28" :height="28" :stroke-width="2" />
            <span class="coordinator-card__pulse" aria-hidden="true" />
          </span>
          <div class="coordinator-card__heading">
            <span class="coordinator-card__tag">
              <span class="status-dot status-dot--live" />
              {{ coordinator.role }}
            </span>
            <h3>{{ coordinator.name }}</h3>
            <p>{{ coordinator.desc }}</p>
          </div>
          <ul class="coordinator-card__points">
            <li v-for="point in coordinator.points" :key="point">
              <span class="coordinator-card__bullet" />
              {{ point }}
            </li>
          </ul>
        </div>

        <div class="coordinator-card__orbit" aria-hidden="true">
          <svg viewBox="0 0 120 120" role="img">
            <defs>
              <linearGradient id="orbitCoreGrad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stop-color="#6366f1" />
                <stop offset="100%" stop-color="#22d3ee" />
              </linearGradient>
            </defs>
            <circle class="orbit-ring" cx="60" cy="60" r="46" />
            <g class="orbit-spokes">
              <line
                v-for="(d, i) in orbitDots"
                :key="`l-${i}`"
                x1="60"
                y1="60"
                :x2="d.x"
                :y2="d.y"
                class="orbit-spoke"
              />
            </g>
            <g class="orbit-nodes">
              <circle
                v-for="(d, i) in orbitDots"
                :key="`d-${i}`"
                :cx="d.x"
                :cy="d.y"
                r="4"
                :class="['orbit-dot', i % 2 === 0 ? 'orbit-dot--indigo' : 'orbit-dot--cyan']"
              />
            </g>
            <circle cx="60" cy="60" r="13" class="orbit-core" />
            <g transform="translate(60,60)">
              <WorkflowIcon x="-9" y="-9" :width="18" :height="18" :stroke-width="2" class="orbit-core-icon" />
            </g>
          </svg>
        </div>
      </article>

      <!-- 8 专家：响应式 4×2 矩阵 -->
      <div class="agents__grid stagger">
        <article
          v-for="agent in specialists"
          :key="agent.index"
          class="agent-card glass-card agent-card--spec"
          :style="{ '--t1': agent.t1, '--t2': agent.t2 }"
        >
          <span class="agent-card__watermark">{{ agent.index }}</span>
          <div class="agent-card__head">
            <span class="agent-card__icon">
              <component :is="agent.icon" :width="23" :height="23" :stroke-width="2" />
            </span>
            <div class="agent-card__title">
              <h3>{{ agent.name }}</h3>
              <span>{{ agent.role }}</span>
            </div>
          </div>
          <p class="agent-card__desc">{{ agent.desc }}</p>
          <ul class="agent-card__points">
            <li v-for="point in agent.points" :key="point">
              <span class="agent-card__bullet" />
              {{ point }}
            </li>
          </ul>
        </article>
      </div>
    </section>

    <!-- ================= 交易主链路 7 步 ================= -->
    <section class="pipeline glass-card anim-fade-in-up">
      <header class="pipeline__header">
        <h2>
          <SparklesIcon :width="18" :height="18" :stroke-width="2.2" />
          交易主链路 · 全流程 Agent 协同
        </h2>
        <span>发布 → 审核 → 搜索 → 议价 → 下单支付 → 面交 → 评价</span>
      </header>

      <div class="pipeline__track">
        <template v-for="(step, idx) in pipeline" :key="step.title">
          <div class="pipeline__node">
            <span class="pipeline__dot">
              <component :is="step.icon" :width="18" :height="18" :stroke-width="2.1" />
              <span class="pipeline__idx">{{ idx + 1 }}</span>
            </span>
            <span class="pipeline__label">{{ step.title }}</span>
          </div>
          <span v-if="idx < pipeline.length - 1" class="pipeline__link" aria-hidden="true">
            <span class="pipeline__link-flow" />
          </span>
        </template>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.home-page {
  max-width: 1200px;
  padding-top: 28px;
}

// ================= Hero =================
.hero {
  position: relative;
  overflow: hidden;
  padding: 52px 56px 56px;
  border-radius: 24px;

  &__bg {
    position: absolute;
    inset: 0;
    pointer-events: none;
    overflow: hidden;
  }

  &__blob {
    position: absolute;
    border-radius: 50%;
    filter: blur(80px);
    opacity: 0.5;
    &--indigo {
      top: -160px;
      right: -80px;
      width: 420px;
      height: 420px;
      background: radial-gradient(circle, #818cf8 0%, transparent 70%);
    }
    &--cyan {
      bottom: -200px;
      left: -60px;
      width: 460px;
      height: 460px;
      background: radial-gradient(circle, #22d3ee 0%, transparent 70%);
      opacity: 0.38;
    }
  }

  &__grid {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(99, 102, 241, 0.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(99, 102, 241, 0.05) 1px, transparent 1px);
    background-size: 42px 42px;
    mask-image: radial-gradient(ellipse 80% 90% at 50% 0%, #000 20%, transparent 78%);
    -webkit-mask-image: radial-gradient(ellipse 80% 90% at 50% 0%, #000 20%, transparent 78%);
  }

  &__inner {
    position: relative;
    z-index: 1;
  }

  &__chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 15px;
    font-size: 12.5px;
    font-weight: 500;
    color: var(--app-text-secondary);
    border-radius: 999px;
    background: var(--app-card-bg-solid);
    border: 1px solid var(--app-card-border);
    box-shadow: var(--app-shadow-card);
  }
  &__chip-sep {
    color: var(--app-text-placeholder);
  }

  &__title {
    margin-top: 20px;
    font-size: 40px;
    font-weight: 800;
    line-height: 1.28;
    letter-spacing: 0.5px;
  }
  &__title-sub {
    display: block;
    margin-top: 4px;
    font-size: 34px;
  }

  &__desc {
    margin-top: 18px;
    max-width: 820px;
    font-size: 15px;
    line-height: 2;
    color: var(--app-text-secondary);

    strong {
      color: var(--app-text-primary);
      font-weight: 700;
    }
    em {
      font-style: normal;
      font-weight: 600;
      color: var(--app-brand);
    }
    &-veto {
      color: var(--app-danger) !important;
    }
  }

  &__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    margin-top: 30px;
  }

  &__btn-primary {
    height: 44px;
    padding: 0 26px;
    font-size: 14.5px;
    border-radius: 12px;
  }

  &__btn-ghost {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    height: 44px;
    padding: 0 22px;
    font-size: 14.5px;
    font-weight: 600;
    color: var(--app-brand);
    border-radius: 12px;
    border: 1px solid var(--app-card-border-strong);
    background: var(--app-card-bg-solid);
    box-shadow: var(--app-shadow-card);
    transition: all 0.24s cubic-bezier(0.34, 1.4, 0.5, 1);
    &:hover {
      transform: translateY(-2px);
      border-color: var(--app-brand);
      color: var(--app-brand);
      box-shadow: 0 10px 26px rgba(99, 102, 241, 0.18);
    }
    &--amber {
      color: #b45309;
      &:hover {
        border-color: #f59e0b;
        color: #b45309;
        box-shadow: 0 10px 26px rgba(245, 158, 11, 0.2);
      }
    }
  }
}

// ================= 区块标题 =================
.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin: 34px 2px 16px;

  h2 {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    font-size: 18px;
    font-weight: 700;
    color: var(--app-text-primary);
    svg {
      color: var(--app-brand);
    }
  }
  p {
    margin-top: 5px;
    font-size: 13px;
    color: var(--app-text-secondary);
  }
  &__rule {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1.6px;
    color: var(--app-text-placeholder);
    font-variant-numeric: tabular-nums;
  }
}

// ================= 协调者中枢卡 =================
.coordinator-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 30px;
  padding: 26px 32px;
  margin-bottom: 18px;
  overflow: hidden;
  border-radius: 22px;
  border-color: var(--app-card-border-strong);
  background:
    radial-gradient(560px 240px at 0% 0%, rgba(99, 102, 241, 0.12), transparent 70%),
    radial-gradient(480px 240px at 100% 100%, rgba(34, 211, 238, 0.1), transparent 70%),
    var(--app-card-bg);

  &__main {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: flex-start;
    gap: 20px;
  }

  &__icon {
    position: relative;
    flex: none;
    width: 62px;
    height: 62px;
    border-radius: 18px;
    display: grid;
    place-items: center;
    color: #fff;
    background: linear-gradient(135deg, #6366f1, #22d3ee);
    box-shadow: 0 10px 28px rgba(99, 102, 241, 0.38);
  }
  &__pulse {
    position: absolute;
    inset: -3px;
    border-radius: 20px;
    border: 2px solid rgba(99, 102, 241, 0.4);
    animation: coordinator-ring 2.6s ease-out infinite;
    pointer-events: none;
  }

  &__heading {
    flex: 1;
    min-width: 0;
    h3 {
      margin: 7px 0 6px;
      font-size: 19px;
      font-weight: 800;
      color: var(--app-text-primary);
    }
    p {
      margin: 0;
      font-size: 13px;
      line-height: 1.85;
      color: var(--app-text-secondary);
    }
  }
  &__tag {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    height: 23px;
    padding: 0 11px;
    border-radius: 999px;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.8px;
    color: var(--app-brand-strong);
    background: var(--app-brand-soft);
    border: 1px solid var(--app-card-border-strong);
  }

  &__points {
    flex: none;
    display: flex;
    flex-direction: column;
    gap: 9px;
    margin: 4px 0 0;
    padding: 0;
    list-style: none;
    li {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 14px;
      font-size: 12px;
      font-weight: 600;
      white-space: nowrap;
      color: var(--app-text-regular);
      background: var(--app-card-bg-solid);
      border: 1px solid var(--app-card-border);
      border-radius: 999px;
      box-shadow: var(--app-shadow-card);
    }
  }
  &__bullet {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #22d3ee);
    flex: none;
  }

  // ---- 1+8 中枢轨道装饰 ----
  &__orbit {
    flex: none;
    width: 132px;
    height: 132px;

    svg {
      width: 100%;
      height: 100%;
      overflow: visible;
    }
  }
}

.orbit-ring {
  fill: none;
  stroke: var(--app-card-border-strong);
  stroke-width: 1.2;
  stroke-dasharray: 3 6;
}
.orbit-spoke {
  stroke: var(--app-card-border);
  stroke-width: 1.2;
}
.orbit-dot {
  &--indigo {
    fill: #818cf8;
  }
  &--cyan {
    fill: #22d3ee;
  }
}
.orbit-nodes {
  animation: orbit-rotate 40s linear infinite;
  transform-origin: 60px 60px;
}
.orbit-core {
  fill: url(#orbitCoreGrad);
  stroke: #fff;
  stroke-width: 2;
}
.orbit-core-icon {
  color: #fff;
}

@keyframes orbit-rotate {
  to {
    transform: rotate(360deg);
  }
}
@keyframes coordinator-ring {
  0% {
    opacity: 0.7;
    transform: scale(0.94);
  }
  70% {
    opacity: 0;
    transform: scale(1.18);
  }
  100% {
    opacity: 0;
    transform: scale(1.18);
  }
}

// ================= 8 专家卡片 =================
.agents__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.agent-card {
  --t1: #6366f1;
  --t2: #22d3ee;

  position: relative;
  padding: 22px 20px 20px;
  overflow: hidden;
  border-radius: 20px;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    opacity: 0;
    border-radius: inherit;
    transition: opacity 0.3s ease;
    pointer-events: none;
    background: radial-gradient(
      420px 200px at 0% 0%,
      color-mix(in srgb, var(--t1) 11%, transparent),
      transparent 70%
    );
  }

  &:hover {
    transform: translateY(-6px);
    border-color: color-mix(in srgb, var(--t1) 38%, transparent);
    box-shadow: 0 18px 44px color-mix(in srgb, var(--t1) 20%, transparent);
  }

  &__watermark {
    position: absolute;
    right: 14px;
    top: 8px;
    font-size: 42px;
    font-weight: 800;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    opacity: 0.08;
    color: var(--t1);
    transition: opacity 0.3s ease;
  }

  &__head {
    display: flex;
    align-items: center;
    gap: 13px;
  }

  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: none;
    width: 48px;
    height: 48px;
    color: #fff;
    border-radius: 15px;
    background: linear-gradient(135deg, var(--t1), var(--t2));
    box-shadow: 0 8px 20px color-mix(in srgb, var(--t1) 32%, transparent);
    transition: transform 0.3s cubic-bezier(0.34, 1.4, 0.5, 1);
  }

  &__title {
    min-width: 0;
    h3 {
      font-size: 15px;
      font-weight: 700;
      color: var(--app-text-primary);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    span {
      display: block;
      margin-top: 3px;
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.2px;
      color: var(--app-text-placeholder);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }

  &__desc {
    margin-top: 13px;
    font-size: 12.5px;
    line-height: 1.75;
    color: var(--app-text-secondary);
    min-height: 66px;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  &__points {
    margin-top: 12px;
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    padding: 0;
    list-style: none;
  }
  &__points li {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    font-size: 11.5px;
    font-weight: 500;
    border-radius: 999px;
    background: var(--el-fill-color-light);
    color: var(--app-text-regular);
    border: 1px solid var(--app-card-border);
  }
  &__bullet {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--t1);
    flex: none;
  }

  &:hover &__icon {
    transform: scale(1.08) rotate(-4deg);
  }
  &:hover &__watermark {
    opacity: 0.18;
  }
  &:hover::before {
    opacity: 1;
  }
}

// ================= 主链路 =================
.pipeline {
  margin-top: 22px;
  padding: 26px 32px 30px;
  border-radius: 20px;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    h2 {
      display: inline-flex;
      align-items: center;
      gap: 9px;
      font-size: 16px;
      font-weight: 700;
      color: var(--app-text-primary);
      svg {
        color: var(--app-brand);
      }
    }
    > span {
      font-size: 12px;
      color: var(--app-text-placeholder);
      letter-spacing: 0.4px;
    }
  }

  &__track {
    display: flex;
    align-items: flex-start;
    margin-top: 26px;
  }

  &__node {
    flex: none;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    width: 86px;
  }

  &__dot {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 46px;
    height: 46px;
    border-radius: 50%;
    color: var(--app-brand);
    background: var(--app-card-bg-solid);
    border: 2px solid rgba(99, 102, 241, 0.25);
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.1);
    transition: all 0.26s cubic-bezier(0.34, 1.4, 0.5, 1);
  }
  &__idx {
    position: absolute;
    right: -4px;
    top: -4px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 18px;
    height: 18px;
    padding: 0 4px;
    font-size: 10.5px;
    font-weight: 700;
    color: #fff;
    border-radius: 999px;
    background: var(--app-gradient);
    box-shadow: 0 2px 6px rgba(99, 102, 241, 0.4);
  }
  &__node:hover &__dot {
    color: #fff;
    background: var(--app-gradient);
    border-color: transparent;
    transform: translateY(-4px) scale(1.05);
    box-shadow: var(--app-shadow-glow);
  }

  &__label {
    font-size: 12.5px;
    font-weight: 600;
    text-align: center;
    color: var(--app-text-regular);
    transition: color 0.2s ease;
  }
  &__node:hover &__label {
    color: var(--app-brand);
  }

  &__link {
    position: relative;
    flex: 1 1 auto;
    min-width: 20px;
    height: 2px;
    margin-top: 23px;
    border-radius: 2px;
    background: linear-gradient(90deg, rgba(99, 102, 241, 0.35), rgba(34, 211, 238, 0.35));
    overflow: hidden;
  }
  &__link-flow {
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent, var(--app-brand), var(--app-accent), transparent);
    background-size: 200% 100%;
    animation: app-flow-line 2.8s linear infinite;
  }
}

// ================= 响应式 =================
@media (max-width: 1180px) {
  .coordinator-card {
    gap: 22px;
    padding: 24px 24px;
  }
  .coordinator-card__main {
    flex-wrap: wrap;
  }
  .coordinator-card__points {
    flex-direction: row;
    flex-wrap: wrap;
    width: 100%;
  }
}

@media (max-width: 1080px) {
  .agents__grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .agent-card__desc {
    min-height: 0;
    -webkit-line-clamp: 2;
  }
  .coordinator-card {
    flex-direction: column;
    align-items: stretch;
  }
  .coordinator-card__orbit {
    display: none;
  }
}

@media (max-width: 760px) {
  .hero {
    padding: 34px 24px 36px;
  }
  .hero__title {
    font-size: 28px;
  }
  .hero__title-sub {
    font-size: 24px;
  }
  .hero__desc {
    font-size: 14px;
  }
  .agents__grid {
    grid-template-columns: 1fr;
  }
  .coordinator-card {
    padding: 22px 20px;
  }
  .coordinator-card__main {
    gap: 14px;
  }
  .section-head__rule {
    display: none;
  }
  .pipeline {
    padding: 22px 18px 24px;
  }
  .pipeline__track {
    overflow-x: auto;
    padding-bottom: 8px;
  }
  .pipeline__node {
    width: 76px;
  }
}
</style>
