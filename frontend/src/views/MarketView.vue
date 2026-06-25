<script setup>
import { onMounted, computed } from 'vue'
import { useMarketStore } from '@/stores/market'
import { useAuthStore } from '@/stores/auth'
import { formatKRW } from '@/utils/format'

const marketStore = useMarketStore()
const authStore = useAuthStore()

const changedCount = computed(() =>
  marketStore.changes.filter((c) => c.changed).length
)

const sourceLabel = computed(() =>
  marketStore.source === 'kamis' ? 'KAMIS 실시간 시세' : '모의 시세 (데모)'
)

onMounted(() => {
  // 시세 비교는 내 매장 식자재 기준이므로 로그인 사용자만 조회한다.
  if (authStore.isLoggedIn) {
    marketStore.loadPreview()
  }
})

async function handleSyncAll() {
  if (!authStore.isLoggedIn) return
  if (!confirm(`변동된 ${changedCount.value}개 식자재 단가를 시세로 반영하고 전체 메뉴를 재계산합니다. 진행할까요?`)) {
    return
  }
  try {
    const result = await marketStore.sync()
    alert(result.message)
  } catch (e) {
    alert('반영 실패: ' + (marketStore.error || e.message))
  }
}

async function handleSyncOne(change) {
  if (!authStore.isLoggedIn) return
  try {
    const result = await marketStore.sync([change.ingredient_id])
    alert(result.message)
  } catch (e) {
    alert('반영 실패: ' + (marketStore.error || e.message))
  }
}

function deltaColor(delta) {
  if (delta > 0) return '#e03131' // 상승: 빨강
  if (delta < 0) return '#1c7ed6' // 하락: 파랑
  return 'var(--ink-light)'
}

function deltaSign(n) {
  return n > 0 ? `+${formatKRW(n)}` : formatKRW(n)
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="banner" style="display: flex; justify-content: space-between; align-items: center;">
      <h1>🥬 식재료 시세 연동</h1>
      <span class="source-chip">{{ sourceLabel }}</span>
    </div>

    <p style="color: var(--ink-light); margin: 12px 0 20px;">
      외부 시세를 불러와 식자재 구매 단가와 비교합니다. 반영하면 단가가 갱신되고 전체 메뉴 수익성이 재계산됩니다.
      <span v-if="marketStore.asOf">(기준일: {{ marketStore.asOf }})</span>
    </p>

    <!-- 비로그인: 내 매장 시세 비교는 로그인 후 -->
    <div v-if="!authStore.isLoggedIn" style="text-align: center; padding: 40px; background: var(--cream); border: 1px solid var(--line); border-radius: 4px;">
      <p style="font-weight: 600; margin-bottom: 8px;">🔒 내 매장 식자재 시세 비교</p>
      <p style="color: var(--ink-light); margin-bottom: 16px;">
        로그인하면 내가 등록한 식자재의 구매 단가와 현재 시세를 비교할 수 있어요.
      </p>
      <RouterLink to="/login" class="btn-coral" style="padding: 10px 20px; font-weight: 700; text-decoration: none;">
        로그인하기
      </RouterLink>
    </div>

    <!-- Loading -->
    <div v-else-if="marketStore.loading && !marketStore.changes.length" style="text-align: center; padding: 40px;">
      <div class="spinner"></div>
      <p>시세 불러오는 중...</p>
    </div>

    <!-- Error -->
    <div v-else-if="marketStore.error" style="color: var(--coral-deep); padding: 20px; background: var(--paper); border: 1px solid var(--line);">
      ⚠️ {{ marketStore.error }}
    </div>

    <template v-else>
      <!-- Summary -->
      <div v-if="marketStore.summary" class="summary-grid">
        <div class="summary-card">
          <div class="summary-num">{{ marketStore.summary.total }}</div>
          <div class="summary-label">조회 품목</div>
        </div>
        <div class="summary-card">
          <div class="summary-num" style="color: #e03131;">▲ {{ marketStore.summary.up }}</div>
          <div class="summary-label">상승</div>
        </div>
        <div class="summary-card">
          <div class="summary-num" style="color: #1c7ed6;">▼ {{ marketStore.summary.down }}</div>
          <div class="summary-label">하락</div>
        </div>
        <div class="summary-card">
          <div class="summary-num" style="color: var(--ink-light);">{{ marketStore.summary.unchanged }}</div>
          <div class="summary-label">변동 없음</div>
        </div>
      </div>

      <!-- Actions -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin: 20px 0 12px;">
        <strong>제안된 단가 변경 ({{ changedCount }}건)</strong>
        <button
          v-if="authStore.isLoggedIn"
          class="btn-coral"
          style="padding: 10px 16px; font-weight: 700;"
          :disabled="marketStore.syncing || changedCount === 0"
          @click="handleSyncAll"
        >
          {{ marketStore.syncing ? '반영 중...' : '⟳ 전체 반영 + 재계산' }}
        </button>
        <small v-else style="color: var(--ink-light);">단가 반영은 로그인 후 가능합니다.</small>
      </div>

      <!-- Table -->
      <div style="overflow-x: auto; border: 1px solid var(--line); border-radius: 4px;">
        <table class="market-table">
          <thead>
            <tr>
              <th>식자재</th>
              <th>분류</th>
              <th class="num">현재 단가</th>
              <th class="num">시세</th>
              <th class="num">증감</th>
              <th class="num">변동률</th>
              <th v-if="authStore.isLoggedIn"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in marketStore.changes" :key="c.ingredient_id" :class="{ unchanged: !c.changed }">
              <td>
                <strong>{{ c.name }}</strong>
              </td>
              <td>{{ c.category || '-' }}</td>
              <td class="num">{{ formatKRW(c.current_price) }}원</td>
              <td class="num">{{ formatKRW(c.market_price) }}원</td>
              <td class="num" :style="{ color: deltaColor(c.delta), fontWeight: 600 }">
                {{ deltaSign(c.delta) }}원
              </td>
              <td class="num" :style="{ color: deltaColor(c.delta), fontWeight: 600 }">
                {{ c.delta_rate > 0 ? '+' : '' }}{{ c.delta_rate }}%
              </td>
              <td v-if="authStore.isLoggedIn" class="num">
                <button
                  class="btn-line"
                  :disabled="!c.changed || marketStore.syncing"
                  @click="handleSyncOne(c)"
                >
                  반영
                </button>
              </td>
            </tr>
            <tr v-if="!marketStore.changes.length">
              <td :colspan="authStore.isLoggedIn ? 7 : 6" style="text-align: center; padding: 30px; color: var(--ink-light);">
                조회된 시세가 없습니다.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.source-chip {
  background: var(--cream);
  color: var(--ink);
  font-size: 13px;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--line);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.summary-card {
  background: var(--cream);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 16px;
  text-align: center;
}

.summary-num {
  font-size: 26px;
  font-weight: 800;
  color: var(--ink);
}

.summary-label {
  margin-top: 4px;
  font-size: 13px;
  color: var(--ink-light);
}

.market-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  font-size: 14px;
}

.market-table th,
.market-table td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
  text-align: left;
}

.market-table th {
  background: var(--cream);
  font-weight: 700;
  font-size: 13px;
}

.market-table .num {
  text-align: right;
}

.market-table tr.unchanged td {
  color: var(--ink-light);
  background: #fafafa;
}

.btn-line {
  padding: 5px 12px;
  border: 1px solid var(--coral);
  background: white;
  color: var(--coral-deep, var(--coral));
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
}

.btn-line:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
