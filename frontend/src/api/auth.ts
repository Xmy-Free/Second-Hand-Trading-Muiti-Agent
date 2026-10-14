/**
 * 认证相关接口
 * POST /api/auth/register | /login | GET /api/auth/me
 */
import type { AppRequestConfig } from './http'
import { httpGet, httpPost } from './http'

/** 用户信息（与后端 UserOut 对齐） */
export interface UserInfo {
  id: number
  /** 学号（登录账号） */
  student_no: string
  nickname: string
  /** 是否管理员（校方） */
  is_admin: boolean
  /** 信用分 */
  credit_score: number
  /** 风险标签，无风险为 null */
  risk_tag: string | null
}

export interface AuthResult {
  token: string
  user: UserInfo
}

export interface LoginPayload {
  student_no: string
  password: string
}

export interface RegisterPayload {
  student_no: string
  password: string
  nickname: string
}

/** 学号 + 密码登录 */
export function login(payload: LoginPayload, config?: AppRequestConfig): Promise<AuthResult> {
  return httpPost<AuthResult>('/auth/login', payload, config)
}

/** 学号 + 密码 + 昵称注册 */
export function register(
  payload: RegisterPayload,
  config?: AppRequestConfig,
): Promise<AuthResult> {
  return httpPost<AuthResult>('/auth/register', payload, config)
}

/** 拉取当前登录用户（令牌恢复/进入应用时校验） */
export function fetchMe(config?: AppRequestConfig): Promise<UserInfo> {
  return httpGet<UserInfo>('/auth/me', config)
}
