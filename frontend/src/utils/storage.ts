/**
 * 会话持久化（localStorage）
 * 与具体框架无关，供 axios 拦截器与 Pinia store 共用，避免循环依赖
 */
import type { UserInfo } from '@/api/auth'

export const TOKEN_KEY = 'campus_ma_token'
export const USER_KEY = 'campus_ma_user'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? ''
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function getStoredUser(): UserInfo | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as UserInfo
  } catch {
    return null
  }
}

export function setStoredUser(user: UserInfo): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}
