<script setup lang="ts">
/**
 * 原始 JSON 高亮视图（自写轻量语法着色，零依赖）
 */
import { computed } from 'vue'
import CopyIcon from '~icons/lucide/copy'
import CheckIcon from '~icons/lucide/check'
import { ref } from 'vue'

const props = defineProps<{
  data: unknown
}>()

const copied = ref(false)

const json = computed(() => {
  try {
    return JSON.stringify(props.data ?? null, null, 2)
  } catch {
    return String(props.data)
  }
})

const highlighted = computed(() => {
  const escaped = json.value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return escaped.replace(
    /("(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
    (match) => {
      let cls = 'jv-number'
      if (/^"/.test(match)) {
        cls = /:$/.test(match) ? 'jv-key' : 'jv-string'
      } else if (/true|false/.test(match)) {
        cls = 'jv-boolean'
      } else if (/null/.test(match)) {
        cls = 'jv-null'
      }
      return `<span class="${cls}">${match}</span>`
    },
  )
})

async function copyJson(): Promise<void> {
  try {
    await navigator.clipboard.writeText(json.value)
    copied.value = true
    window.setTimeout(() => {
      copied.value = false
    }, 1400)
  } catch {
    /* 剪贴板不可用时静默 */
  }
}
</script>

<template>
  <div class="jb">
    <button type="button" class="jb__copy" @click="copyJson">
      <component :is="copied ? CheckIcon : CopyIcon" :width="13" :height="13" />
      {{ copied ? '已复制' : '复制' }}
    </button>
    <pre class="jb__pre"><code class="jb__code" v-html="highlighted"></code></pre>
  </div>
</template>

<style scoped lang="scss">
@use './console.scss' as *;

.jb {
  position: relative;
  border-radius: 12px;
  background: var(--cc-inset-2);
  border: 1px solid var(--cc-border-soft);

  &__copy {
    position: absolute;
    top: 8px;
    right: 8px;
    z-index: 2;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    height: 24px;
    padding: 0 10px;
    font-size: 11px;
    color: var(--cc-text-3);
    background: var(--cc-panel-solid);
    border: 1px solid var(--cc-border);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.16s ease;
    &:hover {
      color: var(--cc-link);
      border-color: var(--cc-border-strong);
    }
  }
  &__pre {
    margin: 0;
    padding: 14px 16px;
    max-height: 520px;
    overflow: auto;
    @include thin-scroll;
  }
  &__code {
    font-size: 12px;
    line-height: 1.7;
    font-family: 'JetBrains Mono', 'SFMono-Regular', ui-monospace, Menlo, Consolas, monospace;

    :deep(.jv-key) {
      color: var(--cc-jv-key);
    }
    :deep(.jv-string) {
      color: var(--cc-jv-string);
    }
    :deep(.jv-number) {
      color: var(--cc-jv-number);
    }
    :deep(.jv-boolean) {
      color: var(--cc-jv-boolean);
    }
    :deep(.jv-null) {
      color: var(--cc-jv-null);
      font-style: italic;
    }
  }
}
</style>
