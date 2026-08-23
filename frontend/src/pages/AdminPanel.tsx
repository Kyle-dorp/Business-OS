import React, { useState } from 'react';
import Button from '../components/Button';
import Card from '../components/Card';

interface Module {
  key: string;
  name: string;
  description: string;
  enabled: boolean;
  users: number;
  pricing: string;
}

const AdminPanel: React.FC = () => {
  const [enabledModules, setEnabledModules] = useState<Module[]>([
    { key: 'scheduling', name: 'Staff Scheduling', description: 'Smart shift generation', enabled: true, users: 15, pricing: 'Free' },
    { key: 'inventory', name: 'Inventory', description: 'Track stock and suppliers', enabled: true, users: 8, pricing: 'Free' },
    { key: 'finance', name: 'Finance', description: 'Accounting and reporting', enabled: true, users: 3, pricing: 'Free' },
  ]);

  const availableModules: Module[] = [
    { key: 'analytics', name: 'Analytics', description: 'Reports and forecasting', enabled: false, users: 0, pricing: '+$49/mo' },
    { key: 'projects', name: 'Projects', description: 'Task management', enabled: false, users: 0, pricing: 'Coming Soon' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <div>
        <h1 style={{ marginBottom: '12px' }}>⚙️ Configuration</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '16px' }}>
          Manage your business modules and settings
        </p>
      </div>

      <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '24px' }}>
        <label style={{ fontSize: '14px', fontWeight: 600, marginRight: '12px' }}>Preset:</label>
        <select style={{
          padding: '8px 12px',
          border: '1px solid #f0f0f0',
          borderRadius: '6px',
          fontSize: '14px',
          background: 'var(--surface)',
          cursor: 'pointer',
        }}>
          <option>Hospitality (Customized)</option>
          <option>Retail</option>
          <option>Professional</option>
        </select>
        <Button variant="primary">+ Add Module</Button>
      </div>

      <div style={{ borderBottom: '1px solid #f0f0f0', paddingBottom: '12px' }}>
        <button style={{
          background: 'none',
          border: 'none',
          fontSize: '14px',
          fontWeight: 500,
          color: 'var(--text)',
          marginRight: '24px',
          cursor: 'pointer',
          paddingBottom: '12px',
          borderBottom: '2px solid var(--accent)',
        }}>
          Enabled ({enabledModules.length})
        </button>
        <button style={{
          background: 'none',
          border: 'none',
          fontSize: '14px',
          fontWeight: 500,
          color: 'var(--text-muted)',
          cursor: 'pointer',
        }}>
          Available ({availableModules.length})
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {enabledModules.map((mod) => (
          <Card key={mod.key}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
              <div>
                <div style={{ fontSize: '16px', fontWeight: 600 }}>✓ {mod.name}</div>
              </div>
              <Button variant="tertiary" size="sm" onClick={() => console.log('Remove', mod.key)}>
                Remove
              </Button>
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '12px' }}>
              {mod.description}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', gap: '8px' }}>
              <span>👥 {mod.users} users</span>
              <span>•</span>
              <span>✓ Active</span>
            </div>
          </Card>
        ))}
      </div>

      <div style={{ marginTop: '32px', paddingTop: '32px', borderTop: '1px solid #f0f0f0' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>Available to Add</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {availableModules.map((mod) => (
            <Card key={mod.key}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                <div>
                  <div style={{ fontSize: '16px', fontWeight: 600 }}>○ {mod.name}</div>
                </div>
                <Button variant="secondary" size="sm" onClick={() => console.log('Add', mod.key)}>
                  {mod.pricing === 'Coming Soon' ? 'Coming Soon' : '+ Add'}
                </Button>
              </div>
              <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                {mod.description}
              </div>
            </Card>
          ))}
        </div>
      </div>

      <div style={{ marginTop: '32px', padding: '24px', background: 'var(--bg)', borderRadius: '12px', textAlign: 'center' }}>
        <div style={{ fontWeight: 600, marginBottom: '8px' }}>Current Plan: Professional</div>
        <div style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '16px' }}>
          5 modules • $99/month • 50 users
        </div>
        <Button variant="secondary" size="sm">Change Plan</Button>
      </div>
    </div>
  );
};

export default AdminPanel;
