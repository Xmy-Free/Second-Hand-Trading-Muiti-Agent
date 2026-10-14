<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import BotIcon from '~icons/lucide/bot'
import IdCardIcon from '~icons/lucide/id-card'
import LockIcon from '~icons/lucide/lock'
import UserIcon from '~icons/lucide/user'
import ArrowRightIcon from '~icons/lucide/arrow-right'
import SparklesIcon from '~icons/lucide/sparkles'
import NetworkIcon from '~icons/lucide/network'
import ScaleIcon from '~icons/lucide/scale'
import BadgeCheckIcon from '~icons/lucide/badge-check'
import TriangleAlertIcon from '~icons/lucide/triangle-alert'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const isRegister = ref(false)
const errorMsg = ref('')
const shaking = ref(false)
let shakeTimer: ReturnType<typeof setTimeout> | undefined

const form = reactive({
  nickname: '',
  student_no: '',
  password: '',
})

const rules: FormRules = {
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
    { min: 2, max: 20, message: '昵称长度为 2–20 个字符', trigger: 'blur' },
  ],
  student_no: [
    { required: true, message: '请输入学号', trigger: 'blur' },
    { pattern: /^\d{6,12}$/, message: '学号应为 6–12 位数字', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度至少 6 位', trigger: 'blur' },
  ],
}

function switchMode(toRegister: boolean): void {
  if (isRegister.value === toRegister) return
  isRegister.value = toRegister
  errorMsg.value = ''
  formRef.value?.clearValidate()
}

function triggerShake(): void {
  shaking.value = false
  // 强制重启动画
  requestAnimationFrame(() => {
    shaking.value = true
    clearTimeout(shakeTimer)
    shakeTimer = setTimeout(() => {
      shaking.value = false
    }, 480)
  })
}

async function onSubmit(): Promise<void> {
  if (loading.value) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  errorMsg.value = ''
  loading.value = true
  try {
    if (isRegister.value) {
      await auth.register(
        {
          nickname: form.nickname.trim(),
          student_no: form.student_no.trim(),
          password: form.password,
        },
        { hideErrorToast: true },
      )
      ElMessage.success('注册成功，已进入校园集市')
    } else {
      await auth.login(
        {
          student_no: form.student_no.trim(),
          password: form.password,
        },
        { hideErrorToast: true },
      )
      ElMessage.success('登录成功，欢迎回来')
    }
    const redirect = route.query.redirect
    router.replace(typeof redirect === 'string' && redirect.startsWith('/') ? redirect : '/home')
  } catch (err) {
    errorMsg.value = err instanceof Error && err.message ? err.message : '操作失败，请稍后重试'
    triggerShake()
  } finally {
    loading.value = false
  }
}

/** 演示种子账号一键填充（作者账号；其余角色由后端种子提供） */
function fillDemoAccount(): void {
  isRegister.value = false
  form.student_no = '2400320321'
  form.password = '123456'
  errorMsg.value = ''
  formRef.value?.clearValidate()
}

const featureBadges = [
  { label: '多 Agent 协同', icon: NetworkIcon },
  { label: '冲突三级裁决', icon: ScaleIcon },
  { label: '决策全程可解释', icon: BadgeCheckIcon },
]
</script>

<template>
  <div class="auth-page">
    <!-- 背景装饰层 -->
    <div class="auth-bg" aria-hidden="true">
      <span class="blob blob--indigo anim-float-slow" />
      <span class="blob blob--cyan anim-float-slower" />
      <span class="blob blob--violet anim-float-slow" />
      <span class="auth-grid" />
      <span class="auth-ring auth-ring--1" />
      <span class="auth-ring auth-ring--2" />
    </div>

    <div class="auth-card-wrap">
      <div class="auth-card glass-card" :class="{ 'auth-card--shake': shaking }">
        <!-- 品牌头 -->
        <div class="auth-header">
          <span class="auth-header__mark">
            <BotIcon :width="30" :height="30" :stroke-width="2" />
          </span>
          <h1 class="auth-header__title">
            校园二手交易 <span class="gradient-text gradient-text--animated">Multi-Agent</span>
          </h1>
          <p class="auth-header__slogan">多智能体协同，让每一笔校园交易诚信、安全、可解释</p>
          <div class="auth-header__badges">
            <span v-for="badge in featureBadges" :key="badge.label" class="feature-badge">
              <component :is="badge.icon" :stroke-width="2.2" />
              {{ badge.label }}
            </span>
          </div>
        </div>

        <!-- 登录 / 注册 切换 -->
        <div class="mode-switch" role="tablist">
          <span
            class="mode-switch__indicator"
            :class="{ 'mode-switch__indicator--right': isRegister }"
          />
          <button
            type="button"
            class="mode-switch__btn"
            :class="{ 'is-active': !isRegister }"
            role="tab"
            :aria-selected="!isRegister"
            @click="switchMode(false)"
          >
            登录
          </button>
          <button
            type="button"
            class="mode-switch__btn"
            :class="{ 'is-active': isRegister }"
            role="tab"
            :aria-selected="isRegister"
            @click="switchMode(true)"
          >
            注册
          </button>
        </div>

        <!-- 错误提示 -->
        <transition name="error-slide">
          <div v-if="errorMsg" class="error-banner" role="alert">
            <TriangleAlertIcon class="error-banner__icon" :stroke-width="2.2" />
            <span>{{ errorMsg }}</span>
          </div>
        </transition>

        <!-- 表单 -->
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          size="large"
          class="auth-form"
          label-position="top"
          @submit.prevent="onSubmit"
        >
          <transition name="field-expand">
            <el-form-item v-if="isRegister" prop="nickname" class="auth-form__item">
              <el-input v-model="form.nickname" placeholder="请输入昵称" clearable autocomplete="nickname">
                <template #prefix>
                  <UserIcon class="input-prefix-icon" :stroke-width="2.1" />
                </template>
              </el-input>
            </el-form-item>
          </transition>

          <el-form-item prop="student_no" class="auth-form__item">
            <el-input
              v-model="form.student_no"
              placeholder="请输入学号"
              clearable
              autocomplete="username"
              inputmode="numeric"
            >
              <template #prefix>
                <IdCardIcon class="input-prefix-icon" :stroke-width="2.1" />
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="password" class="auth-form__item">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              show-password
              autocomplete="current-password"
              @keyup.enter="onSubmit"
            >
              <template #prefix>
                <LockIcon class="input-prefix-icon" :stroke-width="2.1" />
              </template>
            </el-input>
          </el-form-item>

          <el-form-item class="auth-form__item auth-form__submit">
            <button type="submit" class="btn-gradient auth-submit" :disabled="loading">
              <span class="auth-submit__label">
                {{ loading ? (isRegister ? '注册中…' : '登录中…') : isRegister ? '注册并进入' : '登 录' }}
              </span>
              <ArrowRightIcon v-if="!loading" :width="18" :height="18" :stroke-width="2.4" />
              <span v-else class="auth-submit__spinner" />
            </button>
          </el-form-item>
        </el-form>

        <!-- 切换链接 -->
        <p class="auth-switch">
          <template v-if="!isRegister">
            还没有账号？
            <a href="javascript:void(0)" @click="switchMode(true)">立即注册</a>
          </template>
          <template v-else>
            已有账号？
            <a href="javascript:void(0)" @click="switchMode(false)">直接登录</a>
          </template>
        </p>

        <!-- 演示账号提示 -->
        <div class="demo-hint">
          <div class="demo-hint__label">
            <SparklesIcon :width="13" :height="13" :stroke-width="2.2" />
            演示账号（种子账号一键填充）
          </div>
          <div class="demo-hint__chips">
            <button type="button" class="demo-chip" @click="fillDemoAccount">
              作者账号 2400320321
            </button>
          </div>
          <p class="demo-hint__tip">
            买家 / 卖家 / 管理员均使用种子学号登录，默认密码以后端种子数据为准（如 123456）。
          </p>
        </div>
      </div>

      <p class="auth-footer">© 2026 校园二手交易 Multi-Agent 平台 · 课程设计演示原型</p>
    </div>
  </div>
</template>

<style scoped lang="scss">
.auth-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  overflow: hidden;
}

// ---------- 背景层 ----------
.auth-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.55;
}
.blob--indigo {
  top: -140px;
  left: -100px;
  width: 460px;
  height: 460px;
  background: radial-gradient(circle, #818cf8 0%, transparent 70%);
}
.blob--cyan {
  bottom: -180px;
  right: -100px;
  width: 520px;
  height: 520px;
  background: radial-gradient(circle, #22d3ee 0%, transparent 70%);
  opacity: 0.4;
}
.blob--violet {
  top: 38%;
  right: 14%;
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, #a78bfa 0%, transparent 70%);
  opacity: 0.32;
}

.auth-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(99, 102, 241, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(99, 102, 241, 0.06) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(ellipse 75% 65% at 50% 42%, #000 30%, transparent 75%);
  -webkit-mask-image: radial-gradient(ellipse 75% 65% at 50% 42%, #000 30%, transparent 75%);
}

.auth-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px dashed rgba(99, 102, 241, 0.18);
  &--1 {
    width: 680px;
    height: 680px;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
  }
  &--2 {
    width: 920px;
    height: 920px;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    border-color: rgba(34, 211, 238, 0.12);
  }
}

// ---------- 卡片 ----------
.auth-card-wrap {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 440px;
}

.auth-card {
  padding: 36px 36px 28px;
  border-radius: 24px;
  animation: app-scale-in 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;

  &--shake {
    animation: app-shake 0.42s ease;
  }
}

.auth-header {
  text-align: center;

  &__mark {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 60px;
    height: 60px;
    margin-bottom: 14px;
    color: #fff;
    border-radius: 18px;
    background: var(--app-gradient);
    box-shadow:
      0 12px 30px rgba(99, 102, 241, 0.42),
      inset 0 1px 0 rgba(255, 255, 255, 0.4);
  }

  &__title {
    font-size: 23px;
    font-weight: 800;
    color: var(--app-text-primary);
    letter-spacing: 0.3px;
  }

  &__slogan {
    margin-top: 8px;
    font-size: 13px;
    line-height: 1.7;
    color: var(--app-text-secondary);
  }

  &__badges {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 14px;
  }
}

.feature-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  font-size: 11.5px;
  font-weight: 500;
  color: var(--app-text-secondary);
  border-radius: 999px;
  background: var(--app-brand-soft);
  border: 1px solid var(--app-card-border);

  svg {
    width: 13px;
    height: 13px;
    color: var(--app-brand);
  }
}

// ---------- 模式切换 ----------
.mode-switch {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin: 24px 0 20px;
  padding: 4px;
  border-radius: 12px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-card-border);

  &__indicator {
    position: absolute;
    top: 4px;
    left: 4px;
    width: calc(50% - 4px);
    height: calc(100% - 8px);
    border-radius: 9px;
    background: var(--app-gradient);
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
    transition: transform 0.32s cubic-bezier(0.22, 1, 0.36, 1);

    &--right {
      transform: translateX(100%);
    }
  }

  &__btn {
    position: relative;
    z-index: 1;
    height: 36px;
    font-size: 14px;
    font-weight: 600;
    color: var(--app-text-secondary);
    border-radius: 9px;
    transition: color 0.25s ease;

    &.is-active {
      color: #fff;
    }
  }
}

// ---------- 错误条 ----------
.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  margin-bottom: 16px;
  font-size: 13px;
  color: #dc2626;
  background: var(--app-danger-soft);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 10px;

  &__icon {
    flex: none;
    width: 16px;
    height: 16px;
  }
}
.error-slide-enter-active,
.error-slide-leave-active {
  transition: all 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}
.error-slide-enter-from,
.error-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

// ---------- 表单 ----------
.auth-form {
  &__item {
    margin-bottom: 16px;
  }
  &__submit {
    margin-bottom: 0;
  }
}

.input-prefix-icon {
  width: 17px;
  height: 17px;
  color: var(--app-text-placeholder);
  transition: color 0.2s ease;
}

:deep(.el-input__wrapper) {
  padding: 4px 13px;
  box-shadow: 0 0 0 1px var(--app-card-border-strong) inset;
  background: rgba(255, 255, 255, 0.65);

  .el-input__inner {
    height: 36px;
    font-size: 14px;
  }
  &.is-focus {
    box-shadow:
      0 0 0 1px var(--app-brand) inset,
      0 0 0 4px rgba(99, 102, 241, 0.14),
      0 0 18px rgba(99, 102, 241, 0.18) !important;
    background: #fff;

    .input-prefix-icon {
      color: var(--app-brand);
    }
  }
}

:deep(.el-form-item__error) {
  padding-top: 4px;
  font-size: 12px;
}

.auth-submit {
  width: 100%;
  height: 46px;
  margin-top: 4px;
  font-size: 15px;
  letter-spacing: 2px;
  border-radius: 12px;

  &__label {
    letter-spacing: 2px;
  }

  &__spinner {
    width: 18px;
    height: 18px;
    border: 2px solid rgba(255, 255, 255, 0.45);
    border-top-color: #fff;
    border-radius: 50%;
    animation: app-spin 0.7s linear infinite;
  }
}

// ---------- 切换链接 ----------
.auth-switch {
  margin-top: 18px;
  text-align: center;
  font-size: 13px;
  color: var(--app-text-secondary);

  a {
    margin-left: 4px;
    font-weight: 600;
    color: var(--app-brand);
    transition: color 0.2s ease;
    &:hover {
      color: var(--app-accent);
      text-decoration: underline;
    }
  }
}

// ---------- 演示账号 ----------
.demo-hint {
  margin-top: 20px;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--el-fill-color-light);
  border: 1px dashed var(--app-card-border-strong);

  &__label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--app-text-secondary);
  }

  &__chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 9px;
  }

  &__tip {
    margin-top: 8px;
    font-size: 11.5px;
    line-height: 1.6;
    color: var(--app-text-placeholder);
  }
}

.demo-chip {
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--app-brand);
  background: var(--app-card-bg-solid);
  border: 1px solid var(--app-card-border-strong);
  border-radius: 999px;
  transition: all 0.22s cubic-bezier(0.34, 1.4, 0.5, 1);

  &:hover {
    transform: translateY(-1px);
    color: #fff;
    background: var(--app-gradient);
    border-color: transparent;
    box-shadow: 0 6px 16px rgba(99, 102, 241, 0.35);
  }
}

.auth-footer {
  margin-top: 18px;
  text-align: center;
  font-size: 11.5px;
  color: var(--app-text-placeholder);
  letter-spacing: 0.4px;
}

// ---------- 字段展开 / 模式切换过渡 ----------
.field-expand-enter-active,
.field-expand-leave-active {
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
}
.field-expand-enter-from,
.field-expand-leave-to {
  opacity: 0;
  max-height: 0;
  margin-bottom: 0 !important;
  transform: translateY(-8px);
}
.field-expand-enter-to,
.field-expand-leave-from {
  opacity: 1;
  max-height: 80px;
}

// ---------- 响应式 ----------
@media (max-width: 480px) {
  .auth-card {
    padding: 28px 22px 22px;
    border-radius: 20px;
  }
  .auth-header__title {
    font-size: 20px;
  }
  .auth-ring--1,
  .auth-ring--2 {
    display: none;
  }
}
</style>
