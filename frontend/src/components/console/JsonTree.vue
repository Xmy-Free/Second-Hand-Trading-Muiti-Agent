<script setup lang="ts">
/**
 * 黑板状态递归树形视图（SFC 文件名递归自引用）
 * - 对象 / 数组可折叠，默认展开两层
 * - 标量按类型着色
 */
import { computed, ref } from 'vue'
import ChevronIcon from '~icons/lucide/chevron-right'

const props = withDefaults(
  defineProps<{
    data: unknown
    name?: string
    depth?: number
    index?: number
  }>(),
  { name: '', depth: 0, index: -1 },
)

type Kind = 'object' | 'array' | 'string' | 'number' | 'boolean' | 'null'

function kindOf(v: unknown): Kind {
  if (v === null || v === undefined) return 'null'
  if (Array.isArray(v)) return 'array'
  const t = typeof v
  if (t === 'string') return 'string'
  if (t === 'number') return 'number'
  if (t === 'boolean') return 'boolean'
  return 'object'
}

const kind = computed(() => kindOf(props.data))
const isBranch = computed(() => kind.value === 'object' || kind.value === 'array')
const open = ref(props.depth < 2)

interface Entry {
  key: string
  value: unknown
}

const entries = computed<Entry[]>(() => {
  if (kind.value === 'array') {
    return (props.data as unknown[]).map((value, i) => ({ key: String(i), value }))
  }
  if (kind.value === 'object' && props.data) {
    return Object.entries(props.data as Record<string, unknown>).map(([key, value]) => ({
      key,
      value,
    }))
  }
  return []
})

const summary = computed(() => {
  if (kind.value === 'array') return `[ …] ${entries.value.length} 项`
  return `{ …} ${entries.value.length} 个字段`
})

const primitiveText = computed(() => {
  switch (kind.value) {
    case 'string':
      return `"${props.data as string}"`
    case 'number':
      return String(props.data)
    case 'boolean':
      return props.data ? 'true' : 'false'
    default:
      return 'null'
  }
})
</script>

<template>
  <div class="jt">
    <!-- 分支节点 -->
    <template v-if="isBranch">
      <button
        type="button"
        class="jt__row jt__row--branch"
        :style="{ paddingLeft: `${depth * 16}px` }"
        @click="open = !open"
      >
        <ChevronIcon :width="13" :height="13" class="jt__caret" :class="{ 'jt__caret--open': open }" />
        <span v-if="index >= 0" class="jt__idx">{{ index }}</span>
        <span v-else-if="name" class="jt__key">{{ name }}</span>
        <span v-else class="jt__root-key">{{ kind === 'array' ? 'Array' : 'Object' }}</span>
        <span class="jt__punct">{{ kind === 'array' ? '[' : '{' }}</span>
        <span v-if="!open" class="jt__summary">{{ summary }}</span>
        <span v-if="!open" class="jt__punct">{{ kind === 'array' ? ']' : '}' }}</span>
      </button>
      <div v-show="open" class="jt__children">
        <JsonTree
          v-for="(entry, i) in entries"
          :key="entry.key"
          :data="entry.value"
          :name="kind === 'array' ? '' : entry.key"
          :index="kind === 'array' ? i : -1"
          :depth="depth + 1"
        />
        <div class="jt__row jt__close" :style="{ paddingLeft: `${depth * 16}px` }">
          <span class="jt__punct">{{ kind === 'array' ? ']' : '}' }}</span>
        </div>
      </div>
    </template>

    <!-- 标量叶子 -->
    <div v-else class="jt__row" :style="{ paddingLeft: `${depth * 16 + 18}px` }">
      <span v-if="index >= 0" class="jt__idx">{{ index }}</span>
      <span v-else-if="name" class="jt__key">{{ name }}</span>
      <span :class="`jt__value jt__value--${kind}`">{{ primitiveText }}</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use './console.scss' as *;

.jt {
  font-size: 12.5px;
  line-height: 1.6;
  font-family: 'JetBrains Mono', 'SFMono-Regular', ui-monospace, Menlo, Consolas, monospace;

  &__row {
    display: flex;
    align-items: baseline;
    gap: 6px;
    padding: 1px 8px 1px 0;
    border-radius: 6px;
    &--branch {
      width: 100%;
      border: none;
      background: transparent;
      cursor: pointer;
      text-align: left;
      &:hover {
        background: var(--cc-hover-bg);
      }
    }
  }
  &__close {
    opacity: 0.7;
  }
  &__caret {
    flex: none;
    color: var(--cc-text-muted);
    transition: transform 0.16s ease;
    transform: rotate(0deg);
    &--open {
      transform: rotate(90deg);
    }
  }
  &__key {
    color: var(--cc-jv-key);
  }
  &__root-key {
    color: var(--cc-violet-text);
    font-weight: 600;
    font-family: 'Inter', 'PingFang SC', sans-serif;
    font-size: 11.5px;
  }
  &__idx {
    color: var(--cc-text-muted);
    min-width: 18px;
    text-align: right;
  }
  &__punct {
    color: var(--cc-text-3);
  }
  &__summary {
    color: var(--cc-text-muted);
    font-style: italic;
    font-size: 11.5px;
  }
  &__value {
    word-break: break-all;
    &--string {
      color: var(--cc-jv-string);
    }
    &--number {
      color: var(--cc-jv-number);
    }
    &--boolean {
      color: var(--cc-jv-boolean);
    }
    &--null {
      color: var(--cc-jv-null);
      font-style: italic;
    }
  }
}
</style>
