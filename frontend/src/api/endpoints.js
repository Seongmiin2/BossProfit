import api from './client'

export const fetchDashboard = () => api.get('/dashboard/')
export const fetchMenuList = () => api.get('/menus/')
export const fetchMenuDetail = (menuId) => api.get(`/menus/${menuId}/`)
export const postRecalculate = () => api.post('/recalculate/')
