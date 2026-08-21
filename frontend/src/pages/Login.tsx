import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'
import { api } from '../hooks/useApi'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { Card } from '../components/Card'

export const LoginPage = () => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const setAuth = useAuthStore((state) => state.setAuth)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const res = await api.post('/auth/login', { username, password })
      const { token, user } = res.data

      // Check if user is admin
      if (user.is_admin) {
        setAuth(token, user, 0) // Admin has no specific business_id
        navigate('/admin')
        return
      }

      // Get the user's business memberships
      const membershipsRes = await api.get('/auth/memberships', {
        headers: { Authorization: `Bearer ${token}` }
      })

      const businessId = membershipsRes.data[0]?.business_id || user.id
      setAuth(token, user, businessId)
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <Card className="w-full max-w-md shadow-modal">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Business EOS</h1>
          <p className="text-gray-500 mt-2">Beautiful business management platform</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-6">
          <Input
            label="Username"
            placeholder="Enter your username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
          />

          <Input
            label="Password"
            type="password"
            placeholder="Enter your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />

          {error && <div className="text-red-500 text-sm p-3 bg-red-50 rounded-lg">{error}</div>}

          <Button type="submit" variant="primary" size="lg" loading={loading} className="w-full">
            Sign In
          </Button>
        </form>

        <div className="mt-6 text-center text-gray-500 text-sm">
          <p>Demo: Use any username/password to test</p>
        </div>
      </Card>
    </div>
  )
}
