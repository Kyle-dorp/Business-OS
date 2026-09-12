import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatBubble from './components/ChatBubble';
import Dashboard from './pages/Dashboard';
import AdminPanel from './pages/AdminPanel';
import { useModules } from './hooks/useModules';

const App: React.FC = () => {
  const [user, setUser] = useState<any>(null);
  const [workspaceId] = useState('1');
  const [activeTab, setActiveTab] = useState('home');
  const { modules } = useModules(workspaceId);

  useEffect(() => {
    setUser({ name: 'Sarah Park', role: 'Manager' });
  }, []);

  const menuModules = [
    { id: 'home', name: 'Home', icon: '🏠', enabled: true },
    ...modules.map((m) => ({ id: m.key, name: m.name, icon: m.icon || '📦', enabled: m.enabled })),
    { id: 'admin', name: 'Admin', icon: '⚙️', enabled: true },
  ];

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <Sidebar
        modules={menuModules}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        user={user}
        workspaceName="Business-EOS"
      />

      {/* Main Content */}
      <main style={{ flex: 1, padding: '48px', background: 'var(--bg)', overflowY: 'auto' }}>
        {activeTab === 'home' && <Dashboard />}
        {activeTab === 'admin' && <AdminPanel />}
      </main>

      {/* Chat Bubble */}
      <ChatBubble
        title="Ask Claude"
        messages={[
          {
            id: '1',
            type: 'bot',
            content: 'Hi! I can help you optimize your business. What can I assist with?',
            timestamp: new Date(),
          },
        ]}
      />
    </div>
  );
};

export default App;
