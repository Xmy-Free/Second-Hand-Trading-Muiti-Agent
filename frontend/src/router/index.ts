/**
 * 路由表与守卫
 * - /login 独立页（公开）
 * - / 主布局 MainLayout（需登录）
 * - meta.admin 仅管理员（管理员控制台 / 复核终裁）
 * - meta.theme 控制双主题：light 业务浅色 / dark 指挥中心深色
 */
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { bindRouteTheme } from '@/composables/useTheme'

declare module 'vue-router' {
  interface RouteMeta {
    /** 公开页面，无需登录 */
    public?: boolean
    /** 仅管理员可访问 */
    admin?: boolean
    /** 页面主题（默认浅色） */
    theme?: 'light' | 'dark'
    title?: string
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { public: true, theme: 'light', title: '登录' },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/home',
    children: [
      {
        path: 'home',
        name: 'home',
        component: () => import('@/views/HomeView.vue'),
        meta: { title: '首页' },
      },
      {
        path: 'market',
        name: 'market',
        component: () => import('@/views/market/MarketView.vue'),
        meta: { title: '二手市场' },
      },
      {
        path: 'items/:id',
        name: 'item-detail',
        component: () => import('@/views/market/ItemDetailView.vue'),
        meta: { title: '商品详情' },
      },
      {
        path: 'seller/items',
        name: 'seller-items',
        component: () => import('@/views/seller/SellerItemsView.vue'),
        meta: { title: '我的商品' },
      },
      {
        path: 'seller/publish',
        name: 'seller-publish',
        component: () => import('@/views/seller/SellView.vue'),
        meta: { title: '发布商品' },
      },
      {
        path: 'negotiations',
        name: 'negotiations',
        component: () => import('@/views/negotiation/NegotiationsView.vue'),
        meta: { title: '议价室' },
      },
      {
        path: 'negotiations/:id',
        name: 'negotiation-room',
        component: () => import('@/views/negotiation/NegotiationRoomView.vue'),
        meta: { title: '议价进行中' },
      },
      {
        path: 'orders',
        name: 'orders',
        component: () => import('@/views/order/OrdersView.vue'),
        meta: { title: '我的订单' },
      },
      {
        path: 'credit',
        name: 'credit',
        component: () => import('@/views/credit/CreditView.vue'),
        meta: { title: '我的信用' },
      },
      {
        path: 'review',
        name: 'review',
        component: () => import('@/views/admin/ReviewView.vue'),
        meta: { title: '人工复核台', admin: true },
      },
      {
        path: 'appeals-admin',
        name: 'appeals-admin',
        component: () => import('@/views/admin/AppealsView.vue'),
        meta: { title: '纠纷终裁台', admin: true },
      },
      {
        path: 'console',
        name: 'console',
        component: () => import('@/views/console/ConsoleView.vue'),
        meta: { title: 'Mission Control 控制台', admin: true, theme: 'dark' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/home',
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  // 已登录访问登录页 → 首页
  if (to.meta.public) {
    if (to.name === 'login' && auth.isLoggedIn) {
      return { path: '/home' }
    }
    return true
  }

  // 未登录 → 登录页并记录回跳地址
  if (!auth.isLoggedIn) {
    return {
      path: '/login',
      query: to.fullPath !== '/home' ? { redirect: to.fullPath } : undefined,
    }
  }

  // 角色越权
  if (to.meta.admin && !auth.isAdmin) {
    ElMessage.error('无权访问：该区域仅对管理员开放')
    return { path: '/home' }
  }

  return true
})

router.afterEach((to) => {
  bindRouteTheme(to.meta.theme)
  document.title = to.meta.title
    ? `${to.meta.title} · 校园二手交易 Multi-Agent 平台`
    : '校园二手交易 Multi-Agent 平台'
})

export default router
