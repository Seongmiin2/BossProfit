<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import { formatKRW } from '@/utils/format'
import SignalBadge from '@/components/SignalBadge.vue'

const dashboardStore = useDashboardStore()
const authStore = useAuthStore()
const router = useRouter()

const showAssumptionModal = ref(false)
const assumptionForm = ref({})
const savedMessage = ref('')

onMounted(() => dashboardStore.load())

const healthScore = computed(() => {
  const summary = dashboardStore.summary
  if (!summary || !dashboardStore.snapshots.length) return 0
  const targetRate = (dashboardStore.assumption?.target_food_cost_rate || 0.35) * 100
  const costPenalty = Math.max(0, summary.avg_food_cost_rate - targetRate) * 2
  const lossPenalty = (summary.delivery_loss_count / dashboardStore.snapshots.length) * 35
  const profitBonus = summary.total_profit > 0 ? 12 : 0
  return Math.round(Math.min(98, Math.max(18, 82 - costPenalty - lossPenalty + profitBonus)))
})

const healthTone = computed(() => {
  if (healthScore.value >= 80) return { label: '아주 건강해요', className: 'good', emoji: '✨' }
  if (healthScore.value >= 60) return { label: '조금만 다듬어요', className: 'care', emoji: '👀' }
  return { label: '지금 관리가 필요해요', className: 'danger', emoji: '🚨' }
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
        <button v-if="authStore.isLoggedIn" class="soft-button desktop-only" @click="dashboardStore.recalculate()">
          ↻ 최신 정보로 계산
        </button>
      </section>

      <section class="health-card" :class="healthTone.className">
        <div class="health-card-top">
          <div>
            <span class="health-label">이번 달 수익 건강</span>
            <h2>{{ healthTone.emoji }} {{ healthTone.label }}</h2>
            <p>{{ dashboardStore.storeName }}의 메뉴 {{ dashboardStore.snapshots.length }}개를 분석했어요.</p>
          </div>
          <div class="score-ring" :style="{ '--score': `${healthScore * 3.6}deg` }">
            <div>
              <strong>{{ healthScore }}</strong>
              <span>점</span>
            </div>
          </div>
        </div>

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
