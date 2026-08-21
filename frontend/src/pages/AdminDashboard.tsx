import { useEffect, useState } from 'react'
import { api } from '../hooks/useApi'

interface Customer {
  id: number
  name: string
  legal_name: string
  industry: string
  owner: string
  plan: string
  monthly_price_cents: number
  claude_api_tokens: number
  claude_api_cost_cents: number
  profit_cents: number
  modules: string[]
  created_at: string
}

interface Analytics {
  total_customers: number
  total_revenue_cents: number
  total_api_cost_cents: number
  total_profit_cents: number
  avg_revenue_per_customer_cents: number
  total_api_tokens_used: number
}

export function AdminDashboard() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [analytics, setAnalytics] = useState<Analytics | null>(null)
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    try {
      const [customersData, analyticsData] = await Promise.all([
        api.get('/admin/customers'),
        api.get('/admin/analytics'),
      ])
      setCustomers(customersData.data)
      setAnalytics(analyticsData.data)
    } catch (error) {
      console.error('Failed to load admin data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="admin-loading">Loading...</div>
  }

  return (
    <div className="admin-dashboard">
      <div className="admin-header">
        <h1>Business Dashboard</h1>
        <div className="admin-metrics">
          {analytics && (
            <>
              <div className="metric">
                <span className="metric-value">{analytics.total_customers}</span>
                <span className="metric-label">Customers</span>
              </div>
              <div className="metric">
                <span className="metric-value">${(analytics.total_revenue_cents / 100).toFixed(0)}</span>
                <span className="metric-label">Revenue</span>
              </div>
              <div className="metric">
                <span className="metric-value">${(analytics.total_profit_cents / 100).toFixed(0)}</span>
                <span className="metric-label">Profit</span>
              </div>
              <div className="metric">
                <span className="metric-value">{analytics.total_api_tokens_used.toLocaleString()}</span>
                <span className="metric-label">API Tokens</span>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="admin-content">
        <div className="customers-list">
          <h2>Customers</h2>
          <div className="customers-grid">
            {customers.map((customer) => (
              <div
                key={customer.id}
                className={`customer-card ${selectedCustomer?.id === customer.id ? 'active' : ''}`}
                onClick={() => setSelectedCustomer(customer)}
              >
                <div className="customer-name">{customer.name}</div>
                <div className="customer-meta">
                  <span>{customer.industry}</span>
                  <span>{customer.plan}</span>
                </div>
                <div className="customer-profit">
                  ${(customer.profit_cents / 100).toFixed(0)}
                </div>
              </div>
            ))}
          </div>
        </div>

        {selectedCustomer && (
          <div className="customer-detail">
            <div className="detail-header">
              <h2>{selectedCustomer.legal_name}</h2>
              <button onClick={() => setSelectedCustomer(null)}>Close</button>
            </div>

            <div className="detail-section">
              <h3>Information</h3>
              <div className="info-grid">
                <div>
                  <span className="label">Owner</span>
                  <span>{selectedCustomer.owner}</span>
                </div>
                <div>
                  <span className="label">Industry</span>
                  <span>{selectedCustomer.industry}</span>
                </div>
                <div>
                  <span className="label">Plan</span>
                  <span>{selectedCustomer.plan}</span>
                </div>
                <div>
                  <span className="label">Created</span>
                  <span>{new Date(selectedCustomer.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            </div>

            <div className="detail-section">
              <h3>Billing</h3>
              <div className="billing-grid">
                <div>
                  <span className="label">Monthly Price</span>
                  <span className="value">${(selectedCustomer.monthly_price_cents / 100).toFixed(2)}</span>
                </div>
                <div>
                  <span className="label">API Cost</span>
                  <span className="value">${(selectedCustomer.claude_api_cost_cents / 100).toFixed(2)}</span>
                </div>
                <div>
                  <span className="label">Profit</span>
                  <span className="value">${(selectedCustomer.profit_cents / 100).toFixed(2)}</span>
                </div>
                <div>
                  <span className="label">API Tokens</span>
                  <span className="value">{selectedCustomer.claude_api_tokens.toLocaleString()}</span>
                </div>
              </div>
            </div>

            <div className="detail-section">
              <h3>Modules</h3>
              <div className="modules-list">
                {selectedCustomer.modules.map((module) => (
                  <span key={module} className="module-tag">{module}</span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
