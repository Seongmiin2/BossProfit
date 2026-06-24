<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const username = ref('')
const password = ref('')
const showPassword = ref(false)

async function handleSubmit() {
  try {
    await authStore.login(username.value.trim(), password.value)
    const target = authStore.needsOnboarding
      ? '/onboarding'
      : (route.query.redirect || '/app')
    router.replace(target)
  } catch {
    // store에서 사용자에게 표시할 오류를 관리한다.
  }
}
</script>

<template>
  <div class="auth-layout">
    <section class="auth-brand-panel">
      <router-link to="/" class="auth-logo">
        <span>B</span>
        <strong>BOSSPROFIT</strong>
      </router-link>
      <div class="auth-brand-copy">
        <span class="auth-kicker">AI 자영업 경영 안전망</span>
        <h1>시장 변화보다<br>한발 먼저 준비하세요.</h1>
        <p>재료 가격, 메뉴 원가, 앞으로의 대응까지 내 매장 데이터로 연결합니다.</p>
      </div>
      <div class="auth-proof">
        <div><b>01</b><span>내 매장 데이터만 안전하게</span></div>
        <div><b>02</b><span>복잡한 입력은 한 단계씩</span></div>
        <div><b>03</b><span>예측 근거와 신뢰도를 함께</span></div>
      </div>
    </section>

    <section class="auth-form-panel">
      <div class="auth-form-card">
        <div class="auth-form-head">
          <span>다시 만나 반가워요</span>
          <h2>로그인</h2>
          <p>오늘의 매장 상태를 이어서 확인하세요.</p>
        </div>

        <form @submit.prevent="handleSubmit">
          <label class="auth-field">
            <span>사용자명</span>
            <input
              v-model="username"
              type="text"
              autocomplete="username"
              placeholder="사용자명을 입력하세요"
              required
            >
          </label>

          <label class="auth-field">
            <span>비밀번호</span>
            <div class="password-field">
              <input
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="current-password"
                placeholder="비밀번호를 입력하세요"
                required
              >
              <button type="button" @click="showPassword = !showPassword">
                {{ showPassword ? '숨기기' : '보기' }}
              </button>
            </div>
          </label>

          <p v-if="authStore.error" class="auth-error">{{ authStore.error }}</p>

          <button class="auth-primary-button" type="submit" :disabled="authStore.loading">
            <span v-if="authStore.loading" class="button-spinner"></span>
            {{ authStore.loading ? '확인하고 있어요' : '로그인' }}
          </button>
        </form>

        <p class="auth-switch">
          아직 계정이 없나요?
          <router-link to="/register">무료로 시작하기</router-link>
        </p>
      </div>
    </section>
  </div>
</template>
