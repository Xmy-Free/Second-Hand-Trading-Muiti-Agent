/**
 * axios 统一封装
 * - baseURL: /api（Vite 代理至 FastAPI :8000）
 * - 自动携带 JWT
 * - 统一解包后端信封 { code, message, data }：code === 0 取 data
 * - 业务错误 / 网络错误统一 ElMessage 提示
 * - 401：清会话并跳转登录（携带 redirect）
 */
import axios, { AxiosError } from 'axios'
import type { AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { clearSession, getToken } from '@/utils/storage'

/** 后端统一响应信封 */
export interface ApiEnvelope<T = unknown> {
  code: number
  message: string
  data: T
}

/** 应用级请求配置（扩展 axios，支持静默错误提示等） */
export interface AppRequestConfig extends AxiosRequestConfig {
  /** 跳过全局错误提示（由调用方自行展示错误） */
  hideErrorToast?: boolean
}

export const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ---------- 请求拦截：注入令牌 ----------
http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let redirecting = false

function handleUnauthorized(): void {
  clearSession()
  if (redirecting || window.location.pathname === '/login') return
  redirecting = true
  const redirect = window.location.pathname + window.location.search
  window.location.replace(`/login?redirect=${encodeURIComponent(redirect)}`)
}

function isEnvelope(payload: unknown): payload is ApiEnvelope {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'code' in payload &&
    'message' in payload
  )
}

// ---------- 响应拦截：信封解包 ----------
http.interceptors.response.use(
  (response) => {
    const payload = response.data
    const config = response.config as AppRequestConfig
    if (!isEnvelope(payload)) {
      // 非信封结构（如健康检查/第三方回调）原样返回
      return payload
    }
    if (payload.code === 0) {
      return payload.data
    }
    // 业务失败
    if (payload.code === 401) {
      if (!config.hideErrorToast) {
        ElMessage.error(payload.message || '登录状态已过期，请重新登录')
      }
      handleUnauthorized()
      return Promise.reject(new AxiosError(payload.message, String(payload.code)))
    }
    if (!config.hideErrorToast) {
      ElMessage.error(payload.message || '请求失败，请稍后重试')
    }
    return Promise.reject(new AxiosError(payload.message || '请求失败', String(payload.code)))
  },
  (error: AxiosError<ApiEnvelope>) => {
    const status = error.response?.status
    const config = error.config as AppRequestConfig | undefined
    const silent = config?.hideErrorToast === true
    if (status === 401) {
      if (!silent) {
        ElMessage.error(error.response?.data?.message || '登录状态已过期，请重新登录')
      }
      handleUnauthorized()
      return Promise.reject(error)
    }

    let tip = '网络异常，请稍后重试'
    if (error.code === 'ECONNABORTED') {
      tip = '请求超时，请检查后端服务是否启动'
    } else if (error.message === 'Network Error') {
      tip = '无法连接服务器，请确认后端（http://localhost:8000）已启动'
    } else if (error.response?.data?.message) {
      tip = error.response.data.message
    } else if (error.message) {
      tip = error.message
    }
    if (!silent) {
      ElMessage.error(tip)
    }
    return Promise.reject(error)
  },
)

/**
 * 类型化请求入口：拦截器已解包，直接返回 data
 */
export function request<T>(config: AppRequestConfig): Promise<T> {
  return http.request(config) as unknown as Promise<T>
}

export function httpGet<T>(url: string, config?: AppRequestConfig): Promise<T> {
  return request<T>({ ...config, method: 'GET', url })
}

export function httpPost<T>(url: string, data?: unknown, config?: AppRequestConfig): Promise<T> {
  return request<T>({ ...config, method: 'POST', url, data })
}

export function httpPut<T>(url: string, data?: unknown, config?: AppRequestConfig): Promise<T> {
  return request<T>({ ...config, method: 'PUT', url, data })
}

export function httpDelete<T>(url: string, config?: AppRequestConfig): Promise<T> {
  return request<T>({ ...config, method: 'DELETE', url })
}
