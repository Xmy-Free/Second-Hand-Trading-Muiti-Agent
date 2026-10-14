<script setup lang="ts">
/**
 * 区块 5 · 冲突中心：C1–C8 事件时间线 + C6 投票详情
 * 冲突类型 chip 由实际数据驱动（后端返回几类就展示几类）
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  conflicts,
  fmtDateTime,
  sceneMeta,
} from '@/composables/useConsoleData'
import VoteScoreBar from './VoteScoreBar.vue'
import JsonBlock from './JsonBlock.vue'
import SwordsIcon from '~icons/lucide/swords'
import ShieldAlertIcon from '~icons/lucide/shield-alert'
import ScaleIcon from '~icons/lucide/scale'
import TimerIcon from '~icons/lucide/timer'
import LockIcon from '~icons/lucide/lock'
import ScrollTextIcon from '~icons/lucide/scroll-text'
import SlidersIcon from '~icons/lucide/sliders-horizontal'
import VoteIcon from '~icons/lucide/vote'
import RefreshCwIcon from '~icons/lucide/refresh-cw'
import ExternalIcon from '~icons/lucide/external-link'

const router = useRouter()
const sceneFilter = ref('')
const expanded = ref<number | null>(null)

/** 数据驱动：从实际冲突事件中归纳出现过的场景（C1–C8） */
const scenes = computed(() => {
  const present: string[] = []
  for (const c of conflicts.value) {
    if (!present.includes(c.scene)) present.push(c.scene)
  }
  present.sort((a, b) => a.localeCompare(b))
  return [
    { value: '', label: '全部' },
    ...present.map((value) => ({ value, label: `${value} ${sceneMeta(value).short}` })),
  ]
})

function sceneCount(value: string): number {
  return value ? conflicts.value.filter((c) => c.scene === value).length : conflicts.value.length
}

const filtered = computed(() =>
  conflicts.value.filter((c) => !sceneFilter.value || c.scene === sceneFilter.value),
)

const sceneIcons: Record<string, any> = {
  C1: TimerIcon,
  C2: LockIcon,
  C3: ScrollTextIcon,
  C4: ScaleIcon,
  C5: SlidersIcon,
  C6: VoteIcon,
  C7: RefreshCwIcon,
  C8: ShieldAlertIcon,
}

function toggle(id: number) {
  expanded.value = expanded.value === id ? null : id
}

function needsHuman(c: Record<string, any>): boolean {
  const p = c.payload || {}
  if (p.human_required) return true
  return ['item_review', 'veto_review', 'appeal_final', 'risk_final'].includes(p.kind)
}

function gotoHuman(c: Record<string, any>) {
  const kind = c.payload?.kind
  if (kind === 'item_review' || kind === 'veto_review' || ['C8', 'C3'].includes(c.scene)) {
    router.push('/review')
  } else {
    router.push('/appeals-admin')
  }
}
</script>

<template>
  <section class="mc-panel conflicts">
    <header class="mc-panel__head">
      <div class="mc-panel__title">
        <SwordsIcon class="mc-icon" />
        冲突决策中心
        <span class="mc-count">{{ conflicts.length }}</span>
      </div>
      <div class="conflicts__tabs">
        <button v-for="s in scenes" :key="s.value" class="conf-tab"
          :class="{ 'is-active': sceneFilter === s.value }"
          :style="s.value ? { '--sc': sceneMeta(s.value).color } : {}"
          @click="sceneFilter = s.value">
          {{ s.label }}
          <span class="conf-tab__count">{{ sceneCount(s.value) }}</span>
        </button>
      </div>
    </header>

    <div class="conflicts__body">
      <article v-for="c in filtered" :key="c.id" class="conf-card" :style="{ '--sc': sceneMeta(c.scene).color }">
        <header class="conf-card__head" @click="toggle(c.id)">
          <component :is="sceneIcons[c.scene] ?? SwordsIcon" class="conf-card__icon" />
          <div class="conf-card__meta">
            <strong>{{ sceneMeta(c.scene).label }}</strong>
            <span>{{ sceneMeta(c.scene).sub }} · L{{ c.level }} · {{ c.type }}</span>
          </div>
          <time>{{ fmtDateTime(c.created_at) }}</time>
          <span class="conf-card__chev" :class="{ 'is-open': expanded === c.id }">⌄</span>
        </header>
        <p class="conf-card__result">{{ c.result }}</p>

        <div v-show="expanded === c.id" class="conf-card__detail">
          <!-- C6 投票明细 -->
          <template v-if="c.scene === 'C6'">
            <div class="vote-list">
              <div v-for="d in c.payload.details" :key="d.agent" class="vote-row">
                <span class="vote-row__agent">{{ d.agent_name }}</span>
                <span class="vote-row__weight">权 {{ d.weight }}</span>
                <span class="vote-row__conf">置信 {{ (d.confidence * 100).toFixed(0) }}%</span>
                <span class="vote-row__vote" :class="{
                  'v-yes': d.vote > 0, 'v-no': d.vote < 0, 'v-skip': d.vote === 0,
                }">{{ d.vote > 0 ? '同意 +1' : d.vote < 0 ? '反对 −1' : '弃权 0' }}</span>
                <span class="vote-row__weighted">加权 {{ d.weighted.toFixed(3) }}</span>
              </div>
              <div class="vote-row__basis" v-for="(d, i) in c.payload.details" :key="'b' + i">
                <em>{{ d.agent_name }}：</em>{{ Array.isArray(d.basis) ? d.basis.join('；') : d.basis }}
              </div>
            </div>
            <VoteScoreBar :score="c.payload.score" />
          </template>

          <!-- C8 安全依据 -->
          <template v-else-if="c.scene === 'C8'">
            <ul class="reason-list">
              <li v-for="(r, i) in c.payload.reasons" :key="i">
                <b>{{ r.rule }}</b>：{{ r.detail }}
              </li>
            </ul>
          </template>

          <!-- C1 纳什与破裂 -->
          <template v-else-if="c.scene === 'C1'">
            <div class="kv">
              <span>纳什参考价</span><b>¥{{ c.payload.nash_price ?? '—' }}</b>
              <span>最大轮次</span><b>{{ c.payload.max_rounds }}</b>
              <span>原因</span><b>{{ c.payload.reason }}</b>
            </div>
          </template>

          <!-- C2 裁决规则 -->
          <template v-else>
            <div class="kv">
              <span>裁决规则</span><b>{{ c.payload.rule }}</b>
            </div>
          </template>

          <div class="conf-card__foot">
            <span class="mono">{{ c.participants.join(' · ') }}</span>
            <el-button v-if="needsHuman(c)" size="small" type="primary" plain
              @click="gotoHuman(c)">
              前往人工处理 <ExternalIcon />
            </el-button>
          </div>
          <details class="conf-card__raw">
            <summary>原始 payload</summary>
            <JsonBlock :data="c.payload" />
          </details>
        </div>
      </article>

      <div v-if="!filtered.length" class="conflicts__empty">
        <SwordsIcon />
        <p>暂无冲突事件 —— 发起一次违禁品发布、高风险交易或议价僵持即可在此观察</p>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
@use './console.scss' as *;

$border: var(--cc-border);

.mc-panel {
  background: var(--cc-panel);
  border: 1px solid $border;
  border-radius: 16px;
  box-shadow: var(--cc-shadow-panel);
  backdrop-filter: blur(14px);
  overflow: hidden;

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 18px;
    border-bottom: 1px solid var(--cc-divider);
    flex-wrap: wrap;
  }

  &__title {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    font-size: 14px;
    font-weight: 700;
    color: var(--cc-text-1);

    .mc-icon {
      width: 17px;
      height: 17px;
      color: var(--cc-danger);
    }
  }
}

.mc-count {
  display: inline-grid;
  place-items: center;
  min-width: 22px;
  height: 20px;
  padding: 0 7px;
  margin-left: 4px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  color: var(--cc-danger-text);
  background: var(--cc-danger-soft);
}

.conflicts__tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.conf-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid $border;
  background: var(--cc-raise-2);
  color: var(--cc-text-3);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.18s;

  &__count {
    display: inline-grid;
    place-items: center;
    min-width: 17px;
    height: 17px;
    padding: 0 5px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 700;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    background: var(--cc-raise);
    color: var(--cc-text-muted);
  }

  &:hover {
    color: var(--cc-text-1);
  }
  &.is-active {
    color: var(--cc-chip-active-fg);
    border-color: var(--sc, var(--cc-indigo));
    background: var(--cc-chip-active-bg);
    box-shadow: 0 0 12px color-mix(in srgb, var(--sc, var(--cc-indigo)) 30%, transparent);
    .conf-tab__count {
      background: rgba(255, 255, 255, 0.22);
      color: #fff;
    }
  }
}

.conflicts__body {
  padding: 14px 18px;
  max-height: calc(100vh - 280px);
  overflow-y: auto;
  @include thin-scroll;
}

.conf-card {
  border: 1px solid $border;
  border-left: 3px solid var(--sc, var(--cc-indigo));
  border-radius: 12px;
  padding: 0 16px 14px;
  margin-bottom: 12px;
  background: var(--cc-raise-2);
  transition: background 0.2s, border-color 0.2s;

  &:hover {
    background: var(--cc-panel-hover);
  }

  &__head {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 13px 0 10px;
    cursor: pointer;
  }

  &__icon {
    width: 20px;
    height: 20px;
    color: var(--sc);
    filter: drop-shadow(0 0 6px color-mix(in srgb, var(--sc) 45%, transparent));
    flex: none;
  }

  &__meta {
    flex: 1;
    min-width: 0;

    strong {
      display: block;
      font-size: 13.5px;
      color: var(--cc-text-1);
    }
    span {
      font-size: 11.5px;
      color: var(--cc-text-muted);
    }
  }

  time {
    font-family: Consolas, monospace;
    font-size: 11px;
    color: var(--cc-text-faint);
  }

  &__chev {
    color: var(--cc-text-muted);
    transition: transform 0.2s;
    &.is-open {
      transform: rotate(180deg);
    }
  }

  &__result {
    margin: 0 0 8px;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 12.5px;
    color: var(--cc-text-2);
    background: color-mix(in srgb, var(--sc) 9%, transparent);
    border-left: 2px solid var(--sc);
  }

  &__detail {
    padding-top: 6px;
  }

  &__foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin: 10px 0;

    .mono {
      font-size: 11px;
      color: var(--cc-text-muted);
    }
  }

  &__raw {
    margin-top: 8px;
    font-size: 12px;

    summary {
      cursor: pointer;
      color: var(--cc-text-muted);
    }
  }
}

.vote-list {
  margin: 8px 0;
}
.vote-row {
  display: grid;
  grid-template-columns: 1.1fr 0.7fr 0.9fr 1fr 0.9fr;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  margin-bottom: 5px;
  border-radius: 8px;
  background: var(--cc-conf-row-bg);
  border: 1px solid var(--cc-border-soft);
  font-size: 12px;

  &__agent {
    font-weight: 700;
    color: var(--cc-link-2);
  }
  &__weight,
  &__conf {
    color: var(--cc-text-3);
    font-size: 11.5px;
  }
  &__weighted {
    font-family: Consolas, monospace;
    color: var(--cc-cyan-text);
    font-weight: 700;
  }
  &__vote {
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
    justify-self: start;
  }
  .v-yes {
    color: var(--cc-success-text);
    background: var(--cc-success-soft);
  }
  .v-no {
    color: var(--cc-danger-text);
    background: var(--cc-danger-soft);
  }
  .v-skip {
    color: var(--cc-text-3);
    background: var(--cc-raise);
  }
  &__basis {
    grid-column: 1 / -1;
    font-size: 11.5px;
    color: var(--cc-text-muted);
    line-height: 1.5;
    margin-top: 2px;

    em {
      font-style: normal;
      color: var(--cc-link);
    }
  }
}

.reason-list {
  margin: 8px 0;
  padding-left: 0;
  list-style: none;

  li {
    padding: 8px 12px;
    margin-bottom: 5px;
    border-radius: 8px;
    background: var(--cc-danger-soft);
    border-left: 2px solid var(--cc-danger);
    font-size: 12.5px;
    color: var(--cc-text-2);

    b {
      color: var(--cc-danger);
      margin-right: 4px;
    }
  }
}

.kv {
  display: grid;
  grid-template-columns: 90px 1fr;
  gap: 8px 14px;
  margin: 10px 0;
  font-size: 12.5px;

  span {
    color: var(--cc-text-muted);
  }
  b {
    color: var(--cc-text-2);
    font-weight: 600;
  }
}

.conflicts__empty {
  min-height: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--cc-text-faint);
  font-size: 13px;

  svg {
    width: 42px;
    height: 42px;
    opacity: 0.5;
  }
}
</style>
