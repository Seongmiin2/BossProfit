<script setup>
import { ref, onMounted, computed } from 'vue'
import { Line as LineChart } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js'
import client from '@/api/client'
import { formatKRW } from '@/utils/format'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

const loading = ref(false)
const error = ref(null)
const days = ref(30)
const selectedMenu = ref('')
const menus = ref([])

const chartData = ref(null)
const chartOptions = ref({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'top',
    },
  },
  scales: {
    y: {
      beginAtZero: true,
    },
  },
})

onMounted(async () => {
  await loadMenus()
  await loadHistory()
})

async function loadMenus() {
  try {
    const { data } = await client.get('/menus/')
    menus.value = data.map(item => ({
      menu_id: item.menu.menu_id,
      name: item.menu.name,
    }))
  } catch (e) {
    console.error('Failed to load menus:', e)
  }
}

async function loadHistory() {
  loading.value = true
  error.value = null
  try {
    const params = new URLSearchParams()
    params.append('days', days.value)
    if (selectedMenu.value) {
      params.append('menu_id', selectedMenu.value)
    }

    const { data } = await client.get(`/history/?${params.toString()}`)

    chartData.value = {
      labels: data.dates,
      datasets: [
        {
          label: '월 예상 이익 (원)',
          data: data.profit,
          borderColor: '#ff6b6b',
          backgroundColor: 'rgba(255, 107, 107, 0.1)',
          yAxisID: 'y',
          tension: 0.4,
        },
        {
          label: '월 매출 (원)',
          data: data.revenue,
          borderColor: '#4ecdc4',
          backgroundColor: 'rgba(78, 205, 196, 0.1)',
          yAxisID: 'y1',
          tension: 0.4,
        },
      ],
    }

    chartOptions.value.scales = {
      y: {
        type: 'linear',
        display: true,
        position: 'left',
        title: {
          display: true,
          text: '이익 (원)',
        },
      },
      y1: {
        type: 'linear',
        display: true,
        position: 'right',
        title: {
          display: true,
          text: '매출 (원)',
        },
        grid: {
          drawOnChartArea: false,
        },
      },
    }
  } catch (e) {
    error.value = e.message
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function handleFilterChange() {
  await loadHistory()
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="banner">
      <h1>📈 수익성 추이</h1>
    </div>

    <!-- Filters -->
    <div style="background: var(--cream); padding: 16px; border-radius: 4px; margin-bottom: 24px; display: grid; grid-template-columns: auto auto auto; gap: 12px; align-items: end;">
      <div>
        <label class="form-label">기간</label>
        <select v-model.number="days" @change="handleFilterChange" class="form-control" style="width: 120px;">
          <option :value="7">7일</option>
          <option :value="30">30일</option>
          <option :value="60">60일</option>
          <option :value="90">90일</option>
        </select>
      </div>

      <div>
        <label class="form-label">메뉴</label>
        <select v-model="selectedMenu" @change="handleFilterChange" class="form-control">
          <option value="">전체</option>
          <option v-for="menu in menus" :key="menu.menu_id" :value="menu.menu_id">
            {{ menu.name }}
          </option>
        </select>
      </div>

      <button @click="handleFilterChange" class="btn-coral" style="padding: 10px 16px; font-weight: 700;">
        조회
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" style="text-align: center; padding: 40px;">
      <div class="spinner"></div>
      <p>데이터 로드 중...</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" style="color: var(--coral-deep); padding: 20px; background: var(--paper); border: 1px solid var(--line);">
      ⚠️ {{ error }}
    </div>

    <!-- Chart -->
    <div v-else-if="chartData" style="background: white; padding: 20px; border-radius: 4px; border: 1px solid var(--line); margin-bottom: 24px;">
      <div style="position: relative; height: 400px;">
        <LineChart :data="chartData" :options="chartOptions" />
      </div>
    </div>

    <!-- No data -->
    <div v-else style="text-align: center; padding: 40px; color: var(--ink-light);">
      <p>데이터가 없습니다.</p>
      <small>메뉴를 추가하고 재계산을 실행하면 차트가 표시됩니다.</small>
    </div>

    <!-- Legend -->
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 24px;">
      <div style="background: var(--cream); padding: 12px; border-radius: 4px;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
          <div style="width: 12px; height: 12px; background: #ff6b6b; border-radius: 2px;"></div>
          <strong>월 예상 이익</strong>
        </div>
        <small style="color: var(--ink-light);">메뉴별 이익의 합계</small>
      </div>

      <div style="background: var(--cream); padding: 12px; border-radius: 4px;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
          <div style="width: 12px; height: 12px; background: #4ecdc4; border-radius: 2px;"></div>
          <strong>월 매출</strong>
        </div>
        <small style="color: var(--ink-light);">메뉴별 매출의 합계</small>
      </div>
    </div>
  </div>
</template>

<style scoped>
.form-label {
  display: block;
  margin-bottom: 6px;
  font-weight: 600;
  color: var(--ink);
  font-size: 13px;
}

.form-control {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-radius: 4px;
  font-size: 14px;
}

.form-control:focus {
  outline: none;
  border-color: var(--coral);
}
</style>
