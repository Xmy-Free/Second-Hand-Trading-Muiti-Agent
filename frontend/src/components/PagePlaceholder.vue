<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  icon: Component
  title: string
  description: string
  /** 右上角小徽标 */
  tag?: string
}>()
</script>

<template>
  <div class="page-container">
    <div class="ph glass-card">
      <span v-if="tag" class="ph__tag">{{ tag }}</span>
      <span class="ph__icon anim-scale-in">
        <component :is="icon" :width="34" :height="34" :stroke-width="1.8" />
      </span>
      <h2 class="ph__title">{{ title }}</h2>
      <p class="ph__desc">{{ description }}</p>
      <div v-if="$slots.default" class="ph__slot">
        <slot />
      </div>
      <div class="ph__building">
        <span class="status-dot status-dot--warning" />
        模块建设中 · 将在后续任务接入
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.ph {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  margin-top: 32px;
  padding: 64px 40px;

  &__tag {
    position: absolute;
    top: 20px;
    right: 20px;
    padding: 3px 12px;
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: var(--app-brand);
    border-radius: 999px;
    background: var(--app-brand-soft);
    border: 1px solid var(--app-card-border);
  }

  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 84px;
    height: 84px;
    color: #fff;
    border-radius: 24px;
    background: var(--app-gradient);
    box-shadow: var(--app-shadow-glow);
  }

  &__title {
    margin-top: 22px;
    font-size: 22px;
    font-weight: 700;
    color: var(--app-text-primary);
  }

  &__desc {
    max-width: 520px;
    margin-top: 10px;
    font-size: 14px;
    line-height: 1.8;
    color: var(--app-text-secondary);
  }

  &__slot {
    margin-top: 22px;
  }

  &__building {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-top: 28px;
    padding: 7px 16px;
    font-size: 12.5px;
    color: var(--app-text-secondary);
    border-radius: 999px;
    background: var(--el-fill-color-light);
    border: 1px solid var(--app-card-border);
  }
}
</style>
