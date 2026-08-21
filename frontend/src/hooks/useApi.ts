import axios from 'axios'
import { useAuthStore } from '../stores/auth'

// Use environment variable if set, otherwise use current origin (works for both local dev and production)
const API_BASE = import.meta.env.VITE_API_URL || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000')

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
