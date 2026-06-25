<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')

async function handleSubmit() {
  try {
    await authStore.login(username.value, password.value)
    router.push('/dashboard')
  } catch (e) {
    // 에러는 authStore.error에 저장됨
  }
}

function goToRegister() {
  router.push('/register')
}
</script>

<template>
  <div style="max-width: 400px; margin: 60px auto;">
    <div class="banner">
      <h1><span class="coral">BOSSPROFIT</span><br>로그인</h1>
    </div>

    <div style="background: var(--paper); padding: 32px; border: 1px solid var(--line);">
      <form @submit.prevent="handleSubmit">
        <div class="mb-3">
          <label class="form-label">사용자명</label>
          <input
            v-model="username"
            type="text"
            class="form-control"
            placeholder="사용자명 입력"
            required
          />
        </div>

        <div class="mb-3">
          <label class="form-label">비밀번호</label>
          <input
            v-model="password"
            type="password"
            class="form-control"
            placeholder="비밀번호 입력"
            required
          />
        </div>

        <div v-if="authStore.error" style="color: var(--coral-deep); margin-bottom: 16px; font-size: 14px;">
          ⚠️ {{ authStore.error }}
        </div>

        <button
          type="submit"
          class="btn-coral w-100"
          :disabled="authStore.loading"
          style="padding: 12px; font-weight: 700;"
        >
          {{ authStore.loading ? '로그인 중...' : '로그인' }}
        </button>
      </form>

      <div style="margin-top: 16px; text-align: center; font-size: 14px;">
        계정이 없으신가요?
        <a @click="goToRegister" style="color: var(--coral); cursor: pointer; font-weight: 700;">
          회원가입
        </a>
      </div>
    </div>
  </div>
</template>
