import React from 'react'
import { Card } from '../components/Card'
import { BarChart3, TrendingUp, Users, DollarSign } from 'lucide-react'

export const AnalyticsPage = () => {
  return (
    <div className="p-8">
      <div className="max-w-6xl">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Analytics</h1>
          <p className="text-gray-500 mt-2">Track performance and insights</p>
        </div>

        <div className="grid grid-cols-4 gap-6 mb-8">
          {[
            { icon: DollarSign, label: 'Revenue', value: '$0', color: 'text-green-600' },
            { icon: Users, label: 'Customers', value: '0', color: 'text-blue-600' },
            { icon: TrendingUp, label: 'Growth', value: '0%', color: 'text-purple-600' },
            { icon: BarChart3, label: 'Transactions', value: '0', color: 'text-orange-600' },
          ].map((stat) => {
            const Icon = stat.icon
            return (
              <Card key={stat.label}>
                <Icon className={`w-6 h-6 ${stat.color}`} />
                <p className="text-gray-500 text-sm mt-2">{stat.label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</p>
              </Card>
            )
          })}
        </div>

        <Card>
          <h2 className="text-xl font-bold text-gray-900 mb-4">Revenue Trends</h2>
          <div className="text-center py-12 text-gray-500">
            No data yet. Start tracking your business to see analytics here.
          </div>
        </Card>
      </div>
    </div>
  )
}
