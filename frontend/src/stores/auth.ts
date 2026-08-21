import { create } from 'zustand'

interface User {
  id: number
  username: string
  role: 'manager' | 'employee' | 'admin'
  is_admin: boolean
  employee_id?: number
  active: boolean
}

interface AuthState {
  token: string | null
  user: User | null
  currentBusinessId: number | null
  isAuthenticated: boolean
  
  setAuth: (token: string, user: User, businessId: number) => void
  logout: () => void
  setCurrentBusiness: (businessId: number) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  user: localStorage.getItem('user') ? JSON.parse(localStorage.getItem('user')!) : null,
  currentBusinessId: localStorage.getItem('businessId') ? parseInt(localStorage.getItem('businessId')!) : null,
  isAuthenticated: !!localStorage.getItem('token'),
  
  setAuth: (token, user, businessId) => {
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
    localStorage.setItem('businessId', businessId.toString())
    set({ token, user, currentBusinessId: businessId, isAuthenticated: true })
  },
  
  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('businessId')
    set({ token: null, user: null, currentBusinessId: null, isAuthenticated: false })
  },
  
  setCurrentBusiness: (businessId) => {
    localStorage.setItem('businessId', businessId.toString())
    set({ currentBusinessId: businessId })
  },
}))
