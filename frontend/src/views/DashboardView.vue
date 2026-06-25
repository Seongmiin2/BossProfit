<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchStoreAnalysis } from '@/api/endpoints'
import { formatKRW } from '@/utils/format'
import { menuImages, produceImages } from '@/utils/productAssets'

const router = useRouter()
const data = ref(null)
const loading = ref(true)
const error = ref('')

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const response = await fetchStoreAnalysis()
    data.value = response.data
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)

const analysis = computed(() => data.value?.analysis)
const risk = computed(() => data.value?.market_risk)
const forecast = (days) => risk.value?.forecasts?.find((item) => item.horizon_days === days)
const signed = (value) => `${value >= 0 ? '+' : ''}${Number(value).toFixed(1)}%`
const salesLeaders = computed(() => analysis.value?.menus?.filter(item => item.state === 'SALES_LEADER').slice(0, 5) || [])
const costDefense = computed(() => analysis.value?.menus?.filter(item => item.state === 'COST_DEFENSE').slice(0, 5) || [])
const pending = computed(() => analysis.value?.menus?.filter(item => item.state === 'ANALYSIS_PENDING').slice(0, 5) || [])
</script>

<template>
  <div class="bp-dashboard">
    <div v-if="loading" class="bp-state-panel">
      <div class="spinner"></div><strong>시장과 매장 데이터를 연결하고 있습니다.</strong>
    </div>
    <div v-else-if="error" class="bp-state-panel error">
      <strong>대시보드를 불러오지 못했습니다.</strong><p>{{ error }}</p>
      <button @click="load">다시 시도</button>
    </div>

    <template v-else-if="analysis">
      <header class="bp-page-header">
        <div>
          <span class="bp-kicker">TODAY'S DECISION</span>
          <h1>오늘 먼저 확인할 재료와 메뉴</h1>
          <p>{{ analysis.store.name }} · 데이터 기준일 {{ analysis.data_as_of }}</p>
        </div>
        <router-link to="/history" class="bp-outline-button">AI 분석 리포트</router-link>
      </header>

      <section v-if="risk?.state === 'SUCCESS'" class="bp-risk-hero">
        <div class="bp-risk-copy">
          <span>오늘의 시장 위험</span>
          <h2>{{ risk.item.name }} <b>{{ signed(risk.headline_change_rate) }}</b></h2>
          <p>{{ risk.cause }}</p>
          <dl>
            <div><dt>현재 가격</dt><dd>{{ formatKRW(risk.current_price) }}원 / {{ risk.item.unit }}</dd></div>
            <div><dt>7일 전망</dt><dd>{{ forecast(7) ? signed(forecast(7).change_rate) : '-' }}</dd></div>
            <div><dt>30일 전망</dt><dd>{{ forecast(30) ? signed(forecast(30).change_rate) : '-' }}</dd></div>
            <div><dt>신뢰도</dt><dd>{{ forecast(30)?.confidence || '검증 필요' }}</dd></div>
          </dl>
          <div class="bp-risk-interval" v-if="forecast(30)">
            <span>30일 예측구간</span>
            <strong>{{ formatKRW(forecast(30).lower_price) }}~{{ formatKRW(forecast(30).upper_price) }}원</strong>
          </div>
        </div>
        <img :src="produceImages[risk.item.image_key]" :alt="risk.item.name">
        <div class="bp-risk-action">
          <span>영향받을 수 있는 메뉴</span>
          <strong v-if="risk.affected_menus?.length">{{ risk.affected_menus.map(item => item.name).join(', ') }}</strong>
          <strong v-else>판단 보류</strong>
          <p>{{ risk.impact_message || '레시피와 시장 품목 연결을 바탕으로 계산했습니다.' }}</p>
          <button @click="router.push('/menus')">메뉴 영향 확인</button>
        </div>
      </section>

      <section v-else class="bp-state-panel insufficient">
        <strong>실제 시장 예측이 아직 없습니다.</strong>
        <p>{{ risk?.message }}</p>
        <button @click="router.push('/market')">시장 전망 확인</button>
      </section>

      <section class="bp-summary-row">
        <article>
          <span>분석기간</span>
          <strong>{{ analysis.period.from }}<br>~ {{ analysis.period.to }}</strong>
          <small>판매 기록일 {{ analysis.period.record_days }}일</small>
        </article>
        <article class="primary">
          <span>음식 판매량</span>
          <strong>{{ analysis.summary.food_quantity.toLocaleString() }}개</strong>
          <small>실매출 {{ formatKRW(analysis.summary.food_net_revenue) }}원</small>
        </article>
        <article>
          <span>판매량 1위</span>
          <strong>{{ analysis.summary.top_food_menu?.name || '-' }}</strong>
          <small>{{ analysis.summary.top_food_menu?.quantity?.toLocaleString() || 0 }}개</small>
        </article>
        <article>
          <span>가격위험 분석 가능</span>
          <strong>{{ analysis.summary.price_risk_ready_menu_count }}개</strong>
          <small>레시피·시장 품목 연결 기준</small>
        </article>
      </section>

      <section class="bp-decision-section">
        <header><div><span>01</span><h2>판매 주력 메뉴</h2></div><p>실제 판매량과 실매출 기준</p></header>
        <div class="bp-leader-grid">
          <button v-for="menu in salesLeaders" :key="menu.menu_id" @click="router.push(`/menus/${menu.menu_id}`)">
            <img v-if="menu.image_key" :src="menuImages[menu.image_key]" :alt="menu.name">
            <span v-else class="bp-menu-placeholder">{{ menu.name.slice(0, 1) }}</span>
            <div><b>{{ menu.rank }}위</b><strong>{{ menu.name }}</strong><p>{{ menu.quantity.toLocaleString() }}개 · {{ formatKRW(menu.net_revenue) }}원</p></div>
          </button>
        </div>
        <p class="bp-evidence-note">
          {{ salesLeaders[0]?.name }}는 분석기간 동안 가장 많이 판매된 음식 메뉴입니다.
          원가와 고정비가 충분하지 않아 수익성이 좋다고 표현하지 않습니다.
        </p>
      </section>

      <section class="bp-two-column">
        <article class="bp-decision-section compact">
          <header><div><span>02</span><h2>원가 방어가 필요한 메뉴</h2></div></header>
          <div v-if="costDefense.length" class="bp-compact-list">
            <button v-for="menu in costDefense" :key="menu.menu_id" @click="router.push(`/menus/${menu.menu_id}`)">
              <strong>{{ menu.name }}</strong><span>{{ menu.state_reason }}</span><b>확인 →</b>
            </button>
          </div>
          <div v-else class="bp-inline-empty">
            <strong>아직 계산 가능한 메뉴가 없습니다.</strong>
            <p>판매 주력 메뉴의 레시피를 먼저 연결해주세요.</p>
            <button @click="router.push('/ingredients')">재료 연결 확인</button>
          </div>
        </article>

        <article class="bp-decision-section compact">
          <header><div><span>03</span><h2>연결이 필요한 메뉴</h2></div><p>{{ pending.length ? '우선순위 상위' : '' }}</p></header>
          <div class="bp-compact-list">
            <button v-for="menu in pending" :key="menu.menu_id" @click="router.push(`/menus/${menu.menu_id}`)">
              <strong>{{ menu.name }}</strong><span>{{ menu.state_reason }}</span><b>연결 →</b>
            </button>
          </div>
        </article>
      </section>

      <section class="bp-action-today">
        <div><span>04</span><h2>AI가 제안하는 오늘의 행동</h2></div>
        <strong>판매량 상위 5개 메뉴부터 레시피 연결 상태를 확인하세요.</strong>
        <p>시장가격 상승이 실제 메뉴 원가에 미치는 영향을 계산하기 위한 첫 단계입니다.</p>
        <router-link to="/history">근거와 행동계획 보기 →</router-link>
      </section>

      <p class="bp-data-rule">판매 기록이 없는 날은 판매량 0으로 처리하지 않았습니다. 판매성과와 수익성은 분리해 표시합니다.</p>
    </template>
  </div>
</template>
