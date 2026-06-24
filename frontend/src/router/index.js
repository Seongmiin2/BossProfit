import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
  },
  {
    path: '/menus',
    name: 'MenuList',
    component: () => import('@/views/MenuListView.vue'),
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
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/views/HistoryView.vue'),
  },
  {
    path: '/menus/:menuId',
    name: 'MenuDetail',
    component: () => import('@/views/MenuDetailView.vue'),
    props: true,
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/RegisterView.vue'),
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

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  // requiresAuth 메타가 없으면 모든 라우트 허용
  if (to.meta?.requiresAuth && !authStore.isLoggedIn) {
    next('/login')
  } else {
    next()
  }
})

export default router
