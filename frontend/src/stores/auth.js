import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref(localStorage.getItem('access_token'))
  const refreshToken = ref(localStorage.getItem('refresh_token'))
  const loading = ref(false)
  const error = ref(null)

  const isLoggedIn = computed(() => !!accessToken.value)

  async function loadUser() {
    if (!accessToken.value) return
    try {
      const { data } = await api.get('/accounts/me/')
      user.value = data
    } catch (e) {
      console.error('Failed to load user:', e)
      logout()
    }
  }

  async function register(username, password, password2) {
    loading.value = true
    error.value = null
    try {
      await api.post('/accounts/register/', { username, password, password2 })
      await login(username, password)
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function login(username, password) {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.post('/accounts/login/', { username, password })
      accessToken.value = data.access
      refreshToken.value = data.refresh
      localStorage.setItem('access_token', data.access)
      localStorage.setItem('refresh_token', data.refresh)
      await loadUser()
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function refreshAccessToken() {
    if (!refreshToken.value) return false
    try {
      const { data } = await api.post('/accounts/refresh/', { refresh: refreshToken.value })
      accessToken.value = data.access
      localStorage.setItem('access_token', data.access)
      return true
    } catch (e) {
      logout()
      return false
    }
  }

  function logout() {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  function initializeAuth() {
    if (accessToken.value) loadUser()
  }

  return {
    user,
    accessToken,
    refreshToken,
    loading,
    error,
    isLoggedIn,
    register,
    login,
    logout,
    loadUser,
    refreshAccessToken,
    initializeAuth,
  }
})
