<script setup lang="ts">
/**
 * AI 虚拟用户徽章（FR-201）
 * 渐变细标 + Sparkles，议价列表 / 市场卡 / 议价室统一复用
 * - size: sm 迷你（卡片区）/ md 标准（昵称旁）
 * - showText: 是否显示「AI」文字（纯图标场景可关）
 * - persona: 传入后悬停展示人设简介
 */
import SparklesIcon from '~icons/lucide/sparkles'

withDefaults(
  defineProps<{
    size?: 'sm' | 'md'
    showText?: boolean
    persona?: string | null
  }>(),
  { size: 'sm', showText: true, persona: null },
)
</script>

<template>
  <el-tooltip
    v-if="persona"
    :content="`AI 虚拟用户 · ${persona}`"
    placement="top"
    :show-after="240"
    :hide-after="0"
  >
    <span class="ai-badge" :class="`ai-badge--${size}`">
      <SparklesIcon class="ai-badge__icon" :stroke-width="2.4" />
      <em v-if="showText" class="ai-badge__text">AI</em>
    </span>
  </el-tooltip>
  <span v-else class="ai-badge" :class="`ai-badge--${size}`">
    <SparklesIcon class="ai-badge__icon" :stroke-width="2.4" />
    <em v-if="showText" class="ai-badge__text">AI</em>
  </span>
</template>

<style scoped lang="scss">
.ai-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  border-radius: 999px;
  font-style: normal;
  white-space: nowrap;
  cursor: default;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(34, 211, 238, 0.12));
  border: 1px solid rgba(99, 102, 241, 0.3);
  box-shadow: 0 1px 4px rgba(99, 102, 241, 0.12);

  &__icon {
    flex: none;
    background: linear-gradient(135deg, #6366f1, #06b6d4);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }
  &__text {
    font-style: normal;
    font-weight: 800;
    letter-spacing: 0.5px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    background: linear-gradient(135deg, #4f46e5, #0891b2);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }

  &--sm {
    height: 18px;
    padding: 0 6px;
    .ai-badge__icon {
      width: 10px;
      height: 10px;
    }
    .ai-badge__text {
      font-size: 9.5px;
      line-height: 1;
    }
  }
  &--md {
    height: 22px;
    padding: 0 9px;
    .ai-badge__icon {
      width: 12px;
      height: 12px;
    }
    .ai-badge__text {
      font-size: 10.5px;
      line-height: 1;
    }
  }
}
</style>
