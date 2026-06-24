<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMenuStore } from '@/stores/menu'
import { useAuthStore } from '@/stores/auth'
import { formatKRW } from '@/utils/format'
import SignalBadge from '@/components/SignalBadge.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'

const menuStore = useMenuStore()
const authStore = useAuthStore()
const router = useRouter()
const query = ref('')
const filter = ref('all')

onMounted(() => menuStore.loadList())

const filteredMenus = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  return menuStore.menus.filter((snap) => {
    const matchesQuery = !keyword
      || snap.menu.name.toLowerCase().includes(keyword)
      || snap.menu.category.toLowerCase().includes(keyword)
    const matchesFilter = filter.value === 'all'
      || (filter.value === 'good' && snap.signal_color === 'green')
      || (filter.value === 'care' && snap.signal_color !== 'green')
    return matchesQuery && matchesFilter
  })
})

const profitableCount = computed(() =>
  menuStore.menus.filter((snap) => snap.signal_color === 'green').length
)

const goToDetail = (menuId) => {
  router.push({ name: 'MenuDetail', params: { menuId } })
}
</script>

<template>
  <div class="menu-list-page">
    <section class="page-intro">
      <div>
        <span class="section-kicker">메뉴 수익 탐색</span>
        <h1>어떤 메뉴가<br>가게를 키우고 있을까요?</h1>
        <p>판매량뿐 아니라 실제로 남는 이익까지 함께 살펴보세요.</p>
      </div>
      <router-link v-if="authStore.isLoggedIn" to="/menus/create" class="primary-button">
        + 새 메뉴
      </router-link>
    </section>

    <section class="menu-overview-strip">
      <div>
        <span>전체 메뉴</span>
        <strong>{{ menuStore.menus.length }}개</strong>
      </div>
      <div>
        <span>건강한 메뉴</span>
        <strong>{{ profitableCount }}개</strong>
      </div>
      <div>
        <span>관리 추천</span>
        <strong>{{ menuStore.menus.length - profitableCount }}개</strong>
      </div>
    </section>

    <div class="menu-toolbar">
      <label class="search-box">
        <span>⌕</span>
        <input v-model="query" type="search" placeholder="메뉴명이나 카테고리 검색">
      </label>
      <div class="filter-tabs">
        <button :class="{ active: filter === 'all' }" @click="filter = 'all'">전체</button>
        <button :class="{ active: filter === 'good' }" @click="filter = 'good'">건강</button>
        <button :class="{ active: filter === 'care' }" @click="filter = 'care'">관리 추천</button>
      </div>
    </div>

    <div v-if="menuStore.loading" class="state-card compact-state">
      <LoadingSpinner />
      <strong>메뉴를 정리하고 있어요</strong>
    </div>

    <div v-else-if="menuStore.error" class="state-card compact-state state-error">
      <span>!</span>
      <strong>메뉴를 불러오지 못했어요</strong>
      <p>{{ menuStore.error }}</p>
    </div>

    <div v-else-if="filteredMenus.length" class="menu-grid modern-menu-grid">
      <button
        v-for="snap in filteredMenus"
        :key="snap.menu.menu_id"
        class="menu-card modern-menu-card"
        @click="goToDetail(snap.menu.menu_id)"
      >
        <div class="menu-card-head">
          <div class="menu-card-identity">
            <span class="menu-symbol">{{ snap.menu.name.charAt(0) }}</span>
            <div>
              <div class="menu-card-name">{{ snap.menu.name }}</div>
              <div class="menu-card-meta">{{ snap.menu.category }} · 월 {{ snap.menu.monthly_orders }}건</div>
            </div>
          </div>
          <SignalBadge :signal="snap.signal" :signal-color="snap.signal_color" />
        </div>

        <div class="menu-profit-line">
          <div>
            <span>월 예상 이익</span>
            <strong :class="{ negative: snap.monthly_profit < 0 }">
              {{ formatKRW(snap.monthly_profit) }}원
            </strong>
          </div>
          <span class="card-arrow">›</span>
        </div>

        <div class="menu-card-grid">
          <div>
            <span class="label">판매가</span>
            <span class="val">{{ formatKRW(snap.menu.price) }}원</span>
          </div>
          <div>
            <span class="label">원가율</span>
            <span class="val">{{ (snap.food_cost_rate * 100).toFixed(1) }}%</span>
          </div>
          <div>
            <span class="label">1건당 마진</span>
            <span class="val">{{ formatKRW(snap.weighted_margin) }}원</span>
          </div>
        </div>
      </button>
    </div>

    <div v-else class="state-card compact-state">
      <strong>조건에 맞는 메뉴가 없어요</strong>
      <p>검색어나 필터를 바꿔보세요.</p>
    </div>
  </div>
</template>
