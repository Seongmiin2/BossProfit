<script setup>
import { ref, onMounted } from 'vue'
import { useIngredientStore } from '@/stores/ingredient'

const ingredientStore = useIngredientStore()

const showForm = ref(false)
const editingId = ref(null)
const formData = ref({
  ingredient_id: '',
  name: '',
  category: '',
  purchase_quantity: '',
  purchase_price: '',
  unit: 'g',
  is_hq_supplied: false,
  memo: ''
})

onMounted(() => {
  ingredientStore.loadList()
})

function openCreateForm() {
  editingId.value = null
  formData.value = {
    ingredient_id: '',
    name: '',
    category: '',
    purchase_quantity: '',
    purchase_price: '',
    unit: 'g',
    memo: ''
  }
  showForm.value = true
}

function generateIngredientId(name) {
  if (!name) return ''
  // 한글을 영문으로 변환 (간단한 방식)
  return name.toUpperCase().replace(/\s+/g, '_') + '_' + formData.value.unit.toUpperCase()
}

function openEditForm(ingredient) {
  editingId.value = ingredient.ingredient_id
  formData.value = { ...ingredient }
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  editingId.value = null
}

async function handleSubmit() {
  try {
    const payload = { ...formData.value }

    // 생성 시 ID 자동 생성
    if (!editingId.value) {
      payload.ingredient_id = generateIngredientId(formData.value.name)
    }

    if (editingId.value) {
      await ingredientStore.updateIngredient(editingId.value, payload)
      alert('재료 수정 완료')
    } else {
      await ingredientStore.createIngredient(payload)
      alert('재료 생성 완료')
    }
    closeForm()
  } catch (e) {
    console.error(e)
  }
}

async function handleDelete(ingredientId) {
  if (!confirm('정말 삭제하시겠습니까?')) return
  try {
    await ingredientStore.deleteIngredient(ingredientId)
    alert('재료 삭제 완료')
  } catch (e) {
    console.error(e)
  }
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="banner" style="display: flex; align-items: center; justify-content: space-between; gap: 16px;">
      <h1>🧂 재료 관리</h1>
      <button
        @click="openCreateForm"
        class="btn-coral"
        style="padding: 12px 20px; font-weight: 700; font-size: 16px; white-space: nowrap;"
      >
        + 새 재료 추가
      </button>
    </div>

    <!-- Loading -->
    <div v-if="ingredientStore.loading" style="text-align: center; padding: 40px;">
      <div class="spinner"></div>
      <p>로드 중...</p>
    </div>

    <!-- Error -->
    <div v-else-if="ingredientStore.error" style="color: var(--coral-deep); padding: 20px; background: var(--paper); border: 1px solid var(--line);">
      ⚠️ {{ ingredientStore.error }}
    </div>

    <!-- Content -->
    <div v-else>
      <!-- Table -->
      <div v-if="ingredientStore.ingredients.length > 0" class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>재료명</th>
              <th style="width: 80px;">카테고리</th>
              <th class="right" style="width: 100px;">구매가</th>
              <th class="right" style="width: 80px;">구매량</th>
              <th class="right" style="width: 100px;">단위가</th>
              <th style="width: 50px;">단위</th>
              <th style="width: 90px;">본사납품</th>
              <th style="width: 120px;">액션</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ing in ingredientStore.ingredients" :key="ing.ingredient_id">
              <td style="font-weight: 500;">{{ ing.name }}</td>
              <td style="font-size: 13px;">{{ ing.category || '-' }}</td>
              <td class="right tabular">{{ ing.purchase_price.toLocaleString() }}</td>
              <td class="right tabular">{{ ing.purchase_quantity }}</td>
              <td class="right tabular">{{ ing.unit_cost.toFixed(2) }}</td>
              <td style="text-align: center;">{{ ing.unit }}</td>
              <td style="text-align: center;">
                <span v-if="ing.is_hq_supplied" class="hq-badge">본사</span>
                <span v-else style="color: var(--ink-light);">-</span>
              </td>
              <td style="display: flex; gap: 4px;">
                <button
                  @click="openEditForm(ing)"
                  class="btn"
                  style="padding: 6px 10px; font-size: 12px; flex: 1; background: var(--cream); border: 1px solid var(--line);"
                >
                  수정
                </button>
                <button
                  @click="handleDelete(ing.ingredient_id)"
                  class="btn-delete"
                  style="padding: 6px 10px; font-size: 12px; flex: 1;"
                >
                  삭제
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- No data -->
      <div v-else style="text-align: center; padding: 60px 20px; color: var(--ink-light);">
        <p style="font-size: 16px; margin-bottom: 16px;">아직 추가된 재료가 없습니다.</p>
        <p style="font-size: 14px;">+ 새 재료 추가 버튼을 클릭하여 첫 번째 재료를 추가해보세요!</p>
      </div>
    </div>

    <!-- Form Modal -->
    <div v-if="showForm" style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 20px;">
      <div style="background: white; padding: 32px; border-radius: 8px; max-width: 600px; width: 100%; max-height: 90vh; overflow-y: auto;">
        <h2 style="margin-bottom: 24px; color: var(--ink);">
          {{ editingId ? '✏️ 재료 수정' : '➕ 새 재료 추가' }}
        </h2>

        <form @submit.prevent="handleSubmit">
          <!-- 재료명 -->
          <div class="mb-3">
            <label class="form-label">재료명 *</label>
            <input
              v-model="formData.name"
              type="text"
              class="form-control"
              placeholder="예: 돼지 등심, 당근"
              required
            />
          </div>

          <!-- 카테고리 -->
          <div class="mb-3">
            <label class="form-label">카테고리</label>
            <select v-model="formData.category" class="form-control">
              <option value="">선택하지 않음</option>
              <option>돈까스</option>
              <option>우동</option>
              <option>만두</option>
              <option>공통</option>
              <option>안주</option>
              <option>포장</option>
              <option>기타</option>
            </select>
          </div>

          <!-- 구매 정보 -->
          <div style="background: var(--cream-light); padding: 16px; border-radius: 4px; margin-bottom: 16px;">
            <label style="display: block; font-weight: 700; margin-bottom: 12px; color: var(--ink);">구매 정보</label>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;">
              <div>
                <label class="form-label">구매 단가 (원) *</label>
                <input
                  v-model.number="formData.purchase_price"
                  type="number"
                  class="form-control"
                  placeholder="12300"
                  required
                  min="0"
                />
              </div>
              <div>
                <label class="form-label">구매량 *</label>
                <input
                  v-model.number="formData.purchase_quantity"
                  type="number"
                  class="form-control"
                  placeholder="1000"
                  step="0.01"
                  required
                  min="0"
                />
              </div>
            </div>

            <div class="mb-3">
              <label class="form-label">단위</label>
              <select v-model="formData.unit" class="form-control">
                <option>g</option>
                <option>kg</option>
                <option>ml</option>
                <option>l</option>
                <option>개</option>
                <option>팩</option>
                <option>박스</option>
                <option>병</option>
                <option>통</option>
              </select>
            </div>

            <!-- 계산된 단위가 -->
            <div style="background: white; padding: 12px; border-radius: 4px; border: 1px solid var(--line);">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: var(--ink-light); font-size: 13px;">계산된 단위가</span>
                <span style="font-weight: 700; font-size: 18px; color: var(--coral);">
                  {{ formData.purchase_quantity && formData.purchase_price ? (formData.purchase_price / formData.purchase_quantity).toFixed(2) : '0.00' }}
                  원/{{ formData.unit }}
                </span>
              </div>
            </div>
          </div>

          <!-- 본사 납품 여부 -->
          <div class="mb-3">
            <label class="hq-check">
              <input v-model="formData.is_hq_supplied" type="checkbox" />
              <span>
                <strong>본사 납품 재료</strong>
                <small>본사 납품가가 정해져 있어 시장가격 변동 영향이 거의 없는 재료입니다.</small>
              </span>
            </label>
          </div>

          <!-- 메모 -->
          <div class="mb-3">
            <label class="form-label">메모</label>
            <textarea
              v-model="formData.memo"
              class="form-control"
              placeholder="공급처, 보관 방법 등 필요한 정보를 입력하세요"
              rows="3"
            ></textarea>
          </div>

          <!-- 버튼 -->
          <div style="display: flex; gap: 12px; margin-top: 24px;">
            <button
              type="submit"
              class="btn-coral"
              style="flex: 1; padding: 12px; font-weight: 700; font-size: 16px;"
            >
              {{ editingId ? '수정 완료' : '재료 추가' }}
            </button>
            <button
              type="button"
              class="btn"
              style="flex: 1; padding: 12px; font-weight: 700; background: var(--cream); border: 1px solid var(--line);"
              @click="closeForm"
            >
              취소
            </button>
          </div>
        </form>
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
  transition: opacity 0.2s;
}

.btn-delete:hover {
  opacity: 0.9;
}

.form-label {
  display: block;
  margin-bottom: 6px;
  font-weight: 600;
  color: var(--ink);
  font-size: 13px;
}

.form-control {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 4px;
  font-size: 14px;
  font-family: inherit;
}

.form-control:focus {
  outline: none;
  border-color: var(--coral);
  box-shadow: 0 0 0 2px rgba(255, 107, 107, 0.1);
}

.mb-3 {
  margin-bottom: 16px;
}

.hq-badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--coral, #c95626);
  color: white;
  font-size: 11px;
  font-weight: 700;
}

.hq-check {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: var(--cream-light);
  cursor: pointer;
}

.hq-check input {
  margin-top: 3px;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.hq-check span {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.hq-check small {
  color: var(--ink-light);
  font-size: 12px;
}
</style>
