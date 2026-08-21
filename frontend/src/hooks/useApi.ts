import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  const businessId = useAuthStore.getState().currentBusinessId
  if (businessId) {
    config.headers['X-Business-Id'] = businessId
  }
  return config
})

export const useApi = () => {
  return api
}
