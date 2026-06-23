<script setup>
import { onMounted, ref } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import { formatKRW } from '@/utils/format'
import SignalBadge from '@/components/SignalBadge.vue'
import { useRouter } from 'vue-router'

const dashboardStore = useDashboardStore()
const authStore = useAuthStore()
const router = useRouter()

const showAssumptionModal = ref(false)
const assumptionForm = ref({})

onMounted(() => {
  console.log('DashboardView mounted, loading data...')
  dashboardStore.load()
})

const goToDetail = (menuId) => {
  router.push({ name: 'MenuDetail', params: { menuId } })
}

const openAssumptionModal = () => {
  if (dashboardStore.assumption) {
    assumptionForm.value = { ...dashboardStore.assumption }
  }
  showAssumptionModal.value = true
}

const closeAssumptionModal = () => {
  showAssumptionModal.value = false
}

const handleAssumptionSubmit = async () => {
  try {
    await dashboardStore.updateAssumption(assumptionForm.value)
    alert('가정 수정 완료')
    closeAssumptionModal()
  } catch (e) {
    console.error(e)
  }
}
</script>

<template>
  <div>
    <!-- Loading state -->
    <div v-if="dashboardStore.loading" style="text-align: center; padding: 40px;">
      <div class="spinner"></div>
      <p>데이터 로드 중...</p>
    </div>

    <!-- Error state -->
    <div v-else-if="dashboardStore.error" style="color: var(--coral-deep); padding: 20px; background: var(--paper); border: 1px solid var(--line);">
      ⚠️ 오류: {{ dashboardStore.error }}
    </div>

    <!-- Success state -->
    <div v-else-if="dashboardStore.summary">
      <!-- Banner -->
      <div class="banner">
        <h1>
          <span class="coral">BOSSPROFIT</span>
          <br>
          {{ dashboardStore.storeName }}
        </h1>
        <div class="banner-meta">
          메뉴 <strong>{{ dashboardStore.snapshots.length }}</strong>개 · 최근 재계산
        </div>
      </div>

      <!-- KPI Grid -->
      <div class="kpi-grid">
        <div class="kpi">
          <div class="kpi-label">월 예상 매출</div>
          <div class="kpi-value">{{ formatKRW(dashboardStore.summary.total_revenue) }}<span class="kpi-unit">원</span></div>
        </div>
        <div class="kpi">
          <div class="kpi-label">월 예상 이익</div>
          <div class="kpi-value coral">{{ formatKRW(dashboardStore.summary.total_profit) }}<span class="kpi-unit">원</span></div>
        </div>
        <div class="kpi">
          <div class="kpi-label">평균 원가율</div>
          <div class="kpi-value">{{ dashboardStore.summary.avg_food_cost_rate.toFixed(1) }}<span class="kpi-unit">%</span></div>
        </div>
        <div class="kpi">
          <div class="kpi-label">총 주문 건수</div>
          <div class="kpi-value">{{ dashboardStore.summary.total_orders }}<span class="kpi-unit">건</span></div>
        </div>
        <div class="kpi">
          <div class="kpi-label">메뉴당 평균 판매</div>
          <div class="kpi-value">{{ dashboardStore.summary.avg_orders.toFixed(1) }}<span class="kpi-unit">건</span></div>
        </div>
        <div class="kpi">
          <div class="kpi-label">배달 손실 메뉴</div>
          <div class="kpi-value red">{{ dashboardStore.summary.delivery_loss_count }}<span class="kpi-unit">개</span></div>
        </div>
      </div>

      <!-- Insights -->
      <div class="sect-head">
        <span class="sect-label">핵심 인사이트</span>
        <h2>지금 주목할 4가지</h2>
      </div>
      <div class="insights">
        <div v-for="(insight, idx) in dashboardStore.insights" :key="idx" class="insight">
          <div class="insight-text">
            <div class="insight-label">{{ insight.label }}</div>
            <div class="insight-comment">{{ insight.comment }}</div>
          </div>
          <div class="insight-value">{{ insight.value }}</div>
        </div>
      </div>

      <!-- Snapshots Table -->
      <div class="sect-head">
        <span class="sect-label">신호등 분석</span>
        <h2>메뉴별 수익성</h2>
      </div>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>메뉴</th>
              <th class="right">판매가</th>
              <th class="right">월판매량</th>
              <th class="right">원가율</th>
              <th class="right">가중마진</th>
              <th class="right">월이익</th>
              <th>평가</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="snap in dashboardStore.snapshots" :key="snap.menu.menu_id">
              <td class="menu-name">
                <a @click.prevent="goToDetail(snap.menu.menu_id)" href="#" style="cursor: pointer; color: var(--ink);">
                  {{ snap.menu.name }}
                </a>
                <span class="cat">{{ snap.menu.category }}</span>
              </td>
              <td class="right tabular">{{ formatKRW(snap.menu.price) }}</td>
              <td class="right tabular">{{ snap.menu.monthly_orders }}</td>
              <td class="right tabular">{{ (snap.food_cost_rate * 100).toFixed(1) }}%</td>
              <td class="right tabular">{{ formatKRW(snap.weighted_margin) }}</td>
              <td class="right tabular">
                <strong :class="snap.monthly_profit >= 0 ? '' : 'cost-high'">
                  {{ formatKRW(snap.monthly_profit) }}
                </strong>
              </td>
              <td>
                <SignalBadge :signal="snap.signal" :signal-color="snap.signal_color" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Assumption Box -->
      <div class="assumption-box">
        <div class="title">
          📋 현재 가정
          <button
            v-if="authStore.isLoggedIn"
            @click="openAssumptionModal"
            class="btn-coral"
            style="padding: 4px 12px; font-size: 12px; float: right;"
          >
            수정
          </button>
        </div>
        <div class="assumption-grid">
          <div>
            <strong>홀 판매 비중</strong>
            <div>{{ (dashboardStore.assumption.dine_in_share * 100).toFixed(0) }}%</div>
          </div>
          <div>
            <strong>배달 판매 비중</strong>
            <div>{{ (dashboardStore.assumption.delivery_share * 100).toFixed(0) }}%</div>
          </div>
          <div>
            <strong>포장 판매 비중</strong>
            <div>{{ (dashboardStore.assumption.takeout_share * 100).toFixed(0) }}%</div>
          </div>
          <div>
            <strong>배달앱 수수료</strong>
            <div>{{ (dashboardStore.assumption.delivery_commission_rate * 100).toFixed(0) }}%</div>
          </div>
          <div>
            <strong>배달 기사 수수료</strong>
            <div>{{ formatKRW(dashboardStore.assumption.rider_fee) }}</div>
          </div>
          <div>
            <strong>기사료 가게 부담</strong>
            <div>{{ (dashboardStore.assumption.rider_fee_store_share * 100).toFixed(0) }}%</div>
          </div>
          <div>
            <strong>목표 원가율</strong>
            <div>{{ (dashboardStore.assumption.target_food_cost_rate * 100).toFixed(0) }}%</div>
          </div>
          <div>
            <strong>가정 이름</strong>
            <div>{{ dashboardStore.assumption.label }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- No data -->
    <div v-else style="text-align: center; padding: 40px;">
      <p>데이터가 없습니다.</p>
    </div>

    <!-- Assumption Modal -->
    <div v-if="showAssumptionModal" style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;">
      <div style="background: white; padding: 32px; border-radius: 8px; max-width: 600px; width: 90%;">
        <h2 style="margin-bottom: 24px;">가정 수정</h2>

        <form @submit.prevent="handleAssumptionSubmit">
          <!-- 가정 이름 -->
          <div class="mb-3">
            <label class="form-label">가정 이름</label>
            <input v-model="assumptionForm.label" type="text" class="form-control" />
          </div>

          <!-- 판매 비중 -->
          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 12px;">
            <div>
              <label class="form-label">홀 판매 비중</label>
              <div style="display: flex; align-items: center; gap: 8px;">
                <input
                  v-model.number="assumptionForm.dine_in_share"
                  type="number"
                  class="form-control"
                  step="0.01"
                  min="0"
                  max="1"
                />
                <span style="white-space: nowrap;">{{ (assumptionForm.dine_in_share * 100).toFixed(0) }}%</span>
              </div>
            </div>
            <div>
              <label class="form-label">배달 판매 비중</label>
              <div style="display: flex; align-items: center; gap: 8px;">
                <input
                  v-model.number="assumptionForm.delivery_share"
                  type="number"
                  class="form-control"
                  step="0.01"
                  min="0"
                  max="1"
                />
                <span style="white-space: nowrap;">{{ (assumptionForm.delivery_share * 100).toFixed(0) }}%</span>
              </div>
            </div>
            <div>
              <label class="form-label">포장 판매 비중</label>
              <div style="display: flex; align-items: center; gap: 8px;">
                <input
                  v-model.number="assumptionForm.takeout_share"
                  type="number"
                  class="form-control"
                  step="0.01"
                  min="0"
                  max="1"
                />
                <span style="white-space: nowrap;">{{ (assumptionForm.takeout_share * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>

          <!-- 배달 조건 -->
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;">
            <div>
              <label class="form-label">배달앱 수수료율</label>
              <div style="display: flex; align-items: center; gap: 8px;">
                <input
                  v-model.number="assumptionForm.delivery_commission_rate"
                  type="number"
                  class="form-control"
                  step="0.01"
                  min="0"
                  max="1"
                />
                <span style="white-space: nowrap;">{{ (assumptionForm.delivery_commission_rate * 100).toFixed(0) }}%</span>
              </div>
            </div>
            <div>
              <label class="form-label">배달 기사 수수료</label>
              <input
                v-model.number="assumptionForm.rider_fee"
                type="number"
                class="form-control"
              />
            </div>
          </div>

          <!-- 기타 -->
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;">
            <div>
              <label class="form-label">기사료 가게 부담률</label>
              <div style="display: flex; align-items: center; gap: 8px;">
                <input
                  v-model.number="assumptionForm.rider_fee_store_share"
                  type="number"
                  class="form-control"
                  step="0.01"
                  min="0"
                  max="1"
                />
                <span style="white-space: nowrap;">{{ (assumptionForm.rider_fee_store_share * 100).toFixed(0) }}%</span>
              </div>
            </div>
            <div>
              <label class="form-label">목표 원가율</label>
              <div style="display: flex; align-items: center; gap: 8px;">
                <input
                  v-model.number="assumptionForm.target_food_cost_rate"
                  type="number"
                  class="form-control"
                  step="0.01"
                  min="0"
                  max="1"
                />
                <span style="white-space: nowrap;">{{ (assumptionForm.target_food_cost_rate * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>

          <!-- 버튼 -->
          <div style="display: flex; gap: 12px; margin-top: 24px;">
            <button type="submit" class="btn-coral" style="flex: 1; padding: 10px; font-weight: 700;">
              수정하기
            </button>
            <button type="button" class="btn" style="flex: 1; padding: 10px;" @click="closeAssumptionModal">
              취소
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
