<script setup>
import { computed, onMounted, ref } from 'vue'
import { Bar, Doughnut, Line } from 'vue-chartjs'
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js'
import {
  fetchAnalysisReport,
  postActionPlan,
  postAnalysisFollowUp,
} from '@/api/endpoints'
import { formatKRW } from '@/utils/format'

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
)

const report = ref(null)
const loading = ref(true)
const error = ref('')
const question = ref('')
const followUpLoading = ref(false)
const answer = ref(null)
const savedPlanId = ref(null)

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const { data } = await fetchAnalysisReport()
    report.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)

const sales = computed(() => report.value?.sales_analysis)
const monthlyQuantityData = computed(() => ({
  labels: sales.value?.monthly_trend?.map(item => `${Number(item.month.slice(5, 7))}월`) || [],
  datasets: [{
    label: '음식 메뉴 판매량',
    data: sales.value?.monthly_trend?.map(item => item.quantity) || [],
    borderColor: '#d96532',
    backgroundColor: 'rgba(217, 101, 50, .14)',
    fill: true,
    tension: 0.28,
  }],
}))
const monthlyRevenueData = computed(() => ({
  labels: sales.value?.monthly_trend?.map(item => `${Number(item.month.slice(5, 7))}월`) || [],
  datasets: [{
    label: '음식 메뉴 실매출',
    data: sales.value?.monthly_trend?.map(item => item.net_revenue) || [],
    borderColor: '#26302f',
    backgroundColor: 'rgba(38, 48, 47, .1)',
    fill: true,
    tension: 0.28,
  }],
}))
const topMenuData = computed(() => ({
  labels: sales.value?.top_menus?.map(item => item.name) || [],
  datasets: [{
    label: '판매량',
    data: sales.value?.top_menus?.map(item => item.quantity) || [],
    backgroundColor: ['#d96532', '#e58b5e', '#efae8d', '#5e7772', '#93a7a2'],
    borderRadius: 4,
  }],
}))
const categoryData = computed(() => ({
  labels: sales.value?.category_share?.map(item => item.category) || [],
  datasets: [{
    data: sales.value?.category_share?.map(item => item.quantity) || [],
    backgroundColor: ['#d96532', '#26302f', '#b7c4bf'],
  }],
}))
const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: { y: { beginAtZero: true }, x: { grid: { display: false } } },
}

const savePlan = async (plan) => {
  const { data } = await postActionPlan(plan)
  savedPlanId.value = data.id
}

const ask = async (preset) => {
  const value = preset || question.value.trim()
  if (!value) return
  question.value = value
  followUpLoading.value = true
  answer.value = null
  try {
    const { data } = await postAnalysisFollowUp(value)
    answer.value = data
  } catch (e) {
    answer.value = { answer: e.response?.data?.detail || e.message, limitations: [] }
  } finally {
    followUpLoading.value = false
  }
}
</script>

<template>
  <div class="bp-report">
    <div v-if="loading" class="bp-state-panel"><div class="spinner"></div><strong>실제 통계와 시장 전망을 분석하고 있습니다.</strong></div>
    <div v-else-if="error" class="bp-state-panel error"><strong>리포트를 불러오지 못했습니다.</strong><p>{{ error }}</p><button @click="load">다시 시도</button></div>

    <template v-else-if="report">
      <header class="bp-page-header">
        <div>
          <span class="bp-kicker">AI STORE REPORT</span>
          <h1>AI 매장 분석 리포트</h1>
          <p>매장 판매 데이터와 시장가격 전망을 함께 분석했습니다.</p>
        </div>
        <div class="bp-report-basis"><span>분석기간</span><strong>{{ report.data_period.from }}~{{ report.data_period.to }}</strong><small>신뢰도 {{ report.confidence }}</small></div>
      </header>

      <section class="bp-ai-brief">
        <span>AI 핵심 브리핑</span>
        <h2>{{ report.summary }}</h2>
        <p>계산 결과는 SQL·예측 엔진에서 가져오고, 아래 해석은 규칙 기반 설명입니다.</p>
      </section>

      <section class="bp-report-metrics">
        <article v-for="metric in report.key_metrics" :key="metric.label">
          <span>{{ metric.label }}</span>
          <strong v-if="metric.unit === '원'">{{ formatKRW(metric.value) }}원</strong>
          <strong v-else>{{ metric.value ?? '-' }}{{ metric.unit || '' }}</strong>
        </article>
      </section>

      <section class="bp-report-section">
        <header><span>01</span><div><h2>AI 핵심 발견</h2><p>결론과 수치 근거, 한계를 함께 표시합니다.</p></div></header>
        <div class="bp-findings">
          <article v-for="finding in report.findings" :key="finding.title">
            <div class="bp-finding-title"><strong>{{ finding.title }}</strong><span>신뢰도 {{ finding.confidence }}</span></div>
            <div class="bp-finding-evidence">
              <div v-for="item in finding.evidence" :key="item.label"><span>{{ item.label }}</span><b>{{ item.unit === '원' ? `${formatKRW(item.value)}원` : `${item.value}${item.unit || ''}` }}</b></div>
            </div>
            <p>{{ finding.interpretation }}</p>
            <small v-for="limit in finding.limitations" :key="limit">한계 · {{ limit }}</small>
          </article>
        </div>
      </section>

      <section class="bp-report-section">
        <header><span>02</span><div><h2>판매 데이터 차트</h2><p>판매기록이 존재하는 날만 집계했습니다.</p></div></header>
        <div class="bp-report-chart-grid">
          <article><h3>월별 음식 메뉴 판매량</h3><small>단위: 개</small><div><Line :data="monthlyQuantityData" :options="chartOptions" /></div></article>
          <article><h3>월별 음식 메뉴 실매출</h3><small>단위: 원</small><div><Line :data="monthlyRevenueData" :options="chartOptions" /></div></article>
          <article><h3>판매량 TOP 5</h3><small>분석기간 누적</small><div><Bar :data="topMenuData" :options="{ ...chartOptions, indexAxis: 'y' }" /></div></article>
          <article><h3>카테고리별 판매 비중</h3><small>판매수량 기준</small><div><Doughnut :data="categoryData" :options="{ responsive: true, maintainAspectRatio: false }" /></div></article>
        </div>
      </section>

      <section class="bp-report-section">
        <header><span>03</span><div><h2>시장가격 및 메뉴 영향</h2><p>실제 예측과 메뉴 연결 상태를 분리합니다.</p></div></header>
        <div v-if="report.market_risks.length" class="bp-market-risk-list">
          <article v-for="risk in report.market_risks" :key="risk.item.code">
            <div><span>{{ risk.item.name }}</span><strong>{{ risk.headline_change_rate >= 0 ? '+' : '' }}{{ risk.headline_change_rate.toFixed(1) }}%</strong><small>기준일 {{ risk.as_of_date }}</small></div>
            <p>{{ risk.impact_message || '연결된 메뉴 원가 영향을 계산할 수 있습니다.' }}</p>
          </article>
        </div>
        <div v-else class="bp-inline-empty"><strong>실제 가격예측 결과가 없습니다.</strong><p>시장 데이터 수집 상태를 확인해주세요.</p></div>
      </section>

      <section class="bp-report-section">
        <header><span>04</span><div><h2>RAG 검색 근거</h2><p>문서가 없으면 근거를 생성하지 않습니다.</p></div></header>
        <div v-if="report.sources.length" class="bp-source-list">
          <article v-for="source in report.sources" :key="source.title"><strong>{{ source.title }}</strong><p>{{ source.summary }}</p></article>
        </div>
        <div v-else class="bp-inline-empty"><strong>{{ report.source_state.message }}</strong><p>KAMIS 시장동향·농업관측 보고서 수집 후 이 영역에 출처가 표시됩니다.</p></div>
      </section>

      <section class="bp-report-section">
        <header><span>05</span><div><h2>권장 행동계획</h2><p>저장만 하며 사용자 확인 없이 가격 변경이나 발주를 실행하지 않습니다.</p></div></header>
        <div class="bp-action-plans">
          <article v-for="plan in report.recommended_actions" :key="plan.title">
            <span>{{ plan.period }}</span><h3>{{ plan.title }}</h3><p>{{ plan.reason }}</p>
            <dl><div><dt>예상 효과</dt><dd>{{ plan.expected_effect }}</dd></div><div><dt>성공 기준</dt><dd>{{ plan.success_criteria }}</dd></div><div><dt>중단 기준</dt><dd>{{ plan.stop_criteria }}</dd></div></dl>
            <button @click="savePlan(plan)">{{ savedPlanId ? '행동계획 저장됨' : '행동계획 저장' }}</button>
          </article>
        </div>
      </section>

      <section class="bp-follow-up">
        <span>06 · AI 후속 질문</span><h2>현재 리포트를 기준으로 질문하세요.</h2>
        <div class="bp-question-chips">
          <button @click="ask('이번 주에 가장 먼저 확인할 것은 무엇이야?')">이번 주에 가장 먼저 확인할 것은?</button>
          <button @click="ask('양파 가격이 오르면 어떤 메뉴가 영향을 받아?')">양파 가격 영향 메뉴는?</button>
          <button @click="ask('돈까스 판매량을 어떻게 봐야 해?')">돈까스 판매량 해석</button>
        </div>
        <form @submit.prevent="ask()"><input v-model="question" placeholder="후속 질문을 입력하세요"><button>질문하기</button></form>
        <div v-if="followUpLoading" class="bp-inline-state">통계와 예측 결과를 확인 중입니다.</div>
        <article v-else-if="answer" class="bp-answer"><strong>답변</strong><p>{{ answer.answer }}</p><small>엔진: {{ answer.engine || 'structured-analysis' }} · 문서 근거 {{ answer.sources?.length || 0 }}건</small></article>
      </section>

      <section class="bp-limitations">
        <strong>분석 한계</strong>
        <ul><li v-for="limit in report.limitations" :key="limit">{{ limit }}</li></ul>
      </section>
    </template>
  </div>
</template>
