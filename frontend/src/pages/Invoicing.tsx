import React from 'react'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Plus } from 'lucide-react'

export const InvoicingPage = () => {
  return (
    <div className="p-8">
      <div className="max-w-6xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Invoicing</h1>
            <p className="text-gray-500 mt-2">Create and manage customer invoices</p>
          </div>
          <Button variant="primary" icon={<Plus className="w-5 h-5" />}>New Invoice</Button>
        </div>

        <div className="grid grid-cols-3 gap-6 mb-8">
          {[
            { label: 'Total Revenue', value: '$0' },
            { label: 'Paid', value: '$0' },
            { label: 'Outstanding', value: '$0' },
          ].map((stat) => (
            <Card key={stat.label}>
              <p className="text-gray-500 text-sm">{stat.label}</p>
              <p className="text-2xl font-bold text-gray-900 mt-2">{stat.value}</p>
            </Card>
          ))}
        </div>

        <Card>
          <h2 className="text-xl font-bold text-gray-900 mb-4">Recent Invoices</h2>
          <div className="text-center py-12 text-gray-500">
            No invoices yet. Create your first invoice to get started.
          </div>
        </Card>
      </div>
    </div>
  )
}
