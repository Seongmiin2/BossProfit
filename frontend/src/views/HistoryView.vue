<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { Bar, Line } from 'vue-chartjs'
import {
  BarElement, CategoryScale, Chart as ChartJS,
  LinearScale, LineElement, PointElement, Tooltip,
} from 'chart.js'
import { fetchAnalysisReport, fetchSalesCalendar, fetchSalesDayDetail, postAnalysisFollowUp } from '@/api/endpoints'
import { formatKRW } from '@/utils/format'

ChartJS.register(BarElement, CategoryScale, LinearScale, LineElement, PointElement, Tooltip)

const report    = ref(null)
const loading   = ref(true)
const error     = ref('')
const question  = ref('')
const chatLoading = ref(false)
const messages  = ref([])
const chatBox   = ref(null)

const load = async () => {
  loading.value = true
  error.value   = ''
  try {
    const { data } = await fetchAnalysisReport()
    report.value  = data
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)

/* ── 캘린더 장부 ── */
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

const analysis  = computed(() => report.value?.sales_analysis)
const riskItems = computed(() => report.value?.market_risks || [])
const metrics   = computed(() => report.value?.key_metrics || [])

const monthlyData = computed(() => ({
  labels: analysis.value?.monthly_trend?.map(i => `${Number(i.month.slice(5, 7))}월`) || [],
  datasets: [{
    label: '판매량',
    data: analysis.value?.monthly_trend?.map(i => i.quantity) || [],
    borderColor: '#E07856',
    backgroundColor: 'rgba(224,120,86,.1)',
    fill: true,
    tension: 0.3,
    pointRadius: 3,
    pointBackgroundColor: '#E07856',
  }],
}))

const topMenuData = computed(() => ({
  labels: analysis.value?.top_menus?.map(i => i.name) || [],
  datasets: [{
    label: '판매량',
    data: analysis.value?.top_menus?.map(i => i.quantity) || [],
    backgroundColor: ['#E07856','#C44536','#B8893A','#6B8E4E','#5E7772'],
    borderRadius: 4,
  }],
}))

const lineOpts = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    y: { beginAtZero: true, grid: { color: '#E6DCC9' }, ticks: { font: { size: 11 }, color: '#8A7A66' } },
    x: { grid: { display: false }, ticks: { font: { size: 11 }, color: '#8A7A66' } },
  },
}
const barOpts = {
  responsive: true, maintainAspectRatio: false,
  indexAxis: 'y',
  plugins: { legend: { display: false } },
  scales: {
    x: { beginAtZero: true, grid: { color: '#E6DCC9' }, ticks: { font: { size: 11 }, color: '#8A7A66' } },
    y: { grid: { display: false }, ticks: { font: { size: 11 }, color: '#1F1812' } },
  },
}

const PRESETS = [
  '지금 가장 집중할 메뉴는?',
  '재료 가격 위험 메뉴는?',
  '이번 달 매출 올리려면?',
]

const scrollChat = () => nextTick(() => {
  if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
})

const ask = async (preset) => {
  const value = (preset || question.value).trim()
  if (!value || chatLoading.value) return
  question.value = ''
  messages.value.push({ role: 'user', content: value })
  chatLoading.value = true
  scrollChat()
  try {
    const { data } = await postAnalysisFollowUp(value)
    messages.value.push({ role: 'ai', content: data.answer })
  } catch (e) {
    messages.value.push({ role: 'ai', content: '잠시 후 다시 시도해주세요.' })
  } finally {
    chatLoading.value = false
    scrollChat()
  }
}

const signed = v => v != null ? `${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(1)}%` : '--'
</script>

<template>
  <div class="rp">

    <div v-if="loading" class="rp-state">
      <div class="spinner"></div>
      <span>분석 중...</span>
    </div>

    <div v-else-if="error" class="rp-state">
      <strong>{{ error }}</strong>
      <button class="soft-button" @click="load">다시 시도</button>
    </div>

    <template v-else-if="report">

      <!-- ① AI 채팅 (TOP) -->
      <section class="rp-chat">
        <div class="rp-chat-head">
          <span class="rp-ai-dot"></span>
          <div>
            <strong>AI 매장 어시스턴트</strong>
          </div>
          <span v-if="report.used_llm" class="rp-llm-badge">GPT-4o</span>
        </div>

        <div class="rp-chips">
          <button v-for="p in PRESETS" :key="p" class="rp-chip" @click="ask(p)">{{ p }}</button>
        </div>

        <div ref="chatBox" class="rp-chat-body">
          <div v-if="!messages.length" class="rp-chat-intro">
            <p>{{ report.summary }}</p>
            <small>질문을 입력하거나 위 버튼을 눌러 분석을 시작하세요.</small>
          </div>
          <template v-else>
            <div v-for="(msg, i) in messages" :key="i" class="rp-bubble" :class="msg.role">
              <span v-if="msg.role === 'ai'" class="rp-bubble-label">AI</span>
              <p>{{ msg.content }}</p>
            </div>
          </template>
          <div v-if="chatLoading" class="rp-bubble ai">
            <span class="rp-bubble-label">AI</span>
            <p class="rp-typing">분석 중<span class="rp-dot1">.</span><span class="rp-dot2">.</span><span class="rp-dot3">.</span></p>
          </div>
        </div>

        <form class="rp-chat-form" @submit.prevent="ask()">
          <input
            v-model="question"
            placeholder="매장 데이터 기반으로 답변합니다"
            :disabled="chatLoading"
          >
          <button type="submit" :disabled="chatLoading || !question.trim()">전송</button>
        </form>
      </section>

      <!-- ② 핵심 지표 -->
      <section class="rp-metrics">
        <div v-for="m in metrics" :key="m.label" class="rp-metric">
          <span>{{ m.label }}</span>
          <strong v-if="m.unit === '원'">{{ formatKRW(m.value) }}원</strong>
          <strong v-else>{{ m.value ?? '-' }}{{ m.unit || '' }}</strong>
        </div>
      </section>

      <!-- ③ 차트 -->
      <section class="rp-charts">
        <div class="rp-chart-card">
          <h3>월별 판매 추이</h3>
          <div class="rp-chart-wrap">
            <Line :data="monthlyData" :options="lineOpts" />
          </div>
        </div>
        <div class="rp-chart-card">
          <h3>판매 TOP 5</h3>
          <div class="rp-chart-wrap">
            <Bar :data="topMenuData" :options="barOpts" />
          </div>
        </div>
      </section>

      <!-- ③-2 매출 장부 (캘린더) -->
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

      <!-- ④ 재료 가격 위험 -->
      <section v-if="riskItems.length" class="rp-risks">
        <h3>재료 가격 위험</h3>
        <div class="rp-risk-list">
          <div v-for="risk in riskItems" :key="risk.item.code" class="rp-risk-row">
            <span class="rp-risk-name">{{ risk.item.name }}</span>
            <span class="rp-risk-menus">{{ risk.affected_menus.map(m => m.name).join(' · ') || '-' }}</span>
            <strong
              class="rp-risk-rate"
              :class="Math.abs(risk.headline_change_rate) > 5 ? 'rate-danger' : 'rate-warn'"
            >{{ signed(risk.headline_change_rate) }}</strong>
          </div>
        </div>
      </section>

    </template>
  </div>
</template>

<style scoped>
.rp { display: flex; flex-direction: column; gap: 20px; }

/* state */
.rp-state { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 60px 0; color: var(--ink-muted); }

/* ─ AI chat ─ */
.rp-chat {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}
.rp-chat-head {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 16px;
  background: var(--ink);
  color: var(--cream);
}
.rp-ai-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #4ade80; flex-shrink: 0;
  box-shadow: 0 0 6px #4ade80;
}
.rp-chat-head strong { font-size: 14px; font-weight: 600; }
.rp-chat-head span   { font-size: 12px; color: #9BA8A4; }
.rp-llm-badge {
  margin-left: auto;
  font-size: 11px; font-weight: 600;
  background: rgba(224,120,86,.25); color: #E07856;
  border-radius: 4px; padding: 2px 7px;
}
.rp-chips {
  display: flex; gap: 8px; flex-wrap: wrap;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line);
  background: var(--cream);
}
.rp-chip {
  font-size: 12px; font-weight: 500;
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 6px;
  padding: 5px 12px;
  color: var(--ink-soft);
  cursor: pointer;
  transition: background .15s, border-color .15s;
}
.rp-chip:hover { background: var(--cream-deep); border-color: var(--coral); color: var(--ink); }

.rp-chat-body {
  min-height: 140px; max-height: 320px;
  overflow-y: auto;
  padding: 16px;
  display: flex; flex-direction: column; gap: 12px;
}
.rp-chat-intro { color: var(--ink-soft); font-size: 14px; line-height: 1.7; }
.rp-chat-intro small { display: block; margin-top: 8px; color: var(--ink-muted); font-size: 12px; }

.rp-bubble { display: flex; gap: 8px; max-width: 88%; }
.rp-bubble.ai { align-self: flex-start; }
.rp-bubble.user { align-self: flex-end; flex-direction: row-reverse; }
.rp-bubble p {
  margin: 0; padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px; line-height: 1.65;
}
.rp-bubble.ai p    { background: var(--cream-deep); color: var(--ink); }
.rp-bubble.user p  { background: var(--coral); color: #fff; }
.rp-bubble-label {
  font-size: 10px; font-weight: 700;
  background: var(--ink); color: var(--cream);
  border-radius: 4px; padding: 2px 5px;
  height: fit-content; margin-top: 4px; flex-shrink: 0;
}

.rp-typing { display: flex; align-items: baseline; gap: 1px; }
.rp-dot1, .rp-dot2, .rp-dot3 { animation: blink 1.2s infinite; }
.rp-dot2 { animation-delay: .2s; }
.rp-dot3 { animation-delay: .4s; }
@keyframes blink { 0%,80%,100% { opacity: .2 } 40% { opacity: 1 } }

.rp-chat-form {
  display: flex; gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--line);
  background: var(--cream);
}
.rp-chat-form input {
  flex: 1; border: 1px solid var(--line); border-radius: 6px;
  padding: 8px 12px; font-size: 14px; font-family: inherit;
  background: #fff; outline: none;
  transition: border-color .15s;
}
.rp-chat-form input:focus { border-color: var(--coral); }
.rp-chat-form button {
  background: var(--coral); color: #fff;
  border: none; border-radius: 6px;
  padding: 8px 18px; font-size: 14px; font-weight: 600;
  cursor: pointer; transition: opacity .15s;
}
.rp-chat-form button:disabled { opacity: .45; cursor: default; }

/* ─ metrics ─ */
.rp-metrics {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
}
@media (max-width: 640px) { .rp-metrics { grid-template-columns: repeat(2, 1fr); } }
.rp-metric {
  background: #fff; border: 1px solid var(--line); border-radius: 8px;
  padding: 16px; display: flex; flex-direction: column; gap: 6px;
}
.rp-metric span   { font-size: 12px; color: var(--ink-muted); font-weight: 500; }
.rp-metric strong { font-size: 18px; font-weight: 700; color: var(--ink); }

/* ─ charts ─ */
.rp-charts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 720px) { .rp-charts { grid-template-columns: 1fr; } }
.rp-chart-card {
  background: #fff; border: 1px solid var(--line); border-radius: 8px;
  padding: 16px 20px;
}
.rp-chart-card h3 { font-size: 14px; font-weight: 600; color: var(--ink); margin-bottom: 14px; }
.rp-chart-wrap { height: 200px; }

/* ─ 매출 장부 (캘린더) ─ */
.rp-ledger {
  background: #fff; border: 1px solid var(--line); border-radius: 12px;
  padding: 20px 22px; margin-top: 16px;
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

/* ─ risks ─ */
.rp-risks {
  background: #fff; border: 1px solid var(--line); border-radius: 8px;
  padding: 16px 20px;
}
.rp-risks h3 { font-size: 14px; font-weight: 600; color: var(--ink); margin-bottom: 12px; }
.rp-risk-list { display: flex; flex-direction: column; gap: 1px; }
.rp-risk-row {
  display: grid; grid-template-columns: 80px 1fr auto;
  align-items: center; gap: 12px;
  padding: 10px 0;
  border-top: 1px solid var(--line);
  font-size: 14px;
}
.rp-risk-row:first-child { border-top: none; }
.rp-risk-name  { font-weight: 600; color: var(--ink); }
.rp-risk-menus { color: var(--ink-muted); font-size: 13px; }
.rp-risk-rate  { font-weight: 700; font-size: 15px; }
.rate-danger   { color: #C44536; }
.rate-warn     { color: var(--gold); }
</style>
