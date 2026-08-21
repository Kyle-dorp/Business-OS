import React, { useState } from 'react'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Input } from '../components/Input'
import { Plus, Search, Mail, Phone } from 'lucide-react'

export const CustomersPage = () => {
  const [showForm, setShowForm] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // API call would go here
    console.log('Creating customer:', formData)
    setShowForm(false)
    setFormData({ first_name: '', last_name: '', email: '', phone: '' })
  }

  return (
    <div className="p-8">
      <div className="max-w-6xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Customers & CRM</h1>
            <p className="text-gray-500 mt-2">Manage your customer relationships</p>
          </div>
          <Button variant="primary" onClick={() => setShowForm(!showForm)} icon={<Plus className="w-5 h-5" />}>
            Add Customer
          </Button>
        </div>

        {/* Search */}
        <div className="mb-6 relative">
          <Search className="absolute left-4 top-3.5 text-gray-400 w-5 h-5" />
          <Input
            placeholder="Search customers by name or email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Add Customer Form */}
        {showForm && (
          <Card className="mb-8">
            <h2 className="text-xl font-bold text-gray-900 mb-6">New Customer</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="First Name"
                  value={formData.first_name}
                  onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                  required
                />
                <Input
                  label="Last Name"
                  value={formData.last_name}
                  onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  required
                />
              </div>
              <Input
                label="Email"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                required
              />
              <Input
                label="Phone"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              />
              <div className="flex gap-3 pt-4">
                <Button type="submit" variant="primary">Create Customer</Button>
                <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
              </div>
            </form>
          </Card>
        )}

        {/* Customer List */}
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i} hoverable>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-bold text-gray-900">Customer {i}</h3>
                  <div className="flex gap-4 mt-2 text-gray-500 text-sm">
                    <div className="flex items-center gap-1">
                      <Mail className="w-4 h-4" />
                      customer{i}@example.com
                    </div>
                    <div className="flex items-center gap-1">
                      <Phone className="w-4 h-4" />
                      +1 (555) 000-000{i}
                    </div>
                  </div>
                </div>
                <Button variant="secondary" size="sm">View</Button>
              </div>
            </Card>
          ))}
        </div>

        {/* Empty State */}
        <div className="text-center py-12">
          <p className="text-gray-500">No customers yet. Create your first one to get started.</p>
        </div>
      </div>
    </div>
  )
}
