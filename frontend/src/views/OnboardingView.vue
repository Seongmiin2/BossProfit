<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useIngredientStore } from '@/stores/ingredient'
import { useMenuStore } from '@/stores/menu'
import client from '@/api/client'
import BossPersona from '@/components/BossPersona.vue'

const router = useRouter()
const authStore = useAuthStore()
const ingredientStore = useIngredientStore()
const menuStore = useMenuStore()
const localError = ref('')
const saved = ref(false)

const storeForm = reactive({
  name: '',
  business_type: 'KOREAN',
  region: '',
})

const ingredientForm = reactive({
  name: '',
  category: '공통',
  purchase_quantity: '',
  purchase_price: '',
  unit: 'g',
  memo: '',
})

const menuForm = reactive({
  name: '',
  category: '기타',
  price: '',
  monthly_orders: '',
  packaging_cost: 0,
  quantity: '',
})
const saleForm = reactive({
  menu_id: '',
  sale_date: new Date().toISOString().slice(0, 10),
  quantity: '',
})

const currentStep = computed(() => authStore.onboarding?.current_step || 'STORE')
const stepNumber = computed(() => ({
  STORE: 1,
  INGREDIENT: 2,
  MENU: 3,
  RECIPE: 3,
  SALES: 4,
  COMPLETE: 5,
}[currentStep.value] || 1))

const generatedIngredientId = computed(() =>
  `ING_${Date.now().toString(36).toUpperCase()}`
)
const generatedMenuId = computed(() =>
  `MENU_${Date.now().toString(36).toUpperCase()}`
)

async function refresh() {
  await authStore.loadUser()
}

async function saveStore() {
  localError.value = ''
  try {
    await authStore.createStore(storeForm)
    saved.value = true
    setTimeout(() => { saved.value = false }, 700)
  } catch {
    localError.value = authStore.error
  }
}

async function saveIngredient() {
  localError.value = ''
  try {
    await ingredientStore.createIngredient({
      ...ingredientForm,
      ingredient_id: generatedIngredientId.value,
      purchase_quantity: Number(ingredientForm.purchase_quantity),
      purchase_price: Number(ingredientForm.purchase_price),
    })
    await refresh()
    saved.value = true
    setTimeout(() => { saved.value = false }, 700)
  } catch {
    localError.value = ingredientStore.error
  }
}

async function saveMenu() {
  localError.value = ''
  const ingredient = ingredientStore.ingredients[0]
  if (!ingredient) {
    await ingredientStore.loadList()
  }
  const selectedIngredient = ingredientStore.ingredients[0]
  if (!selectedIngredient) {
    localError.value = '먼저 재료를 한 개 등록해주세요.'
    return
  }
  try {
    await menuStore.createMenu({
      menu_id: generatedMenuId.value,
      name: menuForm.name,
      category: menuForm.category,
      price: Number(menuForm.price),
      monthly_orders: Number(menuForm.monthly_orders || 0),
      packaging_cost: Number(menuForm.packaging_cost || 0),
      is_active: true,
      recipe_items: [{
        ingredient_id: selectedIngredient.ingredient_id,
        quantity: Number(menuForm.quantity),
        memo: '최초 온보딩 등록',
      }],
    })
    await refresh()
    saved.value = true
    setTimeout(() => { saved.value = false }, 700)
  } catch {
    localError.value = menuStore.error
  }
}

async function prepareMenuStep() {
  if (!ingredientStore.ingredients.length) {
    await ingredientStore.loadList()
  }
}

watch(currentStep, (value) => {
  if (value === 'MENU' || value === 'RECIPE') prepareMenuStep()
  if (value === 'SALES') {
    menuStore.loadList().then(() => {
      saleForm.menu_id = menuStore.menus[0]?.menu.menu_id || ''
    })
  }
}, { immediate: true })

async function saveSales() {
  localError.value = ''
  try {
    await client.post('/sales/daily/', {
      menu_id: saleForm.menu_id,
      sale_date: saleForm.sale_date,
      quantity: Number(saleForm.quantity),
      channel: 'ALL',
    })
    await refresh()
    saved.value = true
    setTimeout(() => { saved.value = false }, 700)
  } catch (e) {
    localError.value = e.response?.data?.detail || '판매량을 저장하지 못했어요.'
  }
}

async function exitOnboarding() {
  await authStore.logout()
  router.replace('/login')
}
</script>

<template>
  <div class="onboarding-page">
    <header class="onboarding-topbar">
      <router-link to="/" class="auth-logo" aria-label="BOSSPROFIT 메인으로 이동">
        <span>B</span>
        <strong>BOSSPROFIT</strong>
      </router-link>
      <button @click="exitOnboarding">나가기</button>
    </header>

    <main class="onboarding-shell">
      <aside class="onboarding-guide">
        <span class="auth-kicker">내 매장 시작하기</span>
        <h1>하나씩 입력하면<br>첫 분석이 완성돼요.</h1>
        <p>지금 필요한 정보만 묻고 다음 단계는 저장 후에 보여드릴게요.</p>
        <div class="onboarding-persona-cue">
          <BossPersona
            persona="male"
            alt="매장 입력을 안내하는 사장님 페르소나"
          />
          <span>하나씩, 저장하면서</span>
        </div>

        <ol class="onboarding-steps">
          <li :class="{ active: stepNumber === 1, done: stepNumber > 1 }"><b>1</b><span>매장 정보</span></li>
          <li :class="{ active: stepNumber === 2, done: stepNumber > 2 }"><b>2</b><span>첫 재료</span></li>
          <li :class="{ active: stepNumber === 3, done: stepNumber > 3 }"><b>3</b><span>첫 메뉴·레시피</span></li>
          <li :class="{ active: stepNumber === 4, done: stepNumber > 4 }"><b>4</b><span>판매 데이터</span></li>
          <li :class="{ active: stepNumber === 5 }"><b>5</b><span>첫 분석</span></li>
        </ol>
      </aside>

      <section class="onboarding-workspace">
        <Transition name="step-slide" mode="out-in">
          <form
            v-if="currentStep === 'STORE'"
            key="store"
            class="onboarding-card"
            @submit.prevent="saveStore"
          >
            <div class="onboarding-card-head">
              <span>1단계</span>
              <h2>어떤 매장을 운영하고 계세요?</h2>
              <p>분석 결과에 표시할 기본 정보입니다.</p>
            </div>
            <label class="auth-field">
              <span>매장명</span>
              <input v-model="storeForm.name" placeholder="예: 민이네 돈까스" required autofocus>
            </label>
            <label class="auth-field">
              <span>업종</span>
              <select v-model="storeForm.business_type">
                <option value="KOREAN">한식</option>
                <option value="WESTERN">양식</option>
                <option value="JAPANESE">일식</option>
                <option value="CHINESE">중식</option>
                <option value="CAFE">카페·디저트</option>
                <option value="SNACK">분식</option>
                <option value="OTHER">기타</option>
              </select>
            </label>
            <label class="auth-field">
              <span>지역 <small>선택</small></span>
              <input v-model="storeForm.region" placeholder="예: 서울 마포구">
            </label>
            <p v-if="localError" class="auth-error">{{ localError }}</p>
            <button class="auth-primary-button" :disabled="authStore.loading">
              {{ authStore.loading ? '매장을 만들고 있어요' : '매장 등록하기' }}
            </button>
          </form>

          <form
            v-else-if="currentStep === 'INGREDIENT'"
            key="ingredient"
            class="onboarding-card"
            @submit.prevent="saveIngredient"
          >
            <div class="onboarding-card-head">
              <span>2단계</span>
              <h2>가장 자주 쓰는 재료부터 등록할게요.</h2>
              <p>실제로 구입한 포장 단위와 가격을 그대로 입력해주세요.</p>
            </div>
            <label class="auth-field">
              <span>재료명</span>
              <input v-model="ingredientForm.name" placeholder="예: 돼지고기 등심" required autofocus>
            </label>
            <div class="onboarding-two-column">
              <label class="auth-field">
                <span>구매가격</span>
                <div class="unit-input"><input v-model="ingredientForm.purchase_price" type="number" inputmode="numeric" min="0" required><b>원</b></div>
              </label>
              <label class="auth-field">
                <span>구매량</span>
                <div class="unit-input"><input v-model="ingredientForm.purchase_quantity" type="number" inputmode="decimal" min="0.01" step="0.01" required><b>{{ ingredientForm.unit }}</b></div>
              </label>
            </div>
            <label class="auth-field">
              <span>단위</span>
              <select v-model="ingredientForm.unit">
                <option>g</option><option>kg</option><option>ml</option><option>l</option><option>개</option><option>팩</option>
              </select>
            </label>
            <div v-if="ingredientForm.purchase_price && ingredientForm.purchase_quantity" class="live-calculation">
              <span>계산된 단위 원가</span>
              <strong>{{ (ingredientForm.purchase_price / ingredientForm.purchase_quantity).toFixed(2) }}원 / {{ ingredientForm.unit }}</strong>
            </div>
            <p v-if="localError" class="auth-error">{{ localError }}</p>
            <button class="auth-primary-button" :disabled="ingredientStore.loading">
              {{ ingredientStore.loading ? '재료를 저장하고 있어요' : '첫 재료 저장하기' }}
            </button>
          </form>

          <form
            v-else-if="currentStep === 'MENU' || currentStep === 'RECIPE'"
            key="menu"
            class="onboarding-card"
            @submit.prevent="saveMenu"
          >
            <div class="onboarding-card-head">
              <span>3단계</span>
              <h2>첫 메뉴와 레시피를 연결해볼게요.</h2>
              <p>방금 등록한 재료가 이 메뉴에 얼마나 들어가는지 알려주세요.</p>
            </div>
            <label class="auth-field">
              <span>메뉴명</span>
              <input v-model="menuForm.name" placeholder="예: 왕돈까스" required autofocus>
            </label>
            <div class="onboarding-two-column">
              <label class="auth-field">
                <span>판매가</span>
                <div class="unit-input"><input v-model="menuForm.price" type="number" inputmode="numeric" min="1" required><b>원</b></div>
              </label>
              <label class="auth-field">
                <span>최근 월 판매량</span>
                <div class="unit-input"><input v-model="menuForm.monthly_orders" type="number" inputmode="numeric" min="0"><b>건</b></div>
              </label>
            </div>
            <div class="linked-ingredient-card" v-if="ingredientStore.ingredients[0]">
              <div>
                <span>사용 재료</span>
                <strong>{{ ingredientStore.ingredients[0].name }}</strong>
              </div>
              <label class="unit-input compact">
                <input v-model="menuForm.quantity" type="number" inputmode="decimal" min="0.01" step="0.01" required>
                <b>{{ ingredientStore.ingredients[0].unit }}</b>
              </label>
            </div>
            <p v-if="localError" class="auth-error">{{ localError }}</p>
            <button class="auth-primary-button" :disabled="menuStore.loading">
              {{ menuStore.loading ? '메뉴 원가를 계산하고 있어요' : '메뉴와 레시피 저장하기' }}
            </button>
          </form>

          <form
            v-else-if="currentStep === 'SALES'"
            key="sales"
            class="onboarding-card"
            @submit.prevent="saveSales"
          >
            <div class="onboarding-card-head">
              <span>4단계</span>
              <h2>오늘 판매량을 입력해볼까요?</h2>
              <p>앞으로 매일 쌓이는 판매 데이터가 수요 예측의 핵심이 됩니다.</p>
            </div>
            <label class="auth-field">
              <span>메뉴</span>
              <select v-model="saleForm.menu_id" required>
                <option
                  v-for="snap in menuStore.menus"
                  :key="snap.menu.menu_id"
                  :value="snap.menu.menu_id"
                >
                  {{ snap.menu.name }}
                </option>
              </select>
            </label>
            <label class="auth-field">
              <span>판매일</span>
              <input v-model="saleForm.sale_date" type="date" required>
            </label>
            <label class="auth-field">
              <span>판매량</span>
              <div class="unit-input">
                <input
                  v-model="saleForm.quantity"
                  type="number"
                  inputmode="numeric"
                  min="0"
                  placeholder="오늘 몇 개 판매했나요?"
                  required
                >
                <b>건</b>
              </div>
            </label>
            <div class="data-purpose-note">
              <strong>이 데이터는 이렇게 사용돼요</strong>
              <span>요일별 판매 패턴과 30·60·90일 수요 예측의 학습 데이터가 됩니다.</span>
            </div>
            <p v-if="localError" class="auth-error">{{ localError }}</p>
            <button class="auth-primary-button">판매량 저장하고 분석 만들기</button>
          </form>

          <div v-else key="complete" class="onboarding-card onboarding-next-ready">
            <div class="complete-check">✓</div>
            <span class="auth-kicker">첫 분석 준비 완료</span>
            <h2>사장님의 첫 매장 데이터가 연결됐어요.</h2>
            <p>이제부터 구매가격과 판매량을 쌓을수록 예측과 전략이 더 정교해집니다.</p>
            <button class="auth-primary-button" @click="router.replace('/app')">
              내 매장 홈으로 이동
            </button>
          </div>
        </Transition>

        <div v-if="saved" class="onboarding-toast">저장했어요. 다음 단계로 이동합니다.</div>
      </section>
    </main>
  </div>
</template>
