import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '@/api/client'

export const useForecastStore = defineStore('forecast', () => {
  const ingredients = ref([])      // 매장 재료별 예측 요약
  const storeName = ref('')
  const listLoading = ref(false)

  const commodities = ref([])      // 실 시장품목(KAMIS·기상청 실데이터) 예측 대상

  const selectedCode = ref(null)   // 선택된 재료의 market_code
  const detail = ref(null)         // 차트용 상세(시계열 + horizon)
  const loading = ref(false)
  const error = ref(null)

  async function loadIngredients() {
    listLoading.value = true
    error.value = null
    try {
      const { data } = await client.get('/forecast/ingredients/')
      storeName.value = data.store
      ingredients.value = data.ingredients
      return data
    } catch (e) {
      error.value = e.response?.data?.message || e.message
      throw e
    } finally {
      listLoading.value = false
    }
  }

  async function loadCommodities() {
    try {
      const { data } = await client.get('/forecast/items/')
      commodities.value = data
      return data
    } catch (e) {
      error.value = e.response?.data?.message || e.message
      throw e
    }
  }

  async function loadDetail(code) {
    if (!code) return
    selectedCode.value = code
    loading.value = true
    error.value = null
    try {
      const { data } = await client.get(`/forecast/${code}/`)
      detail.value = data
      return data
    } catch (e) {
      detail.value = null
      error.value = e.response?.data?.message || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    ingredients, storeName, listLoading, commodities,
    selectedCode, detail, loading, error,
    loadIngredients, loadCommodities, loadDetail,
  }
})
