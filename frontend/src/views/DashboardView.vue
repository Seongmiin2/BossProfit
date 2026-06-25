<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchStoreAnalysis } from '@/api/endpoints'
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
const connectionPriority = computed(() =>
  (analysis.value?.menus || []).filter(m => m.recipe.status !== 'READY').slice(0, 3),
)

const signed = v =>
  v != null ? `${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(1)}%` : null
const forecast = (risk, days) => risk.forecasts?.find(f => f.horizon_days === days)
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
      <!-- ① 페이지 헤더 -->
      <div class="welcome-row">
        <div>
          <span class="eyebrow">{{ analysis.store.name }}</span>
          <h1>지금 어떤 메뉴를<br>밀어야 할까요?</h1>
        </div>
        <div class="welcome-actions desktop-only">
          <span class="data-date-badge">기준 {{ analysis.data_as_of }}</span>
          <router-link to="/history" class="soft-button">AI 분석 리포트</router-link>
        </div>
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
      <section class="section-block">
        <div class="section-title-row">
          <h2>판매 상위 메뉴</h2>
          <router-link to="/menus">전체 보기 →</router-link>
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

      <!-- ⑤ 먼저 연결할 메뉴 (레시피 미연결 상위 3개) -->
      <section v-if="connectionPriority.length" class="section-block">
        <div class="section-title-row">
          <h2>먼저 연결할 메뉴</h2>
        </div>
        <div class="story-list">
          <div
            v-for="(menu, idx) in connectionPriority"
            :key="menu.menu_id"
            class="story-card"
            style="cursor:pointer"
            @click="router.push(`/menus/${menu.menu_id}`)"
          >
            <div class="story-number">{{ idx + 1 }}</div>
            <div>
              <strong>{{ menu.name }}</strong>
              <p>{{ menu.quantity.toLocaleString() }}개 판매 · {{ menu.recipe.reason }}</p>
            </div>
            <b>연결 →</b>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
