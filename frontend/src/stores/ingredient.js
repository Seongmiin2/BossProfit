import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '@/api/client'

export const useIngredientStore = defineStore('ingredient', () => {
  const ingredients = ref([])
  const loading = ref(false)
  const error = ref(null)

  async function loadList() {
    loading.value = true
    error.value = null
    try {
      const { data } = await client.get('/ingredients/')
      ingredients.value = data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
    } finally {
      loading.value = false
    }
  }

  async function createIngredient(payload) {
    loading.value = true
    error.value = null
    try {
      const { data } = await client.post('/ingredients/create/', payload)
      await loadList()
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateIngredient(ingredientId, payload) {
    loading.value = true
    error.value = null
    try {
      const { data } = await client.put(`/ingredients/${ingredientId}/update/`, payload)
      await loadList()
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteIngredient(ingredientId) {
    loading.value = true
    error.value = null
    try {
      const { data } = await client.delete(`/ingredients/${ingredientId}/delete/`)
      await loadList()
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  return { ingredients, loading, error, loadList, createIngredient, updateIngredient, deleteIngredient }
})
