<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api/client'
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
          <div v-for="outlook in activeItem.outlooks" :key="outlook.horizon_days">
            <span>{{ outlook.horizon_days }}일 전망</span>
            <strong>{{ formatPercent(outlook.change_rate) }}</strong>
            <small>{{ formatPrice(outlook.lower_price) }}~{{ formatPrice(outlook.upper_price) }}</small>
            <i :style="{ height: `${30 + Math.min(Math.abs(outlook.change_rate), 12) * 4}px` }"></i>
          </div>
        </div>

        <section class="ranking-evidence">
          <span>WHY THIS RANK?</span>
          <h3>이 순위가 나온 근거</h3>
          <ul>
            <li v-for="evidence in activeItem.evidence" :key="evidence">
              <b>✓</b><span>{{ evidence }}</span>
            </li>
          </ul>
        </section>

        <section class="ranking-action">
          <span>NEXT ACTION</span>
          <h3>현재 권장 판단</h3>
          <p>{{ activeItem.action }}</p>
          <div>
            <button>내 가게 영향 계산</button>
            <button class="secondary">119에 대응 전략 묻기</button>
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
  </div>
</template>
