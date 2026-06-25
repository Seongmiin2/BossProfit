import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '@/api/client'

export const useMarketStore = defineStore('market', () => {
  const source = ref(null)
  const asOf = ref(null)
  const summary = ref(null)
  const changes = ref([])
  const loading = ref(false)
  const syncing = ref(false)
  const error = ref(null)

  async function loadPreview() {
    loading.value = true
    error.value = null
    try {
      const { data } = await client.get('/market/preview/')
      source.value = data.source
      asOf.value = data.as_of
      summary.value = data.summary
      changes.value = data.changes
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function sync(ingredientIds = null) {
    syncing.value = true
    error.value = null
    try {
      const payload = ingredientIds ? { ingredient_ids: ingredientIds } : {}
      const { data } = await client.post('/market/sync/', payload)
      // 반영 후 최신 미리보기 다시 로드 (변동분이 0에 수렴)
      await loadPreview()
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      throw e
    } finally {
      syncing.value = false
    }
  }

  return { source, asOf, summary, changes, loading, syncing, error, loadPreview, sync }
})
