<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import AppIcon from '@/components/AppIcon.vue'

const route = useRoute()
const router = useRouter()
const dashboardStore = useDashboardStore()
const authStore = useAuthStore()
const isImmersive = computed(() => Boolean(route.meta?.immersive))

const pageTitle = computed(() => ({
  Dashboard: '홈',
  MenuList: '메뉴 분석',
  MenuDetail: '메뉴 상세',
  MenuCreate: '메뉴 추가',
  MenuEdit: '메뉴 수정',
  IngredientList: '재료 관리',
  History: 'AI 분석 리포트',
  Market: '시장',
  MarketRanking: '시장 순위',
  Settings: '내 정보',
  Login: '로그인',
  Register: '회원가입',
}[route.name] || 'BOSSPROFIT'))

const handleRecalculate = async () => {
  await dashboardStore.recalculate()
}

const handleLogout = async () => {
  await authStore.logout()
  router.push('/login')
}
</script>

<template>
  <div class="app-shell">
    <header v-if="!isImmersive" class="site-header">
      <div class="navbar-content">
        <router-link to="/" class="brand">
          <span class="brand-mark">B</span>
          <span class="brand-copy">
            <strong>BOSSPROFIT</strong>
            <small>내 가게 수익 비서</small>
          </span>
        </router-link>

        <nav class="desktop-nav" aria-label="주요 메뉴">
          <router-link to="/app">홈</router-link>
          <router-link to="/menus">메뉴</router-link>
          <router-link to="/history">AI 리포트</router-link>
          <router-link v-if="authStore.isLoggedIn" to="/market">시장</router-link>
          <router-link v-if="authStore.isLoggedIn" to="/ingredients">재료</router-link>
        </nav>

        <div class="header-actions">
          <button
            v-if="authStore.isLoggedIn"
            class="icon-button"
            title="수익 다시 계산하기"
            aria-label="수익 다시 계산하기"
            @click="handleRecalculate"
          >
            <AppIcon name="refresh" :size="19" />
          </button>
          <button v-if="authStore.isLoggedIn" class="profile-button" @click="router.push('/settings')">
            <span class="profile-avatar">{{ authStore.user?.username?.charAt(0)?.toUpperCase() || 'B' }}</span>
            <span class="profile-copy">
              <small>{{ authStore.store?.name || '내 매장' }}</small>
              <strong>{{ authStore.user?.username || '사장님' }} 사장님</strong>
            </span>
            <AppIcon name="chevron" :size="15" />
          </button>
          <button
            v-if="authStore.isLoggedIn"
            class="icon-button logout-icon"
            title="로그아웃"
            aria-label="로그아웃"
            @click="handleLogout"
          >
            <AppIcon name="logout" :size="18" />
          </button>
          <router-link v-else to="/login" class="login-button">로그인</router-link>
        </div>
      </div>
    </header>

    <div v-if="!isImmersive" class="mobile-page-head">
      <router-link to="/" class="mobile-brand">B</router-link>
      <strong>{{ pageTitle }}</strong>
      <router-link :to="authStore.isLoggedIn ? '/settings' : '/login'" class="mobile-head-action">
        <AppIcon v-if="authStore.isLoggedIn" name="user" :size="20" />
        <span v-else>로그인</span>
      </router-link>
    </div>

    <main class="container" :class="{ 'immersive-container': isImmersive }">
      <router-view />
    </main>

    <footer v-if="!isImmersive">
      <p>BOSSPROFIT · 사장님의 더 나은 결정을 돕습니다</p>
    </footer>

    <nav v-if="!isImmersive && authStore.isLoggedIn" class="bottom-nav" aria-label="모바일 주요 메뉴">
      <router-link to="/app">
        <span class="bottom-nav-icon"><AppIcon name="home" :size="20" /></span>
        <span>홈</span>
      </router-link>
      <router-link to="/menus">
        <span class="bottom-nav-icon"><AppIcon name="menu" :size="20" /></span>
        <span>메뉴</span>
      </router-link>
      <router-link to="/market">
        <span class="bottom-nav-icon"><AppIcon name="chart" :size="20" /></span>
        <span>시장</span>
      </router-link>
      <router-link :to="authStore.isLoggedIn ? '/settings' : '/login'">
        <span class="bottom-nav-icon"><AppIcon name="user" :size="20" /></span>
        <span>{{ authStore.isLoggedIn ? '내 정보' : '로그인' }}</span>
      </router-link>
    </nav>
  </div>
</template>
