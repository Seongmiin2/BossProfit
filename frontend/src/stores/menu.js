import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchMenuList, fetchMenuDetail } from '@/api/endpoints'
import client from '@/api/client'

export const useMenuStore = defineStore('menu', () => {
  const menus = ref([])
  const currentMenu = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function loadList() {
    loading.value = true
    error.value = null
    try {
      const { data } = await fetchMenuList()
      menus.value = data
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function loadDetail(menuId) {
    loading.value = true
    error.value = null
    try {
      const { data } = await fetchMenuDetail(menuId)
      currentMenu.value = data
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createMenu(payload) {
    loading.value = true
    error.value = null
    try {
      const { data } = await client.post('/menus/create/', payload)
      await loadList()
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateMenu(menuId, payload) {
    loading.value = true
    error.value = null
    try {
      const { data } = await client.put(`/menus/${menuId}/update/`, payload)
      await loadList()
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteMenu(menuId) {
    loading.value = true
    error.value = null
    try {
      const { data } = await client.delete(`/menus/${menuId}/delete/`)
      await loadList()
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  return { menus, currentMenu, loading, error, loadList, loadDetail, createMenu, updateMenu, deleteMenu }
})
