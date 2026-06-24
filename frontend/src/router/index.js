import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/',
    name: 'Landing',
    component: () => import('@/views/LandingView.vue'),
    meta: { immersive: true },
  },
  {
    path: '/app',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/menus',
    name: 'MenuList',
    component: () => import('@/views/MenuListView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/menus/create',
    name: 'MenuCreate',
    component: () => import('@/views/MenuFormView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/menus/:menuId/edit',
    name: 'MenuEdit',
    component: () => import('@/views/MenuFormView.vue'),
    meta: { requiresAuth: true },
    props: true,
  },
  {
    path: '/ingredients',
    name: 'IngredientList',
    component: () => import('@/views/IngredientListView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/views/HistoryView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/market',
    name: 'Market',
    component: () => import('@/views/MarketView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/menus/:menuId',
    name: 'MenuDetail',
    component: () => import('@/views/MenuDetailView.vue'),
    props: true,
    meta: { requiresAuth: true },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { guestOnly: true, immersive: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { guestOnly: true, immersive: true },
  },
  {
    path: '/onboarding',
    name: 'Onboarding',
    component: () => import('@/views/OnboardingView.vue'),
    meta: { requiresAuth: true, immersive: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: { template: '<div style="padding:40px; text-align:center;"><h1>404 - 페이지를 찾을 수 없습니다</h1><p>경로: {{ $route.path }}</p></div>' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  if (!authStore.initialized) {
    await authStore.initializeAuth()
  }
  if (to.meta?.requiresAuth && !authStore.isLoggedIn) {
    return next({ name: 'Login', query: { redirect: to.fullPath } })
  }
  if (to.meta?.guestOnly && authStore.isLoggedIn) {
    return next(authStore.needsOnboarding ? '/onboarding' : '/app')
  }
  if (
    authStore.isLoggedIn
    && authStore.needsOnboarding
    && to.name !== 'Onboarding'
    && to.name !== 'Landing'
    && to.name !== 'IngredientList'
    && to.name !== 'MenuCreate'
  ) {
    return next('/onboarding')
  }
  next()
})

export default router
