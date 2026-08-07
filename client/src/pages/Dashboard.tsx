import React, { useState } from 'react';

const Dashboard = () => {
  const [period, setPeriod] = useState<'weekly' | 'monthly'>('weekly');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-4xl font-bold text-gray-900">Dashboard</h1>
        <div className="space-x-4">
          <button
            onClick={() => setPeriod('weekly')}
            className={`px-6 py-2 rounded-lg font-semibold transition ${
              period === 'weekly'
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            This Week
          </button>
          <button
            onClick={() => setPeriod('monthly')}
            className={`px-6 py-2 rounded-lg font-semibold transition ${
              period === 'monthly'
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            This Month
          </button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Total Sales Card */}
        <div className="bg-white rounded-xl shadow-lg p-6 hover:shadow-xl transition">
          <p className="text-gray-600 text-sm font-semibold uppercase tracking-wider">Total Sales</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">$12,450</p>
          <p className="text-green-600 text-sm mt-2">+12% from last period</p>
        </div>

        {/* Budget Progress Card */}
        <div className="bg-white rounded-xl shadow-lg p-6 hover:shadow-xl transition">
          <p className="text-gray-600 text-sm font-semibold uppercase tracking-wider">Budget Goal</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">$5,000</p>
          <div className="mt-2 bg-gray-200 rounded-full h-2">
            <div className="bg-indigo-600 h-2 rounded-full" style={{ width: '87%' }}></div>
          </div>
          <p className="text-sm text-gray-600 mt-2">87% of daily target</p>
        </div>

        {/* Cash Variance Card */}
        <div className="bg-white rounded-xl shadow-lg p-6 hover:shadow-xl transition">
          <p className="text-gray-600 text-sm font-semibold uppercase tracking-wider">Cash Variance</p>
          <p className="text-3xl font-bold text-green-600 mt-2">+$145</p>
          <p className="text-gray-600 text-sm mt-2">Over expected</p>
        </div>

        {/* Payroll Owed Card */}
        <div className="bg-white rounded-xl shadow-lg p-6 hover:shadow-xl transition">
          <p className="text-gray-600 text-sm font-semibold uppercase tracking-wider">Payroll Owed</p>
          <p className="text-3xl font-bold text-orange-600 mt-2">$3,240</p>
          <p className="text-gray-600 text-sm mt-2">2 employees</p>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Weekly/Monthly Chart */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Sales Trend</h2>
          <div className="h-64 bg-gradient-to-br from-indigo-100 to-purple-100 rounded-lg flex items-center justify-center">
            <p className="text-gray-500">Chart will load here</p>
          </div>
        </div>

        {/* Payment Breakdown */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Payment Methods</h2>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-gray-700">Cash</span>
              <div className="flex-1 mx-4 bg-gray-200 rounded-full h-2">
                <div className="bg-blue-500 h-2 rounded-full" style={{ width: '45%' }}></div>
              </div>
              <span className="font-semibold text-gray-900 min-w-20">45%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-700">Card</span>
              <div className="flex-1 mx-4 bg-gray-200 rounded-full h-2">
                <div className="bg-purple-500 h-2 rounded-full" style={{ width: '55%' }}></div>
              </div>
              <span className="font-semibold text-gray-900 min-w-20">55%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
