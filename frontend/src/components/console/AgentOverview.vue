<script setup lang="ts">
/**
 * 区块 1 · Agent 总览
 * 数据驱动的 Agent 大卡网格（9 角色自适应）：能力标签云 / 呼吸状态灯 /
 * LLM 徽章 / 实时计数跳动 / 暂停恢复
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import PauseIcon from '~icons/lucide/pause'
import PlayIcon from '~icons/lucide/play'
import CpuIcon from '~icons/lucide/cpu'
import ArrowRightIcon from '~icons/lucide/arrow-right'
import RadioTowerIcon from '~icons/lucide/radio-tower'
import CircleCheckIcon from '~icons/lucide/circle-check'
import CircleSlashIcon from '~icons/lucide/circle-slash'
import DoorOpenIcon from '~icons/lucide/door-open'
import ActivityIcon from '~icons/lucide/activity'
import { activeTheme } from '@/composables/useTheme'
import {
  agentMeta,
  agents,
  agentsBusy,
  agentsLoading,
  fmtRelative,
  flowMeta,
  jumpThread,
  liveTraces,
  nodeLabel,
  nowTick,
  toggleAgent,
} from '@/composables/useConsoleData'
import type { AgentStatusItem } from '@/api/types'

async function beforeToggle(agent: AgentStatusItem): Promise<boolean> {
  const toPause = agent.runtime_status === 'running'
  try {
    await ElMessageBox.confirm(
      toPause
        ? `暂停后「${agent.display_name}」将以自动回复兜底，确认暂停？`
        : `确认恢复「${agent.display_name}」的自主决策？`,
      toPause ? '暂停 Agent' : '恢复 Agent',
      {
        confirmButtonText: toPause ? '暂停' : '恢复',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return false
  }
  const ok = await toggleAgent(agent, toPause)
  if (ok) ElMessage.success(`「${agent.display_name}」已${toPause ? '暂停' : '恢复'}`)
  return ok
}

function traceIcon(status: string): typeof ActivityIcon {
  if (status === 'human') return DoorOpenIcon
  if (status === 'error') return CircleSlashIcon
  if (status === 'exit') return CircleCheckIcon
  return ActivityIcon
}
function traceColor(status: string): string {
  const light = activeTheme.value === 'light'
  if (status === 'human') return light ? '#d97706' : '#fbbf24'
  if (status === 'error') return light ? '#e11d48' : '#fb7185'
  if (status === 'exit') return light ? '#059669' : '#34d399'
  return light ? '#4f46e5' : '#818cf8'
}
function traceText(status: string): string {
  return ({ enter: '进入', exit: '完成', human: '等待人工', error: '异常' } as Record<string, string>)[
    status
  ] ?? status
}
</script>

<template>
  <div class="overview">
    <!-- Agent 卡片 -->
    <div v-if="agentsLoading && !agents.length" class="overview__grid">
      <div v-for="n in 9" :key="n" class="agent-card agent-card--skeleton">
        <div class="skeleton" style="height: 190px; border-radius: 16px" />
      </div>
    </div>

    <div v-else class="overview__grid stagger">
      <article
        v-for="agent in agents"
        :key="agent.name"
        class="agent-card"
        :style="{ '--agent-accent': agent.accent || agentMeta(agent.name).accent }"
        :class="{ 'agent-card--paused': agent.runtime_status === 'paused' }"
      >
        <span class="agent-card__topline" />
        <header class="agent-card__head">
          <span class="agent-card__icon">
            <component :is="agentMeta(agent.name).icon" :width="24" :height="24" :stroke-width="1.9" />
          </span>
          <div class="agent-card__heading">
            <h3>{{ agent.display_name }}</h3>
            <p>{{ agentMeta(agent.name).en }} · {{ agent.name }}</p>
          </div>
          <el-switch
            :model-value="agent.runtime_status === 'running'"
            :loading="agentsBusy === agent.name"
            :before-change="() => beforeToggle(agent)"
            inline-prompt
            active-action-icon=""
            inactive-action-icon=""
          >
            <template #active-action><PlayIcon :width="10" :height="10" /></template>
            <template #inactive-action><PauseIcon :width="10" :height="10" /></template>
          </el-switch>
        </header>

        <p class="agent-card__desc">{{ agent.description || '暂无描述' }}</p>

        <div class="agent-card__caps">
          <span v-for="cap in agent.capabilities" :key="cap" class="cap-tag">{{ cap }}</span>
        </div>

        <footer class="agent-card__foot">
          <div class="metric">
            <span class="metric__label">
              <CpuIcon :width="12" :height="12" />
              ACL 消息
            </span>
            <span :key="`m-${agent.msg_handled}`" class="metric__value num-bump">
              {{ agent.msg_handled }}
            </span>
          </div>
          <div class="metric">
            <span class="metric__label">
              <ActivityIcon :width="12" :height="12" />
              任务
            </span>
            <span :key="`t-${agent.tasks_handled}`" class="metric__value num-bump">
              {{ agent.tasks_handled }}
            </span>
          </div>
          <div class="metric metric--right">
            <span class="runtime-badge" :class="`runtime-badge--${agent.runtime_status}`">
              <span class="runtime-badge__dot" />
              {{ agent.runtime_status === 'running' ? 'RUNNING' : agent.runtime_status === 'paused' ? 'PAUSED' : 'ERROR' }}
            </span>
            <span class="llm-badge" :class="agent.llm_mode === 'llm' ? 'llm-badge--llm' : 'llm-badge--rule'">
              {{ agent.llm_mode === 'llm' ? 'LLM' : 'RULE' }}
            </span>
          </div>
        </footer>

        <div class="agent-card__active">
          <span class="status-dot" :class="agent.runtime_status === 'running' ? 'status-dot--live' : 'status-dot--warning'" />
          最近活动 {{ fmtRelative(agent.last_active_at, nowTick) }}
        </div>
      </article>

      <!-- 后端不可用时占位 -->
      <article v-if="!agents.length" class="agent-card agent-card--empty">
        <RadioTowerIcon :width="26" :height="26" :stroke-width="1.6" />
        <h3>Agent 数据暂不可用</h3>
        <p>请确认后端服务已启动，稍后将自动重连</p>
      </article>
    </div>

    <!-- 实时节点事件脉冲 -->
    <section class="pulse glass-panel">
      <header class="pulse__head">
        <h2>
          <RadioTowerIcon :width="15" :height="15" />
          实时节点脉冲
          <span class="pulse__live">
            <span class="pulse__live-dot" />LIVE
          </span>
        </h2>
        <span class="pulse__hint">node_trace 事件流 · 点击跳转编排追踪</span>
      </header>
      <div v-if="liveTraces.length" class="pulse__list">
        <button
          v-for="(t, i) in liveTraces.slice(0, 10)"
          :key="`${t.ts}-${t.node}-${i}`"
          type="button"
          class="pulse__item"
          @click="jumpThread(t.thread_id)"
        >
          <span class="pulse__icon" :style="{ color: traceColor(t.status), background: `${traceColor(t.status)}1a` }">
            <component :is="traceIcon(t.status)" :width="13" :height="13" />
          </span>
          <span class="pulse__flow" :style="{ color: flowMeta(t.flow).color }">{{ flowMeta(t.flow).label }}</span>
          <span class="pulse__node">{{ nodeLabel(t.node) }}</span>
          <span class="pulse__status" :style="{ color: traceColor(t.status) }">{{ traceText(t.status) }}</span>
          <span v-if="t.summary" class="pulse__summary">{{ t.summary }}</span>
          <span class="pulse__time">{{ fmtRelative(t.ts, nowTick) }}</span>
          <ArrowRightIcon class="pulse__arrow" :width="13" :height="13" />
        </button>
      </div>
      <div v-else class="pulse__empty">
        <ActivityIcon :width="18" :height="18" :stroke-width="1.5" />
        等待 Agent 活动事件… 在市场中触发一次发布或议价即可看到实时脉冲
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
@use './console.scss' as *;

.overview {
  &__grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(258px, 1fr));
    gap: 14px;
  }
}

.glass-panel {
  @include panel;
}

// ---------------- Agent 卡片 ----------------
.agent-card {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 16px 17px 14px;
  border-radius: 16px;
  background: var(--cc-panel);
  border: 1px solid var(--cc-border);
  box-shadow: var(--cc-shadow-card);
  backdrop-filter: blur(14px) saturate(1.3);
  overflow: hidden;
  transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.25s ease, box-shadow 0.25s ease;

  &:hover {
    transform: translateY(-3px);
    border-color: color-mix(in srgb, var(--agent-accent) 45%, transparent);
    box-shadow:
      var(--cc-shadow-panel),
      0 0 26px color-mix(in srgb, var(--agent-accent) 16%, transparent);
  }
  &--paused {
    opacity: 0.86;
  }
  &--skeleton {
    padding: 0;
    border: none;
    background: transparent;
    box-shadow: none;
    backdrop-filter: none;
  }
  &--empty {
    grid-column: 1 / -1;
    align-items: center;
    text-align: center;
    padding: 42px 20px;
    color: var(--cc-text-muted);
    h3 {
      margin-top: 12px;
      font-size: 15px;
      color: var(--cc-text-2);
    }
    p {
      margin-top: 6px;
      font-size: 12.5px;
    }
  }

  &__topline {
    position: absolute;
    top: 0;
    left: 16px;
    right: 16px;
    height: 2px;
    border-radius: 2px;
    background: linear-gradient(90deg, transparent, var(--agent-accent), transparent);
    opacity: 0.7;
  }

  &__head {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  &__icon {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 46px;
    height: 46px;
    border-radius: 14px;
    color: var(--agent-accent);
    background: color-mix(in srgb, var(--agent-accent) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--agent-accent) 38%, transparent);
    box-shadow:
      0 0 18px color-mix(in srgb, var(--agent-accent) 22%, transparent),
      inset 0 1px 0 rgba(255, 255, 255, 0.25);
  }
  &__heading {
    flex: 1;
    min-width: 0;
    h3 {
      font-size: 14.5px;
      font-weight: 700;
      color: var(--cc-text-1);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    p {
      margin-top: 2px;
      font-size: 10.5px;
      color: var(--cc-text-muted);
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }
  &__desc {
    margin-top: 11px;
    font-size: 12px;
    line-height: 1.7;
    color: var(--cc-text-3);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 40px;
  }
  &__caps {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-top: 4px;
    min-height: 26px;
  }
  &__foot {
    display: flex;
    align-items: flex-end;
    gap: 14px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--cc-divider);
  }
  &__active {
    display: flex;
    align-items: center;
    gap: 7px;
    margin-top: 9px;
    font-size: 11px;
    color: var(--cc-text-muted);
  }
}

.cap-tag {
  height: 21px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  font-size: 10.5px;
  color: var(--cc-text-2);
  border-radius: 7px;
  background: var(--cc-raise);
  border: 1px solid var(--cc-border-soft);
  white-space: nowrap;
}

.metric {
  &__label {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 10.5px;
    color: var(--cc-text-muted);
  }
  &__value {
    display: block;
    margin-top: 2px;
    font-size: 22px;
    font-weight: 800;
    line-height: 1.1;
    color: var(--cc-text-1);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-variant-numeric: tabular-nums;
  }
  &--right {
    margin-left: auto;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 6px;
  }
}

.num-bump {
  --bump-color: var(--agent-accent);
  animation: console-num-bump 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}

.runtime-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 8px;
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.6px;
  border-radius: 6px;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  &__dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: currentColor;
  }
  &--running {
    color: var(--cc-success-text);
    background: var(--cc-success-soft);
    .runtime-badge__dot {
      animation: console-live-blink 1.6s ease-in-out infinite;
    }
  }
  &--paused {
    color: var(--cc-warning-text);
    background: var(--cc-warning-soft);
  }
  &--error {
    color: var(--cc-danger-text);
    background: var(--cc-danger-soft);
  }
}

.llm-badge {
  height: 20px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.6px;
  border-radius: 6px;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  &--llm {
    color: var(--cc-violet-text);
    background: var(--cc-violet-soft);
    border: 1px solid var(--cc-violet-border);
    box-shadow: 0 0 10px color-mix(in srgb, var(--cc-violet) 18%, transparent);
  }
  &--rule {
    color: var(--cc-cyan-text);
    background: var(--cc-hover-bg);
    border: 1px solid var(--cc-border-strong);
  }
}

// ---------------- 实时脉冲 ----------------
.pulse {
  margin-top: 16px;
  padding: 14px 18px 16px;

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 10px;
    h2 {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 13.5px;
      font-weight: 600;
      color: var(--cc-text-1);
      svg {
        color: var(--cc-indigo);
      }
    }
  }
  &__live {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    margin-left: 8px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
    color: var(--cc-danger);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
  }
  &__live-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--cc-danger);
    box-shadow: 0 0 8px var(--cc-danger-glow);
    animation: console-live-blink 1.2s ease-in-out infinite;
  }
  &__hint {
    font-size: 11px;
    color: var(--cc-text-faint);
  }
  &__list {
    display: flex;
    flex-direction: column;
  }
  &__item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 7px 8px;
    text-align: left;
    background: transparent;
    border: none;
    border-radius: 9px;
    cursor: pointer;
    animation: app-fade-in 0.3s ease both;
    transition: background 0.15s ease;
    &:hover {
      background: var(--cc-hover-bg);
      .pulse__arrow {
        opacity: 1;
        transform: translateX(0);
      }
    }
  }
  &__icon {
    flex: none;
    width: 24px;
    height: 24px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 7px;
  }
  &__flow {
    flex: none;
    font-size: 11px;
    font-weight: 700;
    width: 52px;
  }
  &__node {
    flex: none;
    font-size: 12px;
    font-weight: 600;
    color: var(--cc-text-2);
    width: 86px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  &__status {
    flex: none;
    font-size: 11px;
    width: 60px;
  }
  &__summary {
    flex: 1;
    min-width: 0;
    font-size: 11.5px;
    color: var(--cc-text-3);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  &__time {
    flex: none;
    font-size: 10.5px;
    color: var(--cc-text-faint);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
  }
  &__arrow {
    flex: none;
    color: var(--cc-indigo);
    opacity: 0.4;
    transform: translateX(-4px);
    transition: all 0.2s ease;
  }
  &__empty {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 9px;
    padding: 26px 0;
    font-size: 12.5px;
    color: var(--cc-text-faint);
  }
}
</style>
