import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchDashboard, postRecalculate } from '@/api/endpoints'
import client from '@/api/client'

export const useDashboardStore = defineStore('dashboard', () => {
  const summary = ref(null)
  const snapshots = ref([])
  const insights = ref([])
  const assumption = ref(null)
  const storeName = ref('')
  const loading = ref(false)
  const error = ref(null)

  async function load() {
    loading.value = true
    error.value = null
    try {
      const { data } = await fetchDashboard()
      summary.value = data.summary
      snapshots.value = data.snapshots
      insights.value = data.insights
      assumption.value = data.assumption
      storeName.value = data.store_name
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function recalculate() {
    try {
      await postRecalculate()
      await load()
    } catch (e) {
      error.value = e.message
    }
  }

  async function updateAssumption(payload) {
    try {
      await client.put('/assumption/', payload)
      await load()
      return true
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      throw e
    }
  }

  return { summary, snapshots, insights, assumption, storeName, loading, error, load, recalculate, updateAssumption }
})
