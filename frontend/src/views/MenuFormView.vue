<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useMenuStore } from '@/stores/menu'
import { useIngredientStore } from '@/stores/ingredient'

const router = useRouter()
const route = useRoute()
const menuStore = useMenuStore()
const ingredientStore = useIngredientStore()

const isEdit = computed(() => !!route.params.menuId)
const menuId = ref(route.params.menuId || '')
const name = ref('')
const category = ref('돈까스')
const price = ref('')
const monthlyOrders = ref('')
const packagingCost = ref('')
const recipeItems = ref([])
const ingredients = computed(() => ingredientStore.ingredients)

onMounted(async () => {
  try {
    // 재료 목록 로드
    if (ingredientStore.ingredients.length === 0) {
      await ingredientStore.loadList()
    }

    // 편집 모드일 경우 메뉴 상세 로드
    if (isEdit.value) {
      await menuStore.loadDetail(route.params.menuId)
      if (menuStore.currentMenu) {
        menuId.value = menuStore.currentMenu.menu.menu_id
        name.value = menuStore.currentMenu.menu.name
        category.value = menuStore.currentMenu.menu.category
        price.value = menuStore.currentMenu.menu.price
        monthlyOrders.value = menuStore.currentMenu.menu.monthly_orders
        packagingCost.value = menuStore.currentMenu.menu.packaging_cost
        recipeItems.value = menuStore.currentMenu.recipe_rows?.map(item => ({
          ingredient_id: item.ingredient_id,
          quantity: item.quantity,
          memo: item.memo || ''
        })) || []
      }
    }
  } catch (e) {
    console.error('Failed to load data:', e)
  }
})

function addRecipeItem() {
  recipeItems.value.push({ ingredient_id: '', quantity: '', memo: '' })
}

function removeRecipeItem(idx) {
  recipeItems.value.splice(idx, 1)
}

async function handleSubmit() {
  const payload = {
    menu_id: menuId.value,
    name: name.value,
    category: category.value,
    price: Number(price.value),
    monthly_orders: Number(monthlyOrders.value),
    packaging_cost: Number(packagingCost.value),
    recipe_items: recipeItems.value.filter(item => item.ingredient_id && item.quantity)
  }

  try {
    if (isEdit.value) {
      await menuStore.updateMenu(menuId.value, payload)
      alert('메뉴 수정 완료')
    } else {
      await menuStore.createMenu(payload)
      alert('메뉴 생성 완료')
    }
    router.push('/menus')
  } catch (e) {
    console.error(e)
  }
}
</script>

<template>
  <div style="max-width: 800px; margin: 40px auto;">
    <div class="banner">
      <h1>{{ isEdit ? '메뉴 수정' : '메뉴 추가' }}</h1>
    </div>

    <div style="background: var(--paper); padding: 32px; border: 1px solid var(--line);">
      <form @submit.prevent="handleSubmit">
        <!-- 메뉴 ID (생성 시만) -->
        <div v-if="!isEdit" class="mb-3">
          <label class="form-label">메뉴 ID *</label>
          <input
            v-model="menuId"
            type="text"
            class="form-control"
            placeholder="M001, M002 등"
            required
          />
        </div>

        <!-- 메뉴명 -->
        <div class="mb-3">
          <label class="form-label">메뉴명 *</label>
          <input
            v-model="name"
            type="text"
            class="form-control"
            placeholder="메뉴명 입력"
            required
          />
        </div>

        <!-- 카테고리 -->
        <div class="mb-3">
          <label class="form-label">카테고리 *</label>
          <select v-model="category" class="form-control" required>
            <option>돈까스</option>
            <option>우동</option>
            <option>만두</option>
            <option>세트</option>
            <option>안주</option>
            <option>기타</option>
          </select>
        </div>

        <!-- 가격 -->
        <div class="mb-3">
          <label class="form-label">판매가 (원) *</label>
          <input
            v-model.number="price"
            type="number"
            class="form-control"
            placeholder="8900"
            required
          />
        </div>

        <!-- 월 판매량 -->
        <div class="mb-3">
          <label class="form-label">월 판매량 (건) *</label>
          <input
            v-model.number="monthlyOrders"
            type="number"
            class="form-control"
            placeholder="100"
            required
          />
        </div>

        <!-- 포장비 -->
        <div class="mb-3">
          <label class="form-label">포장 비용 (원)</label>
          <input
            v-model.number="packagingCost"
            type="number"
            class="form-control"
            placeholder="500"
          />
        </div>

        <!-- 레시피 항목 -->
        <div class="mb-3">
          <label class="form-label">레시피</label>
          <div style="border: 1px solid var(--line); padding: 16px; border-radius: 4px;">
            <div
              v-for="(item, idx) in recipeItems"
              :key="idx"
              style="margin-bottom: 16px; display: grid; grid-template-columns: 2fr 1fr 1fr auto; gap: 12px;"
            >
              <!-- 재료 선택 -->
              <select
                v-model="item.ingredient_id"
                class="form-control"
              >
                <option value="">재료 선택</option>
                <option
                  v-for="ing in ingredients"
                  :key="ing.ingredient_id"
                  :value="ing.ingredient_id"
                >
                  {{ ing.name }}
                </option>
              </select>

              <!-- 수량 -->
              <input
                v-model.number="item.quantity"
                type="number"
                class="form-control"
                placeholder="수량"
                step="0.01"
              />

              <!-- 메모 -->
              <input
                v-model="item.memo"
                type="text"
                class="form-control"
                placeholder="메모"
              />

              <!-- 삭제 버튼 -->
              <button
                type="button"
                class="btn-delete"
                @click="removeRecipeItem(idx)"
                style="padding: 6px 12px;"
              >
                삭제
              </button>
            </div>

            <button
              type="button"
              class="btn-coral"
              @click="addRecipeItem"
              style="width: 100%; padding: 8px; margin-top: 8px;"
            >
              + 재료 추가
            </button>
          </div>
        </div>

        <!-- 제출 -->
        <div style="display: flex; gap: 12px; margin-top: 32px;">
          <button
            type="submit"
            class="btn-coral"
            style="flex: 1; padding: 12px; font-weight: 700;"
          >
            {{ isEdit ? '수정하기' : '생성하기' }}
          </button>
          <button
            type="button"
            class="btn"
            style="flex: 1; padding: 12px;"
            @click="router.push('/menus')"
          >
            취소
          </button>
        </div>

        <div v-if="menuStore.error" style="color: var(--coral-deep); margin-top: 16px; font-size: 14px;">
          ⚠️ {{ menuStore.error }}
        </div>
      </form>
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
  font-size: 12px;
}

.btn-delete:hover {
  background: var(--coral-deep);
  opacity: 0.9;
}
</style>
