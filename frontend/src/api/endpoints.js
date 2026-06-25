import api from './client'

export const fetchDashboard = () => api.get('/dashboard/')
export const fetchMenuList = () => api.get('/menus/')
export const fetchMenuDetail = (menuId) => api.get(`/menus/${menuId}/`)
export const postRecalculate = () => api.post('/recalculate/')
export const fetchPublicPreview = () => api.get('/public/product-preview/')
export const fetchStoreAnalysis = () => api.get('/analysis/store/')
export const fetchAnalysisReport = () => api.get('/analysis/report/')
export const postAnalysisFollowUp = (question) => api.post('/analysis/follow-up/', { question })
export const postActionPlan = (payload) => api.post('/action-plans/', payload)
