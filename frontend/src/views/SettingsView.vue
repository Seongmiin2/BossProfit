<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppIcon from '@/components/AppIcon.vue'

const router = useRouter()
const authStore = useAuthStore()

const profileForm = reactive({
  username: authStore.user?.username || '',
  email: authStore.user?.email || '',
})
const storeForm = reactive({
  name: authStore.store?.name || '',
  business_type: authStore.store?.business_type || 'OTHER',
  region: authStore.store?.region || '',
})
const passwordForm = reactive({
  current_password: '',
  new_password: '',
  new_password2: '',
})

const savingSection = ref('')
const messages = reactive({
  profile: '',
  store: '',
  password: '',
})
const errors = reactive({
  profile: '',
  store: '',
  password: '',
})

const initial = computed(() =>
  (authStore.user?.username || 'B').charAt(0).toUpperCase()
)
const isOwner = computed(() => authStore.store?.role === 'OWNER')

function clearState(section) {
  messages[section] = ''
  errors[section] = ''
}

async function saveProfile() {
  clearState('profile')
  savingSection.value = 'profile'
  try {
    await authStore.updateProfile(profileForm)
    messages.profile = '계정 정보를 저장했어요.'
  } catch (error) {
    errors.profile = authStore.extractError(error)
  } finally {
    savingSection.value = ''
  }
}

async function saveStore() {
  clearState('store')
  savingSection.value = 'store'
  try {
    await authStore.updateStore(storeForm)
    messages.store = '매장 정보를 저장했어요.'
  } catch (error) {
    errors.store = authStore.extractError(error)
  } finally {
    savingSection.value = ''
  }
}

async function savePassword() {
  clearState('password')
  savingSection.value = 'password'
  try {
    await authStore.changePassword(passwordForm)
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    passwordForm.new_password2 = ''
    messages.password = '비밀번호를 변경했어요.'
  } catch (error) {
    errors.password = authStore.extractError(error)
  } finally {
    savingSection.value = ''
  }
}

async function logout() {
  await authStore.logout()
  router.replace('/login')
}
</script>

<template>
  <div class="settings-page">
    <section class="settings-hero">
      <div class="settings-avatar">{{ initial }}</div>
      <div class="settings-identity">
        <span>내 정보</span>
        <h1>{{ authStore.user?.username }} 사장님</h1>
        <p>{{ authStore.store?.name || '매장 정보가 아직 없습니다' }}</p>
      </div>
      <div class="settings-role">
        <AppIcon name="shield" :size="17" />
        {{ isOwner ? '매장 소유자' : '매장 구성원' }}
      </div>
    </section>

    <div class="settings-layout">
      <aside class="settings-summary">
        <div class="settings-summary-head">
          <span>관리 메뉴</span>
          <strong>가게와 계정을<br>한곳에서 관리하세요.</strong>
        </div>
        <nav aria-label="설정 메뉴">
          <a href="#account"><AppIcon name="user" /> 계정 정보 <AppIcon name="chevron" :size="16" /></a>
          <a href="#store"><AppIcon name="store" /> 매장 정보 <AppIcon name="chevron" :size="16" /></a>
          <a href="#security"><AppIcon name="lock" /> 보안 설정 <AppIcon name="chevron" :size="16" /></a>
        </nav>
        <div class="settings-data-note">
          <AppIcon name="shield" :size="18" />
          <p><strong>내 매장 데이터만 보여요.</strong><br>다른 매장과 계정 정보는 분리되어 있습니다.</p>
        </div>
      </aside>

      <div class="settings-sections">
        <section id="account" class="settings-panel">
          <div class="settings-panel-head">
            <div class="panel-icon"><AppIcon name="user" /></div>
            <div>
              <span>ACCOUNT</span>
              <h2>계정 정보</h2>
              <p>로그인에 사용하는 사용자명과 연락 이메일입니다.</p>
            </div>
          </div>
          <form class="settings-form" @submit.prevent="saveProfile">
            <label>
              <span>사용자명</span>
              <input v-model.trim="profileForm.username" autocomplete="username" required>
            </label>
            <label>
              <span>이메일 <small>선택</small></span>
              <input v-model.trim="profileForm.email" type="email" autocomplete="email" placeholder="owner@example.com">
            </label>
            <p v-if="errors.profile" class="settings-message error">{{ errors.profile }}</p>
            <p v-if="messages.profile" class="settings-message success">{{ messages.profile }}</p>
            <div class="settings-form-action">
              <button class="settings-save" :disabled="savingSection === 'profile'">
                {{ savingSection === 'profile' ? '저장 중...' : '계정 정보 저장' }}
              </button>
            </div>
          </form>
        </section>

        <section id="store" class="settings-panel">
          <div class="settings-panel-head">
            <div class="panel-icon warm"><AppIcon name="store" /></div>
            <div>
              <span>STORE</span>
              <h2>매장 정보</h2>
              <p>분석과 시장 비교에 사용되는 기본 매장 정보입니다.</p>
            </div>
          </div>
          <form class="settings-form" @submit.prevent="saveStore">
            <label class="wide">
              <span>매장명</span>
              <input v-model.trim="storeForm.name" required :disabled="!isOwner">
            </label>
            <label>
              <span>업종</span>
              <select v-model="storeForm.business_type" :disabled="!isOwner">
                <option value="KOREAN">한식</option>
                <option value="WESTERN">양식</option>
                <option value="JAPANESE">일식</option>
                <option value="CHINESE">중식</option>
                <option value="CAFE">카페·디저트</option>
                <option value="SNACK">분식</option>
                <option value="OTHER">기타</option>
              </select>
            </label>
            <label>
              <span>지역</span>
              <input v-model.trim="storeForm.region" placeholder="예: 서울 마포구" :disabled="!isOwner">
            </label>
            <p v-if="!isOwner" class="settings-message muted">매장 정보는 소유자만 변경할 수 있어요.</p>
            <p v-if="errors.store" class="settings-message error">{{ errors.store }}</p>
            <p v-if="messages.store" class="settings-message success">{{ messages.store }}</p>
            <div class="settings-form-action">
              <button class="settings-save" :disabled="!isOwner || savingSection === 'store'">
                {{ savingSection === 'store' ? '저장 중...' : '매장 정보 저장' }}
              </button>
            </div>
          </form>
        </section>

        <section id="security" class="settings-panel">
          <div class="settings-panel-head">
            <div class="panel-icon dark"><AppIcon name="lock" /></div>
            <div>
              <span>SECURITY</span>
              <h2>비밀번호 변경</h2>
              <p>현재 비밀번호를 확인한 후 새 비밀번호로 변경합니다.</p>
            </div>
          </div>
          <form class="settings-form" @submit.prevent="savePassword">
            <label class="wide">
              <span>현재 비밀번호</span>
              <input v-model="passwordForm.current_password" type="password" autocomplete="current-password" required>
            </label>
            <label>
              <span>새 비밀번호</span>
              <input v-model="passwordForm.new_password" type="password" minlength="6" autocomplete="new-password" required>
            </label>
            <label>
              <span>새 비밀번호 확인</span>
              <input v-model="passwordForm.new_password2" type="password" minlength="6" autocomplete="new-password" required>
            </label>
            <p v-if="errors.password" class="settings-message error">{{ errors.password }}</p>
            <p v-if="messages.password" class="settings-message success">{{ messages.password }}</p>
            <div class="settings-form-action split">
              <button type="button" class="settings-logout" @click="logout">
                <AppIcon name="logout" :size="17" /> 로그아웃
              </button>
              <button class="settings-save" :disabled="savingSection === 'password'">
                {{ savingSection === 'password' ? '변경 중...' : '비밀번호 변경' }}
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  </div>
</template>
