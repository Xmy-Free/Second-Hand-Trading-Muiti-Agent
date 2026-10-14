/**
 * 主题控制（模块级单例）
 * - 业务页面固定浅色；控制台路由默认浅色（V4 验收要求白色主题），可由用户在控制台头部切换深色
 * - 选择持久化到 localStorage（键 console_theme），切换瞬时生效不刷新
 */
import { ref } from 'vue'

export type AppTheme = 'light' | 'dark'

const STORAGE_KEY = 'console_theme'

function readStoredTheme(): AppTheme {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY)
    if (v === 'light' || v === 'dark') return v
  } catch {
    /* localStorage 不可用时退回默认 */
  }
  return 'light'
}

/** 控制台用户偏好（持久化） */
export const consoleTheme = ref<AppTheme>(readStoredTheme())

/** 当前实际生效的全站主题（响应式，供布局/组件读取） */
export const activeTheme = ref<AppTheme>(
  document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light',
)

export function persistConsoleTheme(): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, consoleTheme.value)
  } catch {
    /* 忽略写入失败 */
  }
}

export function applyDomTheme(theme: AppTheme): void {
  activeTheme.value = theme
  document.documentElement.setAttribute('data-theme', theme)
  document.body.setAttribute('data-theme', theme)
}

/** 路由进入时绑定主题：控制台路由使用用户偏好，其余路由一律浅色 */
export function bindRouteTheme(routeTheme?: 'light' | 'dark'): void {
  applyDomTheme(routeTheme === 'dark' ? consoleTheme.value : 'light')
}

export function toggleConsoleTheme(): void {
  consoleTheme.value = consoleTheme.value === 'dark' ? 'light' : 'dark'
  persistConsoleTheme()
  applyDomTheme(consoleTheme.value)
}
