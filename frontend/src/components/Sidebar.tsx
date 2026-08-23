import React from 'react';

interface Module {
  id: string;
  name: string;
  icon?: React.ReactNode;
  enabled: boolean;
}

interface User {
  name: string;
  role?: string;
}

interface SidebarProps {
  modules: Module[];
  activeTab: string;
  onTabChange: (moduleId: string) => void;
  user?: User;
  workspaceName?: string;
}

const Sidebar: React.FC<SidebarProps> = ({
  modules,
  activeTab,
  onTabChange,
  user,
  workspaceName = 'Business OS',
}) => {
  const enabledModules = modules.filter((m) => m.enabled);

  return (
    <aside
      style={{
        background: 'var(--surface)',
        borderRight: '1px solid #f0f0f0',
        padding: '32px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '48px',
        minHeight: '100vh',
        width: '240px',
      }}
    >
      {/* Brand */}
      <div style={{ fontSize: '18px', fontWeight: 600, letterSpacing: '-0.02em' }}>
        {workspaceName}
      </div>

      {/* Navigation */}
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {enabledModules.length === 0 ? (
          <div style={{ fontSize: '14px', color: 'var(--text-muted)' }}>No modules enabled</div>
        ) : (
          enabledModules.map((module) => (
            <button
              key={module.id}
              onClick={() => onTabChange(module.id)}
              style={{
                padding: '10px 12px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '15px',
                color: activeTab === module.id ? 'var(--text)' : 'var(--text-muted)',
                background: activeTab === module.id ? '#f5f5f5' : 'transparent',
                border: 'none',
                textAlign: 'left',
                transition: 'all 0.2s',
                position: 'relative',
                paddingLeft: activeTab === module.id ? '12px' : '12px',
                fontWeight: activeTab === module.id ? 500 : 400,
              }}
              onMouseEnter={(e) => {
                if (activeTab !== module.id) {
                  (e.currentTarget as HTMLElement).style.background = '#f5f5f5';
                }
              }}
              onMouseLeave={(e) => {
                if (activeTab !== module.id) {
                  (e.currentTarget as HTMLElement).style.background = 'transparent';
                }
              }}
            >
              {activeTab === module.id && (
                <div
                  style={{
                    position: 'absolute',
                    left: '0',
                    top: '0',
                    bottom: '0',
                    width: '3px',
                    background: 'var(--accent)',
                    borderRadius: '0 3px 3px 0',
                  }}
                />
              )}
              <span style={{ marginLeft: activeTab === module.id ? '8px' : '0px' }}>
                {module.icon ? <span style={{ marginRight: '8px' }}>{module.icon}</span> : null}
                {module.name}
              </span>
            </button>
          ))
        )}
      </nav>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Footer */}
      {user && (
        <div
          style={{
            paddingTop: '24px',
            borderTop: '1px solid #f0f0f0',
            fontSize: '13px',
            color: 'var(--text-muted)',
          }}
        >
          <div style={{ fontWeight: 500, color: 'var(--text)', marginBottom: '4px' }}>
            {user.name}
          </div>
          {user.role && <div style={{ fontSize: '12px' }}>{user.role}</div>}
        </div>
      )}
    </aside>
  );
};

export default Sidebar;
