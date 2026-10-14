<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import BrandLogo from '@/components/BrandLogo.vue'
import { activeTheme } from '@/composables/useTheme'
import StoreIcon from '~icons/lucide/store'
import PackageIcon from '~icons/lucide/package'
import MessagesIcon from '~icons/lucide/messages-square'
import ReceiptIcon from '~icons/lucide/receipt-text'
import ShieldIcon from '~icons/lucide/shield-check'
import RadarIcon from '~icons/lucide/radar'
import GavelIcon from '~icons/lucide/gavel'
import StarIcon from '~icons/lucide/star'
import ChevronDownIcon from '~icons/lucide/chevron-down'
import LogoutIcon from '~icons/lucide/log-out'

type IconComponent = Component

interface MenuItem {
  path: string
  label: string
  icon: IconComponent
  admin?: boolean
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { isAdmin } = storeToRefs(auth)

const menus: MenuItem[] = [
  { path: '/market', label: '市场', icon: StoreIcon },
  { path: '/seller/publish', label: '发布', icon: PackageIcon },
  { path: '/seller/items', label: '我的商品', icon: PackageIcon },
  { path: '/negotiations', label: '议价', icon: MessagesIcon },
  { path: '/orders', label: '我的订单', icon: ReceiptIcon },
  { path: '/credit', label: '信用', icon: ShieldIcon },
  { path: '/console', label: 'Agent 控制台', icon: RadarIcon, admin: true },
  { path: '/review', label: '商品复核', icon: GavelIcon, admin: true },
  { path: '/appeals-admin', label: '纠纷终裁', icon: GavelIcon, admin: true },
]

const visibleMenus = computed<MenuItem[]>(() =>
  menus.filter((item) => !item.admin || isAdmin.value),
)

const activeMenu = computed(() => {
  const matched = menus.find((item) => route.path === item.path || route.path.startsWith(`${item.path}/`))
  return matched?.path ?? route.path
})

const isDark = computed(() => activeTheme.value === 'dark')
const avatarText = computed(() => auth.nickname.slice(0, 1).toUpperCase())

async function onCommand(command: string | number | object): Promise<void> {
  const cmd = String(command)
  if (cmd === 'credit') {
    router.push('/credit')
  } else if (cmd === 'console') {
    router.push('/console')
  } else if (cmd === 'logout') {
    try {
      await ElMessageBox.confirm('确定要退出当前账号吗？', '退出登录', {
        confirmButtonText: '退出',
        cancelButtonText: '取消',
        type: 'warning',
      })
      auth.logout()
      router.replace('/login')
    } catch {
      /* 用户取消 */
    }
  }
}
</script>

<template>
  <div class="layout" :class="{ 'layout--dark': isDark }">
    <header class="layout__header glass-bar">
      <div class="layout__inner">
        <router-link to="/home" class="layout__brand" aria-label="返回首页">
          <BrandLogo :subtitle="false" />
        </router-link>

        <el-menu
          class="layout__menu"
          mode="horizontal"
          :default-active="activeMenu"
          :ellipsis="false"
          router
        >
          <el-menu-item v-for="item in visibleMenus" :key="item.path" :index="item.path">
            <component :is="item.icon" class="nav-icon" :stroke-width="2.1" />
            <span>{{ item.label }}</span>
          </el-menu-item>
        </el-menu>

        <div class="layout__actions">
          <router-link to="/credit" class="credit-badge" title="我的信用分">
            <StarIcon class="credit-badge__icon" :stroke-width="2.2" />
            <span class="credit-badge__score">{{ auth.creditScore }}</span>
          </router-link>

          <el-dropdown trigger="click" placement="bottom-end" @command="onCommand">
            <div class="user-chip">
              <span class="user-chip__avatar">{{ avatarText }}</span>
              <span class="user-chip__meta">
                <span class="user-chip__name">
                  {{ auth.nickname }}
                  <span v-if="auth.isAdmin" class="user-chip__tag">管理员</span>
                </span>
                <span class="user-chip__no">{{ auth.studentNo }}</span>
              </span>
              <ChevronDownIcon class="user-chip__caret" :stroke-width="2.2" />
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="credit">
                  <ShieldIcon :stroke-width="2.1" />
                  我的信用
                </el-dropdown-item>
                <el-dropdown-item v-if="auth.isAdmin" command="console">
                  <RadarIcon :stroke-width="2.1" />
                  管理员控制台
                </el-dropdown-item>
                <el-dropdown-item command="logout" divided>
                  <LogoutIcon :stroke-width="2.1" />
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </header>

    <main class="layout__main">
      <router-view v-slot="{ Component, route: viewRoute }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" :key="viewRoute.fullPath" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<style scoped lang="scss">
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;

  &__header {
    position: sticky;
    top: 0;
    z-index: 1000;
    height: 64px;
  }

  &__inner {
    height: 64px;
    max-width: 1360px;
    margin: 0 auto;
    padding: 0 24px;
    display: flex;
    align-items: center;
    gap: 20px;
  }

  &__brand {
    flex: none;
    display: inline-flex;
    align-items: center;
  }

  &__menu {
    flex: 1;
    min-width: 0;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
    &::-webkit-scrollbar {
      display: none;
    }
  }

  &__actions {
    flex: none;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  &__main {
    flex: 1;
    min-height: 0;
  }
}

// ---------- 顶部导航菜单（胶囊式） ----------
.layout__menu {
  :deep(.el-menu-item) {
    height: 38px;
    line-height: 38px;
    margin: 0 2px;
    padding: 0 14px;
    border-radius: 10px;
    color: var(--app-text-secondary);
    font-weight: 500;
    border-bottom: none !important;
    transition:
      color 0.2s ease,
      background-color 0.2s ease,
      transform 0.2s cubic-bezier(0.34, 1.4, 0.5, 1);

    .nav-icon {
      width: 17px;
      height: 17px;
      margin-right: 6px;
      vertical-align: -3px;
    }

    &:hover {
      color: var(--app-brand);
      background: var(--app-nav-item-hover);
    }
    &.is-active {
      color: var(--app-brand);
      font-weight: 600;
      background: var(--app-nav-item-active);
    }
  }
  :deep(.el-menu--horizontal) {
    border-bottom: none;
  }
  // 去掉 Element 水平菜单底部指示条
  :deep(.el-menu-item)::after {
    display: none;
  }
}

// ---------- 信用徽标 ----------
.credit-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--app-card-bg);
  border: 1px solid var(--app-card-border);
  backdrop-filter: blur(12px);
  transition:
    transform 0.2s cubic-bezier(0.34, 1.4, 0.5, 1),
    box-shadow 0.2s ease,
    border-color 0.2s ease;

  &__icon {
    width: 16px;
    height: 16px;
    color: #f59e0b;
  }
  &__score {
    font-size: 13.5px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--app-text-regular);
  }
  &:hover {
    transform: translateY(-1px);
    border-color: rgba(245, 158, 11, 0.45);
    box-shadow: 0 6px 18px rgba(245, 158, 11, 0.18);
  }
}

// ---------- 用户区 ----------
.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  height: 42px;
  padding: 0 10px 0 5px;
  border-radius: 999px;
  border: 1px solid transparent;
  cursor: pointer;
  outline: none;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease;

  &:hover {
    background: var(--app-nav-item-hover);
    border-color: var(--app-card-border);
  }

  &__avatar {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 15px;
    font-weight: 700;
    background: var(--app-gradient);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
  }

  &__meta {
    display: inline-flex;
    flex-direction: column;
    align-items: flex-start;
    line-height: 1.25;
  }

  &__name {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13.5px;
    font-weight: 600;
    color: var(--app-text-primary);
  }

  &__tag {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
    padding: 1px 7px;
    border-radius: 999px;
    color: #fff;
    background: linear-gradient(135deg, #f59e0b, #ef4444);
  }

  &__no {
    font-size: 11px;
    color: var(--app-text-secondary);
    font-variant-numeric: tabular-nums;
  }

  &__caret {
    width: 15px;
    height: 15px;
    color: var(--app-text-secondary);
    transition: transform 0.2s ease;
  }
}

.el-dropdown.is-active .user-chip__caret {
  transform: rotate(180deg);
}

// ---------- 深色指挥中心微调 ----------
.layout--dark {
  .layout__header {
    border-bottom-color: var(--app-card-border);
  }
  .layout__menu :deep(.el-menu-item.is-active) {
    box-shadow: 0 0 16px rgba(99, 102, 241, 0.25);
  }
}

// ---------- 响应式 ----------
@media (max-width: 960px) {
  .layout__inner {
    padding: 0 14px;
    gap: 12px;
  }
  .user-chip__meta {
    display: none;
  }
  .credit-badge {
    padding: 0 10px;
  }
}
@media (max-width: 640px) {
  .layout__brand .brand__name--single {
    display: none;
  }
  .layout__menu :deep(.el-menu-item) {
    padding: 0 12px;
    .nav-icon {
      margin-right: 0;
    }
    span {
      display: none;
    }
  }
}
</style>
