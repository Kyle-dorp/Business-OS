import React from 'react';
import Card from '../components/Card';
import Button from '../components/Button';

interface Module {
  id: string;
  name: string;
  description: string;
  icon: string;
  users: number;
  status: 'active' | 'inactive';
}

const Dashboard: React.FC = () => {
  const modules: Module[] = [
    {
      id: 'scheduling',
      name: 'Staff Scheduling',
      description: 'Smart shift generation with AI, availability management',
      icon: '⏰',
      users: 15,
      status: 'active',
    },
    {
      id: 'inventory',
      name: 'Inventory',
      description: 'Track stock, manage suppliers, record movements',
      icon: '📦',
      users: 8,
      status: 'active',
    },
    {
      id: 'finance',
      name: 'Finance',
      description: 'Double-entry ledger, P&L, balance sheet, reporting',
      icon: '💰',
      users: 3,
      status: 'active',
    },
    {
      id: 'crm',
      name: 'Customers',
      description: 'CRM, profiles, history, preferences',
      icon: '👥',
      users: 8,
      status: 'active',
    },
    {
      id: 'invoicing',
      name: 'Invoicing',
      description: 'Create, track, and manage payments',
      icon: '📄',
      users: 6,
      status: 'active',
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '48px' }}>
      {/* Welcome Section */}
      <div>
        <h1 style={{ marginBottom: '12px' }}>Welcome back</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '16px' }}>
          Your business is running 5 core modules • 8 team members
        </p>
      </div>

      {/* Stats */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '32px',
        }}
      >
        <div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 500, marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Revenue</div>
          <div style={{ fontSize: '36px', fontWeight: 700, fontFamily: 'monospace', marginBottom: '4px' }}>$14.2k</div>
          <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>+12% from last month</div>
        </div>
        <div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 500, marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Staff Online</div>
          <div style={{ fontSize: '36px', fontWeight: 700, fontFamily: 'monospace', marginBottom: '4px' }}>8/12</div>
          <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>today</div>
        </div>
        <div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 500, marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Customers</div>
          <div style={{ fontSize: '36px', fontWeight: 700, fontFamily: 'monospace', marginBottom: '4px' }}>1,240</div>
          <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>+85 this month</div>
        </div>
        <div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 500, marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Inventory</div>
          <div style={{ fontSize: '36px', fontWeight: 700, fontFamily: 'monospace', marginBottom: '4px' }}>340</div>
          <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>15 low stock</div>
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 style={{ fontSize: '20px', marginBottom: '24px' }}>Quick Actions</h2>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <Button variant="primary">+ New Schedule</Button>
          <Button variant="primary">+ New Invoice</Button>
          <Button variant="secondary">View Reports</Button>
        </div>
      </div>

      {/* Modules Grid */}
      <div>
        <h2 style={{ fontSize: '20px', marginBottom: '24px' }}>Your Modules</h2>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '20px',
          }}
        >
          {modules.map((module) => (
            <Card key={module.id}>
              <div style={{ fontSize: '32px', marginBottom: '12px' }}>{module.icon}</div>
              <div style={{ fontSize: '16px', fontWeight: 600, marginBottom: '8px' }}>
                {module.name}
              </div>
              <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '16px' }}>
                {module.description}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', gap: '8px' }}>
                <span>👥 {module.users} users</span>
                <span>•</span>
                <span>✓ {module.status}</span>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
