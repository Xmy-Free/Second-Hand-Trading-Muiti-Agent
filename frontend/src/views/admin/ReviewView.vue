<script setup lang="ts">
/**
 * 管理员·商品人工复核台
 * - item_review 存疑复核：通过上架 / 驳回（必填依据）
 * - veto_review 安全否决：维持冻结 / 证据推翻解除冻结（必填依据）
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getReviewQueue, resumeFlow } from '@/api/moderation'
import type { ReviewQueueItem } from '@/api/moderation'
import GavelIcon from '~icons/lucide/gavel'
import RefreshCwIcon from '~icons/lucide/refresh-cw'
import InboxIcon from '~icons/lucide/inbox'
import ShieldAlertIcon from '~icons/lucide/shield-alert'
import CircleHelpIcon from '~icons/lucide/circle-help'
import CircleCheckIcon from '~icons/lucide/circle-check-big'
import CircleXIcon from '~icons/lucide/circle-x'
import SnowflakeIcon from '~icons/lucide/snowflake'
import UnlockIcon from '~icons/lucide/lock-open'
import ScrollTextIcon from '~icons/lucide/scroll-text'
import TagIcon from '~icons/lucide/tag'
import BanknoteIcon from '~icons/lucide/banknote'
import FileTextIcon from '~icons/lucide/file-text'
import TriangleAlertIcon from '~icons/lucide/triangle-alert'
import ListChecksIcon from '~icons/lucide/list-checks'

const loading = ref(false)
const loadError = ref(false)
const queue = ref<ReviewQueueItem[]>([])
const actingId = ref<string | null>(null)

// ---------- 依据填写对话框（reject / unfreeze） ----------
const basisVisible = ref(false)
const basisAction = ref<'reject' | 'unfreeze'>('reject')
const basisText = ref('')
const basisTarget = ref<ReviewQueueItem | null>(null)
const basisSubmitting = ref(false)

const counts = computed(() => ({
  review: queue.value.filter((q) => q.kind === 'item_review').length,
  veto: queue.value.filter((q) => q.kind === 'veto_review').length,
}))

function confidencePct(q: ReviewQueueItem): number | null {
  if (q.confidence == null || !Number.isFinite(Number(q.confidence))) return null
  return Math.round(Number(q.confidence) * 100)
}

function confidenceClass(pct: number | null): string {
  if (pct == null) return ''
  if (pct >= 80) return 'conf-bar__fill--high'
  if (pct >= 55) return 'conf-bar__fill--mid'
  return 'conf-bar__fill--low'
}

interface ReasonRow {
  rule: string
  detail: string
}

function normalizeReasons(q: ReviewQueueItem): ReasonRow[] {
  return (q.reasons ?? [])
    .map((r) => ({ rule: r.rule || '审核规则', detail: r.detail || r.rule || '' }))
    .filter((r) => r.detail)
}

function itemReasons(q: ReviewQueueItem): ReasonRow[] {
  return (q.item.audit_reason ?? [])
    .map((r) => {
      if (typeof r === 'string') return { rule: '审核记录', detail: r }
      return { rule: r.rule || '审核记录', detail: r.detail || r.rule || '' }
    })
    .filter((r) => r.detail)
}

async function loadQueue(): Promise<void> {
  loading.value = true
  loadError.value = false
  try {
    queue.value = await getReviewQueue()
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function isVeto(q: ReviewQueueItem): boolean {
  return q.kind === 'veto_review'
}

async function callResume(
  q: ReviewQueueItem,
  action: 'approve' | 'reject' | 'maintain' | 'unfreeze',
  basis?: string,
): Promise<void> {
  actingId.value = q.thread_id
  try {
    await resumeFlow(q.thread_id, { action, basis })
    const messages: Record<string, string> = {
      approve: '复核通过，商品已上架',
      reject: '已驳回并写回裁决依据',
      maintain: '已维持冻结，安全否决继续生效',
      unfreeze: '证据成立，商品已解除冻结并上架',
    }
    ElMessage.success(messages[action])
    await loadQueue()
  } catch {
    /* 全局提示 */
  } finally {
    actingId.value = null
  }
}

async function onApprove(q: ReviewQueueItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认「${q.item.title}」通过人工复核并直接上架？该决定会写入审计轨迹。`,
      '通过上架确认',
      { confirmButtonText: '通过并上架', cancelButtonText: '取消', type: 'success' },
    )
  } catch {
    return
  }
  await callResume(q, 'approve')
}

function openBasis(q: ReviewQueueItem, action: 'reject' | 'unfreeze'): void {
  basisTarget.value = q
  basisAction.value = action
  basisText.value = ''
  basisVisible.value = true
}

const basisDialogTitle = computed(() =>
  basisAction.value === 'reject' ? '驳回商品 · 填写裁决依据' : '证据推翻 · 解除安全冻结',
)

async function submitBasis(): Promise<void> {
  if (!basisTarget.value || basisSubmitting.value) return
  const text = basisText.value.trim()
  if (text.length < 5) {
    ElMessage.warning('请填写至少 5 个字的裁决依据，该依据将写入审计轨迹')
    return
  }
  basisSubmitting.value = true
  try {
    await resumeFlow(basisTarget.value.thread_id, { action: basisAction.value, basis: text })
    ElMessage.success(basisAction.value === 'reject' ? '已驳回并写回裁决依据' : '证据成立，已解除冻结')
    basisVisible.value = false
    await loadQueue()
  } catch {
    /* 全局提示 */
  } finally {
    basisSubmitting.value = false
    actingId.value = null
  }
}

async function onMaintain(q: ReviewQueueItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `维持对「${q.item.title}」的安全冻结？冻结状态将继续生效并写回审计。`,
      '维持冻结确认',
      {
        confirmButtonText: '维持冻结',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch {
    return
  }
  await callResume(q, 'maintain')
}

function fmtTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(loadQueue)
</script>

<template>
  <div class="page-container review-page">
    <!-- 页头 -->
    <header class="review-head anim-fade-in-up">
      <div>
        <h1>
          <GavelIcon :width="21" :height="21" :stroke-width="2.2" />
          商品人工复核台
        </h1>
        <p>对 Agent 存疑与安全否决的商品进行人工兜底裁决，所有结论与依据均写入审计轨迹。</p>
      </div>
      <div class="review-head__side">
        <div v-if="!loading && !loadError" class="head-counts">
          <span class="head-count head-count--warning">
            <CircleHelpIcon :width="14" :height="14" :stroke-width="2.3" />
            存疑复核 <b>{{ counts.review }}</b>
          </span>
          <span class="head-count head-count--danger">
            <ShieldAlertIcon :width="14" :height="14" :stroke-width="2.3" />
            安全否决 <b>{{ counts.veto }}</b>
          </span>
        </div>
        <button class="refresh-btn" :disabled="loading" @click="loadQueue">
          <RefreshCwIcon :width="15" :height="15" :stroke-width="2.2" :class="{ 'anim-spin': loading }" />
          刷新队列
        </button>
      </div>
    </header>

    <!-- 骨架 -->
    <section v-if="loading" class="queue-list">
      <div v-for="n in 3" :key="n" class="skeleton-case glass-card">
        <div class="skeleton skeleton-case__badge" />
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
      <h3>复核队列加载失败</h3>
      <p>无法连接后端服务或登录态失效，请稍后重试。</p>
      <el-button type="primary" @click="loadQueue">重新加载</el-button>
    </section>

    <!-- 空队列 -->
    <section v-else-if="!queue.length" class="state-card glass-card">
      <span class="state-card__icon">
        <InboxIcon :width="30" :height="30" :stroke-width="1.8" />
      </span>
      <h3>复核队列为空</h3>
      <p>当前没有存疑商品或安全否决等待人工处理，Agent 防线运转正常。</p>
      <el-button @click="loadQueue">
        <RefreshCwIcon :width="14" :height="14" :stroke-width="2.2" style="margin-right: 5px" />
        再检查一次
      </el-button>
    </section>

    <!-- 证据卡列表 -->
    <section v-else class="queue-list stagger">
      <article
        v-for="q in queue"
        :key="q.thread_id"
        class="case-card glass-card"
        :class="isVeto(q) ? 'case-card--veto' : 'case-card--review'"
      >
        <!-- 卡头：类型 + 置信度 -->
        <header class="case-card__head">
          <div class="case-kind">
            <span class="case-kind__icon" :class="isVeto(q) ? 'case-kind__icon--veto' : 'case-kind__icon--review'">
              <ShieldAlertIcon v-if="isVeto(q)" :width="18" :height="18" :stroke-width="2.1" />
              <CircleHelpIcon v-else :width="18" :height="18" :stroke-width="2.1" />
            </span>
            <div>
              <h3>
                {{ isVeto(q) ? '安全否决复核 · veto_review' : '存疑商品复核 · item_review' }}
              </h3>
              <p>{{ q.summary || '等待人工裁决' }}</p>
            </div>
          </div>
          <div class="case-meta">
            <div v-if="confidencePct(q) !== null" class="conf">
              <div class="conf__top">
                <span>引擎置信度</span>
                <b>{{ confidencePct(q) }}%</b>
              </div>
              <span class="conf-bar">
                <span
                  class="conf-bar__fill"
                  :class="confidenceClass(confidencePct(q))"
                  :style="{ width: `${confidencePct(q)}%` }"
                />
              </span>
            </div>
            <span class="case-time">进入队列 {{ fmtTime(q.created_at) }}</span>
          </div>
        </header>

        <div class="case-card__content">
          <!-- 左：商品信息 -->
          <div class="item-panel">
            <span class="panel-title">
              <FileTextIcon :width="14" :height="14" :stroke-width="2.2" />
              商品信息
            </span>
            <h4 class="item-panel__title">{{ q.item.title }}</h4>
            <div class="item-panel__chips">
              <span class="info-chip">
                <TagIcon :width="12" :height="12" :stroke-width="2.2" />
                {{ q.item.category || '其他' }}
              </span>
              <span class="info-chip">{{ q.item.condition_level || '成色未知' }}</span>
              <span class="info-chip info-chip--price">
                <BanknoteIcon :width="12" :height="12" :stroke-width="2.2" />
                ¥{{ q.item.price }}
              </span>
            </div>
            <p class="item-panel__desc">{{ q.item.description }}</p>
            <div class="item-panel__seller">
              卖家：{{ q.item.seller_nickname || `用户#${q.item.seller_id}` }}
              · 信用 {{ q.item.seller_credit }}
            </div>
          </div>

          <!-- 右：逐条审核依据 -->
          <div class="reason-panel">
            <span class="panel-title">
              <ScrollTextIcon :width="14" :height="14" :stroke-width="2.2" />
              逐条审核依据
            </span>
            <div v-if="normalizeReasons(q).length" class="reason-stack">
              <div v-for="(r, i) in normalizeReasons(q)" :key="i" class="reason-chip">
                <span class="reason-chip__idx">{{ i + 1 }}</span>
                <div>
                  <span class="reason-chip__rule">{{ r.rule }}</span>
                  <p class="reason-chip__detail">{{ r.detail }}</p>
                </div>
              </div>
            </div>
            <div v-else-if="itemReasons(q).length" class="reason-stack">
              <div v-for="(r, i) in itemReasons(q)" :key="i" class="reason-chip">
                <span class="reason-chip__idx">{{ i + 1 }}</span>
                <div>
                  <span class="reason-chip__rule">{{ r.rule }}</span>
                  <p class="reason-chip__detail">{{ r.detail }}</p>
                </div>
              </div>
            </div>
            <p v-else class="reason-empty">引擎未返回结构化依据，请结合商品描述人工判断。</p>
          </div>
        </div>

        <!-- 裁决操作 -->
        <footer class="case-card__footer">
          <template v-if="isVeto(q)">
            <div class="footer-hint footer-hint--danger">
              <SnowflakeIcon :width="14" :height="14" :stroke-width="2.3" />
              默认维持安全否决；仅有确凿证据时才可推翻冻结
            </div>
            <div class="footer-actions">
              <el-button
                type="danger"
                :loading="actingId === q.thread_id"
                @click="onMaintain(q)"
              >
                <SnowflakeIcon v-if="actingId !== q.thread_id" :width="15" :height="15" :stroke-width="2.2" style="margin-right: 5px" />
                维持冻结
              </el-button>
              <el-button plain class="unfreeze-btn" :disabled="actingId === q.thread_id" @click="openBasis(q, 'unfreeze')">
                <UnlockIcon :width="15" :height="15" :stroke-width="2.2" style="margin-right: 5px" />
                证据推翻，解除冻结
              </el-button>
            </div>
          </template>
          <template v-else>
            <div class="footer-hint">
              <ListChecksIcon :width="14" :height="14" :stroke-width="2.3" />
              请核对左侧商品与右侧依据后作出终局判断
            </div>
            <div class="footer-actions">
              <el-button
                type="primary"
                :loading="actingId === q.thread_id"
                @click="onApprove(q)"
              >
                <CircleCheckIcon v-if="actingId !== q.thread_id" :width="15" :height="15" :stroke-width="2.2" style="margin-right: 5px" />
                通过上架
              </el-button>
              <el-button
                type="danger"
                plain
                :disabled="actingId === q.thread_id"
                @click="openBasis(q, 'reject')"
              >
                <CircleXIcon :width="15" :height="15" :stroke-width="2.2" style="margin-right: 5px" />
                驳回
              </el-button>
            </div>
          </template>
        </footer>
      </article>
    </section>

    <!-- 裁决依据对话框（驳回 / 解除冻结） -->
    <el-dialog
      v-model="basisVisible"
      :title="basisDialogTitle"
      width="540px"
      :close-on-click-modal="false"
      align-center
    >
      <div v-if="basisTarget" class="basis-dialog">
        <div
          class="basis-dialog__banner"
          :class="basisAction === 'unfreeze' ? 'basis-dialog__banner--danger' : 'basis-dialog__banner--warning'"
        >
          <component
            :is="basisAction === 'unfreeze' ? ShieldAlertIcon : CircleXIcon"
            :width="17"
            :height="17"
            :stroke-width="2.2"
          />
          <p>
            <template v-if="basisAction === 'unfreeze'">
              你正在以人工证据推翻安全 Agent 的一票否决，该高危操作将全程留痕，请慎重填写推翻依据。
            </template>
            <template v-else>
              驳回后卖家可看到该依据并获得 1 次修改重提机会，请写明具体问题。
            </template>
          </p>
        </div>

        <div class="basis-dialog__item">
          <span>裁决商品</span>
          <b>{{ basisTarget.item.title }}</b>
        </div>

        <label class="basis-dialog__label">
          {{ basisAction === 'unfreeze' ? '解除冻结依据（必填）' : '驳回理由（必填）' }}
        </label>
        <el-input
          v-model="basisText"
          type="textarea"
          :autosize="{ minRows: 4, maxRows: 9 }"
          maxlength="300"
          show-word-limit
          resize="none"
          :placeholder="
            basisAction === 'unfreeze'
              ? '例如：经核查商品图片与凭证为正规教材附带光盘，非作弊器材，规则命中系关键词误判…'
              : '例如：描述过于简单且无法判断商品状况，请补充实物图与购入渠道后重提…'
          "
        />
      </div>
      <template #footer>
        <el-button @click="basisVisible = false">取消</el-button>
        <el-button
          :type="basisAction === 'unfreeze' ? 'danger' : 'primary'"
          :loading="basisSubmitting"
          @click="submitBasis"
        >
          {{ basisSubmitting ? '写回中…' : basisAction === 'unfreeze' ? '确认解除冻结' : '确认驳回' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.review-page {
  max-width: 1200px;
  padding-top: 26px;
}

// ---------- 页头 ----------
.review-head {
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
  &__side {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
}

.head-counts {
  display: flex;
  gap: 8px;
}
.head-count {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 13px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 999px;
  background: var(--app-card-bg);
  border: 1px solid var(--app-card-border);
  b {
    font-size: 13.5px;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }
  &--warning {
    color: #b45309;
    b {
      color: #b45309;
    }
  }
  &--danger {
    color: var(--app-danger);
    b {
      color: var(--app-danger);
    }
  }
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 38px;
  padding: 0 16px;
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
}

// ---------- 证据卡 ----------
.queue-list {
  display: grid;
  gap: 18px;
  margin-top: 20px;
}

.case-card {
  border-radius: 20px;
  overflow: hidden;

  &--veto {
    border-color: rgba(239, 68, 68, 0.3);
    box-shadow: 0 10px 30px rgba(239, 68, 68, 0.08);
  }
  &--review {
    border-color: rgba(245, 158, 11, 0.3);
    box-shadow: 0 10px 30px rgba(245, 158, 11, 0.07);
  }

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    flex-wrap: wrap;
    padding: 18px 24px;
    border-bottom: 1px solid var(--app-divider);
  }
}

.case-kind {
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
    border-radius: 13px;
    &--review {
      color: #b45309;
      background: var(--app-warning-soft);
      box-shadow: 0 6px 16px rgba(245, 158, 11, 0.2);
    }
    &--veto {
      color: var(--app-danger);
      background: var(--app-danger-soft);
      box-shadow: 0 6px 16px rgba(239, 68, 68, 0.2);
    }
  }
  h3 {
    font-size: 15.5px;
    font-weight: 700;
    color: var(--app-text-primary);
  }
  p {
    margin-top: 3px;
    font-size: 12.5px;
    color: var(--app-text-secondary);
  }
}

.case-meta {
  display: flex;
  align-items: center;
  gap: 18px;
}
.conf {
  width: 190px;
  &__top {
    display: flex;
    justify-content: space-between;
    font-size: 11.5px;
    color: var(--app-text-secondary);
    margin-bottom: 6px;
    b {
      font-size: 12.5px;
      font-weight: 800;
      color: var(--app-text-primary);
      font-variant-numeric: tabular-nums;
    }
  }
}
.conf-bar {
  display: block;
  height: 8px;
  border-radius: 999px;
  background: var(--el-fill-color-dark);
  overflow: hidden;
  &__fill {
    display: block;
    height: 100%;
    border-radius: 999px;
    transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
    &--high {
      background: linear-gradient(90deg, #f59e0b, #ef4444);
    }
    &--mid {
      background: linear-gradient(90deg, #6366f1, #22d3ee);
    }
    &--low {
      background: linear-gradient(90deg, #94a3b8, #64748b);
    }
  }
}
.case-time {
  font-size: 11.5px;
  color: var(--app-text-placeholder);
  white-space: nowrap;
}

.case-card__content {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
}

.panel-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.3px;
  color: var(--app-text-placeholder);
}

// 商品信息
.item-panel {
  padding: 20px 24px;
  border-right: 1px solid var(--app-divider);

  &__title {
    margin-top: 10px;
    font-size: 16px;
    font-weight: 700;
    color: var(--app-text-primary);
    line-height: 1.5;
  }
  &__chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
  }
  &__desc {
    margin-top: 12px;
    padding: 12px 14px;
    font-size: 13px;
    line-height: 1.8;
    color: var(--app-text-regular);
    background: var(--el-fill-color-light);
    border-radius: 12px;
    border: 1px solid var(--app-card-border);
    white-space: pre-wrap;
    word-break: break-word;
  }
  &__seller {
    margin-top: 10px;
    font-size: 12px;
    color: var(--app-text-placeholder);
  }
}

.info-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 11px;
  font-size: 11.5px;
  font-weight: 500;
  color: var(--app-text-secondary);
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);
  border-radius: 999px;
  &--price {
    color: var(--app-brand);
    font-weight: 700;
    background: var(--app-brand-soft);
    border-color: rgba(99, 102, 241, 0.2);
  }
}

// 依据面板
.reason-panel {
  padding: 20px 24px;
}
.reason-stack {
  display: grid;
  gap: 9px;
  margin-top: 10px;
}
.reason-chip {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 11px 14px;
  border-radius: 12px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);
  &__idx {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: none;
    width: 21px;
    height: 21px;
    margin-top: 1px;
    font-size: 11px;
    font-weight: 700;
    color: #fff;
    border-radius: 50%;
    background: var(--app-gradient);
  }
  &__rule {
    font-size: 11.5px;
    font-weight: 700;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: var(--app-brand);
  }
  &__detail {
    margin-top: 3px;
    font-size: 12.5px;
    line-height: 1.7;
    color: var(--app-text-regular);
  }
}
.reason-empty {
  margin-top: 10px;
  padding: 14px;
  font-size: 12.5px;
  color: var(--app-text-placeholder);
  text-align: center;
  border: 1px dashed var(--app-card-border-strong);
  border-radius: 12px;
}

// 底部操作
.case-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  padding: 15px 24px;
  border-top: 1px solid var(--app-divider);
  background: var(--el-fill-color-extra-light);
}
.footer-hint {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: var(--app-text-secondary);
  svg {
    color: var(--app-warning);
  }
  &--danger svg {
    color: var(--app-danger);
  }
}
.footer-actions {
  display: flex;
  gap: 10px;
}
.unfreeze-btn {
  font-weight: 600;
  color: #b45309;
  border-color: rgba(245, 158, 11, 0.45);
  &:hover,
  &:focus {
    color: #b45309 !important;
    border-color: #f59e0b !important;
    background: var(--app-warning-soft) !important;
  }
}

// ---------- 骨架 / 状态卡 ----------
.skeleton-case {
  padding: 22px 24px;
  border-radius: 20px;
  &__badge {
    width: 180px;
    height: 44px;
    border-radius: 13px;
  }
  &__title {
    width: 46%;
    height: 16px;
    margin-top: 18px;
  }
  &__line {
    width: 80%;
    height: 12px;
    margin-top: 12px;
    &--short {
      width: 30%;
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

// ---------- 依据对话框 ----------
.basis-dialog {
  &__banner {
    display: flex;
    gap: 10px;
    padding: 12px 14px;
    border-radius: 12px;
    margin-bottom: 14px;
    svg {
      flex: none;
      margin-top: 2px;
    }
    p {
      font-size: 12.5px;
      line-height: 1.7;
    }
    &--warning {
      color: #92400e;
      background: var(--app-warning-soft);
      border: 1px solid rgba(245, 158, 11, 0.3);
    }
    &--danger {
      color: #b91c1c;
      background: var(--app-danger-soft);
      border: 1px solid rgba(239, 68, 68, 0.3);
    }
  }
  &__item {
    display: flex;
    justify-content: space-between;
    gap: 14px;
    padding: 10px 14px;
    margin-bottom: 16px;
    font-size: 12.5px;
    border-radius: 10px;
    background: var(--el-fill-color-light);
    span {
      color: var(--app-text-secondary);
      flex: none;
    }
    b {
      font-weight: 600;
      text-align: right;
      color: var(--app-text-primary);
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
@media (max-width: 860px) {
  .case-card__content {
    grid-template-columns: 1fr;
  }
  .item-panel {
    border-right: none;
    border-bottom: 1px solid var(--app-divider);
  }
  .case-meta {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
