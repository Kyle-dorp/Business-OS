import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import './App.css';
import Navigation from './components/Navigation';
import Dashboard from './pages/Dashboard';
import Sheets from './pages/Sheets';
import Tips from './pages/Tips';
import Payroll from './pages/Payroll';
import AuditLogs from './pages/AuditLogs';
import Settings from './pages/Settings';
import { useStore } from './store/appStore';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const { user, setUser } = useStore();

  useEffect(() => {
    // Check authentication on mount
    checkAuthentication();
  }, []);

  const checkAuthentication = async () => {
    try {
      // Verify certificate auth by hitting the health endpoint
      const response = await fetch('https://localhost:8443/health', {
        method: 'GET',
        credentials: 'include', // Send certificate
      });

      if (response.ok) {
        // Get user info
        const userResponse = await fetch('https://localhost:8443/api/employees/current/profile', {
          credentials: 'include',
        });

        if (userResponse.ok) {
          const userData = await userResponse.json();
          setUser(userData);
          setIsAuthenticated(true);
        }
      }
    } catch (error) {
      console.error('Authentication check failed:', error);
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-indigo-600 to-purple-700">
        <div className="text-center">
          <div className="mb-4">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-white border-r-transparent"></div>
          </div>
          <p className="text-white text-lg font-semibold">Loading BAMs Dashboard...</p>
          <p className="text-indigo-200 text-sm mt-2">Verifying certificate authentication</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-indigo-600 to-purple-700">
        <div className="text-center max-w-md">
          <div className="mb-6">
            <div className="text-6xl mb-4">🔐</div>
            <h1 className="text-3xl font-bold text-white mb-2">Certificate Required</h1>
            <p className="text-indigo-200">This dashboard uses mutual TLS (mTLS) for secure authentication.</p>
          </div>
          <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-lg p-6 text-left">
            <h3 className="text-white font-semibold mb-3">Setup Instructions:</h3>
            <ol className="text-indigo-100 text-sm space-y-2">
              <li>1. Install your client certificate on this device</li>
              <li>2. Ensure browser/system has the certificate loaded</li>
              <li>3. Reload this page</li>
              <li>4. Your device certificate will be verified automatically</li>
            </ol>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 w-full bg-indigo-500 hover:bg-indigo-600 text-white font-semibold py-2 px-4 rounded-lg transition"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <Router>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
        <Navigation />
        <main className="max-w-7xl mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/sheets" element={<Sheets />} />
            <Route path="/tips" element={<Tips />} />
            <Route path="/payroll" element={<Payroll />} />
            <Route path="/audit" element={<AuditLogs />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
