import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useStore } from '../store/appStore';

const Navigation = () => {
  const location = useLocation();
  const { user } = useStore();

  const isActive = (path: string) => location.pathname === path ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-600 hover:text-gray-900';

  return (
    <nav className="bg-white shadow-lg sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex justify-between items-center h-16">
          {/* Logo/Brand */}
          <Link to="/" className="flex items-center space-x-2 font-bold text-2xl text-indigo-600">
            <span className="text-3xl">📊</span>
            <span>BAMs Dashboard</span>
          </Link>

          {/* Tabs */}
          <div className="flex space-x-8 items-center flex-1 ml-12">
            <Link to="/" className={`pb-4 ${isActive('/')} transition`}>
              Dashboard
            </Link>
            <Link to="/sheets" className={`pb-4 ${isActive('/sheets')} transition`}>
              Sheets
            </Link>
            <Link to="/tips" className={`pb-4 ${isActive('/tips')} transition`}>
              Tips & Taxes
            </Link>
            <Link to="/payroll" className={`pb-4 ${isActive('/payroll')} transition`}>
              Payroll
            </Link>
            <Link to="/audit" className={`pb-4 ${isActive('/audit')} transition`}>
              Audit
            </Link>
          </div>

          {/* Profile */}
          <div className="flex items-center space-x-4">
            <div className="text-right">
              <p className="font-semibold text-gray-900">{user?.name || 'User'}</p>
              <p className="text-xs text-gray-500 capitalize">{user?.role || 'staff'}</p>
            </div>
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold">
              {user?.name?.charAt(0).toUpperCase() || 'U'}
            </div>
            <Link to="/settings" className="text-gray-600 hover:text-gray-900 transition">
              ⚙️
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navigation;
