/**
 * 鉴权 Store
 * - token 持久化 localStorage
 * - 当前用户信息、登录 / 注册 / 登出
 * - isAdmin 角色标识
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as authApi from '@/api/auth'
import type { AppRequestConfig } from '@/api/http'
import type { LoginPayload, RegisterPayload, UserInfo } from '@/api/auth'
import { clearSession, getStoredUser, getToken, setStoredUser, setToken } from '@/utils/storage'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(getToken())
  const user = ref<UserInfo | null>(getStoredUser())

  const isLoggedIn = computed(() => Boolean(token.value))
  const isAdmin = computed(() => Boolean(user.value?.is_admin))
  const creditScore = computed(() => user.value?.credit_score ?? 0)
  const nickname = computed(() => user.value?.nickname ?? '同学')
  const studentNo = computed(() => user.value?.student_no ?? '')
  const riskTag = computed(() => user.value?.risk_tag ?? '')

  function commitSession(data: { token: string; user: UserInfo }): void {
    token.value = data.token
    user.value = data.user
    setToken(data.token)
    setStoredUser(data.user)
  }

  async function login(payload: LoginPayload, config?: AppRequestConfig): Promise<UserInfo> {
    const data = await authApi.login(payload, config)
    commitSession(data)
    return data.user
  }

  async function register(payload: RegisterPayload, config?: AppRequestConfig): Promise<UserInfo> {
    const data = await authApi.register(payload, config)
    commitSession(data)
    return data.user
  }

  /** 使用令牌重新拉取用户（应用启动 / 路由守卫中校验） */
  async function fetchProfile(): Promise<UserInfo> {
    const me = await authApi.fetchMe()
    user.value = me
    setStoredUser(me)
    return me
  }

  function logout(): void {
    token.value = ''
    user.value = null
    clearSession()
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    creditScore,
    nickname,
    studentNo,
    riskTag,
    login,
    register,
    fetchProfile,
    logout,
  }
})
