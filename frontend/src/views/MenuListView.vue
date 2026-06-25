<script setup>
import { onMounted } from 'vue'
import { useMenuStore } from '@/stores/menu'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { formatKRW } from '@/utils/format'
import SignalBadge from '@/components/SignalBadge.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'

const menuStore = useMenuStore()
const authStore = useAuthStore()
const router = useRouter()

onMounted(() => {
  menuStore.loadList()
})

const goToDetail = (menuId) => {
  router.push({ name: 'MenuDetail', params: { menuId } })
}
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
      <div class="sect-head" style="margin: 0;">
        <h2 style="margin: 0;">🍜 메뉴 전체</h2>
      </div>
      <router-link
        v-if="authStore.isLoggedIn"
        to="/menus/create"
        class="btn-coral"
        style="padding: 10px 16px; font-weight: 700; text-decoration: none; display: inline-block;"
      >
        + 메뉴 추가
      </router-link>
    </div>

    <div v-if="menuStore.loading" style="text-align: center; padding: 40px;">
      <LoadingSpinner />
    </div>

    <div v-else-if="menuStore.error" style="color: var(--coral-deep); padding: 20px;">
      ⚠️ {{ menuStore.error }}
    </div>

    <div v-else class="menu-grid">
      <a
        v-for="snap in menuStore.menus"
        :key="snap.menu.menu_id"
        @click="goToDetail(snap.menu.menu_id)"
        class="menu-card"
      >
        <div class="menu-card-head">
          <div>
            <div class="menu-card-name">{{ snap.menu.name }}</div>
            <div class="menu-card-meta">{{ snap.menu.category }}</div>
          </div>
          <SignalBadge :signal="snap.signal" :signal-color="snap.signal_color" />
        </div>
        <div class="menu-card-grid">
          <div>
            <div class="label">판매가</div>
            <div class="val">{{ formatKRW(snap.menu.price) }}</div>
          </div>
          <div>
            <div class="label">월판매량</div>
            <div class="val">{{ snap.menu.monthly_orders }}건</div>
          </div>
          <div>
            <div class="label">원가율</div>
            <div class="val">{{ (snap.food_cost_rate * 100).toFixed(1) }}%</div>
          </div>
          <div>
            <div class="label">월이익</div>
            <div class="val" :class="snap.monthly_profit >= 0 ? '' : 'coral'">
              {{ formatKRW(snap.monthly_profit) }}
            </div>
          </div>
        </div>
      </a>
    </div>
  </div>
</template>
