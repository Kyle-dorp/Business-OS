import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { BarChart3, Users, ShoppingCart, FileText, Zap, MessageSquare, Settings, LogOut } from 'lucide-react'

export const Dashboard = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const modules = [
    { id: 'inventory', name: 'Inventory', icon: ShoppingCart, color: 'bg-blue-100 text-blue-600' },
    { id: 'customers', name: 'Customers & CRM', icon: Users, color: 'bg-green-100 text-green-600' },
    { id: 'invoicing', name: 'Invoicing', icon: FileText, color: 'bg-amber-100 text-amber-600' },
    { id: 'payroll', name: 'Payroll', icon: BarChart3, color: 'bg-purple-100 text-purple-600' },
    { id: 'team', name: 'Team Chat', icon: MessageSquare, color: 'bg-pink-100 text-pink-600' },
    { id: 'analytics', name: 'Analytics', icon: Zap, color: 'bg-indigo-100 text-indigo-600' },
  ]

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-64' : 'w-20'} bg-white border-r border-gray-200 transition-all duration-300 flex flex-col`}>
        <div className="p-6 border-b border-gray-200">
          <h2 className={`font-bold text-gray-900 ${sidebarOpen ? 'text-2xl' : 'text-sm'} transition-all`}>
            {sidebarOpen ? 'Business EOS' : 'B'}
          </h2>
        </div>

        <nav className="flex-1 p-4 space-y-2">
          {modules.map((mod) => {
            const Icon = mod.icon
            return (
              <button
                key={mod.id}
                onClick={() => navigate(`/${mod.id}`)}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-gray-100 transition-all text-left text-gray-700 hover:text-gray-900"
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                {sidebarOpen && <span className="font-medium">{mod.name}</span>}
              </button>
            )
          })}
        </nav>

        <div className="p-4 border-t border-gray-200 space-y-2">
          <button className="w-full flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-gray-100 transition-all text-gray-700">
            <Settings className="w-5 h-5" />
            {sidebarOpen && <span className="font-medium">Settings</span>}
          </button>
          <button onClick={handleLogout} className="w-full flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-red-50 transition-all text-red-600">
            <LogOut className="w-5 h-5" />
            {sidebarOpen && <span className="font-medium">Logout</span>}
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 p-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-gray-500 mt-1">Welcome back, {user?.username}</p>
          </div>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 hover:bg-gray-100 rounded-lg transition-all"
          >
            {sidebarOpen ? '←' : '→'}
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-8">
          <div className="max-w-7xl">
            <h2 className="text-2xl font-bold text-gray-900 mb-8">Features</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {modules.map((mod) => {
                const Icon = mod.icon
                return (
                  <Card
                    key={mod.id}
                    hoverable
                    onClick={() => navigate(`/${mod.id}`)}
                    className="cursor-pointer"
                  >
                    <div className="flex items-start gap-4">
                      <div className={`p-3 rounded-lg ${mod.color}`}>
                        <Icon className="w-6 h-6" />
                      </div>
                      <div className="flex-1">
                        <h3 className="font-bold text-gray-900">{mod.name}</h3>
                        <p className="text-gray-500 text-sm mt-1">Manage your {mod.name.toLowerCase()}</p>
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>

            {/* Quick Stats */}
            <div className="mt-12">
              <h2 className="text-2xl font-bold text-gray-900 mb-6">Quick Stats</h2>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                {[
                  { label: 'Total Revenue', value: '$0', change: '+0%' },
                  { label: 'Customers', value: '0', change: '+0%' },
                  { label: 'Inventory Items', value: '0', change: '+0%' },
                  { label: 'Pending Invoices', value: '0', change: '+0%' },
                ].map((stat) => (
                  <Card key={stat.label}>
                    <p className="text-gray-500 text-sm">{stat.label}</p>
                    <p className="text-3xl font-bold text-gray-900 mt-2">{stat.value}</p>
                    <p className="text-green-600 text-sm mt-2">{stat.change}</p>
                  </Card>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
