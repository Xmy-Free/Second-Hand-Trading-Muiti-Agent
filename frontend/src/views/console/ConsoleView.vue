<script setup lang="ts">
/**
 * 多 Agent 管理控制台 · Mission Control
 * 五区块：Agent 总览 / 编排追踪 / 消息总线 / 黑板快照 / 冲突中心
 * 数据：REST 预载 + /ws/control 实时帧，单例见 composables/useConsoleData
 * 主题：深色 / 浅色双主题，偏好持久化 localStorage（console_theme）
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AgentOverview from '@/components/console/AgentOverview.vue'
import OrchestrationTrace from '@/components/console/OrchestrationTrace.vue'
import MessageBus from '@/components/console/MessageBus.vue'
import BlackboardPanel from '@/components/console/BlackboardPanel.vue'
import ConflictCenter from '@/components/console/ConflictCenter.vue'
import DemoTheater from '@/components/console/DemoTheater.vue'
import {
  activeTab,
  connected,
  demo,
  demoRunning,
  fetchDemoStatus,
  handleFrame,
  loadAgents,
  loadConflicts,
  loadInstances,
  loadMessages,
  loadRecentTraces,
  setConnected,
  startDemo,
  startTicker,
  stopDemo,
} from '@/composables/useConsoleData'
import { bindRouteTheme, consoleTheme, toggleConsoleTheme } from '@/composables/useTheme'
import { useConsoleSocket } from '@/ws'
import LayoutGridIcon from '~icons/lucide/layout-grid'
import NetworkIcon from '~icons/lucide/network'
import RadioIcon from '~icons/lucide/radio'
import DatabaseIcon from '~icons/lucide/database'
import SwordsIcon from '~icons/lucide/swords'
import WifiOffIcon from '~icons/lucide/wifi-off'
import SunIcon from '~icons/lucide/sun'
import MoonIcon from '~icons/lucide/moon'
import PlayIcon from '~icons/lucide/play'
import SquareIcon from '~icons/lucide/square'

// 进入控制台立即应用用户偏好主题（瞬时、无刷新）
bindRouteTheme('dark')

type TabKey = 'overview' | 'orchestration' | 'messages' | 'blackboard' | 'conflicts'
const tabs: Array<{ key: TabKey; label: string; icon: any }> = [
  { key: 'overview', label: 'Agent 总览', icon: LayoutGridIcon },
  { key: 'orchestration', label: '编排追踪', icon: NetworkIcon },
  { key: 'messages', label: '消息总线', icon: RadioIcon },
  { key: 'blackboard', label: '黑板快照', icon: DatabaseIcon },
  { key: 'conflicts', label: '冲突中心', icon: SwordsIcon },
]

const ready = ref(false)
const { connected: socketConnected, close } = useConsoleSocket((frame) => handleFrame(frame))
watch(socketConnected, (v) => setConnected(v), { immediate: true })

onMounted(async () => {
  startTicker()
  await Promise.all([
    loadAgents(),
    loadInstances(),
    loadConflicts(),
    loadMessages(),
    fetchDemoStatus(),
    loadRecentTraces(),
  ])
  ready.value = true
})

onBeforeUnmount(() => close())
</script>

<template>
  <div class="console-page" :data-console-theme="consoleTheme">
    <!-- 背景装饰 -->
    <div class="console-bg" aria-hidden="true">
      <span class="console-bg__grid" />
      <span class="console-bg__glow console-bg__glow--a" />
      <span class="console-bg__glow console-bg__glow--b" />
    </div>

    <header class="console-hero">
      <div class="console-hero__left">
        <div class="console-hero__badge">
          <NetworkIcon />
        </div>
        <div>
          <h1>Mission Control · 多 Agent 指挥中心</h1>
          <p>协调者 Agent 统一注册与编排 · ACL 消息总线 · LangGraph 黑板状态 · 三级冲突决策全程可观测</p>
        </div>
      </div>
      <div class="console-hero__status">
        <!-- 一键全自动演示（FR-101） -->
        <el-tooltip
          content="全自动演示 9 Agent 协作全链路（发布→安全否决→搜索→议价→建单→支付→交付→评价）"
          placement="bottom"
          :show-after="260"
        >
          <button
            v-if="!demoRunning"
            type="button"
            class="demo-launch"
            :disabled="demo.starting"
            @click="startDemo()"
          >
            <span class="demo-launch__shine" aria-hidden="true" />
            <PlayIcon :width="15" :height="15" :stroke-width="2.5" />
            {{ demo.starting ? '启动中…' : '一键演示' }}
          </button>
          <button
            v-else
            type="button"
            class="demo-launch demo-launch--running"
            :disabled="demo.stopping"
            @click="stopDemo()"
          >
            <span class="demo-launch__spinner" aria-hidden="true" />
            <SquareIcon :width="12" :height="12" :stroke-width="2.6" />
            停止演示
            <span class="demo-launch__phase">
              {{ demo.phaseIndex }}/{{ demo.phaseCount }}
            </span>
          </button>
        </el-tooltip>

        <span class="ws-pill" :class="{ 'ws-pill--off': !connected }">
          <i />
          {{ connected ? '/ws/control 实时通道已连接' : '实时通道重连中' }}
          <WifiOffIcon v-if="!connected" />
        </span>

        <!-- 主题切换：太阳 / 月亮，滑块平滑位移 + 图标旋转淡入 -->
        <button
          type="button"
          class="theme-switch"
          role="switch"
          :aria-checked="consoleTheme === 'light'"
          :title="consoleTheme === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
          @click="toggleConsoleTheme()"
        >
          <span class="theme-switch__track">
            <span class="theme-switch__thumb">
              <MoonIcon class="theme-switch__icon theme-switch__icon--moon" />
              <SunIcon class="theme-switch__icon theme-switch__icon--sun" />
            </span>
          </span>
          <span class="theme-switch__label">{{ consoleTheme === 'dark' ? '深色' : '浅色' }}</span>
        </button>
      </div>
    </header>

    <nav class="console-tabs">
      <button v-for="t in tabs" :key="t.key" class="console-tab"
        :class="{ 'is-active': activeTab === t.key }" @click="activeTab = t.key">
        <component :is="t.icon" class="console-tab__icon" />
        {{ t.label }}
      </button>
    </nav>

    <main class="console-content" v-loading="!ready" :element-loading-background="'var(--cc-mask)'">
      <Transition name="console-fade" mode="out-in">
        <AgentOverview v-if="activeTab === 'overview'" key="overview" />
        <OrchestrationTrace v-else-if="activeTab === 'orchestration'" key="orch" />
        <MessageBus v-else-if="activeTab === 'messages'" key="msg" />
        <BlackboardPanel v-else-if="activeTab === 'blackboard'" key="board" />
        <ConflictCenter v-else key="conf" />
      </Transition>
    </main>

    <!-- 一键演示剧场浮层（8 阶段时间线 / 结果卡） -->
    <DemoTheater />
  </div>
</template>

<style scoped lang="scss">
.console-page {
  position: relative;
  min-height: calc(100vh - 64px);
  padding: 28px 28px 48px;
  max-width: 1440px;
  margin: 0 auto;
}

.console-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;

  &__grid {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(var(--cc-grid-line) 1px, transparent 1px),
      linear-gradient(90deg, var(--cc-grid-line) 1px, transparent 1px);
    background-size: 44px 44px;
    mask-image: radial-gradient(ellipse 90% 70% at 50% 0%, #000 30%, transparent 80%);
  }

  &__glow {
    position: absolute;
    width: 480px;
    height: 480px;
    border-radius: 50%;
    filter: blur(120px);
    opacity: var(--cc-glow-opacity);

    &--a {
      top: -160px;
      left: 8%;
      background: var(--cc-glow-a);
    }
    &--b {
      top: 10%;
      right: 4%;
      background: var(--cc-glow-b);
    }
  }
}

.console-hero {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 22px;

  &__left {
    display: flex;
    align-items: center;
    gap: 16px;
    min-width: 0;
  }

  &__badge {
    flex: none;
    width: 52px;
    height: 52px;
    border-radius: 16px;
    display: grid;
    place-items: center;
    color: var(--cc-indigo);
    font-size: 26px;
    background:
      linear-gradient(135deg, rgba(99, 102, 241, 0.22), rgba(34, 211, 238, 0.16)),
      var(--cc-panel);
    border: 1px solid var(--cc-border-strong);
    box-shadow: 0 0 24px var(--cc-edge-glow-flow), var(--cc-shadow-card);
  }

  h1 {
    margin: 0 0 4px;
    font-size: 24px;
    font-weight: 800;
    letter-spacing: 0.5px;
    background: var(--cc-title-gradient);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }

  p {
    margin: 0;
    font-size: 13px;
    color: var(--cc-text-3);
  }

  &__status {
    flex: none;
    display: flex;
    align-items: center;
    gap: 12px;
  }
}

.ws-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  font-size: 12.5px;
  color: var(--cc-success-text);
  background: var(--cc-success-soft);
  border: 1px solid var(--cc-success-border);

  i {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--cc-success);
    box-shadow: 0 0 10px var(--cc-success);
    animation: ws-pulse 1.8s infinite;
  }

  &--off {
    color: var(--cc-danger-text);
    background: var(--cc-danger-soft);
    border-color: var(--cc-danger-border);
    i {
      background: var(--cc-danger);
      box-shadow: 0 0 10px var(--cc-danger);
    }
  }
}

@keyframes ws-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

// ---------------- 一键演示主按钮 ----------------
.demo-launch {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 18px;
  font-size: 13.5px;
  font-weight: 700;
  letter-spacing: 0.3px;
  color: #fff;
  border: none;
  border-radius: 999px;
  background: linear-gradient(135deg, #6366f1 0%, #06b6d4 100%);
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.38), inset 0 1px 0 rgba(255, 255, 255, 0.28);
  cursor: pointer;
  overflow: hidden;
  transition: transform 0.22s ease, box-shadow 0.22s ease, filter 0.22s ease;

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 12px 30px rgba(99, 102, 241, 0.48), inset 0 1px 0 rgba(255, 255, 255, 0.32);
  }
  &:active:not(:disabled) {
    transform: translateY(0);
  }
  &:disabled {
    cursor: default;
    filter: saturate(0.85);
  }

  // 克制的呼吸高光扫过
  &__shine {
    position: absolute;
    inset: 0;
    background: linear-gradient(
      105deg,
      transparent 38%,
      rgba(255, 255, 255, 0.28) 50%,
      transparent 62%
    );
    background-size: 260% 100%;
    animation: demo-shine 3.6s ease-in-out infinite;
    pointer-events: none;
  }
  &__phase {
    padding-left: 9px;
    margin-left: 1px;
    font-size: 11.5px;
    font-weight: 800;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    border-left: 1px solid rgba(255, 255, 255, 0.35);
  }
  &__spinner {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 2px solid rgba(255, 255, 255, 0.4);
    border-top-color: #fff;
    animation: app-spin 0.8s linear infinite;
  }

  // 运行态：停止演示（柔红玻璃，双主题均成立）
  &--running {
    color: var(--cc-danger-text);
    background: var(--cc-danger-soft);
    border: 1px solid var(--cc-danger-border);
    box-shadow: none;
    backdrop-filter: blur(14px);
    .demo-launch__shine {
      display: none;
    }
    &:hover:not(:disabled) {
      background: color-mix(in srgb, var(--cc-danger) 16%, transparent);
      box-shadow: 0 8px 22px var(--cc-danger-glow);
    }
    .demo-launch__spinner {
      border-color: color-mix(in srgb, var(--cc-danger-text) 35%, transparent);
      border-top-color: var(--cc-danger-text);
    }
    .demo-launch__phase {
      border-left-color: color-mix(in srgb, var(--cc-danger-text) 30%, transparent);
    }
  }
}

@keyframes demo-shine {
  0% { background-position: 130% 0; }
  55%, 100% { background-position: -130% 0; }
}

// ---------------- 主题切换开关 ----------------
.theme-switch {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  height: 34px;
  padding: 0 12px 0 6px;
  border-radius: 999px;
  background: var(--cc-panel);
  border: 1px solid var(--cc-border);
  box-shadow: var(--cc-shadow-card);
  backdrop-filter: blur(14px);
  cursor: pointer;

  &:hover {
    border-color: var(--cc-border-strong);
    box-shadow: 0 6px 20px var(--cc-hover-bg);
  }

  &__track {
    position: relative;
    width: 46px;
    height: 24px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid rgba(148, 163, 184, 0.25);
    transition: background 0.34s ease, border-color 0.34s ease;
  }
  &__thumb {
    position: absolute;
    top: 50%;
    left: 2px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: linear-gradient(135deg, #c7d2fe, #818cf8);
    box-shadow: 0 2px 6px rgba(2, 6, 23, 0.45);
    transform: translateY(-50%) translateX(0);
    transition:
      transform 0.34s cubic-bezier(0.34, 1.56, 0.64, 1),
      background 0.34s ease,
      box-shadow 0.34s ease;
  }
  &__icon {
    position: absolute;
    width: 11px;
    height: 11px;
    transition: opacity 0.28s ease, transform 0.34s cubic-bezier(0.34, 1.56, 0.64, 1);
    &--moon {
      color: #fff7ed;
      opacity: 1;
      transform: rotate(0deg) scale(1);
    }
    &--sun {
      color: #b45309;
      opacity: 0;
      transform: rotate(-90deg) scale(0.4);
    }
  }
  &__label {
    font-size: 12px;
    font-weight: 600;
    color: var(--cc-text-2);
    letter-spacing: 1px;
  }

  // 浅色态：滑块右移，太阳旋入
  .console-page[data-console-theme='light'] & {
    .theme-switch__track {
      background: linear-gradient(135deg, #6366f1, #22d3ee);
      border-color: transparent;
    }
    .theme-switch__thumb {
      background: linear-gradient(135deg, #fffbeb, #fde68a);
      transform: translateY(-50%) translateX(22px);
      box-shadow: 0 2px 8px rgba(217, 119, 6, 0.4);
    }
    .theme-switch__icon--moon {
      opacity: 0;
      transform: rotate(90deg) scale(0.4);
    }
    .theme-switch__icon--sun {
      opacity: 1;
      transform: rotate(0deg) scale(1);
    }
  }
}

.console-tabs {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 8px;
  padding: 6px;
  margin-bottom: 20px;
  border-radius: 16px;
  background: var(--cc-panel-solid);
  border: 1px solid var(--cc-border);
  backdrop-filter: blur(14px);
  width: fit-content;
  max-width: 100%;
  overflow-x: auto;
}

.console-tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 18px;
  border: none;
  border-radius: 11px;
  background: transparent;
  color: var(--cc-text-muted);
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.22s ease;

  &__icon {
    width: 16px;
    height: 16px;
  }

  &:hover {
    color: var(--cc-text-2);
    background: var(--cc-hover-bg);
  }

  &.is-active {
    color: #fff;
    background: linear-gradient(135deg, #6366f1, #06b6d4);
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.35);
  }
}

.console-content {
  position: relative;
  z-index: 1;
}

.console-fade-enter-active,
.console-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}
.console-fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.console-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 900px) {
  .console-hero {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
