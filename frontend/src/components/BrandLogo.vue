<script setup lang="ts">
import BotIcon from '~icons/lucide/bot'

withDefaults(
  defineProps<{
    /** 标志尺寸（px） */
    size?: number
    /** 是否显示副标题 */
    subtitle?: boolean
  }>(),
  {
    size: 38,
    subtitle: true,
  },
)
</script>

<template>
  <div class="brand" :class="{ 'brand--inline': !subtitle }">
    <span
      class="brand__mark"
      :style="{ width: `${size}px`, height: `${size}px`, borderRadius: `${size * 0.32}px` }"
    >
      <BotIcon :width="size * 0.58" :height="size * 0.58" :stroke-width="2.2" />
    </span>
    <span v-if="subtitle" class="brand__text">
      <span class="brand__name">校园二手交易</span>
      <span class="brand__sub">Multi-Agent 协同平台</span>
    </span>
    <span v-else class="brand__name brand__name--single">校园二手交易</span>
  </div>
</template>

<style scoped lang="scss">
.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  user-select: none;

  &__mark {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    background: var(--app-gradient);
    box-shadow: 0 6px 18px rgba(99, 102, 241, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.35);
    transition: transform 0.22s cubic-bezier(0.34, 1.4, 0.5, 1);
  }

  &__text {
    display: inline-flex;
    flex-direction: column;
    line-height: 1.15;
  }

  &__name {
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 0.5px;
    background: var(--app-gradient);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
    white-space: nowrap;
  }

  &__name--single {
    font-size: 17px;
  }

  &__sub {
    margin-top: 2px;
    font-size: 10.5px;
    font-weight: 500;
    letter-spacing: 1.6px;
    color: var(--app-text-secondary);
    white-space: nowrap;
  }
}

a:hover .brand__mark,
.brand:hover .brand__mark {
  transform: rotate(-6deg) scale(1.06);
}
</style>
