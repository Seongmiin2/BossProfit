<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api/client'
import { fetchStoreAnalysis, postAnalysisFollowUp } from '@/api/endpoints'
import AppIcon from '@/components/AppIcon.vue'
import onionImage from '@/assets/produce/onion.webp'
import cabbageImage from '@/assets/produce/napa-cabbage.webp'
import greenOnionImage from '@/assets/produce/green-onion.webp'
import potatoImage from '@/assets/produce/potato.webp'
import garlicImage from '@/assets/produce/garlic.webp'

const route = useRoute()
const router = useRouter()

const rankingTypes = [
  { key: 'today', label: '오늘 변동', title: '오늘 가격 변동 TOP 5', description: '직전 유효 거래일 대비 등락률 기준' },
  { key: 'tomorrow', label: '내일 전망', title: '내일 예상 변동 TOP 5', description: '내일 중앙 예측값의 예상 등락률 기준' },
]

const images = {
  onion: onionImage,
  'napa-cabbage': cabbageImage,
  'green-onion': greenOnionImage,
  potato: potatoImage,
  garlic: garlicImage,
}

const query = ref(String(route.query.q || ''))
const items = ref([])
const metrics = ref({ is_verified: false })
const asOfDate = ref(null)
const generatedAt = ref(null)
const isDemo = ref(false)
const loading = ref(false)
const error = ref('')
const activeCode = ref('')
const pulseIndex = ref(0)

const activeType = computed(() =>
  rankingTypes.some((item) => item.key === route.params.type) ? route.params.type : 'tomorrow'
)
const currentType = computed(() => rankingTypes.find((item) => item.key === activeType.value))
const activeItem = computed(() =>
  items.value.find((item) => item.code === activeCode.value) || items.value[0] || null
)
const priceChart = computed(() => {
  const history = activeItem.value?.history || []
  const forecast = activeItem.value?.forecast_series || []
  if (!history.length) return null

  const allValues = [
    ...history.map((h) => h.price),
    ...forecast.flatMap((f) => [f.lower, f.upper, f.median]),
  ]
  const min = Math.min(...allValues)
  const max = Math.max(...allValues)
  const range = max - min || 1

  const total = history.length + forecast.length
  const xStep = 100 / Math.max(total - 1, 1)
  const yOf = (v) => +(46 - ((v - min) / range) * 42).toFixed(2)
  const xOf = (i) => +(i * xStep).toFixed(2)

  const histPts = history.map((h, i) => `${xOf(i)},${yOf(h.price)}`)
  const anchorX = xOf(history.length - 1)
  const anchorY = yOf(history[history.length - 1].price)

  const fcLine = forecast.map((f, i) => `${xOf(history.length + i)},${yOf(f.median)}`)
  const upper = forecast.map((f, i) => `${xOf(history.length + i)},${yOf(f.upper)}`)
  const lower = forecast.map((f, i) => `${xOf(history.length + i)},${yOf(f.lower)}`)

  return {
    historyLine: histPts.join(' '),
    forecastLine: forecast.length
      ? [`${anchorX},${anchorY}`, ...fcLine].join(' ')
      : '',
    band: forecast.length
      ? [`${anchorX},${anchorY}`, ...upper, ...lower.reverse(), `${anchorX},${anchorY}`].join(' ')
      : '',
    dividerX: anchorX,
    hasForecast: forecast.length > 0,
    max,
    min,
    current: history[history.length - 1].price,
    forecastEnd: forecast.length ? forecast[forecast.length - 1] : null,
  }
})

function formatPercent(value) {
  if (value === null || value === undefined) return '--'
  return `${value > 0 ? '+' : ''}${Number(value).toFixed(1)}%`
}

function formatPrice(value) {
  if (value === null || value === undefined) return '--'
  return `${Math.round(value).toLocaleString()}원`
}

function rankMovement(item) {
  if (item.rank_delta === null || item.rank_delta === undefined) return { label: 'NEW', tone: 'new' }
  if (item.rank_delta > 0) return { label: `▲ ${item.rank_delta}`, tone: 'up' }
  if (item.rank_delta < 0) return { label: `▼ ${Math.abs(item.rank_delta)}`, tone: 'down' }
  return { label: '―', tone: 'same' }
}

async function loadRanking() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get(`/market/rankings/${activeType.value}/`, {
      params: {
        limit: 5,
        ...(query.value.trim() ? { q: query.value.trim() } : {}),
      },
    })
    items.value = data.items
    metrics.value = data.metrics
    asOfDate.value = data.as_of_date
    generatedAt.value = data.generated_at
    isDemo.value = data.is_demo
    activeCode.value = data.items[0]?.code || ''
    pulseIndex.value = 0
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || '시장 순위를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

function selectType(type) {
  router.push({
    name: 'MarketRanking',
    params: { type },
    query: query.value.trim() ? { q: query.value.trim() } : {},
  })
}

function search() {
  router.replace({
    name: 'MarketRanking',
    params: { type: activeType.value },
    query: query.value.trim() ? { q: query.value.trim() } : {},
  })
  loadRanking()
}

function selectItem(item, index) {
  activeCode.value = item.code
  pulseIndex.value = index
}

/* ── 액션 버튼: 내 가게 영향 계산 / 119 대응 전략 ── */
const actionModal = ref(null)      // { mode: 'impact' | 'advice', title }
const actionLoading = ref(false)
const actionError = ref('')
const impactResult = ref(null)     // 매칭된 risk 항목 | { empty: true }
const adviceAnswer = ref('')

function closeActionModal() {
  actionModal.value = null
}

function goIngredients() {
  closeActionModal()
  router.push('/ingredients')
}

async function openImpact() {
  if (!activeItem.value) return
  actionModal.value = { mode: 'impact', title: '내 가게 영향 계산' }
  actionLoading.value = true
  actionError.value = ''
  impactResult.value = null
  try {
    const { data } = await fetchStoreAnalysis()
    const risks = data?.market_risks?.items || []
    const match = risks.find((risk) => risk.item?.code === activeItem.value.code)
    impactResult.value = match || { empty: true }
  } catch (requestError) {
    actionError.value = requestError.response?.status === 409
      ? '먼저 매장을 등록해주세요.'
      : (requestError.response?.data?.detail || '영향을 계산하지 못했습니다.')
  } finally {
    actionLoading.value = false
  }
}

async function openAdvice() {
  if (!activeItem.value) return
  const item = activeItem.value
  actionModal.value = { mode: 'advice', title: '119 대응 전략' }
  actionLoading.value = true
  actionError.value = ''
  adviceAnswer.value = ''
  const question =
    `${item.name} 가격이 ${formatPercent(item.change_rate)} 전망입니다. `
    + `우리 가게에서 ${item.name}를 쓰는 메뉴의 대응 전략과 `
    + `구매 시점(선구매·관망) 판단을 구체적으로 알려주세요.`
  try {
    const { data } = await postAnalysisFollowUp(question)
    adviceAnswer.value = data.answer
  } catch (requestError) {
    actionError.value = requestError.response?.status === 409
      ? '먼저 매장을 등록해주세요.'
      : (requestError.response?.data?.detail || 'AI 답변을 가져오지 못했습니다.')
  } finally {
    actionLoading.value = false
  }
}

watch(() => route.params.type, loadRanking)
watch(() => route.query.q, () => {
  query.value = String(route.query.q || '')
  loadRanking()
})

onMounted(loadRanking)
</script>

<template>
  <div class="ranking-page">
    <section class="ranking-hero">
      <router-link to="/market" class="ranking-back"><span>←</span> 시장으로</router-link>
      <div class="ranking-hero-main">
        <div>
          <span class="section-kicker">LIVE MARKET RANKING</span>
          <h1>{{ currentType.title }}</h1>
          <p>{{ currentType.description }}으로 현재 움직임, 향후 전망, 구매 판단을 함께 보여줍니다.</p>
        </div>
        <div class="ranking-status">
          <span>마지막 갱신</span>
          <strong>{{ generatedAt ? new Date(generatedAt).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) : '--:--' }}</strong>
          <small>{{ isDemo ? '데모 데이터' : '운영 데이터' }} · {{ asOfDate || '기준일 없음' }}</small>
        </div>
      </div>
    </section>

    <nav class="ranking-type-tabs" aria-label="랭킹 종류">
      <button
        v-for="type in rankingTypes"
        :key="type.key"
        :class="{ active: activeType === type.key }"
        @click="selectType(type.key)"
      >
        {{ type.label }}
      </button>
    </nav>

    <form class="ranking-search" @submit.prevent="search">
      <AppIcon name="chart" :size="19" />
      <input v-model="query" placeholder="품목명으로 검색하세요. 예: 양파" aria-label="랭킹 품목 검색">
      <button>검색</button>
    </form>

    <section class="ranking-engine-strip">
      <div>
        <span>방향 적중률</span>
        <strong>{{ metrics.is_verified ? formatPercent(metrics.direction_accuracy) : '--%' }}</strong>
        <small>{{ metrics.is_verified ? metrics.model_version : 'rolling backtest 연결 전' }}</small>
      </div>
      <div>
        <span>평균 오차 WAPE</span>
        <strong>{{ metrics.is_verified ? formatPercent(metrics.wape) : '--%' }}</strong>
        <small>{{ metrics.is_verified ? '검증 완료' : '품목·horizon별 측정 예정' }}</small>
      </div>
      <div>
        <span>80% 구간 적중률</span>
        <strong>{{ metrics.is_verified ? formatPercent(metrics.interval_coverage) : '--%' }}</strong>
        <small>{{ metrics.is_verified ? `${metrics.evaluation_start}~${metrics.evaluation_end}` : '검증 데이터 연결 전' }}</small>
      </div>
      <p>실제 rolling backtest를 통과한 성능만 공개합니다. 데모 데이터에서는 정확도를 만들지 않습니다.</p>
    </section>

    <div v-if="loading" class="ranking-empty">
      <div class="spinner"></div>
      <strong>시장 순위를 계산하고 있어요.</strong>
    </div>

    <section v-else-if="error" class="ranking-empty">
      <strong>순위를 불러오지 못했습니다.</strong>
      <p>{{ error }}</p>
      <button @click="loadRanking">다시 시도</button>
    </section>

    <div v-else-if="activeItem" class="ranking-layout">
      <section class="ranking-list-panel">
        <div class="ranking-panel-head">
          <div>
            <span>TOP 5</span>
            <h2>주목 품목</h2>
          </div>
          <small>품목을 누르면 상세가 바뀝니다</small>
        </div>

        <button
          v-for="(item, index) in items"
          :key="item.code"
          class="ranking-row"
          :class="{ active: activeItem.code === item.code }"
          @click="selectItem(item, index)"
        >
          <b>{{ String(item.rank).padStart(2, '0') }}</b>
          <img :src="images[item.image_key]" :alt="`${item.name} 신선 식재료`">
          <div>
            <strong>{{ item.name }}</strong>
            <span>{{ item.category }} · {{ item.region }}</span>
          </div>
          <span class="rank-movement" :class="rankMovement(item).tone">{{ rankMovement(item).label }}</span>
          <p>
            <strong>{{ formatPercent(item.change_rate) }}</strong>
            <span>{{ formatPrice(item.current_price) }} / {{ item.unit }}</span>
          </p>
          <i :class="item.decision_tone">{{ item.decision }}</i>
          <span class="row-chevron">›</span>
        </button>
      </section>

      <aside class="ranking-detail-panel">
        <div class="ranking-item-visual">
          <img :src="images[activeItem.image_key]" :alt="`${activeItem.name} 품목 이미지`">
          <div>
            <span>{{ activeItem.category }} · {{ activeItem.region }}</span>
            <h2>{{ activeItem.name }}</h2>
            <p>{{ formatPrice(activeItem.current_price) }} / {{ activeItem.unit }}</p>
          </div>
          <i :class="activeItem.decision_tone">{{ activeItem.decision }}</i>
        </div>

        <p class="ranking-summary">{{ activeItem.summary }}</p>

        <div class="ranking-price-chart" v-if="priceChart">
          <div>
            <span>최근 14일 가격 + 7일 예측</span>
            <strong>{{ formatPercent(activeItem.change_rate) }}</strong>
          </div>
          <div class="chart-canvas">
            <svg viewBox="0 0 100 50" preserveAspectRatio="none" aria-label="최근 가격 흐름과 7일 예측">
              <polygon v-if="priceChart.hasForecast" :points="priceChart.band" class="chart-band" />
              <line v-if="priceChart.hasForecast" :x1="priceChart.dividerX" y1="2" :x2="priceChart.dividerX" y2="48" class="chart-divider" vector-effect="non-scaling-stroke" />
              <polyline :points="priceChart.historyLine" fill="none" stroke="currentColor" stroke-width="2.3" vector-effect="non-scaling-stroke" />
              <polyline v-if="priceChart.hasForecast" :points="priceChart.forecastLine" fill="none" class="chart-forecast" stroke-width="2.3" stroke-dasharray="3 2.5" vector-effect="non-scaling-stroke" />
            </svg>
            <span class="axis-label axis-max">{{ formatPrice(priceChart.max) }}</span>
            <span class="axis-label axis-min">{{ formatPrice(priceChart.min) }}</span>
          </div>
          <div class="chart-prices">
            <span>현재가 <b>{{ formatPrice(priceChart.current) }}</b></span>
            <span v-if="priceChart.forecastEnd">7일 후 예측 <b>{{ formatPrice(priceChart.forecastEnd.median) }}</b> ({{ formatPrice(priceChart.forecastEnd.lower) }}~{{ formatPrice(priceChart.forecastEnd.upper) }})</span>
          </div>
          <div class="chart-legend">
            <span><i class="lg-actual"></i>실제 가격</span>
            <span><i class="lg-forecast"></i>7일 예측</span>
            <span><i class="lg-band"></i>예측 구간</span>
          </div>
        </div>

        <div class="ranking-outlook">
          <div
            v-for="outlook in activeItem.outlooks"
            :key="outlook.horizon_days"
            class="outlook-col"
            :class="outlook.change_rate >= 0 ? 'is-up' : 'is-down'"
          >
            <span>{{ outlook.horizon_days }}일 전망</span>
            <strong>{{ formatPercent(outlook.change_rate) }}</strong>
            <small>{{ formatPrice(outlook.lower_price) }}~{{ formatPrice(outlook.upper_price) }}</small>
            <div class="outlook-track">
              <i :style="{ height: `${6 + Math.min(Math.abs(outlook.change_rate), 12) * 3.4}px` }"></i>
            </div>
          </div>
        </div>

        <section class="ranking-action">
          <span>NEXT ACTION</span>
          <h3>현재 권장 판단</h3>
          <p>{{ activeItem.action }}</p>
          <div>
            <button @click="openImpact">내 가게 영향 계산</button>
            <button class="secondary" @click="openAdvice">119에 대응 전략 묻기</button>
          </div>
        </section>

        <footer>
          <span>데이터 출처</span>
          <p>{{ activeItem.source || 'KAMIS · 공영도매시장 · 주산지 기상 데이터 연동 예정' }}</p>
        </footer>
      </aside>
    </div>

    <section v-else class="ranking-empty">
      <strong>검색 결과가 없습니다.</strong>
      <p>다른 품목명으로 검색해주세요.</p>
      <button @click="query = ''; search()">전체 순위 보기</button>
    </section>

    <!-- 액션 모달: 내 가게 영향 계산 / 119 대응 전략 -->
    <div v-if="actionModal" class="mra-overlay" @click.self="closeActionModal">
      <div class="mra-modal">
        <div class="mra-head">
          <div>
            <span class="mra-eyebrow">{{ activeItem?.name }}</span>
            <h3>{{ actionModal.title }}</h3>
          </div>
          <button class="mra-close" @click="closeActionModal">✕</button>
        </div>

        <div v-if="actionLoading" class="mra-state">
          <div class="spinner"></div>
          <span>{{ actionModal.mode === 'advice' ? 'AI가 대응 전략을 작성 중입니다…' : '매장 데이터를 분석 중입니다…' }}</span>
        </div>

        <div v-else-if="actionError" class="mra-state">
          <strong>{{ actionError }}</strong>
          <button v-if="actionError.includes('매장')" @click="goIngredients">매장·재료 설정하러 가기 →</button>
        </div>

        <!-- 내 가게 영향 계산 -->
        <template v-else-if="actionModal.mode === 'impact'">
          <template v-if="impactResult && !impactResult.empty">
            <div class="mra-summary">
              <div>
                <span>예상 변동률</span>
                <strong :class="impactResult.headline_change_rate >= 0 ? 'mra-up' : 'mra-down'">
                  {{ formatPercent(impactResult.headline_change_rate) }}
                </strong>
              </div>
              <div v-if="impactResult.current_price">
                <span>현재가</span>
                <strong>{{ formatPrice(impactResult.current_price) }} / {{ impactResult.item.unit }}</strong>
              </div>
            </div>
            <p class="mra-msg">{{ impactResult.impact_message }}</p>
            <span class="mra-label">영향받는 내 메뉴</span>
            <div class="mra-menus">
              <button
                v-for="menu in impactResult.affected_menus"
                :key="menu.menu_id"
                class="mra-chip"
                @click="router.push(`/menus/${menu.menu_id}`)"
              >{{ menu.name }} ›</button>
            </div>
          </template>
          <div v-else class="mra-state">
            <strong>{{ activeItem?.name }}를 쓰는 연결된 메뉴가 없습니다.</strong>
            <p>재료를 메뉴에 연결하면 가격 변동의 영향을 계산해드려요.</p>
            <button @click="goIngredients">재료 연결하기 →</button>
          </div>
        </template>

        <!-- 119 대응 전략 -->
        <div v-else class="mra-advice">
          <span class="mra-advice-badge">BUSINESS 119</span>
          <p>{{ adviceAnswer }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mra-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0, 0, 0, .45);
  display: flex; align-items: center; justify-content: center; padding: 20px;
}
.mra-modal {
  width: 100%; max-width: 460px; max-height: 84vh; overflow-y: auto;
  background: #fff; border-radius: 16px; padding: 22px 24px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, .25);
}
.mra-head { display: flex; align-items: flex-start; justify-content: space-between; }
.mra-eyebrow { font-size: 12px; font-weight: 800; color: var(--primary); }
.mra-head h3 { margin-top: 4px; font-size: 20px; font-weight: 900; color: var(--text); }
.mra-close {
  width: 30px; height: 30px; border: none; border-radius: 8px;
  background: #f3f1ec; color: var(--text); font-size: 14px; cursor: pointer;
}

.mra-state {
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  padding: 30px 8px; text-align: center; color: var(--text-soft);
}
.mra-state strong { font-size: 15px; color: var(--text); }
.mra-state p { font-size: 13px; color: var(--text-soft); margin: 0; }
.mra-state button {
  margin-top: 6px; border: none; border-radius: 8px; padding: 10px 18px;
  background: var(--primary); color: #fff; font-weight: 700; font-size: 13px; cursor: pointer;
}

.mra-summary { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 16px 0; }
.mra-summary > div { padding: 12px 14px; border-radius: 12px; background: #faf8f5; }
.mra-summary span { display: block; font-size: 11px; color: var(--text-faint); }
.mra-summary strong { font-size: 18px; font-weight: 900; color: var(--text); }
.mra-summary strong.mra-up { color: #C44536; }
.mra-summary strong.mra-down { color: #2563EB; }

.mra-msg { font-size: 13px; line-height: 1.65; color: var(--text-soft); margin: 0 0 14px; }
.mra-label { display: block; font-size: 11px; font-weight: 800; color: var(--text-faint); margin-bottom: 8px; }
.mra-menus { display: flex; flex-wrap: wrap; gap: 8px; }
.mra-chip {
  border: 1px solid var(--app-line); background: #fff; border-radius: 999px;
  padding: 7px 14px; font-size: 13px; font-weight: 600; color: var(--text); cursor: pointer;
  transition: border-color .15s, background .15s;
}
.mra-chip:hover { border-color: var(--primary); background: #fff7f2; }

.mra-advice-badge {
  display: inline-block; font-size: 11px; font-weight: 800;
  color: var(--primary); background: #fff1ea; border-radius: 6px;
  padding: 3px 9px; margin-bottom: 10px;
}
.mra-advice p { font-size: 14px; line-height: 1.75; color: var(--text); white-space: pre-wrap; margin: 0; }
</style>
