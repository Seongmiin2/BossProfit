<script setup>
import { useRouter } from 'vue-router'
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import { onMounted } from 'vue'

const router = useRouter()
const dashboardStore = useDashboardStore()
const authStore = useAuthStore()

const handleRecalculate = async () => {
  await dashboardStore.recalculate()
}

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}

onMounted(() => {
  authStore.initializeAuth()
})
</script>

<template>
  <header class="site-header">
    <div class="navbar-content">
      <router-link to="/" class="brand" style="cursor: pointer;">
        BOSSPROFIT
      </router-link>
      <nav class="nav">
        <router-link to="/dashboard">대시보드</router-link>
        <router-link to="/menus">메뉴</router-link>
        <router-link to="/history">추이</router-link>
        <router-link to="/market">시세</router-link>
        <router-link v-if="authStore.isLoggedIn" to="/forecast">예측</router-link>
        <router-link v-if="authStore.isLoggedIn" to="/ingredients">재료</router-link>
      </nav>
      <div style="display: flex; align-items: center; gap: 12px;">
        <button v-if="authStore.isLoggedIn" class="btn-coral" @click="handleRecalculate">⟳ 재계산</button>

        <div v-if="authStore.isLoggedIn" style="display: flex; align-items: center; gap: 12px; color: var(--cream); font-size: 14px;">
          <span>{{ authStore.user?.username }}</span>
          <button class="btn-coral" @click="handleLogout" style="padding: 6px 12px; font-size: 12px;">
            로그아웃
          </button>
        </div>

        <div v-else style="display: flex; gap: 8px;">
          <router-link to="/login" style="color: var(--cream); cursor: pointer; padding: 8px 14px; transition: color 0.15s;">로그인</router-link>
          <router-link to="/register" class="btn-coral" style="display: inline-block; text-align: center;">가입</router-link>
        </div>
      </div>
    </div>
  </header>

  <main class="container">
    <router-view />
  </main>

  <footer>
    <p>BOSSPROFIT © 2026 — 자영업자를 위한 메뉴 단위 수익성 분석</p>
  </footer>
</template>

