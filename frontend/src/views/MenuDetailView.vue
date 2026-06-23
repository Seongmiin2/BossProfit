<script setup>
import { onMounted, watch } from 'vue'
import { useMenuStore } from '@/stores/menu'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { formatKRW } from '@/utils/format'
import RecipeBar from '@/components/RecipeBar.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'

const props = defineProps({
  menuId: String,
})

const menuStore = useMenuStore()
const authStore = useAuthStore()
const router = useRouter()

const loadMenu = () => {
  if (props.menuId) {
    menuStore.loadDetail(props.menuId)
  }
}

onMounted(loadMenu)

watch(() => props.menuId, loadMenu)

const goToMenuList = () => {
  router.push('/menus')
}

const goToEdit = () => {
  router.push({ name: 'MenuEdit', params: { menuId: props.menuId } })
}

const handleDelete = async () => {
  if (!confirm('정말 삭제하시겠습니까?')) return
  try {
    await menuStore.deleteMenu(props.menuId)
    alert('메뉴 삭제 완료')
    router.push('/menus')
  } catch (e) {
    console.error(e)
  }
}
</script>

<template>
  <div>
    <div v-if="menuStore.loading" style="text-align: center; padding: 40px;">
      <LoadingSpinner />
    </div>

    <div v-else-if="menuStore.error" style="color: var(--coral-deep); padding: 20px;">
      ⚠️ {{ menuStore.error }}
    </div>

    <div v-else-if="menuStore.currentMenu">
      <!-- Header -->
      <div class="detail-header">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <div>
            <a class="breadcrumb" @click="goToMenuList" style="cursor: pointer;">← 메뉴 목록</a>
            <div class="tag">{{ menuStore.currentMenu.menu.category }}</div>
            <h1>{{ menuStore.currentMenu.menu.name }}</h1>
            <div class="sub">
              <strong>{{ formatKRW(menuStore.currentMenu.menu.price) }}</strong>
              · 월판매량
              <strong>{{ menuStore.currentMenu.menu.monthly_orders }}건</strong>
            </div>
          </div>
          <div v-if="authStore.isLoggedIn" style="display: flex; gap: 8px;">
            <button
              @click="goToEdit"
              class="btn-coral"
              style="padding: 8px 16px; font-weight: 700;"
            >
              수정
            </button>
            <button
              @click="handleDelete"
              class="btn-delete"
              style="padding: 8px 16px; font-weight: 700;"
            >
              삭제
            </button>
          </div>
        </div>
      </div>

      <!-- Margin Grid -->
      <div class="margin-grid">
        <div class="margin-card">
          <div class="lbl">홀 마진</div>
          <div
            :class="['val', menuStore.currentMenu.result.dine_in_margin >= 0 ? 'pos' : 'neg']"
          >
            {{ formatKRW(menuStore.currentMenu.result.dine_in_margin) }}
            <span class="unit">원</span>
          </div>
          <div class="note">식사 가격에서 재료 원가만 제외</div>
        </div>
        <div class="margin-card">
          <div class="lbl">포장 마진</div>
          <div
            :class="['val', menuStore.currentMenu.result.takeout_margin >= 0 ? 'pos' : 'neg']"
          >
            {{ formatKRW(menuStore.currentMenu.result.takeout_margin) }}
            <span class="unit">원</span>
          </div>
          <div class="note">포장 비용을 추가로 제외</div>
        </div>
        <div class="margin-card">
          <div class="lbl">배달 마진</div>
          <div
            :class="['val', menuStore.currentMenu.result.delivery_margin >= 0 ? 'pos' : 'neg']"
          >
            {{ formatKRW(menuStore.currentMenu.result.delivery_margin) }}
            <span class="unit">원</span>
          </div>
          <div class="note">배달 수수료·기사료까지 제외</div>
        </div>
      </div>

      <!-- Weighted Banner -->
      <div class="weighted-banner">
        <div>
          <div class="lbl-coral">가중평균 마진</div>
          <div class="big" :class="menuStore.currentMenu.result.weighted_margin >= 0 ? '' : 'coral'">
            {{ formatKRW(menuStore.currentMenu.result.weighted_margin) }}
            <span style="font-size: 24px;">원</span>
          </div>
        </div>
        <div>
          <div class="lbl-grey">월 예상 이익 ({{ menuStore.currentMenu.menu.monthly_orders }}건)</div>
          <div class="big coral">
            {{ formatKRW(menuStore.currentMenu.result.monthly_profit) }}
            <span style="font-size: 24px;">원</span>
          </div>
        </div>
      </div>

      <!-- Recipe Breakdown -->
      <div class="sect-head">
        <span class="sect-label">재료 분해</span>
        <h2>{{ menuStore.currentMenu.menu.name }}의 원가 구성</h2>
      </div>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>재료</th>
              <th class="right">사용량</th>
              <th class="right">단가</th>
              <th class="right">원가</th>
              <th>비중</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in menuStore.currentMenu.recipe_rows" :key="row.ingredient_id">
              <td>{{ row.ingredient_name }}</td>
              <td class="right tabular">{{ row.quantity }}{{ row.unit }}</td>
              <td class="right tabular">{{ row.unit_cost.toFixed(2) }}</td>
              <td class="right tabular">{{ formatKRW(row.cost) }}</td>
              <td>
                <RecipeBar :percentage="row.share" />
              </td>
            </tr>
            <tr style="background: var(--cream-deep); font-weight: 700;">
              <td colspan="3">총 재료 원가</td>
              <td class="right tabular">
                {{ formatKRW(menuStore.currentMenu.result.base_cost) }}
              </td>
              <td style="text-align: center;">
                {{ (menuStore.currentMenu.result.food_cost_rate * 100).toFixed(1) }}%
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.btn-delete {
  background: var(--coral-deep);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-delete:hover {
  opacity: 0.9;
}
</style>
