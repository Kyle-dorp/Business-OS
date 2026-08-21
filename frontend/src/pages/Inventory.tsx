import React from 'react'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Plus } from 'lucide-react'

export const InventoryPage = () => {
  return (
    <div className="p-8">
      <div className="max-w-6xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Inventory</h1>
            <p className="text-gray-500 mt-2">Track products, stock levels, and reorders</p>
          </div>
          <Button variant="primary" icon={<Plus className="w-5 h-5" />}>Add Item</Button>
        </div>

        <div className="grid grid-cols-4 gap-6 mb-8">
          {[
            { label: 'Total Items', value: '0' },
            { label: 'Low Stock', value: '0' },
            { label: 'Total Value', value: '$0' },
            { label: 'Last Restock', value: 'Never' },
          ].map((stat) => (
            <Card key={stat.label}>
              <p className="text-gray-500 text-sm">{stat.label}</p>
              <p className="text-2xl font-bold text-gray-900 mt-2">{stat.value}</p>
            </Card>
          ))}
        </div>

        <Card>
          <h2 className="text-xl font-bold text-gray-900 mb-4">Items</h2>
          <div className="text-center py-12 text-gray-500">
            No inventory items yet. Create your first item to get started.
          </div>
        </Card>
      </div>
    </div>
  )
}
