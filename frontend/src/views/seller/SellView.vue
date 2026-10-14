<script setup lang="ts">
/**
 * 卖家发布页：自然语言描述 → AI 结构化 + 违禁审核双引擎
 * 成功后按 status 渲染：在售成功卡（含建议价区间条）/ 转人工 / 冻结否决 / 驳回 / 待补充
 */
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { publishItem } from '@/api/items'
import type { ItemOut } from '@/api/types'
import SparklesIcon from '~icons/lucide/sparkles'
import ShieldCheckIcon from '~icons/lucide/shield-check'
import CpuIcon from '~icons/lucide/cpu'
import ListChecksIcon from '~icons/lucide/list-checks'
import CircleCheckIcon from '~icons/lucide/circle-check-big'
import TriangleAlertIcon from '~icons/lucide/triangle-alert'
import BanIcon from '~icons/lucide/ban'
import FileQuestionIcon from '~icons/lucide/file-question'
import HourglassIcon from '~icons/lucide/hourglass'
import TagIcon from '~icons/lucide/tag'
import BanknoteIcon from '~icons/lucide/banknote'
import ImageIcon from '~icons/lucide/image'
import SendIcon from '~icons/lucide/send-horizontal'
import RotateCcwIcon from '~icons/lucide/rotate-ccw'
import ArrowRightIcon from '~icons/lucide/arrow-right'
import PackageCheckIcon from '~icons/lucide/package-check'
import LightbulbIcon from '~icons/lucide/lightbulb'
import ScanSearchIcon from '~icons/lucide/scan-search'

const router = useRouter()

const EXAMPLES = [
  '九成新索尼头戴耳机，去年双十一购入，只用过几次，配件齐全，200元出',
  '高等数学同济第七版教材，上册，有少量笔记不影响使用，15元',
  '宿舍用小型桌面收纳架，白色三层，毕业带不走，30元校内自提',
]

const form = reactive({
  description: '',
  title: '',
  price: '' as string | number,
  image_url: '',
})

const submitting = ref(false)
const result = ref<ItemOut | null>(null)

const descLength = computed(() => form.description.trim().length)
const canSubmit = computed(() => descLength.value >= 5 && !submitting.value)
const numericPrice = computed<number | null>(() => {
  if (form.price === '' || form.price === null) return null
  const n = Number(form.price)
  return Number.isFinite(n) && n >= 0 ? n : null
})

function applyExample(text: string): void {
  form.description = text
}

function resetForm(): void {
  form.description = ''
  form.title = ''
  form.price = ''
  form.image_url = ''
  result.value = null
}

interface ReasonRow {
  rule: string
  detail: string
}

function normalizeReasons(item: ItemOut): ReasonRow[] {
  return (item.audit_reason ?? []).map((r) => {
    if (typeof r === 'string') return { rule: '审核依据', detail: r }
    return { rule: r.rule || '审核依据', detail: r.detail || r.rule || '' }
  }).filter((r) => r.detail)
}

const reasons = computed<ReasonRow[]>(() => (result.value ? normalizeReasons(result.value) : []))

// ---------- 结果状态判定 ----------
const tone = computed<'success' | 'warning' | 'danger' | 'info' | null>(() => {
  const item = result.value
  if (!item) return null
  switch (item.status) {
    case 'on_sale':
      return 'success'
    case 'manual':
    case 'draft':
      return 'warning'
    case 'frozen':
    case 'rejected':
      return 'danger'
    case 'pending':
      return 'info'
    default:
      return 'info'
  }
})

// ---------- 建议价区间条 ----------
interface RangeScale {
  zoneLeft: number
  zoneWidth: number
  priceLeft: number | null
  domainLow: number
  domainHigh: number
}

const rangeScale = computed<RangeScale | null>(() => {
  const item = result.value
  if (!item || item.price_suggest_min == null || item.price_suggest_max == null) return null
  const low = Number(item.price_suggest_min)
  const high = Number(item.price_suggest_max)
  if (!Number.isFinite(low) || !Number.isFinite(high) || high <= 0) return null
  const seller = Number(item.price) || 0
  const domainLow = Math.max(0, Math.min(low, seller) * 0.85)
  const domainHigh = Math.max(high, seller) * 1.12
  const span = domainHigh - domainLow || 1
  const pct = (v: number) => Math.min(100, Math.max(0, ((v - domainLow) / span) * 100))
  return {
    zoneLeft: pct(low),
    zoneWidth: Math.max(4, pct(high) - pct(low)),
    priceLeft: seller > 0 ? pct(seller) : null,
    domainLow,
    domainHigh,
  }
})

const inSuggestRange = computed(() => {
  const item = result.value
  if (!item || !rangeScale.value || item.price_suggest_min == null || item.price_suggest_max == null) {
    return null
  }
  const p = Number(item.price)
  return p >= Number(item.price_suggest_min) && p <= Number(item.price_suggest_max)
})

async function onSubmit(): Promise<void> {
  if (submitting.value) return
  if (descLength.value < 5) {
    ElMessage.warning('商品描述至少 5 个字，写写品牌、成色和使用情况吧')
    return
  }
  if (form.price !== '' && numericPrice.value === null) {
    ElMessage.warning('价格需要是不小于 0 的数字')
    return
  }

  submitting.value = true
  try {
    const data = await publishItem({
      description: form.description.trim(),
      title: form.title.trim() || undefined,
      price: numericPrice.value,
      image_url: form.image_url.trim() || null,
    })
    result.value = data
    if (data.status === 'on_sale') {
      ElMessage.success('审核通过，商品已上架在售')
    } else if (data.status === 'manual') {
      ElMessage.warning('商品存疑，已转入人工复核队列')
    } else if (data.status === 'frozen') {
      ElMessage.error('触发安全否决，商品已被冻结')
    } else if (data.status === 'draft') {
      ElMessage.warning('信息不足，补充描述后可重新提交')
    } else if (data.status === 'rejected') {
      ElMessage.error('商品未通过审核，可按驳回依据修改后重提')
    } else {
      ElMessage.success('商品已提交，等待审核')
    }
  } catch {
    // 全局拦截器已弹出错误提示
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page-container sell-page">
    <!-- 页头 -->
    <header class="page-head anim-fade-in-up">
      <div>
        <h1>
          <SparklesIcon :width="21" :height="21" :stroke-width="2.2" />
          发布闲置 · 一句话描述你的商品
        </h1>
        <p>用大白话描述即可，AI 自动完成结构化建档、成色识别、类目归类与建议定价，同时经过违禁审核双引擎校验。</p>
      </div>
    </header>

    <!-- 双引擎说明条 -->
    <section class="engine-bar glass-card anim-fade-in-up">
      <div class="engine-bar__lead">
        <span class="engine-bar__lead-icon">
          <CpuIcon :width="18" :height="18" :stroke-width="2.1" />
        </span>
        <div>
          <strong>AI 结构化 + 违禁审核 双引擎</strong>
          <span>引擎模式由后端按可用性自动切换，规则引擎永远兜底安全底线</span>
        </div>
      </div>
      <div class="engine-bar__badges">
        <span class="engine-chip engine-chip--llm">
          <SparklesIcon :width="13" :height="13" :stroke-width="2.3" />
          <b>LLM 大模型引擎</b>
          <em>语义理解 · 灵活判定</em>
        </span>
        <span class="engine-chip engine-chip--rule">
          <ShieldCheckIcon :width="13" :height="13" :stroke-width="2.3" />
          <b>RULE 规则引擎</b>
          <em>确定性底线 · 一票否决</em>
        </span>
      </div>
    </section>

    <div class="sell-grid">
      <!-- 左：发布表单 -->
      <section class="form-card glass-card anim-fade-in-up">
        <div class="form-card__block">
          <label class="field-label field-label--required">
            <ScanSearchIcon :width="15" :height="15" :stroke-width="2.2" />
            商品自然语言描述
          </label>
          <el-input
            v-model="form.description"
            type="textarea"
            :autosize="{ minRows: 6, maxRows: 12 }"
            maxlength="500"
            show-word-limit
            resize="none"
            placeholder="例如：九成新索尼头戴耳机，去年双十一购入，只用过几次，配件齐全，200元出"
            class="desc-input"
          />
          <div class="example-row">
            <span class="example-row__label">
              <LightbulbIcon :width="13" :height="13" :stroke-width="2.2" />
              没头绪？点一句试试：
            </span>
            <button
              v-for="(ex, i) in EXAMPLES"
              :key="i"
              type="button"
              class="example-chip"
              @click="applyExample(ex)"
            >
              {{ ex.length > 18 ? `${ex.slice(0, 18)}…` : ex }}
            </button>
          </div>
        </div>

        <div class="form-card__block">
          <label class="field-label">
            <TagIcon :width="15" :height="15" :stroke-width="2.2" />
            商品标题 <span class="field-label__optional">（可选，留空由 AI 提炼）</span>
          </label>
          <el-input
            v-model="form.title"
            maxlength="40"
            placeholder="例如：索尼 WH-1000XM4 头戴降噪耳机"
            clearable
          />
        </div>

        <div class="form-card__row">
          <div class="form-card__block">
            <label class="field-label">
              <BanknoteIcon :width="15" :height="15" :stroke-width="2.2" />
              心理价位 <span class="field-label__optional">（可选，元）</span>
            </label>
            <el-input
              v-model="form.price"
              type="number"
              min="0"
              placeholder="不填则采用建议价中位数"
              clearable
            >
              <template #append>元</template>
            </el-input>
          </div>
          <div class="form-card__block form-card__block--url">
            <label class="field-label">
              <ImageIcon :width="15" :height="15" :stroke-width="2.2" />
              图片 URL <span class="field-label__optional">（可选）</span>
            </label>
            <el-input v-model="form.image_url" placeholder="https://…" clearable />
          </div>
        </div>

        <div v-if="form.image_url.trim()" class="image-preview">
          <img :src="form.image_url.trim()" alt="商品图片预览" @error="(e) => ((e.target as HTMLImageElement).style.opacity = '0.25')" />
          <span>图片预览 · 加载失败时将展示占位图</span>
        </div>

        <div class="form-card__footer">
          <button type="button" class="submit-btn btn-gradient" :disabled="!canSubmit" @click="onSubmit">
            <template v-if="submitting">
              <span class="submit-btn__spinner" />
              AI 正在结构化与审核…
            </template>
            <template v-else>
              <SendIcon :width="17" :height="17" :stroke-width="2.3" />
              提交并智能审核
            </template>
          </button>
          <button type="button" class="reset-btn" @click="resetForm">
            <RotateCcwIcon :width="14" :height="14" :stroke-width="2.2" />
            清空重写
          </button>
        </div>
      </section>

      <!-- 右：结果卡 / 引导 -->
      <aside class="result-col">
        <!-- 未提交：引导 -->
        <div v-if="!result" class="guide-card glass-card anim-fade-in-up">
          <span class="guide-card__icon">
            <PackageCheckIcon :width="26" :height="26" :stroke-width="1.9" />
          </span>
          <h3>提交后你将看到</h3>
          <ul>
            <li>
              <CircleCheckIcon :width="15" :height="15" :stroke-width="2.2" />
              AI 提炼的标题、类目与成色
            </li>
            <li>
              <CircleCheckIcon :width="15" :height="15" :stroke-width="2.2" />
              基于同类在售商品的建议价区间
            </li>
            <li>
              <CircleCheckIcon :width="15" :height="15" :stroke-width="2.2" />
              逐条可解释的审核依据
            </li>
            <li>
              <ShieldCheckIcon :width="15" :height="15" :stroke-width="2.2" />
              存疑转人工、违禁即冻结的即时结论
            </li>
          </ul>
          <p class="guide-card__tip">描述越具体（品牌 / 型号 / 成色 / 购入时间），结构化与建议价越准。</p>
        </div>

        <!-- 在售成功卡 -->
        <article
          v-else-if="tone === 'success'"
          class="result-card result-card--success glass-card anim-scale-in"
        >
          <header class="result-card__head">
            <span class="result-card__icon result-card__icon--success">
              <CircleCheckIcon :width="24" :height="24" :stroke-width="2.2" />
            </span>
            <div>
              <h3>审核通过 · 商品已上架</h3>
              <p>双引擎校验无风险，已进入二手市场公开在售</p>
            </div>
          </header>

          <div class="struct-grid">
            <div class="struct-item struct-item--wide">
              <span class="struct-item__label">商品标题</span>
              <strong class="struct-item__value">{{ result.title }}</strong>
            </div>
            <div class="struct-item">
              <span class="struct-item__label">类目</span>
              <strong class="struct-item__value">{{ result.category || '其他' }}</strong>
            </div>
            <div class="struct-item">
              <span class="struct-item__label">成色</span>
              <strong class="struct-item__value">{{ result.condition_level || '其他' }}</strong>
            </div>
            <div class="struct-item">
              <span class="struct-item__label">卖家定价</span>
              <strong class="struct-item__value struct-item__value--price">¥{{ result.price }}</strong>
            </div>
          </div>

          <!-- 建议价区间条 -->
          <div v-if="rangeScale" class="range-box">
            <div class="range-box__head">
              <span class="range-box__title">
                <ListChecksIcon :width="14" :height="14" :stroke-width="2.2" />
                AI 建议价区间
              </span>
              <span class="range-box__numbers">
                ¥{{ result.price_suggest_min }} <i>—</i> ¥{{ result.price_suggest_max }}
                <em v-if="inSuggestRange === true" class="range-box__tag range-box__tag--in">定价合理</em>
                <em v-else-if="inSuggestRange === false" class="range-box__tag range-box__tag--out">偏离建议</em>
              </span>
            </div>
            <div class="range-bar">
              <span class="range-bar__zone" :style="{ left: `${rangeScale.zoneLeft}%`, width: `${rangeScale.zoneWidth}%` }" />
              <span
                v-if="rangeScale.priceLeft !== null"
                class="range-bar__marker"
                :style="{ left: `${rangeScale.priceLeft}%` }"
              >
                <span class="range-bar__pin" />
                <span class="range-bar__cap">我的定价 ¥{{ result.price }}</span>
              </span>
            </div>
            <div class="range-bar__ends">
              <span>¥{{ Math.round(rangeScale.domainLow) }}</span>
              <span>¥{{ Math.round(rangeScale.domainHigh) }}</span>
            </div>
          </div>

          <div v-if="reasons.length" class="reason-list">
            <span class="reason-list__title">审核记录</span>
            <div v-for="(r, i) in reasons" :key="i" class="reason-row">
              <span class="reason-row__rule">{{ r.rule }}</span>
              <span class="reason-row__detail">{{ r.detail }}</span>
            </div>
          </div>

          <div class="result-card__actions">
            <el-button type="primary" @click="router.push('/seller/items')">
              查看我的商品
              <ArrowRightIcon :width="14" :height="14" :stroke-width="2.3" style="margin-left: 4px" />
            </el-button>
            <el-button @click="resetForm">继续发布</el-button>
          </div>
        </article>

        <!-- 转人工复核 -->
        <article
          v-else-if="result.status === 'manual'"
          class="result-card result-card--warning glass-card anim-scale-in"
        >
          <header class="result-card__head">
            <span class="result-card__icon result-card__icon--warning">
              <HourglassIcon :width="23" :height="23" :stroke-width="2.1" />
            </span>
            <div>
              <h3>存疑商品 · 已转人工复核</h3>
              <p>{{ result.pending_human?.summary || '引擎对审核结论把握不足，已提交管理员人工复核，请耐心等待' }}</p>
            </div>
          </header>
          <div class="result-lines">
            <div class="result-lines__row"><span>商品标题</span><b>{{ result.title }}</b></div>
            <div class="result-lines__row"><span>类目 / 成色</span><b>{{ result.category || '其他' }} · {{ result.condition_level || '其他' }}</b></div>
            <div class="result-lines__row"><span>当前定价</span><b>¥{{ result.price }}</b></div>
          </div>
          <div v-if="reasons.length" class="reason-list">
            <span class="reason-list__title">存疑依据（管理员将重点复核）</span>
            <div v-for="(r, i) in reasons" :key="i" class="reason-row">
              <span class="reason-row__rule">{{ r.rule }}</span>
              <span class="reason-row__detail">{{ r.detail }}</span>
            </div>
          </div>
          <div class="result-card__actions">
            <el-button type="warning" plain @click="router.push('/seller/items')">去我的商品查看进度</el-button>
            <el-button @click="resetForm">再发一件</el-button>
          </div>
        </article>

        <!-- 安全否决冻结 -->
        <article
          v-else-if="result.status === 'frozen'"
          class="result-card result-card--danger glass-card anim-scale-in"
        >
          <header class="result-card__head">
            <span class="result-card__icon result-card__icon--danger">
              <BanIcon :width="23" :height="23" :stroke-width="2.1" />
            </span>
            <div>
              <h3>安全一票否决 · 商品已冻结</h3>
              <p>规则引擎命中禁止交易项，商品不允许上架，证据已直送管理员安全复核台</p>
            </div>
          </header>
          <div class="veto-basis">
            <TriangleAlertIcon :width="15" :height="15" :stroke-width="2.3" />
            <div>
              <strong>否决依据</strong>
              <p v-if="result.reason_text">{{ result.reason_text }}</p>
              <p v-else-if="reasons.length">{{ reasons.map((r) => r.detail).join('；') }}</p>
              <p v-else>该商品命中平台安全规则，已被冻结。</p>
            </div>
          </div>
          <ul v-if="reasons.length" class="veto-rules">
            <li v-for="(r, i) in reasons" :key="i">
              <span class="reason-row__rule reason-row__rule--danger">{{ r.rule }}</span>
              <span class="reason-row__detail">{{ r.detail }}</span>
            </li>
          </ul>
          <div class="result-card__actions">
            <el-button type="danger" plain @click="router.push('/seller/items')">去我的商品查看</el-button>
            <el-button @click="resetForm">重新发布</el-button>
          </div>
        </article>

        <!-- 审核驳回 -->
        <article
          v-else-if="result.status === 'rejected'"
          class="result-card result-card--danger glass-card anim-scale-in"
        >
          <header class="result-card__head">
            <span class="result-card__icon result-card__icon--danger">
              <TriangleAlertIcon :width="23" :height="23" :stroke-width="2.1" />
            </span>
            <div>
              <h3>审核未通过 · 商品被驳回</h3>
              <p>可依据下方驳回意见修改描述或价格，重新提交审核（仅 1 次重提机会）</p>
            </div>
          </header>
          <div v-if="reasons.length" class="reason-list">
            <span class="reason-list__title">驳回依据</span>
            <div v-for="(r, i) in reasons" :key="i" class="reason-row">
              <span class="reason-row__rule reason-row__rule--danger">{{ r.rule }}</span>
              <span class="reason-row__detail">{{ r.detail }}</span>
            </div>
          </div>
          <div class="result-card__actions">
            <el-button type="danger" @click="router.push('/seller/items')">
              去修改重提
              <ArrowRightIcon :width="14" :height="14" :stroke-width="2.3" style="margin-left: 4px" />
            </el-button>
            <el-button @click="resetForm">换个商品发布</el-button>
          </div>
        </article>

        <!-- 待补充 -->
        <article
          v-else-if="result.status === 'draft'"
          class="result-card result-card--warning glass-card anim-scale-in"
        >
          <header class="result-card__head">
            <span class="result-card__icon result-card__icon--warning">
              <FileQuestionIcon :width="23" :height="23" :stroke-width="2.1" />
            </span>
            <div>
              <h3>信息待补充 · 暂未送审</h3>
              <p>结构化引擎认为关键信息不足，补充后可再次提交</p>
            </div>
          </header>
          <ul v-if="result.missing?.length" class="missing-list">
            <li v-for="(m, i) in result.missing" :key="i">
              <TriangleAlertIcon :width="14" :height="14" :stroke-width="2.3" />
              {{ m }}
            </li>
          </ul>
          <div class="result-card__actions">
            <el-button type="warning" plain @click="resetForm">补充描述后重提</el-button>
            <el-button @click="router.push('/seller/items')">去我的商品</el-button>
          </div>
        </article>

        <!-- 待审核 / 其他 -->
        <article v-else class="result-card result-card--info glass-card anim-scale-in">
          <header class="result-card__head">
            <span class="result-card__icon result-card__icon--info">
              <HourglassIcon :width="23" :height="23" :stroke-width="2.1" />
            </span>
            <div>
              <h3>已提交 · {{ result.status_text || '审核处理中' }}</h3>
              <p>审核流程进行中，可在「我的商品」中查看最新状态与审核依据</p>
            </div>
          </header>
          <div class="result-card__actions">
            <el-button type="primary" plain @click="router.push('/seller/items')">去我的商品查看</el-button>
            <el-button @click="resetForm">继续发布</el-button>
          </div>
        </article>
      </aside>
    </div>
  </div>
</template>

<style scoped lang="scss">
.sell-page {
  max-width: 1200px;
  padding-top: 26px;
}

// ---------- 页头 ----------
.page-head {
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
    line-height: 1.7;
    color: var(--app-text-secondary);
  }
}

// ---------- 双引擎说明条 ----------
.engine-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
  margin-top: 18px;
  padding: 16px 22px;
  border-radius: 16px;
  background:
    linear-gradient(135deg, rgba(99, 102, 241, 0.06), rgba(34, 211, 238, 0.05)),
    var(--app-card-bg);

  &__lead {
    display: flex;
    align-items: center;
    gap: 13px;
    strong {
      display: block;
      font-size: 14px;
      font-weight: 700;
      color: var(--app-text-primary);
    }
    span:not(.engine-bar__lead-icon) {
      display: block;
      margin-top: 2px;
      font-size: 12px;
      color: var(--app-text-secondary);
    }
  }
  &__lead-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    flex: none;
    color: #fff;
    border-radius: 12px;
    background: var(--app-gradient);
    box-shadow: 0 6px 16px rgba(99, 102, 241, 0.3);
  }
  &__badges {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }
}

.engine-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 14px;
  border-radius: 12px;
  border: 1px solid var(--app-card-border);
  background: var(--app-card-bg-solid);
  svg {
    flex: none;
  }
  b {
    font-size: 12.5px;
    font-weight: 700;
  }
  em {
    font-style: normal;
    font-size: 11px;
    color: var(--app-text-placeholder);
    padding-left: 7px;
    margin-left: 1px;
    border-left: 1px solid var(--app-divider);
  }
  &--llm {
    color: #4f46e5;
  }
  &--rule {
    color: #059669;
  }
}

// ---------- 两栏布局 ----------
.sell-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(340px, 1fr);
  gap: 20px;
  margin-top: 20px;
  align-items: start;
}

// ---------- 表单卡 ----------
.form-card {
  padding: 26px 28px 24px;
  border-radius: 20px;

  &__block {
    margin-bottom: 20px;
    &:last-of-type {
      margin-bottom: 0;
    }
    &--url {
      flex: 1.2;
    }
  }
  &__row {
    display: flex;
    gap: 16px;
    .form-card__block {
      flex: 1;
    }
  }
  &__footer {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-top: 24px;
    padding-top: 20px;
    border-top: 1px dashed var(--app-card-border-strong);
  }
}

.field-label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 9px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--app-text-primary);
  svg {
    color: var(--app-brand);
  }
  &--required::after {
    content: '*';
    margin-left: 2px;
    color: var(--app-danger);
  }
  &__optional {
    font-size: 12px;
    font-weight: 400;
    color: var(--app-text-placeholder);
  }
}

.desc-input {
  :deep(.el-textarea__inner) {
    padding: 13px 15px;
    font-size: 14px;
    line-height: 1.8;
  }
}

.example-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  &__label {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
    color: var(--app-warning);
    font-weight: 500;
  }
}
.example-chip {
  padding: 4px 11px;
  font-size: 12px;
  color: var(--app-text-secondary);
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);
  border-radius: 999px;
  transition: all 0.2s cubic-bezier(0.34, 1.4, 0.5, 1);
  &:hover {
    color: var(--app-brand);
    border-color: var(--app-brand);
    background: var(--app-brand-soft);
    transform: translateY(-1px);
  }
}

.image-preview {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding: 10px;
  border-radius: 12px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);
  img {
    width: 72px;
    height: 54px;
    object-fit: cover;
    border-radius: 8px;
    background: #fff;
    transition: opacity 0.3s ease;
  }
  span {
    font-size: 12px;
    color: var(--app-text-placeholder);
  }
}

.submit-btn {
  height: 44px;
  padding: 0 30px;
  font-size: 14.5px;
  border-radius: 12px;
}
.submit-btn__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: #fff;
  border-radius: 50%;
  animation: app-spin 0.7s linear infinite;
}
.reset-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 44px;
  padding: 0 18px;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--app-text-secondary);
  border-radius: 12px;
  transition: all 0.2s ease;
  &:hover {
    color: var(--app-brand);
    background: var(--app-brand-soft);
  }
}

// ---------- 右侧引导卡 ----------
.guide-card {
  padding: 28px 26px;
  border-radius: 20px;
  position: sticky;
  top: 84px;

  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 54px;
    height: 54px;
    color: #fff;
    border-radius: 16px;
    background: var(--app-gradient);
    box-shadow: var(--app-shadow-glow);
  }
  h3 {
    margin-top: 16px;
    font-size: 16px;
    font-weight: 700;
    color: var(--app-text-primary);
  }
  ul {
    margin-top: 14px;
    display: grid;
    gap: 11px;
  }
  li {
    display: flex;
    align-items: flex-start;
    gap: 9px;
    font-size: 13px;
    line-height: 1.6;
    color: var(--app-text-regular);
    svg {
      flex: none;
      margin-top: 2px;
      color: var(--app-success);
    }
  }
  &__tip {
    margin-top: 16px;
    padding: 11px 14px;
    font-size: 12px;
    line-height: 1.7;
    color: var(--app-text-secondary);
    background: var(--app-warning-soft);
    border: 1px dashed rgba(245, 158, 11, 0.35);
    border-radius: 10px;
  }
}

// ---------- 结果卡通用 ----------
.result-card {
  padding: 26px;
  border-radius: 20px;

  &__head {
    display: flex;
    align-items: flex-start;
    gap: 14px;
  }
  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: none;
    width: 50px;
    height: 50px;
    border-radius: 15px;
    &--success {
      color: var(--app-success);
      background: var(--app-success-soft);
      box-shadow: 0 8px 20px rgba(16, 185, 129, 0.18);
    }
    &--warning {
      color: var(--app-warning);
      background: var(--app-warning-soft);
      box-shadow: 0 8px 20px rgba(245, 158, 11, 0.2);
    }
    &--danger {
      color: var(--app-danger);
      background: var(--app-danger-soft);
      box-shadow: 0 8px 20px rgba(239, 68, 68, 0.2);
    }
    &--info {
      color: var(--app-info);
      background: var(--app-info-soft);
      box-shadow: 0 8px 20px rgba(14, 165, 233, 0.18);
    }
  }
  h3 {
    font-size: 16.5px;
    font-weight: 700;
    color: var(--app-text-primary);
  }
  .result-card__head p {
    margin-top: 5px;
    font-size: 12.5px;
    line-height: 1.65;
    color: var(--app-text-secondary);
  }
  &__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 20px;
  }

  &--success {
    border-color: rgba(16, 185, 129, 0.28);
    box-shadow: 0 14px 36px rgba(16, 185, 129, 0.1);
  }
  &--warning {
    border-color: rgba(245, 158, 11, 0.32);
    box-shadow: 0 14px 36px rgba(245, 158, 11, 0.12);
  }
  &--danger {
    border-color: rgba(239, 68, 68, 0.3);
    box-shadow: 0 14px 36px rgba(239, 68, 68, 0.12);
  }
}

// 结构化信息格
.struct-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 18px;
}
.struct-item {
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);
  &--wide {
    grid-column: 1 / -1;
  }
  &__label {
    display: block;
    font-size: 11.5px;
    color: var(--app-text-placeholder);
    margin-bottom: 4px;
  }
  &__value {
    font-size: 14px;
    font-weight: 600;
    color: var(--app-text-primary);
    word-break: break-all;
    &--price {
      color: var(--app-brand);
      font-size: 16px;
      font-variant-numeric: tabular-nums;
    }
  }
}

// 建议价区间条
.range-box {
  margin-top: 16px;
  padding: 16px 18px;
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(99, 102, 241, 0.05), rgba(34, 211, 238, 0.05)),
    var(--app-card-bg-solid);
  border: 1px solid var(--app-card-border);

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
    gap: 6px;
    font-size: 13px;
    font-weight: 700;
    color: var(--app-text-primary);
    svg {
      color: var(--app-brand);
    }
  }
  &__numbers {
    font-size: 14px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--app-brand);
    i {
      font-style: normal;
      margin: 0 3px;
      color: var(--app-text-placeholder);
      font-weight: 400;
    }
  }
  &__tag {
    margin-left: 8px;
    padding: 2px 9px;
    font-size: 11px;
    font-style: normal;
    border-radius: 999px;
    font-weight: 600;
    &--in {
      color: #047857;
      background: var(--app-success-soft);
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    &--out {
      color: #b45309;
      background: var(--app-warning-soft);
      border: 1px solid rgba(245, 158, 11, 0.35);
    }
  }
}

.range-bar {
  position: relative;
  height: 10px;
  margin: 26px 6px 6px;
  border-radius: 999px;
  background: var(--el-fill-color-dark);

  &__zone {
    position: absolute;
    top: -3px;
    bottom: -3px;
    border-radius: 999px;
    background: linear-gradient(90deg, #6366f1, #22d3ee);
    box-shadow: 0 3px 10px rgba(99, 102, 241, 0.35);
  }
  &__marker {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    z-index: 2;
  }
  &__pin {
    display: block;
    width: 16px;
    height: 16px;
    margin: 0 auto;
    border-radius: 50%;
    background: #fff;
    border: 4px solid #f59e0b;
    box-shadow: 0 2px 8px rgba(245, 158, 11, 0.5);
  }
  &__cap {
    position: absolute;
    top: 16px;
    left: 50%;
    transform: translateX(-50%);
    white-space: nowrap;
    font-size: 11px;
    font-weight: 700;
    color: #b45309;
  }
  &__ends {
    display: flex;
    justify-content: space-between;
    margin-top: 16px;
    font-size: 11px;
    color: var(--app-text-placeholder);
    font-variant-numeric: tabular-nums;
  }
}

// 依据列表
.reason-list {
  margin-top: 16px;
  &__title {
    display: block;
    font-size: 12.5px;
    font-weight: 700;
    color: var(--app-text-secondary);
    margin-bottom: 8px;
  }
}
.reason-row {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 9px 12px;
  border-radius: 10px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);
  & + .reason-row {
    margin-top: 6px;
  }
  &__rule {
    flex: none;
    padding: 2px 9px;
    height: fit-content;
    font-size: 11px;
    font-weight: 600;
    color: var(--app-brand);
    background: var(--app-brand-soft);
    border-radius: 999px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    &--danger {
      color: var(--app-danger);
      background: var(--app-danger-soft);
    }
  }
  &__detail {
    font-size: 12.5px;
    line-height: 1.7;
    color: var(--app-text-regular);
  }
}

.result-lines {
  margin-top: 16px;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--app-card-border);
  &__row {
    display: flex;
    justify-content: space-between;
    gap: 14px;
    padding: 10px 14px;
    font-size: 13px;
    background: var(--el-fill-color-light);
    & + & {
      border-top: 1px solid var(--app-card-border);
    }
    span {
      color: var(--app-text-secondary);
      flex: none;
    }
    b {
      font-weight: 600;
      color: var(--app-text-primary);
      text-align: right;
    }
  }
}

// 冻结否决
.veto-basis {
  display: flex;
  gap: 11px;
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--app-danger-soft);
  border: 1px solid rgba(239, 68, 68, 0.3);
  svg {
    flex: none;
    margin-top: 2px;
    color: var(--app-danger);
  }
  strong {
    font-size: 13px;
    font-weight: 700;
    color: #b91c1c;
  }
  p {
    margin-top: 5px;
    font-size: 13px;
    line-height: 1.7;
    color: #991b1b;
  }
}
.veto-rules {
  margin-top: 10px;
  display: grid;
  gap: 6px;
}
.veto-rules li {
  display: flex;
  align-items: flex-start;
  gap: 9px;
}

// 待补充
.missing-list {
  margin-top: 14px;
  display: grid;
  gap: 8px;
  li {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 10px 13px;
    font-size: 13px;
    color: #92400e;
    background: var(--app-warning-soft);
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 10px;
    svg {
      flex: none;
      margin-top: 2px;
    }
  }
}

// ---------- 响应式 ----------
@media (max-width: 960px) {
  .sell-grid {
    grid-template-columns: 1fr;
  }
  .guide-card {
    position: static;
  }
}
@media (max-width: 560px) {
  .form-card__row {
    flex-direction: column;
    gap: 20px;
  }
  .struct-grid {
    grid-template-columns: 1fr;
  }
  .form-card,
  .result-card {
    padding: 20px;
  }
}
</style>
