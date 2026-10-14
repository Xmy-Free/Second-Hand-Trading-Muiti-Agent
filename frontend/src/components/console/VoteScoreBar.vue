<script setup lang="ts">
/**
 * C6 加权投票总分仪表：[-1, +0.5 灰区, +1]，阈值 ±0.5
 */
import { computed } from 'vue'
import { activeTheme } from '@/composables/useTheme'

const props = defineProps<{
  score: number
}>()

const clamped = computed(() => Math.max(-1, Math.min(1, props.score)))
const percent = computed(() => ((clamped.value + 1) / 2) * 100)

const decision = computed<{ text: string; color: string }>(() => {
  const light = activeTheme.value === 'light'
  if (props.score >= 0.5) return { text: 'allow · 放行支付', color: light ? '#059669' : '#34d399' }
  if (props.score <= -0.5) return { text: 'block · 拦截取消', color: light ? '#e11d48' : '#fb7185' }
  return { text: 'manual · 升级人工终裁', color: light ? '#d97706' : '#fbbf24' }
})

const ticks = [
  { v: -1, label: '-1.0' },
  { v: -0.5, label: '-0.5' },
  { v: 0, label: '0' },
  { v: 0.5, label: '+0.5' },
  { v: 1, label: '+1.0' }
]
</script>

<template>
  <div class="vbar">
    <div class="vbar__head">
      <span class="vbar__title">加权总分</span>
      <span class="vbar__decision" :style="{ color: decision.color }">{{ decision.text }}</span>
    </div>
    <div class="vbar__track-wrap">
      <div class="vbar__track">
        <span class="vbar__zone vbar__zone--block" />
        <span class="vbar__zone vbar__zone--manual" />
        <span class="vbar__zone vbar__zone--allow" />
        <span class="vbar__threshold" style="left: 25%" />
        <span class="vbar__threshold vbar__threshold--center" style="left: 50%" />
        <span class="vbar__threshold" style="left: 75%" />
        <span class="vbar__marker" :style="{ left: `${percent}%` }">
          <span class="vbar__needle" />
          <span class="vbar__score">{{ score >= 0 ? '+' : '' }}{{ score.toFixed(2) }}</span>
        </span>
      </div>
    </div>
    <div class="vbar__ticks">
      <span
        v-for="t in ticks"
        :key="t.v"
        class="vbar__tick"
        :style="{ left: `${((t.v + 1) / 2) * 100}%` }"
        :class="{ 'vbar__tick--strong': t.v === -0.5 || t.v === 0.5 }"
      >
        {{ t.label }}
      </span>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use './console.scss' as *;

.vbar {
  &__head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 26px;
  }
  &__title {
    font-size: 12.5px;
    font-weight: 600;
    color: var(--cc-text-2);
  }
  &__decision {
    font-size: 12.5px;
    font-weight: 700;
    letter-spacing: 0.3px;
  }
  &__track-wrap {
    padding: 0 2px;
  }
  &__track {
    position: relative;
    display: flex;
    height: 14px;
    border-radius: 999px;
    overflow: visible;
  }
  &__zone {
    height: 100%;
    &--block {
      width: 25%;
      background: var(--cc-zone-block);
      border-radius: 999px 0 0 999px;
      box-shadow: inset 0 0 8px color-mix(in srgb, var(--cc-danger) 25%, transparent);
    }
    &--manual {
      width: 50%;
      background: var(--cc-zone-manual);
      box-shadow: inset 0 0 8px color-mix(in srgb, var(--cc-warning) 22%, transparent);
    }
    &--allow {
      width: 25%;
      background: var(--cc-zone-allow);
      border-radius: 0 999px 999px 0;
      box-shadow: inset 0 0 8px color-mix(in srgb, var(--cc-success) 25%, transparent);
    }
  }
  &__threshold {
    position: absolute;
    top: -3px;
    bottom: -3px;
    width: 1px;
    background: var(--cc-threshold);
    transform: translateX(-0.5px);
    &--center {
      background: var(--cc-threshold-strong);
      height: 24px;
      top: -5px;
      bottom: -5px;
    }
  }
  &__marker {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    transition: left 0.7s cubic-bezier(0.22, 1, 0.36, 1);
    z-index: 2;
  }
  &__needle {
    display: block;
    width: 4px;
    height: 26px;
    margin: 0 auto;
    border-radius: 2px;
    background: var(--cc-needle);
    box-shadow: 0 0 10px var(--cc-needle-glow), 0 0 22px var(--cc-edge-glow-flow);
  }
  &__score {
    position: absolute;
    top: -24px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 12.5px;
    font-weight: 800;
    color: var(--cc-text-1);
    white-space: nowrap;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    text-shadow: 0 0 10px color-mix(in srgb, var(--cc-indigo) 50%, transparent);
  }
  &__ticks {
    position: relative;
    margin-top: 8px;
    height: 14px;
  }
  &__tick {
    position: absolute;
    transform: translateX(-50%);
    font-size: 10px;
    color: var(--cc-text-muted);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    &:first-child {
      transform: translateX(0);
    }
    &:last-child {
      transform: translateX(-100%);
    }
    &--strong {
      color: var(--cc-text-3);
      font-weight: 700;
    }
  }
}
</style>
