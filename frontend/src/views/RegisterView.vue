<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const step = ref(1)
const username = ref('')
const password = ref('')
const password2 = ref('')
const agreed = ref(false)
const localError = ref('')
const showPassword = ref(false)

const progress = computed(() => `${step.value * 25}%`)

function nextFromUsername() {
  localError.value = ''
  if (username.value.trim().length < 3) {
    localError.value = '사용자명은 3자 이상 입력해주세요.'
    return
  }
  step.value = 2
}

function nextFromPassword() {
  localError.value = ''
  if (password.value.length < 6) {
    localError.value = '비밀번호는 6자 이상 입력해주세요.'
    return
  }
  if (password.value !== password2.value) {
    localError.value = '비밀번호가 서로 일치하지 않아요.'
    return
  }
  step.value = 3
}

async function handleSubmit() {
  localError.value = ''
  if (!agreed.value) {
    localError.value = '서비스 이용을 위해 필수 약관에 동의해주세요.'
    return
  }
  try {
    await authStore.register(
      username.value.trim(),
      password.value,
      password2.value,
    )
    step.value = 4
    setTimeout(() => router.replace('/onboarding'), 900)
  } catch {
    if (authStore.error?.includes('사용자명')) step.value = 1
  }
}
</script>

<template>
  <div class="auth-layout">
    <section class="auth-brand-panel register-brand">
      <router-link to="/" class="auth-logo">
        <span>B</span>
        <strong>BOSSPROFIT</strong>
      </router-link>
      <div class="auth-brand-copy">
        <span class="auth-kicker">3분이면 시작할 수 있어요</span>
        <h1>한 번에 하나씩,<br>필요한 것만 물을게요.</h1>
        <p>가입 후 매장과 첫 재료, 첫 메뉴를 순서대로 등록합니다.</p>
      </div>
      <div class="auth-step-preview">
        <span :class="{ active: step >= 1 }">계정</span>
        <i></i>
        <span :class="{ active: step >= 2 }">보안</span>
        <i></i>
        <span :class="{ active: step >= 3 }">약관</span>
        <i></i>
        <span :class="{ active: step >= 4 }">완료</span>
      </div>
    </section>

    <section class="auth-form-panel">
      <div class="auth-form-card register-card">
        <div class="auth-progress"><span :style="{ width: progress }"></span></div>

        <Transition name="step-slide" mode="out-in">
          <div v-if="step === 1" key="username" class="auth-step">
            <div class="auth-form-head">
              <span>1 / 4</span>
              <h2>어떻게 불러드릴까요?</h2>
              <p>로그인과 매장 화면에서 사용할 사용자명을 입력해주세요.</p>
            </div>
            <label class="auth-field">
              <span>사용자명</span>
              <input
                v-model="username"
                type="text"
                autocomplete="username"
                placeholder="예: bossprofit"
                autofocus
                @keyup.enter="nextFromUsername"
              >
              <small>영문, 숫자를 포함해 3자 이상 권장합니다.</small>
            </label>
            <p v-if="localError || authStore.error" class="auth-error">
              {{ localError || authStore.error }}
            </p>
            <button class="auth-primary-button" type="button" @click="nextFromUsername">
              다음
            </button>
          </div>

          <div v-else-if="step === 2" key="password" class="auth-step">
            <button class="auth-back" @click="step = 1">← 이전</button>
            <div class="auth-form-head">
              <span>2 / 4</span>
              <h2>계정을 안전하게 지켜주세요.</h2>
              <p>다른 서비스에서 사용하지 않는 비밀번호를 권장합니다.</p>
            </div>
            <label class="auth-field">
              <span>비밀번호</span>
              <div class="password-field">
                <input
                  v-model="password"
                  :type="showPassword ? 'text' : 'password'"
                  autocomplete="new-password"
                  placeholder="6자 이상 입력"
                >
                <button type="button" @click="showPassword = !showPassword">
                  {{ showPassword ? '숨기기' : '보기' }}
                </button>
              </div>
            </label>
            <label class="auth-field">
              <span>비밀번호 확인</span>
              <input
                v-model="password2"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="new-password"
                placeholder="한 번 더 입력"
                @keyup.enter="nextFromPassword"
              >
            </label>
            <p v-if="localError" class="auth-error">{{ localError }}</p>
            <button class="auth-primary-button" type="button" @click="nextFromPassword">
              다음
            </button>
          </div>

          <div v-else-if="step === 3" key="terms" class="auth-step">
            <button class="auth-back" @click="step = 2">← 이전</button>
            <div class="auth-form-head">
              <span>3 / 4</span>
              <h2>마지막으로 확인해주세요.</h2>
              <p>매장 데이터는 사용자별로 분리해 안전하게 관리합니다.</p>
            </div>
            <label class="terms-card">
              <input v-model="agreed" type="checkbox">
              <span>
                <strong>필수 약관에 동의합니다.</strong>
                <small>서비스 이용약관 및 개인정보 처리방침</small>
              </span>
            </label>
            <p v-if="localError || authStore.error" class="auth-error">
              {{ localError || authStore.error }}
            </p>
            <button
              class="auth-primary-button"
              type="button"
              :disabled="authStore.loading"
              @click="handleSubmit"
            >
              <span v-if="authStore.loading" class="button-spinner"></span>
              {{ authStore.loading ? '계정을 만들고 있어요' : '가입 완료' }}
            </button>
          </div>

          <div v-else key="complete" class="auth-complete">
            <div class="complete-check">✓</div>
            <h2>가입이 완료됐어요.</h2>
            <p>이제 사장님의 매장을 하나씩 설정해볼게요.</p>
          </div>
        </Transition>

        <p v-if="step < 4" class="auth-switch">
          이미 계정이 있나요?
          <router-link to="/login">로그인</router-link>
        </p>
      </div>
    </section>
  </div>
</template>
