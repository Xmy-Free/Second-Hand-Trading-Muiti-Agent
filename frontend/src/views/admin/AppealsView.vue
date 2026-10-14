<script setup lang="ts">
/**
 * 管理员·纠纷三级终裁台
 * 左：申诉信息；右：证据包（商品审核记录 / 议价序列 / 双方信用 / 规则建议）
 * 终裁：维持交易 uphold / 裁决退款 refund，均必填裁决依据
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getAppealQueue, resumeFlow } from '@/api/moderation'
import type { AppealQueueItem } from '@/api/moderation'
import ScaleIcon from '~icons/lucide/scale'
import RefreshCwIcon from '~icons/lucide/refresh-cw'
import InboxIcon from '~icons/lucide/inbox'
import TriangleAlertIcon from '~icons/lucide/triangle-alert'
import UserIcon from '~icons/lucide/user'
import ReceiptIcon from '~icons/lucide/receipt-text'
import BanknoteIcon from '~icons/lucide/banknote'
import MessageSquareIcon from '~icons/lucide/message-square-quote'
import PackageIcon from '~icons/lucide/package'
import MessagesSquareIcon from '~icons/lucide/messages-square'
import ShieldCheckIcon from '~icons/lucide/shield-check'
import GavelIcon from '~icons/lucide/gavel'
import CheckCheckIcon from '~icons/lucide/check-check'
import Undo2Icon from '~icons/lucide/undo-2'
import BracesIcon from '~icons/lucide/braces'
import ChevronDownIcon from '~icons/lucide/chevron-down'
import ThumbsUpIcon from '~icons/lucide/thumbs-up'
import RotateCcwIcon from '~icons/lucide/rotate-ccw'
import CpuIcon from '~icons/lucide/cpu'

interface Party {
  id?: number
  nickname?: string
  credit?: number
  risk_tag?: string
}
interface OfferRow {
  round?: number
  from_role?: string
  price?: number
  basis?: string
}
interface ItemEvidence {
  id?: number
  title?: string
  condition_level?: string
  audit_reason?: Array<{ rule?: string; detail?: string } | string>
}
interface EvidenceShape {
  appeal?: { reason?: string; created_at?: string }
  order?: { id?: number; order_no?: string; status?: string; deal_price?: number; created_at?: string }
  item?: ItemEvidence
  buyer?: Party
  seller?: Party
  offers?: OfferRow[]
}

const loading = ref(false)
const loadError = ref(false)
const queue = ref<AppealQueueItem[]>([])
const actingId = ref<string | null>(null)
const rawJsonOpen = reactive(new Set<string>())

// ---------- 终裁依据对话框 ----------
const rulingVisible = ref(false)
const rulingAction = ref<'uphold' | 'refund'>('uphold')
const rulingBasis = ref('')
const rulingTarget = ref<AppealQueueItem | null>(null)
const rulingSubmitting = ref(false)

function evidence(q: AppealQueueItem): EvidenceShape {
  return (q.evidence ?? {}) as EvidenceShape
}

function itemAudit(q: AppealQueueItem): Array<{ rule: string; detail: string }> {
  const rows = evidence(q).item?.audit_reason ?? []
  return rows
    .map((r) => {
      if (typeof r === 'string') return { rule: '审核记录', detail: r }
      return { rule: r.rule || '审核记录', detail: r.detail || r.rule || '' }
    })
    .filter((r) => r.detail)
}

function offers(q: AppealQueueItem): OfferRow[] {
  return evidence(q).offers ?? []
}

const ROLE_META: Record<string, { label: string; cls: string }> = {
  buyer: { label: '买家', cls: 'role-tag--buyer' },
  seller: { label: '卖家', cls: 'role-tag--seller' },
  agent: { label: 'Agent 建议', cls: 'role-tag--agent' },
}

function roleMeta(role?: string): { label: string; cls: string } {
  return ROLE_META[role ?? ''] ?? { label: role || '未知', cls: 'role-tag--agent' }
}

function riskText(tag?: string): string {
  if (!tag || tag === 'normal' || tag === 'low') return '风险正常'
  if (tag === 'medium') return '风险关注'
  if (tag === 'high' || tag === 'frozen') return '高风险'
  return tag
}

function riskClass(tag?: string): string {
  if (tag === 'high' || tag === 'frozen') return 'risk--high'
  if (tag === 'medium') return 'risk--mid'
  return 'risk--low'
}

const SUGGESTION_META: Record<string, { label: string; cls: string }> = {
  uphold: { label: '规则建议：维持交易', cls: 'suggest-badge--uphold' },
  refund: { label: '规则建议：裁决退款', cls: 'suggest-badge--refund' },
  manual: { label: '规则无法覆盖 · 升级人工', cls: 'suggest-badge--manual' },
}

function suggestionMeta(q: AppealQueueItem) {
  const key = q.rule_suggestion?.suggestion ?? 'manual'
  return SUGGESTION_META[key] ?? SUGGESTION_META.manual
}

function rawJson(q: AppealQueueItem): string {
  try {
    return JSON.stringify(q.evidence ?? {}, null, 2)
  } catch {
    return String(q.evidence ?? '')
  }
}

function toggleJson(threadId: string): void {
  if (rawJsonOpen.has(threadId)) rawJsonOpen.delete(threadId)
  else rawJsonOpen.add(threadId)
}

async function loadQueue(): Promise<void> {
  loading.value = true
  loadError.value = false
  try {
    queue.value = await getAppealQueue()
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function openRuling(q: AppealQueueItem, action: 'uphold' | 'refund'): void {
  rulingTarget.value = q
  rulingAction.value = action
  rulingBasis.value = ''
  rulingVisible.value = true
}

const rulingTitle = computed(() =>
  rulingAction.value === 'uphold' ? '终裁：维持交易' : '终裁：裁决退款',
)

async function submitRuling(): Promise<void> {
  if (!rulingTarget.value || rulingSubmitting.value) return
  const basis = rulingBasis.value.trim()
  if (basis.length < 5) {
    ElMessage.warning('请填写至少 5 个字的裁决依据，终裁结论将写入审计轨迹')
    return
  }
  rulingSubmitting.value = true
  actingId.value = rulingTarget.value.thread_id
  try {
    await resumeFlow(rulingTarget.value.thread_id, { action: rulingAction.value, basis })
    ElMessage.success(rulingAction.value === 'uphold' ? '终裁完成：维持交易' : '终裁完成：裁决退款并联动信用')
    rulingVisible.value = false
    await loadQueue()
  } catch {
    /* 全局提示 */
  } finally {
    rulingSubmitting.value = false
    actingId.value = null
  }
}

function fmtTime(iso?: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(loadQueue)
</script>

<template>
  <div class="page-container appeals-page">
    <!-- 页头 -->
    <header class="appeals-head anim-fade-in-up">
      <div>
        <h1>
          <ScaleIcon :width="21" :height="21" :stroke-width="2.2" />
          纠纷三级终裁台
        </h1>
        <p>规则无法定责的纠纷在此终局：核对完整证据包后作出维持或退款裁决，结论联动信用并全程留痕。</p>
      </div>
      <button class="refresh-btn" :disabled="loading" @click="loadQueue">
        <RefreshCwIcon :width="15" :height="15" :stroke-width="2.2" :class="{ 'anim-spin': loading }" />
        刷新队列
        <template v-if="!loading && queue.length">
          <span class="refresh-btn__count">{{ queue.length }}</span>
        </template>
      </button>
    </header>

    <!-- 骨架 -->
    <section v-if="loading" class="appeal-list">
      <div v-for="n in 2" :key="n" class="skeleton-case glass-card">
        <div class="skeleton skeleton-case__title" />
        <div class="skeleton skeleton-case__line" />
        <div class="skeleton skeleton-case__line skeleton-case__line--short" />
      </div>
    </section>

    <!-- 失败态 -->
    <section v-else-if="loadError" class="state-card glass-card">
      <span class="state-card__icon state-card__icon--danger">
        <TriangleAlertIcon :width="30" :height="30" :stroke-width="1.9" />
      </span>
      <h3>终裁队列加载失败</h3>
      <p>无法连接后端服务或登录态失效，请稍后重试。</p>
      <el-button type="primary" @click="loadQueue">重新加载</el-button>
    </section>

    <!-- 空状态 -->
    <section v-else-if="!queue.length" class="state-card glass-card">
      <span class="state-card__icon">
        <InboxIcon :width="30" :height="30" :stroke-width="1.8" />
      </span>
      <h3>暂无待终裁纠纷</h3>
      <p>所有申诉均已被规则引擎直裁或处理完毕，三级终裁台当前空闲。</p>
      <el-button @click="loadQueue">
        <RefreshCwIcon :width="14" :height="14" :stroke-width="2.2" style="margin-right: 5px" />
        再检查一次
      </el-button>
    </section>

    <!-- 纠纷案件卡 -->
    <section v-else class="appeal-list stagger">
      <article v-for="q in queue" :key="q.thread_id" class="case-card glass-card">
        <!-- 卡头 -->
        <header class="case-card__head">
          <div class="case-title">
            <span class="case-title__icon">
              <GavelIcon :width="18" :height="18" :stroke-width="2.1" />
            </span>
            <div>
              <h3>纠纷申诉 #{{ q.appeal_id }} <span class="case-title__no">订单 {{ q.order_no || q.order_id }}</span></h3>
              <p>进入终裁 {{ fmtTime(q.created_at) }}</p>
            </div>
          </div>
          <span class="suggest-badge" :class="suggestionMeta(q).cls">
            <CpuIcon :width="13" :height="13" :stroke-width="2.3" />
            {{ suggestionMeta(q).label }}
            <em v-if="q.rule_suggestion">
              {{ Math.round((q.rule_suggestion.confidence ?? 0) * 100) }}%
            </em>
          </span>
        </header>

        <div class="case-card__layout">
          <!-- 左：申诉信息 -->
          <div class="appeal-panel">
            <span class="panel-label">
              <MessageSquareIcon :width="14" :height="14" :stroke-width="2.2" />
              申诉信息
            </span>

            <div class="appeal-rows">
              <div class="appeal-row">
                <span class="appeal-row__label">
                  <UserIcon :width="13" :height="13" :stroke-width="2.2" />
                  申诉人
                </span>
                <b>{{ q.appellant_nickname || '匿名用户' }}</b>
              </div>
              <div class="appeal-row">
                <span class="appeal-row__label">
                  <ReceiptIcon :width="13" :height="13" :stroke-width="2.2" />
                  订单号
                </span>
                <b class="appeal-row__mono">{{ q.order_no || q.order_id }}</b>
              </div>
              <div class="appeal-row">
                <span class="appeal-row__label">
                  <PackageIcon :width="13" :height="13" :stroke-width="2.2" />
                  涉案商品
                </span>
                <b>{{ q.item_title }}</b>
              </div>
              <div class="appeal-row">
                <span class="appeal-row__label">
                  <BanknoteIcon :width="13" :height="13" :stroke-width="2.2" />
                  争议金额
                </span>
                <b class="appeal-row__amount">¥{{ q.deal_price }}</b>
              </div>
            </div>

            <div class="appeal-reason">
              <span>申诉理由</span>
              <p>{{ q.reason }}</p>
            </div>

            <!-- 规则建议依据 高亮 -->
            <div v-if="q.rule_suggestion?.basis?.length" class="rule-basis">
              <span class="rule-basis__head">
                <ScaleIcon :width="13" :height="13" :stroke-width="2.3" />
                协调者规则建议依据
              </span>
              <ul>
                <li v-for="(b, i) in q.rule_suggestion.basis" :key="i">
                  <span class="rule-basis__dot" />
                  {{ b }}
                </li>
              </ul>
            </div>
          </div>

          <!-- 右：证据包 -->
          <div class="evidence-panel">
            <span class="panel-label">
              <ShieldCheckIcon :width="14" :height="14" :stroke-width="2.2" />
              证据包 Evidence
            </span>

            <!-- 双方信用 -->
            <div class="ev-section">
              <span class="ev-section__title">买卖双方信用</span>
              <div class="parties">
                <div class="party">
                  <span class="party__role party__role--buyer">买家</span>
                  <b class="party__name">{{ evidence(q).buyer?.nickname || '—' }}</b>
                  <span class="party__credit">
                    信用 <strong>{{ evidence(q).buyer?.credit ?? '—' }}</strong>
                  </span>
                  <span class="party__risk" :class="riskClass(evidence(q).buyer?.risk_tag)">
                    {{ riskText(evidence(q).buyer?.risk_tag) }}
                  </span>
                </div>
                <div class="parties__vs">VS</div>
                <div class="party">
                  <span class="party__role party__role--seller">卖家</span>
                  <b class="party__name">{{ evidence(q).seller?.nickname || '—' }}</b>
                  <span class="party__credit">
                    信用 <strong>{{ evidence(q).seller?.credit ?? '—' }}</strong>
                  </span>
                  <span class="party__risk" :class="riskClass(evidence(q).seller?.risk_tag)">
                    {{ riskText(evidence(q).seller?.risk_tag) }}
                  </span>
                </div>
              </div>
            </div>

            <!-- 商品审核记录 -->
            <div class="ev-section">
              <span class="ev-section__title">
                商品审核记录
                <em v-if="evidence(q).item?.condition_level">{{ evidence(q).item?.condition_level }}</em>
              </span>
              <div v-if="itemAudit(q).length" class="ev-reasons">
                <div v-for="(r, i) in itemAudit(q)" :key="i" class="ev-reason">
                  <span class="ev-reason__rule">{{ r.rule }}</span>
                  <span class="ev-reason__detail">{{ r.detail }}</span>
                </div>
              </div>
              <p v-else class="ev-empty">该商品无额外审核记录。</p>
            </div>

            <!-- 议价序列 -->
            <div class="ev-section">
              <span class="ev-section__title">
                <MessagesSquareIcon :width="13" :height="13" :stroke-width="2.3" />
                议价出价序列
              </span>
              <div v-if="offers(q).length" class="offer-table">
                <div v-for="(o, i) in offers(q)" :key="i" class="offer-row">
                  <span class="offer-row__round">R{{ o.round ?? i + 1 }}</span>
                  <span class="offer-row__role">
                    <span class="role-tag" :class="roleMeta(o.from_role).cls">{{ roleMeta(o.from_role).label }}</span>
                  </span>
                  <span class="offer-row__price">¥{{ o.price }}</span>
                  <span class="offer-row__basis">{{ o.basis || '—' }}</span>
                </div>
              </div>
              <p v-else class="ev-empty">该订单为一口价成交，无议价记录。</p>
            </div>

            <!-- 原始 JSON 折叠 -->
            <div class="raw-box">
              <button type="button" class="raw-box__toggle" @click="toggleJson(q.thread_id)">
                <BracesIcon :width="13" :height="13" :stroke-width="2.3" />
                查看原始证据 JSON
                <ChevronDownIcon
                  :width="14"
                  :height="14"
                  :stroke-width="2.3"
                  class="raw-box__caret"
                  :class="{ 'raw-box__caret--open': rawJsonOpen.has(q.thread_id) }"
                />
              </button>
              <transition name="collapse">
                <pre v-show="rawJsonOpen.has(q.thread_id)" class="raw-box__code">{{ rawJson(q) }}</pre>
              </transition>
            </div>
          </div>
        </div>

        <!-- 终裁操作 -->
        <footer class="case-card__footer">
          <span class="footer-note">
            <GavelIcon :width="14" :height="14" :stroke-width="2.2" />
            三级终裁为终局结论，裁决依据将同步给买卖双方并写入审计轨迹
          </span>
          <div class="footer-actions">
            <button
              class="ruling-btn ruling-btn--uphold"
              :disabled="actingId !== null"
              :class="{ 'is-loading': actingId === q.thread_id && rulingAction === 'uphold' }"
              @click="openRuling(q, 'uphold')"
            >
              <CheckCheckIcon :width="17" :height="17" :stroke-width="2.3" />
              维持交易 uphold
            </button>
            <button
              class="ruling-btn ruling-btn--refund"
              :disabled="actingId !== null"
              @click="openRuling(q, 'refund')"
            >
              <Undo2Icon :width="17" :height="17" :stroke-width="2.3" />
              裁决退款 refund
            </button>
          </div>
        </footer>
      </article>
    </section>

    <!-- 终裁依据对话框 -->
    <el-dialog
      v-model="rulingVisible"
      :title="rulingTitle"
      width="560px"
      :close-on-click-modal="false"
      align-center
    >
      <div v-if="rulingTarget" class="ruling-dialog">
        <div
          class="ruling-dialog__banner"
          :class="rulingAction === 'uphold' ? 'ruling-dialog__banner--uphold' : 'ruling-dialog__banner--refund'"
        >
          <component
            :is="rulingAction === 'uphold' ? ThumbsUpIcon : RotateCcwIcon"
            :width="18"
            :height="18"
            :stroke-width="2.2"
          />
          <p>
            <template v-if="rulingAction === 'uphold'">
              维持交易后订单继续履约流程，卖家无需退款；若规则曾建议退款，请在依据中说明不采纳的理由。
            </template>
            <template v-else>
              裁决退款将向买家退回 ¥{{ rulingTarget.deal_price }}，并对卖家联动信用扣罚，请确保证据充分。
            </template>
          </p>
        </div>

        <div class="ruling-dialog__meta">
          <div><span>申诉编号</span><b>#{{ rulingTarget.appeal_id }}</b></div>
          <div><span>订单号</span><b>{{ rulingTarget.order_no }}</b></div>
          <div><span>争议金额</span><b>¥{{ rulingTarget.deal_price }}</b></div>
        </div>

        <label class="ruling-dialog__label">裁决依据（必填）</label>
        <el-input
          v-model="rulingBasis"
          type="textarea"
          :autosize="{ minRows: 4, maxRows: 10 }"
          maxlength="300"
          show-word-limit
          resize="none"
          :placeholder="
            rulingAction === 'uphold'
              ? '例如：证据显示商品与描述一致且买家已验货面交，议价过程卖家无隐瞒，维持交易…'
              : '例如：议价时卖家承诺功能正常但实际无法开机，审核记录存在同类投诉，裁决全额退款并扣减信用…'
          "
        />
      </div>
      <template #footer>
        <el-button @click="rulingVisible = false">取消</el-button>
        <el-button
          :type="rulingAction === 'uphold' ? 'success' : 'danger'"
          :loading="rulingSubmitting"
          @click="submitRuling"
        >
          {{ rulingSubmitting ? '裁决写回中…' : rulingAction === 'uphold' ? '确认维持交易' : '确认裁决退款' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.appeals-page {
  max-width: 1200px;
  padding-top: 26px;
}

// ---------- 页头 ----------
.appeals-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;

  h1 {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    font-size: 22px;
    font-weight: 800;
    color: var(--app-text-primary);
    svg {
      color: var(--app-brand);
    }
  }
  p {
    margin-top: 8px;
    font-size: 13.5px;
    color: var(--app-text-secondary);
  }
}

.refresh-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 40px;
  padding: 0 18px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--app-text-secondary);
  border-radius: 11px;
  background: var(--app-card-bg);
  border: 1px solid var(--app-card-border-strong);
  transition: all 0.2s ease;
  &:hover:not(:disabled) {
    color: var(--app-brand);
    border-color: var(--app-brand);
    transform: translateY(-1px);
  }
  &:disabled {
    opacity: 0.6;
  }
  &__count {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    font-size: 11.5px;
    font-weight: 700;
    color: #fff;
    border-radius: 999px;
    background: var(--app-gradient);
  }
}

// ---------- 案件卡 ----------
.appeal-list {
  display: grid;
  gap: 20px;
  margin-top: 20px;
}

.case-card {
  border-radius: 20px;
  overflow: hidden;

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    flex-wrap: wrap;
    padding: 18px 24px;
    border-bottom: 1px solid var(--app-divider);
  }
}

.case-title {
  display: flex;
  align-items: center;
  gap: 13px;
  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    flex: none;
    color: #fff;
    border-radius: 13px;
    background: var(--app-gradient);
    box-shadow: 0 6px 18px rgba(99, 102, 241, 0.3);
  }
  h3 {
    font-size: 15.5px;
    font-weight: 700;
    color: var(--app-text-primary);
  }
  &__no {
    margin-left: 8px;
    font-size: 12px;
    font-weight: 500;
    color: var(--app-text-placeholder);
  }
  p {
    margin-top: 3px;
    font-size: 12px;
    color: var(--app-text-secondary);
  }
}

.suggest-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 15px;
  font-size: 12.5px;
  font-weight: 700;
  border-radius: 999px;
  em {
    font-style: normal;
    font-size: 11.5px;
    font-weight: 800;
    padding: 1px 7px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.55);
  }
  &--uphold {
    color: #047857;
    background: var(--app-success-soft);
    border: 1px solid rgba(16, 185, 129, 0.32);
  }
  &--refund {
    color: #b91c1c;
    background: var(--app-danger-soft);
    border: 1px solid rgba(239, 68, 68, 0.3);
  }
  &--manual {
    color: #92400e;
    background: var(--app-warning-soft);
    border: 1px solid rgba(245, 158, 11, 0.32);
  }
}

// 左右布局
.case-card__layout {
  display: grid;
  grid-template-columns: minmax(300px, 0.9fr) minmax(0, 1.1fr);
}

.panel-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.4px;
  color: var(--app-text-placeholder);
}

// 左：申诉
.appeal-panel {
  padding: 20px 24px;
  border-right: 1px solid var(--app-divider);
  background:
    linear-gradient(180deg, rgba(99, 102, 241, 0.035), transparent 220px);
}

.appeal-rows {
  margin-top: 12px;
  border-radius: 13px;
  overflow: hidden;
  border: 1px solid var(--app-card-border);
}
.appeal-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  font-size: 13px;
  background: var(--el-fill-color-extra-light);
  & + & {
    border-top: 1px solid var(--app-card-border);
  }
  &__label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    flex: none;
    color: var(--app-text-secondary);
    svg {
      color: var(--app-brand);
    }
  }
  b {
    font-weight: 600;
    color: var(--app-text-primary);
    text-align: right;
    word-break: break-all;
  }
  &__mono {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 12.5px;
  }
  &__amount {
    color: var(--app-danger) !important;
    font-size: 15px;
    font-variant-numeric: tabular-nums;
  }
}

.appeal-reason {
  margin-top: 14px;
  padding: 13px 15px;
  border-radius: 13px;
  background: var(--app-brand-soft);
  border: 1px solid rgba(99, 102, 241, 0.18);
  span {
    font-size: 11.5px;
    font-weight: 700;
    letter-spacing: 0.3px;
    color: var(--app-brand);
  }
  p {
    margin-top: 7px;
    font-size: 13px;
    line-height: 1.8;
    color: var(--app-text-regular);
    white-space: pre-wrap;
    word-break: break-word;
  }
}

.rule-basis {
  margin-top: 14px;
  padding: 13px 15px;
  border-radius: 13px;
  background: var(--app-warning-soft);
  border: 1px solid rgba(245, 158, 11, 0.32);
  &__head {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11.5px;
    font-weight: 700;
    color: #92400e;
  }
  ul {
    margin-top: 8px;
    display: grid;
    gap: 7px;
  }
  li {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 12.5px;
    line-height: 1.7;
    color: #78350f;
  }
  &__dot {
    flex: none;
    width: 6px;
    height: 6px;
    margin-top: 8px;
    border-radius: 50%;
    background: #f59e0b;
    box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2);
  }
}

// 右：证据
.evidence-panel {
  padding: 20px 24px;
}
.ev-section {
  margin-top: 14px;
  &__title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12.5px;
    font-weight: 700;
    color: var(--app-text-primary);
    em {
      font-style: normal;
      padding: 1px 8px;
      font-size: 11px;
      font-weight: 600;
      color: var(--app-brand);
      background: var(--app-brand-soft);
      border-radius: 999px;
    }
  }
}

.parties {
  display: flex;
  align-items: stretch;
  gap: 10px;
  margin-top: 9px;
}
.party {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 12px 14px;
  border-radius: 13px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);
  &__role {
    align-self: flex-start;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 700;
    border-radius: 999px;
    color: #fff;
    &--buyer {
      background: linear-gradient(135deg, #4f46e5, #6366f1);
    }
    &--seller {
      background: linear-gradient(135deg, #0891b2, #22d3ee);
    }
  }
  &__name {
    font-size: 14px;
    font-weight: 700;
    color: var(--app-text-primary);
  }
  &__credit {
    font-size: 12px;
    color: var(--app-text-secondary);
    strong {
      font-size: 14px;
      font-weight: 800;
      color: var(--app-brand);
      font-variant-numeric: tabular-nums;
    }
  }
  &__risk {
    align-self: flex-start;
    font-size: 11px;
    font-weight: 600;
    padding: 1px 9px;
    border-radius: 999px;
    &--low {
      color: #047857;
      background: var(--app-success-soft);
    }
    &--mid {
      color: #92400e;
      background: var(--app-warning-soft);
    }
    &--high {
      color: #b91c1c;
      background: var(--app-danger-soft);
    }
  }
}
.parties__vs {
  align-self: center;
  flex: none;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1px;
  color: var(--app-text-placeholder);
}

.ev-reasons {
  display: grid;
  gap: 7px;
  margin-top: 9px;
}
.ev-reason {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 9px 12px;
  border-radius: 10px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);
  &__rule {
    flex: none;
    padding: 1px 8px;
    height: fit-content;
    font-size: 10.5px;
    font-weight: 600;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: var(--app-brand);
    background: var(--app-brand-soft);
    border-radius: 999px;
  }
  &__detail {
    font-size: 12.5px;
    line-height: 1.7;
    color: var(--app-text-regular);
  }
}
.ev-empty {
  margin-top: 9px;
  padding: 11px;
  font-size: 12px;
    color: var(--app-text-placeholder);
  text-align: center;
  border: 1px dashed var(--app-card-border-strong);
  border-radius: 10px;
}

.offer-table {
  margin-top: 9px;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--app-card-border);
}
.offer-row {
  display: grid;
  grid-template-columns: 42px 92px 72px 1fr;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  font-size: 12.5px;
  background: var(--el-fill-color-extra-light);
  & + & {
    border-top: 1px solid var(--app-card-border);
  }
  &__round {
    font-size: 11px;
    font-weight: 800;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: var(--app-brand);
  }
  &__price {
    font-weight: 800;
    font-size: 13px;
    color: var(--app-text-primary);
    font-variant-numeric: tabular-nums;
  }
  &__basis {
    color: var(--app-text-secondary);
    line-height: 1.6;
  }
}
.role-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 9px;
  font-size: 11px;
  font-weight: 700;
  border-radius: 999px;
  &--buyer {
    color: #4338ca;
    background: rgba(99, 102, 241, 0.12);
  }
  &--seller {
    color: #0e7490;
    background: rgba(34, 211, 238, 0.14);
  }
  &--agent {
    color: #b45309;
    background: rgba(245, 158, 11, 0.14);
  }
}

.raw-box {
  margin-top: 14px;
  border-radius: 11px;
  border: 1px solid var(--app-card-border);
  overflow: hidden;
  &__toggle {
    display: flex;
    align-items: center;
    gap: 7px;
    width: 100%;
    padding: 9px 13px;
    font-size: 12px;
    font-weight: 600;
    color: var(--app-text-secondary);
    background: var(--el-fill-color-light);
    transition: color 0.2s ease;
    &:hover {
      color: var(--app-brand);
    }
  }
  &__caret {
    margin-left: auto;
    transition: transform 0.24s ease;
    &--open {
      transform: rotate(180deg);
    }
  }
  &__code {
    margin: 0;
    padding: 13px 15px;
    max-height: 260px;
    overflow: auto;
    font-family: 'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace;
    font-size: 11.5px;
    line-height: 1.7;
    color: var(--app-text-regular);
    background: var(--el-fill-color-extra-light);
    border-top: 1px solid var(--app-card-border);
    white-space: pre;
  }
}

// 底部终裁
.case-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 18px 24px;
  border-top: 1px solid var(--app-divider);
  background:
    linear-gradient(90deg, rgba(16, 185, 129, 0.05), rgba(239, 68, 68, 0.05)),
    var(--el-fill-color-extra-light);
}
.footer-note {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: var(--app-text-secondary);
  svg {
    color: var(--app-brand);
  }
}
.footer-actions {
  display: flex;
  gap: 12px;
}
.ruling-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 46px;
  padding: 0 24px;
  font-size: 14.5px;
  font-weight: 700;
  color: #fff;
  border-radius: 13px;
  transition: all 0.24s cubic-bezier(0.34, 1.4, 0.5, 1);
  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
  &--uphold {
    background: linear-gradient(135deg, #059669, #10b981);
    box-shadow: 0 8px 22px rgba(16, 185, 129, 0.34);
    &:not(:disabled):hover {
      transform: translateY(-2px);
      box-shadow: 0 12px 30px rgba(16, 185, 129, 0.42);
    }
  }
  &--refund {
    background: linear-gradient(135deg, #dc2626, #f43f5e);
    box-shadow: 0 8px 22px rgba(239, 68, 68, 0.32);
    &:not(:disabled):hover {
      transform: translateY(-2px);
      box-shadow: 0 12px 30px rgba(239, 68, 68, 0.42);
    }
  }
}

// ---------- 骨架 / 状态卡 ----------
.skeleton-case {
  padding: 24px;
  border-radius: 20px;
  &__title {
    width: 36%;
    height: 18px;
  }
  &__line {
    width: 78%;
    height: 13px;
    margin-top: 14px;
    &--short {
      width: 28%;
    }
  }
}

.state-card {
  margin-top: 26px;
  padding: 60px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  border-radius: 20px;

  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 78px;
    height: 78px;
    color: #fff;
    border-radius: 23px;
    background: var(--app-gradient);
    box-shadow: var(--app-shadow-glow);
    &--danger {
      background: linear-gradient(135deg, #dc2626, #fb7185);
      box-shadow: 0 12px 30px rgba(239, 68, 68, 0.32);
    }
  }
  h3 {
    margin-top: 18px;
    font-size: 17px;
    font-weight: 700;
    color: var(--app-text-primary);
  }
  p {
    margin: 8px 0 20px;
    max-width: 400px;
    font-size: 13px;
    line-height: 1.7;
    color: var(--app-text-secondary);
  }
}

// ---------- 终裁对话框 ----------
.ruling-dialog {
  &__banner {
    display: flex;
    gap: 10px;
    padding: 13px 15px;
    border-radius: 12px;
    margin-bottom: 14px;
    svg {
      flex: none;
      margin-top: 2px;
    }
    p {
      font-size: 12.5px;
      line-height: 1.75;
    }
    &--uphold {
      color: #047857;
      background: var(--app-success-soft);
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    &--refund {
      color: #b91c1c;
      background: var(--app-danger-soft);
      border: 1px solid rgba(239, 68, 68, 0.3);
    }
  }
  &__meta {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 16px;
    div {
      padding: 9px 12px;
      border-radius: 10px;
      background: var(--el-fill-color-light);
      span {
        display: block;
        font-size: 11px;
        color: var(--app-text-placeholder);
        margin-bottom: 3px;
      }
      b {
        font-size: 12.5px;
        font-weight: 700;
        color: var(--app-text-primary);
        word-break: break-all;
      }
    }
  }
  &__label {
    display: block;
    margin-bottom: 8px;
    font-size: 13px;
    font-weight: 600;
    color: var(--app-text-primary);
  }
}

// ---------- 响应式 ----------
@media (max-width: 900px) {
  .case-card__layout {
    grid-template-columns: 1fr;
  }
  .appeal-panel {
    border-right: none;
    border-bottom: 1px solid var(--app-divider);
  }
}
@media (max-width: 600px) {
  .offer-row {
    grid-template-columns: 36px 80px 64px;
    grid-template-rows: auto auto;
    &__basis {
      grid-column: 1 / -1;
    }
  }
  .ruling-dialog__meta {
    grid-template-columns: 1fr !important;
  }
  .ruling-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
