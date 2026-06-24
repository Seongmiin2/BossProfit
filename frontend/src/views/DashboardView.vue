<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import { formatKRW } from '@/utils/format'
import SignalBadge from '@/components/SignalBadge.vue'
import BossPersona from '@/components/BossPersona.vue'

const dashboardStore = useDashboardStore()
const authStore = useAuthStore()
const router = useRouter()

const showAssumptionModal = ref(false)
const showHealthCriteria = ref(false)
const assumptionForm = ref({})
const savedMessage = ref('')

onMounted(() => dashboardStore.load())

const healthCriteria = computed(() => {
  const summary = dashboardStore.summary
  if (!summary || !dashboardStore.snapshots.length) return []
  const targetRate = (dashboardStore.assumption?.target_food_cost_rate || 0.35) * 100
  return [
    {
      label: '월 예상 이익',
      value: `${formatKRW(summary.total_profit)}원`,
      passed: summary.total_profit > 0,
      description: '예상 이익이 0원보다 큰지 확인합니다.',
    },
    {
      label: '평균 원가율',
      value: `${summary.avg_food_cost_rate.toFixed(1)}%`,
      passed: summary.avg_food_cost_rate <= targetRate,
      description: `설정한 목표 원가율 ${targetRate.toFixed(0)}% 이내인지 확인합니다.`,
    },
    {
      label: '배달 손실 메뉴',
      value: `${summary.delivery_loss_count}개`,
      passed: summary.delivery_loss_count === 0,
      description: '배달 판매 시 적자가 발생하는 메뉴가 없는지 확인합니다.',
    },
  ]
})

const passedHealthCriteria = computed(() =>
  healthCriteria.value.filter((item) => item.passed).length
)

const healthTone = computed(() => {
  if (passedHealthCriteria.value === 3) {
    return { label: '현재 기준은 안정적이에요', className: 'good' }
  }
  if (passedHealthCriteria.value === 2) {
    return { label: '한 가지를 점검해보세요', className: 'care' }
  }
  return { label: '우선 확인할 항목이 있어요', className: 'danger' }
})

const profitRate = computed(() => {
  const summary = dashboardStore.summary
  if (!summary?.total_revenue) return 0
  return (summary.total_profit / summary.total_revenue) * 100
})

const attentionMenus = computed(() =>
  dashboardStore.snapshots
    .filter((snap) => snap.signal_color !== 'green')
    .sort((a, b) => a.monthly_profit - b.monthly_profit)
    .slice(0, 3)
)

const bestMenu = computed(() =>
  [...dashboardStore.snapshots].sort((a, b) => b.monthly_profit - a.monthly_profit)[0]
)

const primaryAction = computed(() => {
  if (dashboardStore.summary?.delivery_loss_count > 0) {
    return {
      eyebrow: '오늘 먼저 볼 것',
      title: `배달 손실 메뉴가 ${dashboardStore.summary.delivery_loss_count}개 있어요`,
      description: '배달 가격이나 최소 주문 금액을 조정하면 수익을 지킬 수 있어요.',
      button: '손실 메뉴 확인',
      path: '/menus',
      icon: '🛵',
    }
  }
  return {
    eyebrow: '오늘의 추천',
    title: '현재 수익 구조가 안정적이에요',
    description: '잘 팔리는 메뉴의 판매 흐름을 리포트에서 확인해보세요.',
    button: '리포트 보기',
    path: '/history',
    icon: '🌱',
  }
})

const openAssumptionModal = () => {
  assumptionForm.value = { ...dashboardStore.assumption }
  savedMessage.value = ''
  showAssumptionModal.value = true
}

const closeAssumptionModal = () => {
  showAssumptionModal.value = false
  savedMessage.value = ''
}

const handleAssumptionSubmit = async () => {
  try {
    await dashboardStore.updateAssumption(assumptionForm.value)
    savedMessage.value = '새 조건으로 수익을 다시 계산했어요.'
    setTimeout(closeAssumptionModal, 900)
  } catch {
    savedMessage.value = ''
  }
}
</script>

<template>
  <div class="home-page">
    <div v-if="dashboardStore.loading" class="state-card">
      <div class="spinner"></div>
      <strong>가게 수익을 살펴보고 있어요</strong>
      <p>잠시만 기다려주세요.</p>
    </div>

    <div v-else-if="dashboardStore.error" class="state-card state-error">
      <span>!</span>
      <strong>정보를 불러오지 못했어요</strong>
      <p>{{ dashboardStore.error }}</p>
      <button class="primary-button" @click="dashboardStore.load()">다시 시도</button>
    </div>

    <template v-else-if="dashboardStore.summary">
      <section class="welcome-row">
        <div>
          <p class="eyebrow">오늘의 BOSSPROFIT</p>
          <h1>
            {{ authStore.user?.username ? `${authStore.user.username} 사장님,` : '사장님,' }}
            <br>
            가게 수익을 확인해볼까요?
          </h1>
        </div>
        <div class="welcome-actions desktop-only">
          <div class="dashboard-personas" aria-label="BOSSPROFIT 남녀 사장님 페르소나">
            <div>
              <BossPersona persona="female" alt="" />
              <BossPersona persona="male" alt="" />
            </div>
            <p><strong>함께 보는 오늘</strong><span>시장과 매장을 한눈에</span></p>
          </div>
          <button v-if="authStore.isLoggedIn" class="soft-button" @click="dashboardStore.recalculate()">
            ↻ 최신 정보로 계산
          </button>
        </div>
      </section>

      <section class="health-card" :class="healthTone.className">
        <div class="health-card-top">
          <div class="health-card-copy">
            <div class="health-label-row">
              <span class="health-label">이번 달 운영 체크</span>
              <button
                class="health-criteria-toggle"
                type="button"
                :aria-expanded="showHealthCriteria"
                @click="showHealthCriteria = !showHealthCriteria"
              >
                판단 기준
              </button>
            </div>
            <h2>{{ healthTone.label }}</h2>
            <p>{{ dashboardStore.storeName }}의 메뉴 {{ dashboardStore.snapshots.length }}개를 분석했어요.</p>
          </div>
          <div
            class="score-ring"
            :style="{ '--score': `${(passedHealthCriteria / 3) * 360}deg` }"
            :aria-label="`운영 체크 기준 3개 중 ${passedHealthCriteria}개 양호`"
          >
            <div class="score-ring-content">
              <strong>{{ passedHealthCriteria }}<small>/3</small></strong>
              <span>양호</span>
            </div>
          </div>
        </div>

        <Transition name="criteria-reveal">
          <div v-if="showHealthCriteria" class="health-criteria-panel">
            <div
              v-for="criterion in healthCriteria"
              :key="criterion.label"
              class="health-criterion"
              :class="{ passed: criterion.passed }"
            >
              <span class="criterion-status">{{ criterion.passed ? '✓' : '!' }}</span>
              <div>
                <strong>{{ criterion.label }}</strong>
                <p>{{ criterion.description }}</p>
              </div>
              <b>{{ criterion.value }}</b>
            </div>
            <small>이 값은 예측 모델 점수가 아니라 현재 매장 데이터를 확인하는 3가지 운영 기준입니다.</small>
          </div>
        </Transition>

        <div class="health-summary">
          <div>
            <span>예상 월이익</span>
            <strong>{{ formatKRW(dashboardStore.summary.total_profit) }}원</strong>
          </div>
          <div>
            <span>매출 대비 이익</span>
            <strong>{{ profitRate.toFixed(1) }}%</strong>
          </div>
          <div>
            <span>평균 원가율</span>
            <strong>{{ dashboardStore.summary.avg_food_cost_rate.toFixed(1) }}%</strong>
          </div>
        </div>
      </section>

      <section class="action-card">
        <div class="action-icon">{{ primaryAction.icon }}</div>
        <div class="action-copy">
          <span>{{ primaryAction.eyebrow }}</span>
          <h2>{{ primaryAction.title }}</h2>
          <p>{{ primaryAction.description }}</p>
        </div>
        <button class="action-button" @click="router.push(primaryAction.path)">
          {{ primaryAction.button }} <span>→</span>
        </button>
      </section>

      <section class="section-block">
        <div class="section-title-row">
          <div>
            <span class="section-kicker">한눈에 보기</span>
            <h2>이번 달 가게 숫자</h2>
          </div>
          <router-link to="/history">자세히 보기</router-link>
        </div>

        <div class="metric-grid">
          <article class="metric-card metric-primary">
            <span class="metric-icon">₩</span>
            <p>예상 매출</p>
            <strong>{{ formatKRW(dashboardStore.summary.total_revenue) }}원</strong>
            <small>총 {{ formatKRW(dashboardStore.summary.total_orders) }}건 주문 기준</small>
          </article>
          <article class="metric-card">
            <span class="metric-icon mint">✓</span>
            <p>가장 든든한 메뉴</p>
            <strong>{{ bestMenu?.menu.name || '-' }}</strong>
            <small v-if="bestMenu">월이익 {{ formatKRW(bestMenu.monthly_profit) }}원</small>
          </article>
          <article class="metric-card">
            <span class="metric-icon orange">!</span>
            <p>살펴볼 메뉴</p>
            <strong>{{ attentionMenus.length }}개</strong>
            <small>가격과 원가를 확인해보세요</small>
          </article>
        </div>
      </section>

      <section class="section-block">
        <div class="section-title-row">
          <div>
            <span class="section-kicker">BOSSPROFIT 인사이트</span>
            <h2>숫자 속에서 찾은 이야기</h2>
          </div>
        </div>
        <div class="story-list">
          <article v-for="(insight, index) in dashboardStore.insights" :key="insight.label" class="story-card">
            <span class="story-number">{{ String(index + 1).padStart(2, '0') }}</span>
            <div>
              <strong>{{ insight.label }}</strong>
              <p>{{ insight.comment }}</p>
            </div>
            <b>{{ insight.value }}</b>
          </article>
        </div>
      </section>

      <section v-if="attentionMenus.length" class="section-block">
        <div class="section-title-row">
          <div>
            <span class="section-kicker">관리 추천</span>
            <h2>먼저 살펴보면 좋은 메뉴</h2>
          </div>
          <router-link to="/menus">전체 메뉴</router-link>
        </div>
        <div class="attention-list">
          <button
            v-for="snap in attentionMenus"
            :key="snap.menu.menu_id"
            class="attention-item"
            @click="router.push({ name: 'MenuDetail', params: { menuId: snap.menu.menu_id } })"
          >
            <div class="menu-symbol">{{ snap.menu.name.charAt(0) }}</div>
            <div class="attention-copy">
              <strong>{{ snap.menu.name }}</strong>
              <span>원가율 {{ (snap.food_cost_rate * 100).toFixed(1) }}% · 월 {{ snap.menu.monthly_orders }}건</span>
            </div>
            <SignalBadge :signal="snap.signal" :signal-color="snap.signal_color" />
            <span class="chevron">›</span>
          </button>
        </div>
      </section>

      <section class="store-settings-card">
        <div>
          <span class="section-kicker">계산 기준</span>
          <h2>{{ dashboardStore.assumption?.label }}</h2>
          <p>
            홀 {{ Math.round((dashboardStore.assumption?.dine_in_share || 0) * 100) }}% ·
            배달 {{ Math.round((dashboardStore.assumption?.delivery_share || 0) * 100) }}% ·
            포장 {{ Math.round((dashboardStore.assumption?.takeout_share || 0) * 100) }}%
          </p>
        </div>
        <button v-if="authStore.isLoggedIn" class="soft-button" @click="openAssumptionModal">조건 바꾸기</button>
      </section>
    </template>

    <div v-else class="state-card">
      <strong>아직 분석할 데이터가 없어요</strong>
      <p>메뉴와 재료를 추가하면 수익 상태를 알려드릴게요.</p>
      <button class="primary-button" @click="router.push('/menus')">메뉴 확인하기</button>
    </div>

    <div v-if="showAssumptionModal" class="modal-backdrop" @click.self="closeAssumptionModal">
      <div class="app-modal">
        <div class="modal-handle"></div>
        <div class="modal-head">
          <div>
            <span class="section-kicker">내 매장 설정</span>
            <h2>수익 계산 조건</h2>
          </div>
          <button class="modal-close" @click="closeAssumptionModal">×</button>
        </div>

        <form @submit.prevent="handleAssumptionSubmit">
          <label class="field">
            <span>설정 이름</span>
            <input v-model="assumptionForm.label" type="text">
          </label>

          <div class="form-section">
            <strong>판매 비중</strong>
            <p>세 항목의 합이 100%가 되도록 입력해주세요.</p>
            <div class="share-grid">
              <label class="field compact">
                <span>홀</span>
                <div><input v-model.number="assumptionForm.dine_in_share" type="number" step="0.01" min="0" max="1"><b>비율</b></div>
              </label>
              <label class="field compact">
                <span>배달</span>
                <div><input v-model.number="assumptionForm.delivery_share" type="number" step="0.01" min="0" max="1"><b>비율</b></div>
              </label>
              <label class="field compact">
                <span>포장</span>
                <div><input v-model.number="assumptionForm.takeout_share" type="number" step="0.01" min="0" max="1"><b>비율</b></div>
              </label>
            </div>
          </div>

          <div class="two-column-fields">
            <label class="field">
              <span>배달앱 수수료율</span>
              <input v-model.number="assumptionForm.delivery_commission_rate" type="number" step="0.01" min="0" max="1">
            </label>
            <label class="field">
              <span>배달 기사 수수료</span>
              <input v-model.number="assumptionForm.rider_fee" type="number" min="0">
            </label>
            <label class="field">
              <span>기사료 가게 부담률</span>
              <input v-model.number="assumptionForm.rider_fee_store_share" type="number" step="0.01" min="0" max="1">
            </label>
            <label class="field">
              <span>목표 원가율</span>
              <input v-model.number="assumptionForm.target_food_cost_rate" type="number" step="0.01" min="0" max="1">
            </label>
          </div>

          <p v-if="dashboardStore.error" class="form-error">{{ dashboardStore.error }}</p>
          <p v-if="savedMessage" class="form-success">{{ savedMessage }}</p>

          <button type="submit" class="primary-button full-button">저장하고 다시 계산하기</button>
        </form>
      </div>
    </div>
  </div>
</template>
