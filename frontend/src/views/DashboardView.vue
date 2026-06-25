<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchStoreAnalysis, fetchSalesCalendar, fetchSalesDayDetail } from '@/api/endpoints'
import { formatKRW } from '@/utils/format'

const router = useRouter()
const data = ref(null)
const loading = ref(true)
const error = ref('')

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchStoreAnalysis()
    data.value = res.data
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)

const analysis = computed(() => data.value?.analysis)
const marketRisks = computed(() => data.value?.market_risks)
const riskItems = computed(() => marketRisks.value?.items || [])
const topMenus = computed(() => (analysis.value?.menus || []).slice(0, 5))
const heroMenu = computed(() => topMenus.value[0] || null)
const todayRevenue = computed(() => analysis.value?.summary?.today_estimate || null)
const signed = v =>
  v != null ? `${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(1)}%` : null
const forecast = (risk, days) => risk.forecasts?.find(f => f.horizon_days === days)

/* ── 매출 장부 (캘린더) ── */
const calendar = ref(null)
const calLoading = ref(false)
const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

const loadCalendar = async (year, month) => {
  calLoading.value = true
  try {
    const params = (year && month) ? { year, month } : {}
    const { data } = await fetchSalesCalendar(params)
    calendar.value = data
  } catch {
    calendar.value = null
  } finally {
    calLoading.value = false
  }
}
onMounted(() => loadCalendar())

const calKey = computed(() =>
  calendar.value ? `${calendar.value.year}-${String(calendar.value.month).padStart(2, '0')}` : null,
)
const calIndex = computed(() =>
  calendar.value?.available_months?.indexOf(calKey.value) ?? -1,
)
const hasPrevMonth = computed(() => calIndex.value > 0)
const hasNextMonth = computed(() =>
  calIndex.value >= 0 && calIndex.value < (calendar.value?.available_months?.length || 0) - 1,
)
const goMonth = (delta) => {
  const months = calendar.value?.available_months || []
  const next = months[calIndex.value + delta]
  if (!next) return
  const [y, m] = next.split('-').map(Number)
  loadCalendar(y, m)
}

const calendarCells = computed(() => {
  if (!calendar.value) return []
  const { year, month, days } = calendar.value
  const revByDay = {}
  days.forEach(d => { revByDay[d.day] = d.revenue })
  const firstWeekday = new Date(year, month - 1, 1).getDay() // 0=일
  const daysInMonth = new Date(year, month, 0).getDate()
  const cells = []
  for (let i = 0; i < firstWeekday; i++) cells.push(null)
  for (let day = 1; day <= daysInMonth; day++) {
    cells.push({ day, revenue: revByDay[day] ?? null })
  }
  return cells
})
const calMaxRevenue = computed(() =>
  Math.max(1, ...(calendar.value?.days?.map(d => d.revenue) || [1])),
)
const shortKRW = (v) => v >= 10000 ? `${(v / 10000).toFixed(v >= 100000 ? 0 : 1)}만` : v.toLocaleString()

/* ── 일자별 매출표 (모달) ── */
const dayDetail = ref(null)
const dayLoading = ref(false)
const selectDay = async (cell) => {
  if (!cell || !cell.revenue) return
  const { year, month } = calendar.value
  const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(cell.day).padStart(2, '0')}`
  dayLoading.value = true
  dayDetail.value = { date: dateStr, items: [], total: 0, total_quantity: 0 }
  try {
    const { data } = await fetchSalesDayDetail(dateStr)
    dayDetail.value = data
  } catch {
    dayDetail.value = null
  } finally {
    dayLoading.value = false
  }
}
const closeDayDetail = () => { dayDetail.value = null }
</script>

<template>
  <div>
    <!-- Loading -->
    <div v-if="loading" class="state-card">
      <div class="spinner"></div>
      <strong>매장 데이터를 분석하고 있습니다</strong>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="state-card">
      <strong>데이터를 불러오지 못했습니다</strong>
      <p>{{ error }}</p>
      <button class="primary-button full-button" @click="load">다시 시도</button>
    </div>

    <!-- Empty -->
    <div v-else-if="!analysis || analysis.state === 'EMPTY'" class="state-card">
      <strong>판매 데이터가 아직 없습니다</strong>
      <p>POS 엑셀을 불러오면 메뉴 분석이 시작됩니다.</p>
    </div>

    <template v-else>
      <!-- ① 페이지 헤더 + 오늘 매출 -->
      <div class="welcome-row">
        <div class="welcome-left">
          <span class="eyebrow eyebrow-pill">📍 {{ analysis.store.name }}</span>
          <h1>지금 <span class="hl">어떤 메뉴</span>를<br>밀어야 할까요?</h1>
        </div>

        <!-- 오늘 매출 (AI 예상) -->
        <section v-if="todayRevenue" class="today-card today-card-side">
          <div class="today-head">
            <span class="today-title">오늘 매출</span>
            <span v-if="todayRevenue.date" class="today-badge">{{ todayRevenue.date }}</span>
          </div>
          <div class="today-metrics">
            <div class="today-metric">
              <span class="today-metric-label">실제 판매 매출</span>
              <strong>{{ formatKRW(todayRevenue.total) }}원</strong>
            </div>
            <div class="today-metric ai">
              <span class="today-metric-label">AI 예측 매출 <i class="today-badge">AI</i></span>
              <strong>{{ formatKRW(todayRevenue.ai_forecast) }}원</strong>
            </div>
          </div>
          <router-link to="/history" class="today-report-link">AI 분석 리포트 →</router-link>
        </section>
      </div>

      <!-- ② 핵심 추천 카드 -->
      <div v-if="heroMenu" class="rec-hero">
        <div class="rec-hero-body">
          <span class="rec-badge">지금 밀 메뉴</span>
          <h2 class="rec-menu-name">{{ heroMenu.name }}</h2>
          <div class="rec-stats">
            <span>총 {{ heroMenu.quantity.toLocaleString() }}개 판매</span>
            <i class="rec-dot"></i>
            <span>{{ formatKRW(heroMenu.net_revenue) }}원</span>
            <template v-if="heroMenu.trend_rate != null">
              <i class="rec-dot"></i>
              <span :class="heroMenu.trend_rate >= 0 ? 'rec-trend-up' : 'rec-trend-down'">
                최근 30일 {{ signed(heroMenu.trend_rate) }}
              </span>
            </template>
          </div>
          <p v-if="heroMenu.recipe?.status !== 'READY'" class="rec-note">
            재료를 연결하면 <strong>앞으로 재료비 변동 후에도 가장 남는 메뉴</strong>를 계산해드릴게요.
            <router-link to="/ingredients" class="rec-cta-link">재료 연결하기 →</router-link>
          </p>
          <p v-else class="rec-note rec-note-ok">
            원가 분석 연결 완료 ·
            <router-link :to="`/menus/${heroMenu.menu_id}`" class="rec-cta-link">
              자세한 분석 보기 →
            </router-link>
          </p>
        </div>
        <div class="rec-hero-rank">
          <span>1</span>
          <small>판매 1위</small>
        </div>
      </div>

      <!-- ③ 판매 상위 메뉴 -->
      <section class="section-block" style="margin-top: 24px;">
        <div class="section-title-row">
          <h2>판매 상위 메뉴</h2>
          <router-link to="/menus">전체 보기 →</router-link>
        </div>
        <div class="trend-caption">
          <span class="ah-label">전달 대비 판매량 추이</span>
          <span class="ah-legend">
            <i class="up"></i>증가
            <i class="down"></i>감소
          </span>
        </div>
        <div class="attention-list">
          <button
            v-for="menu in topMenus"
            :key="menu.menu_id"
            class="attention-item"
            @click="router.push(`/menus/${menu.menu_id}`)"
          >
            <div class="menu-symbol">{{ menu.name.slice(0, 1) }}</div>
            <div class="attention-copy">
              <strong>{{ menu.name }}</strong>
              <span>{{ menu.quantity.toLocaleString() }}개 · {{ formatKRW(menu.net_revenue) }}원</span>
            </div>
            <span
              v-if="menu.trend_rate != null"
              class="signal"
              :class="menu.trend_rate > 5 ? 'signal-green' : menu.trend_rate < -5 ? 'signal-red' : 'signal-yellow'"
            >{{ signed(menu.trend_rate) }}</span>
            <span v-else></span>
            <span class="chevron">›</span>
          </button>
        </div>
      </section>

      <!-- ④ 재료 가격 위험 -->
      <section class="section-block">
        <div class="section-title-row">
          <h2>재료 가격 위험</h2>
        </div>

        <!-- 연결된 위험 재료가 있을 때 -->
        <div v-if="riskItems.length" class="attention-list">
          <button
            v-for="risk in riskItems"
            :key="risk.item.code"
            class="attention-item"
            @click="router.push('/ingredients')"
          >
            <div class="menu-symbol">{{ risk.item.name.slice(0, 1) }}</div>
            <div class="attention-copy">
              <strong>{{ risk.item.name }}</strong>
              <span>{{ risk.affected_menus.map(m => m.name).join(', ') || '연결 확인 필요' }}</span>
            </div>
            <span
              class="signal"
              :class="Math.abs(risk.headline_change_rate) > 5 ? 'signal-red' : 'signal-yellow'"
            >{{ signed(risk.headline_change_rate) }}</span>
            <span class="chevron">›</span>
          </button>
        </div>

        <!-- 연결 없을 때 -->
        <div v-else class="action-card">
          <div class="action-icon">🌾</div>
          <div class="action-copy">
            <span>분석 준비 필요</span>
            <h2>재료 연결이 아직 없어요</h2>
            <p>판매 1위 메뉴의 재료를 연결하면 가격 위험을 계산합니다.</p>
          </div>
          <button class="action-button" @click="router.push('/ingredients')">
            재료 연결하기 <span>→</span>
          </button>
        </div>
      </section>

      <!-- ⑤ 매출 장부 (캘린더) -->
      <section v-if="calendar" class="rp-ledger">
        <div class="rp-ledger-head">
          <div class="rp-ledger-title">
            <button class="rp-ledger-nav" :disabled="!hasPrevMonth" @click="goMonth(-1)">‹</button>
            <h3>{{ calendar.year }}년 {{ calendar.month }}월 매출 장부</h3>
            <button class="rp-ledger-nav" :disabled="!hasNextMonth" @click="goMonth(1)">›</button>
          </div>
          <div class="rp-ledger-total">
            <span>총 매출액</span>
            <strong>{{ formatKRW(calendar.total) }}원</strong>
          </div>
        </div>
        <div class="rp-cal">
          <div v-for="(w, i) in WEEKDAYS" :key="w" class="rp-cal-wd" :class="{ sun: i === 0, sat: i === 6 }">{{ w }}</div>
          <component
            :is="cell && cell.revenue ? 'button' : 'div'"
            v-for="(cell, idx) in calendarCells"
            :key="idx"
            class="rp-cal-cell"
            :class="{ empty: !cell, hassale: cell && cell.revenue }"
            @click="selectDay(cell)"
          >
            <template v-if="cell">
              <span class="rp-cal-day">{{ cell.day }}</span>
              <span v-if="cell.revenue" class="rp-cal-rev">{{ shortKRW(cell.revenue) }}</span>
              <i v-if="cell.revenue" class="rp-cal-bar" :style="{ height: `${4 + (cell.revenue / calMaxRevenue) * 22}px` }"></i>
            </template>
          </component>
        </div>
        <p class="rp-ledger-note">날짜를 누르면 그날의 메뉴별 매출표를 볼 수 있어요. 실제 일별 판매 매출 기준입니다.</p>
      </section>

      <!-- 일자별 매출표 모달 -->
      <div v-if="dayDetail" class="rp-day-overlay" @click.self="closeDayDetail">
        <div class="rp-day-modal">
          <div class="rp-day-head">
            <div>
              <span class="rp-day-eyebrow">일자별 매출표</span>
              <h3>{{ dayDetail.date }}</h3>
            </div>
            <button class="rp-day-close" @click="closeDayDetail">✕</button>
          </div>
          <div class="rp-day-summary">
            <div><span>총 매출</span><strong>{{ formatKRW(dayDetail.total) }}원</strong></div>
            <div><span>총 판매량</span><strong>{{ (dayDetail.total_quantity || 0).toLocaleString() }}개</strong></div>
          </div>
          <div v-if="dayLoading" class="rp-day-empty">불러오는 중…</div>
          <table v-else-if="dayDetail.items.length" class="rp-day-table">
            <thead>
              <tr><th>메뉴</th><th class="r">수량</th><th class="r">매출</th></tr>
            </thead>
            <tbody>
              <tr v-for="it in dayDetail.items" :key="it.menu_id">
                <td>{{ it.name }}</td>
                <td class="r">{{ it.quantity.toLocaleString() }}개</td>
                <td class="r">{{ formatKRW(it.net_revenue) }}원</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="rp-day-empty">이 날의 판매 기록이 없습니다.</div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* ─ 매출 장부 (캘린더) ─ */
.rp-ledger {
  background: #fff; border: 1px solid var(--line); border-radius: 12px;
  padding: 20px 22px; margin-top: 24px;
}
.rp-ledger-head {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 12px; margin-bottom: 16px;
}
.rp-ledger-title { display: flex; align-items: center; gap: 10px; }
.rp-ledger-title h3 { font-size: 18px; font-weight: 800; color: var(--ink); }
.rp-ledger-nav {
  width: 30px; height: 30px; border-radius: 8px;
  border: 1px solid var(--line); background: #fff;
  color: var(--ink); font-size: 18px; line-height: 1; cursor: pointer;
}
.rp-ledger-nav:disabled { opacity: 0.35; cursor: default; }
.rp-ledger-total { text-align: right; }
.rp-ledger-total span { display: block; font-size: 11px; color: var(--ink-muted); }
.rp-ledger-total strong { font-size: 20px; font-weight: 900; color: var(--coral, #c95626); }

.rp-cal { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
.rp-cal-wd {
  text-align: center; padding: 6px 0; font-size: 12px; font-weight: 800;
  color: var(--ink-muted);
}
.rp-cal-wd.sun { color: #d8593f; }
.rp-cal-wd.sat { color: #3f78d8; }
.rp-cal-cell {
  position: relative; min-height: 64px; padding: 7px 8px;
  border: 1px solid #f0ede7; border-radius: 9px; background: #faf9f6;
  display: flex; flex-direction: column; gap: 3px;
}
.rp-cal-cell.empty { border: none; background: transparent; }
.rp-cal-cell.hassale { background: #fff7f2; border-color: #f3ddd0; }
.rp-cal-day { font-size: 12px; font-weight: 700; color: var(--ink-muted); }
.rp-cal-rev { font-size: 13px; font-weight: 900; color: var(--coral, #c95626); }
.rp-cal-bar {
  margin-top: auto; width: 100%; border-radius: 3px;
  background: linear-gradient(180deg, #e89150, #c95626);
}
.rp-ledger-note { margin-top: 12px; font-size: 11px; color: var(--ink-muted); }
button.rp-cal-cell { text-align: left; cursor: pointer; transition: transform .12s, box-shadow .12s; font: inherit; }
button.rp-cal-cell:hover { transform: translateY(-2px); box-shadow: 0 6px 14px rgba(201,86,38,.16); border-color: #e0894a; }
@media (max-width: 600px) {
  .rp-cal-cell { min-height: 52px; padding: 5px; }
  .rp-cal-rev { font-size: 11px; }
}

/* ─ 일자별 매출표 모달 ─ */
.rp-day-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,.45);
  display: flex; align-items: center; justify-content: center; padding: 20px;
}
.rp-day-modal {
  width: 100%; max-width: 460px; max-height: 84vh; overflow-y: auto;
  background: #fff; border-radius: 16px; padding: 22px 24px;
  box-shadow: 0 24px 60px rgba(0,0,0,.25);
}
.rp-day-head { display: flex; align-items: flex-start; justify-content: space-between; }
.rp-day-eyebrow { font-size: 12px; font-weight: 800; color: var(--coral, #c95626); }
.rp-day-head h3 { margin-top: 4px; font-size: 20px; font-weight: 900; color: var(--ink); }
.rp-day-close {
  width: 30px; height: 30px; border: none; border-radius: 8px;
  background: #f3f1ec; color: var(--ink); font-size: 14px; cursor: pointer;
}
.rp-day-summary { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 16px 0; }
.rp-day-summary > div { padding: 12px 14px; border-radius: 12px; background: #faf8f5; }
.rp-day-summary span { display: block; font-size: 11px; color: var(--ink-muted); }
.rp-day-summary strong { font-size: 18px; font-weight: 900; color: var(--ink); }
.rp-day-table { width: 100%; border-collapse: collapse; }
.rp-day-table th {
  text-align: left; padding: 8px 6px; font-size: 11px; font-weight: 800;
  color: var(--ink-muted); border-bottom: 1px solid var(--line);
}
.rp-day-table td { padding: 9px 6px; font-size: 13px; border-bottom: 1px solid #f3f1ec; }
.rp-day-table .r { text-align: right; }
.rp-day-table tbody td.r:last-child { font-weight: 800; color: var(--coral, #c95626); }
.rp-day-empty { padding: 24px 0; text-align: center; color: var(--ink-muted); font-size: 13px; }
</style>
