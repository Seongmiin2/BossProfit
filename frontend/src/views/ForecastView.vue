<script setup>
import { ref, computed, onMounted } from 'vue'
import { Line as LineChart } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler,
} from 'chart.js'
import { useForecastStore } from '@/stores/forecast'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const store = useForecastStore()

const confidenceLabel = { HIGH: '높음', MEDIUM: '보통', LOW: '낮음' }
const confidenceColor = { HIGH: '#2f9e44', MEDIUM: '#f08c00', LOW: '#e03131' }
const categoryFilter = ref('전체')

onMounted(async () => {
  await store.loadIngredients()
  const first = store.ingredients.find((i) => i.market_code)
  if (first) await store.loadDetail(first.market_code)
})

const categories = computed(() => {
  const set = new Set((store.ingredients || []).map((i) => i.category).filter(Boolean))
  return ['전체', ...set]
})

const rows = computed(() => {
  const list = store.ingredients || []
  if (categoryFilter.value === '전체') return list
  return list.filter((i) => i.category === categoryFilter.value)
})

function pointFor(row, horizon) {
  return (row.points || []).find((p) => p.horizon_days === horizon) || null
}

function deltaColor(rate) {
  if (rate == null) return '#868e96'
  if (rate > 0.5) return '#e03131'
  if (rate < -0.5) return '#1c7ed6'
  return '#868e96'
}

async function selectRow(row) {
  if (row.market_code) await store.loadDetail(row.market_code)
}

const selectedName = computed(() => store.detail?.item?.name || '')
const unit = computed(() => store.detail?.item?.unit || '')

const chartData = computed(() => {
  const d = store.detail
  if (!d || !d.history) return null
  const hDates = d.history.dates
  const hPrices = d.history.prices
  const points = [...d.points].sort((a, b) => a.horizon_days - b.horizon_days)

  const labels = [...hDates, ...points.map((p) => p.target_date)]
  const n = labels.length
  const lastIdx = hDates.length - 1
  const lastActual = hPrices[hPrices.length - 1]
  const fill = (len) => new Array(len).fill(null)

  const actual = [...hPrices, ...fill(points.length)]
  const median = fill(n), lower = fill(n), upper = fill(n)
  if (lastIdx >= 0) { median[lastIdx] = lastActual; lower[lastIdx] = lastActual; upper[lastIdx] = lastActual }
  points.forEach((p, i) => {
    const idx = hDates.length + i
    median[idx] = Number(p.median); lower[idx] = Number(p.lower_80); upper[idx] = Number(p.upper_80)
  })

  return {
    labels,
    datasets: [
      { label: '실제 단가', data: actual, borderColor: '#1c7ed6', borderWidth: 2, pointRadius: 0, tension: 0.3 },
      { label: '예측 중앙값', data: median, borderColor: '#f76707', borderWidth: 2, borderDash: [6, 4], pointRadius: 3, tension: 0.2 },
      { label: '80% 하한', data: lower, borderColor: 'rgba(247,103,7,0.25)', borderWidth: 1, pointRadius: 0 },
      { label: '80% 상한', data: upper, borderColor: 'rgba(247,103,7,0.25)', backgroundColor: 'rgba(247,103,7,0.12)', borderWidth: 1, pointRadius: 0, fill: '-1' },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { position: 'top' },
    tooltip: { callbacks: { label: (ctx) => ctx.parsed.y == null ? null : `${ctx.dataset.label}: ${ctx.parsed.y} 원` } },
  },
  scales: { y: { title: { display: true, text: '단가 (원/단위)' } } },
}
</script>

<template>
  <div>
    <div class="banner">
      <h1>🔮 재료 가격 예측</h1>
      <p style="margin: 4px 0 0; opacity: 0.85;">{{ store.storeName }} · 내 재료 {{ store.ingredients?.length ?? 0 }}개의 단가 추세 예측</p>
    </div>

    <div v-if="store.error" style="background:#ffe3e3;color:#c92a2a;padding:12px;border-radius:4px;margin-bottom:16px;">
      {{ store.error }}
    </div>

    <div v-if="store.listLoading" style="padding:40px;text-align:center;color:#868e96;">불러오는 중…</div>

    <template v-else>
      <!-- 차트: 선택된 재료 -->
      <div style="background:#fff;border:1px solid #e9ecef;border-radius:4px;padding:16px;margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <strong>{{ selectedName || '재료를 선택하세요' }}</strong>
          <span v-if="store.detail" style="color:#868e96;font-size:0.85rem;">기준일 {{ store.detail.as_of }}</span>
        </div>
        <div style="height:300px;">
          <LineChart v-if="chartData" :data="chartData" :options="chartOptions" />
          <div v-else style="height:100%;display:flex;align-items:center;justify-content:center;color:#adb5bd;">
            예측 데이터 없음
          </div>
        </div>
      </div>

      <!-- 카테고리 필터 -->
      <div style="margin:16px 0 8px;display:flex;gap:8px;flex-wrap:wrap;">
        <button v-for="c in categories" :key="c" @click="categoryFilter = c"
          :style="{
            padding:'4px 12px', borderRadius:'14px', cursor:'pointer', fontSize:'0.85rem',
            border:'1px solid ' + (categoryFilter===c ? '#f76707' : '#dee2e6'),
            background: categoryFilter===c ? '#f76707' : '#fff',
            color: categoryFilter===c ? '#fff' : '#495057',
          }">
          {{ c }}
        </button>
      </div>

      <!-- 재료별 예측 테이블 -->
      <div style="background:#fff;border:1px solid #e9ecef;border-radius:4px;overflow:hidden;">
        <table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
          <thead>
            <tr style="background:#f8f9fa;text-align:left;">
              <th style="padding:10px 14px;">재료</th>
              <th style="padding:10px 14px;">카테고리</th>
              <th style="padding:10px 14px;text-align:right;">공급단가</th>
              <th style="padding:10px 14px;text-align:right;">현재 단가<br><span style="font-size:0.7rem;color:#adb5bd;font-weight:400;">KAMIS 시세</span></th>
              <th style="padding:10px 14px;text-align:right;">7일 예측</th>
              <th style="padding:10px 14px;text-align:right;">30일 예측</th>
              <th style="padding:10px 14px;text-align:center;">신뢰</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.ingredient_id" @click="selectRow(row)"
              :style="{
                cursor:'pointer', borderTop:'1px solid #f1f3f5',
                background: store.selectedCode===row.market_code ? '#fff4e6' : 'transparent',
              }">
              <td style="padding:9px 14px;font-weight:600;">{{ row.name }}</td>
              <td style="padding:9px 14px;color:#868e96;">{{ row.category || '-' }}</td>
              <td style="padding:9px 14px;text-align:right;">{{ row.supply_unit_cost }} <span style="color:#adb5bd;font-size:0.8rem;">원/{{ row.unit }}</span></td>
              <td style="padding:9px 14px;text-align:right;">
                <template v-if="row.market_price != null">{{ row.market_price }} <span style="color:#adb5bd;font-size:0.8rem;">원/{{ row.unit }}</span></template>
                <span v-else style="color:#adb5bd;">-</span>
              </td>
              <td v-for="h in [7,30]" :key="h" style="padding:9px 14px;text-align:right;">
                <template v-if="pointFor(row,h)">
                  {{ pointFor(row,h).median }}
                  <span :style="{color: deltaColor(pointFor(row,h).delta_rate), fontSize:'0.8rem', display:'block'}">
                    {{ pointFor(row,h).delta_rate > 0 ? '▲' : pointFor(row,h).delta_rate < 0 ? '▼' : '–' }}
                    {{ Math.abs(pointFor(row,h).delta_rate ?? 0) }}%
                  </span>
                </template>
                <span v-else style="color:#adb5bd;">-</span>
              </td>
              <td style="padding:9px 14px;text-align:center;">
                <span v-if="pointFor(row,30)"
                  :style="{background: confidenceColor[pointFor(row,30).confidence], color:'#fff', padding:'2px 8px', borderRadius:'10px', fontSize:'0.75rem'}">
                  {{ confidenceLabel[pointFor(row,30).confidence] }}
                </span>
                <span v-else style="color:#adb5bd;">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p style="margin-top:14px;font-size:0.78rem;color:#adb5bd;">
        ▲ 가격 상승 예상(원가 부담↑) · ▼ 하락 예상 · 행을 클릭하면 해당 재료의 시계열 예측 차트를 봅니다.
        실제 시세가 없는 가공재료는 현재 단가 기준 합성 시세로 추세를 추정합니다.
      </p>
    </template>
  </div>
</template>
