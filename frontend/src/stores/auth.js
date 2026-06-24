import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref(localStorage.getItem('access_token'))
  const refreshToken = ref(localStorage.getItem('refresh_token'))
  const loading = ref(false)
  const error = ref(null)
  const initialized = ref(false)

  const isLoggedIn = computed(() => !!accessToken.value)
  const store = computed(() => user.value?.store || null)
  const onboarding = computed(() => user.value?.onboarding || null)
  const needsOnboarding = computed(() =>
    isLoggedIn.value && (
      !store.value
      || ['STORE', 'INGREDIENT', 'MENU', 'RECIPE'].includes(onboarding.value?.current_step)
    )
  )

  function extractError(e) {
    const data = e.response?.data
    if (!data) return e.message
    if (typeof data.detail === 'string') return data.detail
    const firstValue = Object.values(data)[0]
    if (Array.isArray(firstValue)) return firstValue[0]
    if (typeof firstValue === 'string') return firstValue
    return '입력 내용을 다시 확인해주세요.'
  }

  async function updateProfile(payload) {
    const { data } = await api.put('/accounts/profile/', payload)
    user.value = data
    return data
  }

  async function updateStore(payload) {
    const { data } = await api.put('/accounts/store/update/', payload)
    user.value = data
    return data
  }

  async function changePassword(payload) {
    const { data } = await api.post('/accounts/password/', payload)
    return data
  }

  async function loadUser() {
    if (!accessToken.value) return
    try {
      const { data } = await api.get('/accounts/me/')
      user.value = data
    } catch (e) {
      clearSession()
    } finally {
      initialized.value = true
    }
  }

  async function register(username, password, password2) {
    loading.value = true
    error.value = null
    try {
      await api.post('/accounts/register/', { username, password, password2 })
      await login(username, password)
    } catch (e) {
      error.value = extractError(e)
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
      error.value = extractError(e)
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
      clearSession()
      return false
    }
  }

  function clearSession() {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    initialized.value = true
  }

  async function logout() {
    const token = refreshToken.value
    try {
      if (token && accessToken.value) {
        await api.post('/accounts/logout/', { refresh: token })
      }
    } catch {
      // 서버 토큰 상태와 무관하게 로컬 세션은 반드시 종료한다.
    } finally {
      clearSession()
    }
  }

  async function createStore(payload) {
    loading.value = true
    error.value = null
    try {
      await api.post('/accounts/store/', payload)
      await loadUser()
      return user.value.store
    } catch (e) {
      error.value = extractError(e)
      throw e
    } finally {
      loading.value = false
    }
  }

  async function initializeAuth() {
    if (accessToken.value) {
      await loadUser()
    } else {
      initialized.value = true
    }
  }

  return {
    user,
    accessToken,
    refreshToken,
    loading,
    error,
    initialized,
    isLoggedIn,
    store,
    onboarding,
    needsOnboarding,
    extractError,
    register,
    login,
    logout,
    loadUser,
    refreshAccessToken,
    initializeAuth,
    createStore,
    updateProfile,
    updateStore,
    changePassword,
  }
})
