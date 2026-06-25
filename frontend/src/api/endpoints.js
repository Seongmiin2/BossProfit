import api from './client'

export const fetchDashboard = () => api.get('/dashboard/')
export const fetchMenuList = () => api.get('/menus/')
export const fetchMenuDetail = (menuId) => api.get(`/menus/${menuId}/`)
export const postRecalculate = () => api.post('/recalculate/')
export const fetchPublicPreview = () => api.get('/public/product-preview/')
export const fetchStoreAnalysis = (params) => api.get('/analysis/store/', { params })
export const fetchAnalysisReport = () => api.get('/analysis/report/')
export const fetchSalesCalendar = (params) => api.get('/analysis/calendar/', { params })
export const fetchSalesDayDetail = (date) => api.get('/analysis/calendar/day/', { params: { date } })
export const postAnalysisFollowUp = (question) => api.post('/analysis/follow-up/', { question })
export const postActionPlan = (payload) => api.post('/action-plans/', payload)
