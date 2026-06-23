import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import { useAuthStore } from './stores/auth'

import 'bootstrap/dist/css/bootstrap.min.css'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// 앱 마운트 후 auth 초기화
app.mount('#app')

// Pinia store 초기화 (마운트 후)
const authStore = useAuthStore()
authStore.initializeAuth()
