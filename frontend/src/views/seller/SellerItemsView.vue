<script setup lang="ts">
/**
 * 卖家·我的商品：状态徽标 / 建议价 / 审核依据可展开 /
 * 在售下架 / 被驳回修改重提（限 1 次）/ 冻结警示
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMyItems, offShelfItem, resubmitItem } from '@/api/items'
import type { ItemOut } from '@/api/types'
import PackagePlusIcon from '~icons/lucide/package-plus'
import PackageIcon from '~icons/lucide/package'
import ChevronDownIcon from '~icons/lucide/chevron-down'
import ArrowDownIcon from '~icons/lucide/arrow-down-to-line'
import PencilIcon from '~icons/lucide/file-pen-line'
import BanIcon from '~icons/lucide/ban'
import TriangleAlertIcon from '~icons/lucide/triangle-alert'
import CircleCheckIcon from '~icons/lucide/circle-check-big'
import HourglassIcon from '~icons/lucide/hourglass'
import SnowflakeIcon from '~icons/lucide/snowflake'
import PackageXIcon from '~icons/lucide/package-x'
import PackageCheckIcon from '~icons/lucide/package-check'
import RefreshCwIcon from '~icons/lucide/refresh-cw'
import ImageOffIcon from '~icons/lucide/image-off'
import TagIcon from '~icons/lucide/tag'
import BanknoteIcon from '~icons/lucide/banknote'
import LayersIcon from '~icons/lucide/layers'
import ScrollTextIcon from '~icons/lucide/scroll-text'
import XIcon from '~icons/lucide/x'

type Tone = 'success' | 'warning' | 'danger' | 'info'

const router = useRouter()

const loading = ref(false)
const loadError = ref(false)
const items = ref<ItemOut[]>([])
const busyId = ref<number | null>(null)
const expanded = reactive(new Set<number>())

// ---------- 修改重提对话框 ----------
const dialogVisible = ref(false)
const editLoading = ref(false)
const editing = ref<ItemOut | null>(null)
const editResult = ref<ItemOut | null>(null)
const editForm = reactive({ description: '', price: '' as string | number })

const STATUS_META: Record<string, { tone: Tone; icon: typeof PackageIcon }> = {
  on_sale: { tone: 'success', icon: CircleCheckIcon },
  pending: { tone: 'info', icon: HourglassIcon },
  manual: { tone: 'warning', icon: HourglassIcon },
  draft: { tone: 'warning', icon: PencilIcon },
  rejected: { tone: 'danger', icon: TriangleAlertIcon },
  frozen: { tone: 'danger', icon: BanIcon },
  off_shelf: { tone: 'info', icon: ArrowDownIcon },
  locked: { tone: 'warning', icon: PackageCheckIcon },
  dealed: { tone: 'success', icon: PackageCheckIcon },
}

function metaOf(status: string): { tone: Tone; icon: typeof PackageIcon } {
  return STATUS_META[status] ?? { tone: 'info', icon: PackageIcon }
}

interface ReasonRow {
  rule: string
  detail: string
}

function normalizeReasons(item: ItemOut): ReasonRow[] {
  return (item.audit_reason ?? [])
    .map((r) => {
      if (typeof r === 'string') return { rule: '审核依据', detail: r }
      return { rule: r.rule || '审核依据', detail: r.detail || r.rule || '' }
    })
    .filter((r) => r.detail)
}

async function loadItems(): Promise<void> {
  loading.value = true
  loadError.value = false
  try {
    items.value = await getMyItems()
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function toggleReason(id: number): void {
  if (expanded.has(id)) expanded.delete(id)
  else expanded.add(id)
}

// ---------- 下架 ----------
async function onOffShelf(item: ItemOut): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `下架后「${item.title}」将不再出现在市场中，确定下架吗？`,
      '确认下架商品',
      {
        confirmButtonText: '确认下架',
        cancelButtonText: '再想想',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch {
    return
  }
  busyId.value = item.id
  try {
    const updated = await offShelfItem(item.id)
    const idx = items.value.findIndex((it) => it.id === updated.id)
    if (idx >= 0) items.value[idx] = updated
    ElMessage.success('商品已下架')
  } catch {
    /* 全局提示 */
  } finally {
    busyId.value = null
  }
}

// ---------- 修改重提 ----------
function openEdit(item: ItemOut): void {
  editing.value = item
  editResult.value = null
  editForm.description = item.description
  editForm.price = item.price != null ? String(item.price) : ''
  dialogVisible.value = true
}

const editNumericPrice = computed<number | null>(() => {
  if (editForm.price === '' || editForm.price === null) return null
  const n = Number(editForm.price)
  return Number.isFinite(n) && n >= 0 ? n : null
})

async function submitResubmit(): Promise<void> {
  if (!editing.value || editLoading.value) return
  if (editForm.description.trim().length < 5) {
    ElMessage.warning('商品描述至少 5 个字')
    return
  }
  if (editForm.price !== '' && editNumericPrice.value === null) {
    ElMessage.warning('价格需要是不小于 0 的数字')
    return
  }
  editLoading.value = true
  try {
    const updated = await resubmitItem(editing.value.id, {
      description: editForm.description.trim(),
      price: editNumericPrice.value,
    })
    editResult.value = updated
    const idx = items.value.findIndex((it) => it.id === updated.id)
    if (idx >= 0) items.value[idx] = updated
    if (updated.status === 'on_sale') {
      ElMessage.success('重提审核通过，商品已重新上架')
    } else if (updated.status === 'manual') {
      ElMessage.warning('重提后仍存疑，已再次转人工复核')
    } else if (updated.status === 'frozen') {
      ElMessage.error('重提触发安全否决，商品已冻结')
    } else if (updated.status === 'rejected') {
      ElMessage.error('重提后仍被驳回，已无再次修改机会')
    } else {
      ElMessage.success('商品已重新提交审核')
    }
  } catch {
    /* 全局提示 */
  } finally {
    editLoading.value = false
  }
}

function closeEdit(): void {
  dialogVisible.value = false
  editing.value = null
  editResult.value = null
}

const editToneClass = computed<string>(() => {
  const s = editResult.value?.status
  if (s === 'on_sale') return 'edit-result--success'
  if (s === 'frozen' || s === 'rejected') return 'edit-result--danger'
  if (s === 'manual' || s === 'draft') return 'edit-result--warning'
  return 'edit-result--info'
})

const stats = computed(() => {
  let onSale = 0
  let pending = 0
  let abnormal = 0
  for (const it of items.value) {
    if (it.status === 'on_sale') onSale += 1
    else if (it.status === 'pending' || it.status === 'manual' || it.status === 'draft') pending += 1
    else if (it.status === 'rejected' || it.status === 'frozen') abnormal += 1
  }
  return { total: items.value.length, onSale, pending, abnormal }
})

onMounted(loadItems)
</script>

<template>
  <div class="page-container seller-items-page">
    <!-- 页头 -->
    <header class="list-head anim-fade-in-up">
      <div class="list-head__main">
        <h1>
          <PackageIcon :width="21" :height="21" :stroke-width="2.2" />
          我的商品
        </h1>
        <p>结构化档案、建议价区间与逐条审核依据全量可查，审核状态以后端实时返回为准。</p>
      </div>
      <div class="list-head__actions">
        <button class="head-btn head-btn--ghost" :disabled="loading" @click="loadItems">
          <RefreshCwIcon :width="15" :height="15" :stroke-width="2.2" :class="{ 'anim-spin': loading }" />
          刷新
        </button>
        <button class="head-btn btn-gradient" @click="router.push('/seller/publish')">
          <PackagePlusIcon :width="16" :height="16" :stroke-width="2.3" />
          发布新商品
        </button>
      </div>
    </header>

    <!-- 统计条 -->
    <section v-if="!loading && !loadError && items.length" class="stat-strip anim-fade-in-up">
      <div class="stat-chip">
        <LayersIcon :width="15" :height="15" :stroke-width="2.2" />
        全部 <b>{{ stats.total }}</b>
      </div>
      <div class="stat-chip stat-chip--success">
        <CircleCheckIcon :width="15" :height="15" :stroke-width="2.2" />
        在售 <b>{{ stats.onSale }}</b>
      </div>
      <div class="stat-chip stat-chip--warning">
        <HourglassIcon :width="15" :height="15" :stroke-width="2.2" />
        审核中 <b>{{ stats.pending }}</b>
      </div>
      <div class="stat-chip stat-chip--danger">
        <TriangleAlertIcon :width="15" :height="15" :stroke-width="2.2" />
        异常 <b>{{ stats.abnormal }}</b>
      </div>
    </section>

    <!-- 骨架屏 -->
    <section v-if="loading" class="item-grid">
      <div v-for="n in 6" :key="n" class="skeleton-card glass-card">
        <div class="skeleton skeleton-card__cover" />
        <div class="skeleton skeleton-card__line skeleton-card__line--title" />
        <div class="skeleton skeleton-card__line" />
        <div class="skeleton skeleton-card__line skeleton-card__line--short" />
      </div>
    </section>

    <!-- 失败态 -->
    <section v-else-if="loadError" class="state-card glass-card">
      <span class="state-card__icon state-card__icon--danger">
        <PackageXIcon :width="30" :height="30" :stroke-width="1.9" />
      </span>
      <h3>商品加载失败</h3>
      <p>无法连接服务或会话已过期，请检查网络后重试。</p>
      <el-button type="primary" @click="loadItems">
        <RefreshCwIcon :width="15" :height="15" :stroke-width="2.2" style="margin-right: 5px" />
        重新加载
      </el-button>
    </section>

    <!-- 空状态 -->
    <section v-else-if="!items.length" class="state-card glass-card">
      <span class="state-card__icon">
        <PackagePlusIcon :width="30" :height="30" :stroke-width="1.9" />
      </span>
      <h3>还没有发布过商品</h3>
      <p>用一句自然语言描述你的闲置，AI 会自动建档、定价建议并完成违禁审核。</p>
      <el-button type="primary" size="large" @click="router.push('/seller/publish')">
        <PackagePlusIcon :width="16" :height="16" :stroke-width="2.3" style="margin-right: 6px" />
        立即发布第一件商品
      </el-button>
    </section>

    <!-- 商品卡片网格 -->
    <section v-else class="item-grid stagger">
      <article
        v-for="item in items"
        :key="item.id"
        class="item-card glass-card"
        :class="`item-card--${metaOf(item.status).tone}`"
      >
        <!-- 封面 -->
        <div class="item-card__cover">
          <img v-if="item.image_url" :src="item.image_url" :alt="item.title" referrerpolicy="no-referrer"
            @error="(e) => ((e.target as HTMLImageElement).style.display = 'none')" />
          <span v-else class="item-card__cover-placeholder">
            <ImageOffIcon :width="22" :height="22" :stroke-width="1.8" />
          </span>
          <span class="item-card__badge" :class="`item-card__badge--${metaOf(item.status).tone}`">
            <component :is="metaOf(item.status).icon" :width="12" :height="12" :stroke-width="2.4" />
            {{ item.status_text }}
          </span>
          <span v-if="item.status === 'frozen'" class="item-card__stamp">
            <SnowflakeIcon :width="13" :height="13" :stroke-width="2.3" />
            安全冻结
          </span>
        </div>

        <div class="item-card__body">
          <h3 class="item-card__title" :title="item.title">{{ item.title }}</h3>
          <div class="item-card__meta">
            <span class="meta-tag">{{ item.category || '其他' }}</span>
            <span class="meta-sp">·</span>
            <span class="meta-tag">{{ item.condition_level || '成色未知' }}</span>
          </div>

          <div class="item-card__prices">
            <div class="price-block">
              <span class="price-block__label">
                <BanknoteIcon :width="12" :height="12" :stroke-width="2.2" />
                我的定价
              </span>
              <strong class="price-block__value">¥{{ item.price }}</strong>
            </div>
            <div v-if="item.price_suggest_min != null && item.price_suggest_max != null" class="price-block price-block--suggest">
              <span class="price-block__label">
                <TagIcon :width="12" :height="12" :stroke-width="2.2" />
                AI 建议价
              </span>
              <strong class="price-block__value price-block__value--suggest">
                ¥{{ item.price_suggest_min }}–{{ item.price_suggest_max }}
              </strong>
            </div>
          </div>

          <!-- 冻结警示条 -->
          <div v-if="item.status === 'frozen'" class="inline-alert inline-alert--danger">
            <BanIcon :width="14" :height="14" :stroke-width="2.3" />
            <span>安全否决已冻结，不可操作，等待管理员安全复核</span>
          </div>
          <div v-else-if="item.status === 'manual'" class="inline-alert inline-alert--warning">
            <HourglassIcon :width="14" :height="14" :stroke-width="2.3" />
            <span>存疑转人工复核中，结果将自动写回</span>
          </div>
          <div v-else-if="item.status === 'rejected' && item.reject_count > 1" class="inline-alert inline-alert--danger">
            <TriangleAlertIcon :width="14" :height="14" :stroke-width="2.3" />
            <span>已使用唯一一次重提机会，无法再次提交</span>
          </div>

          <!-- 审核依据 -->
          <div v-if="normalizeReasons(item).length || item.reason_text" class="audit-box">
            <button type="button" class="audit-box__toggle" @click="toggleReason(item.id)">
              <ScrollTextIcon :width="13" :height="13" :stroke-width="2.2" />
              审核依据（{{ normalizeReasons(item).length || 1 }}）
              <ChevronDownIcon
                :width="14"
                :height="14"
                :stroke-width="2.3"
                class="audit-box__caret"
                :class="{ 'audit-box__caret--open': expanded.has(item.id) }"
              />
            </button>
            <transition name="collapse">
              <div v-show="expanded.has(item.id)" class="audit-box__panel">
                <p v-if="item.reason_text" class="audit-box__summary">{{ item.reason_text }}</p>
                <div v-for="(r, i) in normalizeReasons(item)" :key="i" class="audit-reason">
                  <span class="audit-reason__rule">{{ r.rule }}</span>
                  <span class="audit-reason__detail">{{ r.detail }}</span>
                </div>
                <p v-if="!normalizeReasons(item).length && !item.reason_text" class="audit-box__empty">
                  暂无审核依据
                </p>
              </div>
            </transition>
          </div>
        </div>

        <!-- 操作区 -->
        <footer class="item-card__footer">
          <template v-if="item.status === 'on_sale'">
            <el-button
              plain
              class="footer-btn"
              :loading="busyId === item.id"
              @click="onOffShelf(item)"
            >
              <ArrowDownIcon v-if="busyId !== item.id" :width="14" :height="14" :stroke-width="2.2" style="margin-right: 4px" />
              下架
            </el-button>
          </template>
          <template v-else-if="item.status === 'rejected' && item.reject_count <= 1">
            <el-button type="primary" plain class="footer-btn" @click="openEdit(item)">
              <PencilIcon :width="14" :height="14" :stroke-width="2.2" style="margin-right: 4px" />
              修改重提
            </el-button>
          </template>
          <template v-else-if="item.status === 'frozen'">
            <span class="footer-locked">
              <SnowflakeIcon :width="13" :height="13" :stroke-width="2.2" />
              冻结中 · 不可操作
            </span>
          </template>
          <template v-else-if="item.status === 'off_shelf'">
            <span class="footer-locked footer-locked--muted">商品已下架</span>
          </template>
          <template v-else-if="item.status === 'dealed' || item.status === 'locked'">
            <span class="footer-locked footer-locked--muted">{{ item.status_text }}</span>
          </template>
          <template v-else>
            <span class="footer-locked footer-locked--muted">
              <HourglassIcon :width="13" :height="13" :stroke-width="2.2" />
              审核流程处理中
            </span>
          </template>
        </footer>
      </article>
    </section>

    <!-- 修改重提对话框 -->
    <el-dialog
      v-model="dialogVisible"
      width="560px"
      :show-close="false"
      :close-on-click-modal="false"
      align-center
      class="resubmit-dialog"
    >
      <template #header>
        <div class="dialog-head">
          <span class="dialog-head__icon">
            <PencilIcon :width="18" :height="18" :stroke-width="2.1" />
          </span>
          <div>
            <h3>修改后重新送审</h3>
            <p>每个被驳回商品仅有 1 次重提机会，请按驳回依据补充信息</p>
          </div>
          <button type="button" class="dialog-head__close" @click="closeEdit">
            <XIcon :width="17" :height="17" :stroke-width="2.2" />
          </button>
        </div>
      </template>

      <!-- 重提结果回显 -->
      <transition name="pop">
        <div v-if="editResult" class="edit-result" :class="editToneClass">
          <component
            :is="editResult.status === 'on_sale' ? CircleCheckIcon : editResult.status === 'frozen' || editResult.status === 'rejected' ? TriangleAlertIcon : HourglassIcon"
            :width="18"
            :height="18"
            :stroke-width="2.2"
          />
          <div>
            <strong>重提结果：{{ editResult.status_text }}</strong>
            <p v-if="editResult.reason_text">{{ editResult.reason_text }}</p>
            <p v-else>最新审核状态已写回「我的商品」列表。</p>
          </div>
        </div>
      </transition>

      <template v-if="editing && !editResult">
        <div v-if="editing.reason_text" class="edit-reject-basis">
          <TriangleAlertIcon :width="14" :height="14" :stroke-width="2.3" />
          <div>
            <span>上次驳回依据</span>
            <p>{{ editing.reason_text }}</p>
          </div>
        </div>

        <el-form label-position="top" class="edit-form">
          <el-form-item label="商品描述（必填）">
            <el-input
              v-model="editForm.description"
              type="textarea"
              :autosize="{ minRows: 5, maxRows: 10 }"
              maxlength="500"
              show-word-limit
              resize="none"
              placeholder="补充品牌、型号、成色、购入时间与使用情况…"
            />
          </el-form-item>
          <el-form-item label="调整价格（可选，元）">
            <el-input v-model="editForm.price" type="number" min="0" placeholder="不填则保持原价" clearable>
              <template #append>元</template>
            </el-input>
          </el-form-item>
        </el-form>
      </template>

      <template #footer>
        <el-button v-if="editResult" type="primary" @click="closeEdit">完成</el-button>
        <template v-else>
          <el-button @click="closeEdit">取消</el-button>
          <el-button type="primary" :loading="editLoading" @click="submitResubmit">
            {{ editLoading ? '重新审核中…' : '确认修改并重新提交' }}
          </el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.seller-items-page {
  max-width: 1200px;
  padding-top: 26px;
}

// ---------- 页头 ----------
.list-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;

  &__main h1 {
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
  &__main p {
    margin-top: 8px;
    font-size: 13.5px;
    color: var(--app-text-secondary);
  }
  &__actions {
    display: flex;
    gap: 10px;
  }
}

.head-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 40px;
  padding: 0 18px;
  font-size: 13.5px;
  font-weight: 600;
  border-radius: 11px;
  &--ghost {
    color: var(--app-text-secondary);
    background: var(--app-card-bg);
    border: 1px solid var(--app-card-border-strong);
    backdrop-filter: blur(12px);
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
}

// ---------- 统计条 ----------
.stat-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}
.stat-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 15px;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--app-text-secondary);
  background: var(--app-card-bg);
  border: 1px solid var(--app-card-border);
  border-radius: 999px;
  backdrop-filter: blur(12px);
  b {
    font-size: 14px;
    font-weight: 700;
    color: var(--app-text-primary);
    font-variant-numeric: tabular-nums;
  }
  &--success {
    color: var(--app-success);
    b {
      color: var(--app-success);
    }
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

// ---------- 卡片网格 ----------
.item-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: 18px;
  margin-top: 18px;
}

.item-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 18px;

  &:hover {
    transform: translateY(-4px);
    box-shadow: var(--app-shadow-card-hover);
  }
  &--danger {
    border-color: rgba(239, 68, 68, 0.22);
  }
  &--warning {
    border-color: rgba(245, 158, 11, 0.24);
  }

  &__cover {
    position: relative;
    height: 168px;
    background:
      linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(34, 211, 238, 0.08)),
      var(--el-fill-color-light);
    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
  }
  &__cover-placeholder {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--app-text-placeholder);
  }

  &__badge {
    position: absolute;
    top: 12px;
    left: 12px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 11px;
    font-size: 11.5px;
    font-weight: 700;
    color: #fff;
    border-radius: 999px;
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.14);
    backdrop-filter: blur(4px);
    &--success {
      background: linear-gradient(135deg, #059669, #34d399);
    }
    &--warning {
      background: linear-gradient(135deg, #d97706, #fbbf24);
    }
    &--danger {
      background: linear-gradient(135deg, #dc2626, #fb7185);
    }
    &--info {
      background: linear-gradient(135deg, #4f46e5, #22d3ee);
    }
  }

  &__stamp {
    position: absolute;
    right: 12px;
    bottom: 12px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 11px;
    font-size: 11.5px;
    font-weight: 700;
    letter-spacing: 1px;
    color: #fff;
    background: rgba(220, 38, 38, 0.82);
    border: 1px solid rgba(255, 255, 255, 0.35);
    border-radius: 8px;
    backdrop-filter: blur(4px);
  }

  &__body {
    flex: 1;
    padding: 16px 18px 8px;
  }

  &__title {
    font-size: 15px;
    font-weight: 700;
    line-height: 1.5;
    color: var(--app-text-primary);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 44px;
  }

  &__meta {
    display: flex;
    align-items: center;
    gap: 7px;
    margin-top: 8px;
  }
  .meta-tag {
    padding: 2px 9px;
    font-size: 11px;
    font-weight: 500;
    color: var(--app-text-secondary);
    background: var(--el-fill-color-light);
    border-radius: 999px;
  }
  .meta-sp {
    color: var(--app-text-placeholder);
    font-size: 11px;
  }

  &__prices {
    display: flex;
    align-items: stretch;
    gap: 10px;
    margin-top: 14px;
  }

  &__footer {
    display: flex;
    align-items: center;
    padding: 12px 18px 16px;
  }
}

.price-block {
  flex: 1;
  padding: 9px 12px;
  border-radius: 11px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);
  &--suggest {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.06), rgba(34, 211, 238, 0.06));
    border-color: rgba(99, 102, 241, 0.18);
  }
  &__label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--app-text-placeholder);
  }
  &__value {
    display: block;
    margin-top: 3px;
    font-size: 17px;
    font-weight: 800;
    color: var(--app-text-primary);
    font-variant-numeric: tabular-nums;
    &--suggest {
      font-size: 14.5px;
      background: var(--app-gradient);
      -webkit-background-clip: text;
      background-clip: text;
      -webkit-text-fill-color: transparent;
    }
  }
}

// 内联警示
.inline-alert {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 12px;
  padding: 9px 12px;
  font-size: 12px;
  line-height: 1.6;
  border-radius: 10px;
  svg {
    flex: none;
    margin-top: 2px;
  }
  &--danger {
    color: #b91c1c;
    background: var(--app-danger-soft);
    border: 1px solid rgba(239, 68, 68, 0.25);
  }
  &--warning {
    color: #92400e;
    background: var(--app-warning-soft);
    border: 1px solid rgba(245, 158, 11, 0.3);
  }
}

// 审核依据折叠
.audit-box {
  margin-top: 12px;
  border-radius: 11px;
  border: 1px solid var(--app-card-border);
  background: var(--el-fill-color-extra-light);
  overflow: hidden;

  &__toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 9px 12px;
    font-size: 12px;
    font-weight: 600;
    color: var(--app-text-secondary);
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
  &__panel {
    padding: 4px 12px 12px;
  }
  &__summary {
    padding: 8px 10px;
    margin-bottom: 8px;
    font-size: 12px;
    line-height: 1.7;
    color: var(--app-text-regular);
    background: var(--el-fill-color-light);
    border-radius: 8px;
  }
  &__empty {
    font-size: 12px;
    color: var(--app-text-placeholder);
    padding: 4px 0;
  }
}

.audit-reason {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 7px 0;
  border-top: 1px dashed var(--app-card-border);
  &:first-child {
    border-top: none;
  }
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
    font-size: 12px;
    line-height: 1.7;
    color: var(--app-text-regular);
  }
}

.footer-btn {
  width: 100%;
  border-radius: 10px;
  font-weight: 600;
}
.footer-locked {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  justify-content: center;
  padding: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--app-danger);
  border-radius: 10px;
  background: var(--app-danger-soft);
  &--muted {
    color: var(--app-text-placeholder);
    background: var(--el-fill-color-light);
    font-weight: 500;
  }
}

// ---------- 骨架 / 状态卡 ----------
.skeleton-card {
  padding: 0 0 18px;
  overflow: hidden;
  border-radius: 18px;
  &__cover {
    height: 168px;
    border-radius: 0;
  }
  &__line {
    height: 14px;
    margin: 14px 18px 0;
    &--title {
      height: 18px;
      width: 62%;
    }
    &--short {
      width: 42%;
    }
  }
}

.state-card {
  margin-top: 26px;
  padding: 56px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  border-radius: 20px;

  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 76px;
    height: 76px;
    color: #fff;
    border-radius: 22px;
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
    max-width: 380px;
    font-size: 13px;
    line-height: 1.7;
    color: var(--app-text-secondary);
  }
}

// ---------- 重提对话框 ----------
.dialog-head {
  display: flex;
  align-items: center;
  gap: 13px;
  position: relative;
  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: none;
    width: 42px;
    height: 42px;
    color: #fff;
    border-radius: 12px;
    background: var(--app-gradient);
    box-shadow: 0 6px 16px rgba(99, 102, 241, 0.3);
  }
  h3 {
    font-size: 16px;
    font-weight: 700;
    color: var(--app-text-primary);
  }
  p {
    margin-top: 3px;
    font-size: 12px;
    color: var(--app-text-secondary);
  }
  &__close {
    position: absolute;
    right: -6px;
    top: -6px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border-radius: 9px;
    color: var(--app-text-placeholder);
    transition: all 0.2s ease;
    &:hover {
      color: var(--app-danger);
      background: var(--app-danger-soft);
    }
  }
}

.edit-reject-basis {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  margin-bottom: 16px;
  border-radius: 12px;
  background: var(--app-danger-soft);
  border: 1px solid rgba(239, 68, 68, 0.25);
  svg {
    flex: none;
    margin-top: 2px;
    color: var(--app-danger);
  }
  span {
    font-size: 12px;
    font-weight: 700;
    color: #b91c1c;
  }
  p {
    margin-top: 4px;
    font-size: 12.5px;
    line-height: 1.7;
    color: #991b1b;
  }
}

.edit-form :deep(.el-form-item__label) {
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text-primary);
}

.edit-result {
  display: flex;
  gap: 11px;
  padding: 14px 16px;
  border-radius: 12px;
  margin-bottom: 4px;
  svg {
    flex: none;
    margin-top: 2px;
  }
  strong {
    font-size: 13.5px;
    font-weight: 700;
  }
  p {
    margin-top: 4px;
    font-size: 12.5px;
    line-height: 1.7;
  }
  &--success {
    color: #047857;
    background: var(--app-success-soft);
    border: 1px solid rgba(16, 185, 129, 0.3);
  }
  &--danger {
    color: #b91c1c;
    background: var(--app-danger-soft);
    border: 1px solid rgba(239, 68, 68, 0.3);
  }
  &--warning {
    color: #92400e;
    background: var(--app-warning-soft);
    border: 1px solid rgba(245, 158, 11, 0.32);
  }
  &--info {
    color: #0369a1;
    background: var(--app-info-soft);
    border: 1px solid rgba(14, 165, 233, 0.3);
  }
}
</style>
