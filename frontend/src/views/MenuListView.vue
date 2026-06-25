<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { fetchStoreAnalysis } from '@/api/endpoints'
import { formatKRW } from '@/utils/format'
import { menuImages, menuPlaceholder } from '@/utils/productAssets'

const photoFor = (menu) => menuImages[menu?.image_key] || menuPlaceholder

const payload = ref(null)
const loading = ref(true)
const error = ref('')
const query = ref('')
const activeSegment = ref('sales')
const selected = ref(null)

const dateFrom = ref('')
const dateTo = ref('')
const activePreset = ref('all')

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const params = {}
    if (dateFrom.value) params.from = dateFrom.value
    if (dateTo.value) params.to = dateTo.value
    const { data } = await fetchStoreAnalysis(params)
    payload.value = data
    selected.value = data.analysis.top_menus?.[0] || null
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)

const analysis = computed(() => payload.value?.analysis)
const availablePeriod = computed(() => analysis.value?.available_period || {})

const shiftDate = (iso, days) => {
  const d = new Date(iso)
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

const applyPreset = (key) => {
  activePreset.value = key
  const to = availablePeriod.value?.to
  if (key === 'all' || !to) {
    dateFrom.value = ''
    dateTo.value = ''
  } else {
    const days = { '7': 6, '30': 29, '90': 89 }[key]
    dateTo.value = to
    dateFrom.value = shiftDate(to, days)
  }
  load()
}

const applyCustom = () => {
  activePreset.value = 'custom'
  load()
}
const maxQuantity = computed(() => Math.max(...(analysis.value?.top_menus?.map(item => item.quantity) || [1])))
const maxRevenue = computed(() => Math.max(...(analysis.value?.menus?.map(item => item.net_revenue) || [1])))
const filtered = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  const stateBySegment = {
    sales: 'SALES_LEADER',
    cost: 'COST_DEFENSE',
    pending: 'ANALYSIS_PENDING',
  }
  return [...(analysis.value?.menus || [])].filter((item) => {
    const stateMatch = String(item.state).trim() === stateBySegment[activeSegment.value]
    const queryMatch = !keyword || item.name.toLowerCase().includes(keyword)
    return stateMatch && queryMatch
  })
})
const tabCounts = computed(() => ({
  SALES_LEADER: analysis.value?.menus?.filter(item => item.state === 'SALES_LEADER').length || 0,
  COST_DEFENSE: analysis.value?.menus?.filter(item => item.state === 'COST_DEFENSE').length || 0,
  ANALYSIS_PENDING: analysis.value?.menus?.filter(item => item.state === 'ANALYSIS_PENDING').length || 0,
}))
const trendText = (value) => value == null ? '비교 가능한 기록 부족' : `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
const percentText = (value) => value == null ? '-' : `${(value * 100).toFixed(1)}%`

const detailPanel = ref(null)
const selectMenu = async (menu) => {
  selected.value = menu
  await nextTick()
  detailPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
</script>

<template>
  <div class="bp-menu-analysis">
    <div v-if="loading" class="bp-state-panel"><div class="spinner"></div><strong>실제 판매자료를 분석하고 있습니다.</strong></div>
    <div v-else-if="error" class="bp-state-panel error"><strong>메뉴 분석을 불러오지 못했습니다.</strong><p>{{ error }}</p><button @click="load">다시 시도</button></div>

    <template v-else-if="analysis">
      <header class="bp-page-header">
        <div>
          <span class="bp-kicker">MENU PORTFOLIO</span>
          <h1>어떤 메뉴가 가장 많이 팔리고 있을까요?</h1>
          <p>판매 흐름과 재료가격 위험을 함께 확인하세요.</p>
        </div>
        <router-link to="/menus/create" class="bp-outline-button">메뉴 추가</router-link>
      </header>

      <section class="bp-period-bar">
        <div class="bp-period-presets">
          <button :class="{ active: activePreset === 'all' }" @click="applyPreset('all')">전체</button>
          <button :class="{ active: activePreset === '7' }" @click="applyPreset('7')">최근 7일</button>
          <button :class="{ active: activePreset === '30' }" @click="applyPreset('30')">최근 30일</button>
          <button :class="{ active: activePreset === '90' }" @click="applyPreset('90')">최근 90일</button>
        </div>
        <div class="bp-period-range">
          <input type="date" v-model="dateFrom" :min="availablePeriod.from" :max="availablePeriod.to">
          <span>~</span>
          <input type="date" v-model="dateTo" :min="availablePeriod.from" :max="availablePeriod.to">
          <button class="bp-period-apply" @click="applyCustom">적용</button>
        </div>
      </section>

      <section class="bp-menu-stats">
        <article><span>분석기간</span><strong>{{ analysis.period.from }}<br>~ {{ analysis.period.to }}</strong></article>
        <article><span>음식 메뉴</span><strong>{{ analysis.summary.food_menu_count }}개</strong></article>
        <article class="primary"><span>음식 판매량</span><strong>{{ analysis.summary.food_quantity.toLocaleString() }}개</strong></article>
        <article><span>음식 실매출</span><strong>{{ formatKRW(analysis.summary.food_net_revenue) }}원</strong></article>
        <article><span>판매량 1위</span><strong>{{ analysis.summary.top_food_menu?.name }}</strong></article>
        <article><span>가격위험 분석 가능</span><strong>{{ analysis.summary.price_risk_ready_menu_count }}개</strong></article>
      </section>

      <section class="bp-analysis-panel">
        <header><div><span>판매량 TOP 5</span><h2>실제 POS 판매성과</h2></div><small>단위: 개 · {{ analysis.period.from }}~{{ analysis.period.to }}</small></header>
        <div class="bp-horizontal-bars">
          <button v-for="menu in analysis.top_menus" :key="menu.menu_id" @click="selectMenu(menu)">
            <span>{{ menu.rank }}</span><strong>{{ menu.name }}</strong>
            <i><b :style="{ width: `${(menu.quantity / maxQuantity) * 100}%` }"></b></i>
            <em>{{ menu.quantity.toLocaleString() }}개</em>
          </button>
        </div>
      </section>

      <section class="bp-two-column bp-chart-row">
        <article class="bp-analysis-panel">
          <header><div><span>월별 판매량·실매출</span><h2>판매 흐름</h2></div><small>기록이 있는 날만 집계</small></header>
          <div class="bp-month-columns">
            <div v-for="row in analysis.monthly_trend" :key="row.month">
              <i :style="{ height: `${Math.max(8, (row.quantity / Math.max(...analysis.monthly_trend.map(x => x.quantity))) * 100)}%` }"></i>
              <strong>{{ row.quantity.toLocaleString() }}</strong>
              <span>{{ row.month.slice(5, 7) }}월</span>
              <small>{{ formatKRW(row.net_revenue) }}원</small>
            </div>
          </div>
        </article>

        <article class="bp-analysis-panel">
          <header><div><span>AI 핵심 판단</span><h2>판매성과와 원가위험을 분리합니다</h2></div></header>
          <div class="bp-insight-copy">
            <strong>{{ analysis.summary.top_food_menu?.name }}가 음식 판매량 1위입니다.</strong>
            <p>{{ analysis.summary.top_food_menu?.quantity.toLocaleString() }}개 판매됐지만 원가와 고정비가 충분하지 않아 ‘효자 메뉴’라고 판단하지 않습니다.</p>
            <div><span>판매 주력</span><b>판매량·실매출 근거</b></div>
            <div><span>원가 방어</span><b>레시피·시장가격 연결 필요</b></div>
            <div><span>분석 대기</span><b>부족한 데이터 표시</b></div>
          </div>
        </article>
      </section>

      <section class="bp-analysis-panel">
        <header><div><span>메뉴 포트폴리오</span><h2>판매량과 실매출 비교</h2></div><small>원 크기: 최근 30일 판매량</small></header>
        <div class="bp-scatter">
          <span class="axis-y">실매출 ↑</span>
          <button
            v-for="menu in analysis.menus.slice(0, 20)"
            :key="menu.menu_id"
            :title="`${menu.name}: ${menu.quantity}개 / ${formatKRW(menu.net_revenue)}원`"
            :style="{
              left: `${Math.max(4, Math.min(94, (menu.quantity / maxQuantity) * 92))}%`,
              bottom: `${Math.max(5, Math.min(90, (menu.net_revenue / maxRevenue) * 88))}%`,
              width: `${18 + Math.min(26, (menu.recent_30d_quantity || 0) / 3)}px`,
              height: `${18 + Math.min(26, (menu.recent_30d_quantity || 0) / 3)}px`,
            }"
            :class="menu.state.toLowerCase()"
            @click="selectMenu(menu)"
          >{{ menu.rank <= 5 ? menu.rank : '' }}</button>
          <span class="axis-x">판매량 →</span>
        </div>
      </section>

      <section class="bp-menu-browser">
        <header>
          <div class="bp-tab-row">
            <button :class="{ active: activeSegment === 'sales' }" @click="activeSegment = 'sales'">판매 주력 {{ tabCounts.SALES_LEADER }}</button>
            <button :class="{ active: activeSegment === 'cost' }" @click="activeSegment = 'cost'">원가 방어 {{ tabCounts.COST_DEFENSE }}</button>
            <button :class="{ active: activeSegment === 'pending' }" @click="activeSegment = 'pending'">분석 대기 {{ tabCounts.ANALYSIS_PENDING }}</button>
          </div>
          <input v-model="query" type="search" placeholder="메뉴 검색">
        </header>

        <div v-if="filtered.length" class="bp-photo-menu-grid">
          <button v-for="menu in filtered" :key="menu.menu_id" @click="selectMenu(menu)">
            <img :src="photoFor(menu)" :alt="menu.name">
            <div class="bp-menu-card-body">
              <span>{{ menu.state_label }} · {{ menu.state_reason }}</span>
              <h3>{{ menu.name }}</h3>
              <dl>
                <div><dt>6개월 판매량</dt><dd>{{ menu.quantity.toLocaleString() }}개</dd></div>
                <div><dt>누적 실매출</dt><dd>{{ formatKRW(menu.net_revenue) }}원</dd></div>
                <div><dt>최근 30일</dt><dd>{{ menu.recent_30d_quantity == null ? '기록 없음' : `${menu.recent_30d_quantity}개` }}</dd></div>
                <div><dt>판매 추세</dt><dd>{{ trendText(menu.trend_rate) }}</dd></div>
              </dl>
              <p v-if="!menu.profitability">{{ menu.profitability_message || '레시피와 시장가격을 연결해 원가 위험을 계산했습니다.' }}</p>
              <b>판단 근거 보기 →</b>
            </div>
          </button>
        </div>
        <div v-else class="bp-inline-empty">
          <strong>{{ activeSegment === 'cost' ? '원가 위험을 계산할 수 있는 메뉴가 없습니다.' : '조건에 맞는 메뉴가 없습니다.' }}</strong>
          <p>{{ activeSegment === 'cost' ? '메뉴 레시피와 시장 품목을 연결해주세요.' : '검색어를 지워주세요.' }}</p>
        </div>
      </section>

      <section v-if="selected" ref="detailPanel" class="bp-menu-detail-panel">
        <div class="bp-detail-visual">
          <img :src="photoFor(selected)" :alt="selected.name">
        </div>
        <div class="bp-detail-content">
          <span>{{ selected.state_label }} · {{ selected.state_reason }}</span>
          <h2>{{ selected.name }}</h2>
          <div class="bp-detail-metrics">
            <div><small>누적 판매량</small><strong>{{ selected.quantity.toLocaleString() }}개</strong></div>
            <div><small>누적 실매출</small><strong>{{ formatKRW(selected.net_revenue) }}원</strong></div>
            <div><small>평균 판매단가</small><strong>{{ formatKRW(selected.average_selling_price) }}원</strong></div>
            <div><small>할인금액</small><strong>{{ formatKRW(selected.discount_amount) }}원</strong></div>
          </div>
          <div v-if="selected.profitability" class="bp-detail-metrics">
            <div><small>재료원가</small><strong>{{ formatKRW(selected.profitability.food_cost) }}원</strong></div>
            <div><small>원가율</small><strong>{{ percentText(selected.profitability.food_cost_rate) }}</strong></div>
            <div><small>재료마진</small><strong>{{ formatKRW(selected.profitability.margin_amount) }}원</strong></div>
            <div><small>마진율</small><strong>{{ percentText(selected.profitability.margin_rate) }}</strong></div>
          </div>
          <div class="bp-data-gap">
            <strong>데이터 상태</strong>
            <p v-if="selected.profitability">재료원가 기준 수익성을 계산했습니다. 시장가격 위험은 {{ selected.price_risk_state === 'AVAILABLE' ? '계산 가능합니다.' : '시장 품목 연결 후 계산할 수 있습니다.' }}</p>
            <p v-else>{{ selected.recipe.reason || '레시피와 시장 품목이 연결됐습니다.' }}</p>
          </div>
          <router-link :to="`/menus/${selected.menu_id}`">상세 분석 화면 열기 →</router-link>
        </div>
      </section>

      <p class="bp-data-rule">메뉴 사진은 같은 종류(우동·돈까스·만두) 기준으로 표시하고, 해당 사진이 없는 메뉴는 공통 플레이스홀더로 표시합니다.</p>
    </template>
  </div>
</template>
