import React from 'react';

const Sheets = () => {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-4xl font-bold text-gray-900">Daily Closings</h1>
        <button className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-indigo-700 transition">
          + Add Entry
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-lg overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Date</th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Cashier</th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Total Sales</th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Cash In</th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Card In</th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Variance</th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b hover:bg-gray-50">
              <td className="px-6 py-4 text-sm text-gray-900">08/05/2026</td>
              <td className="px-6 py-4 text-sm text-gray-900">John</td>
              <td className="px-6 py-4 text-sm text-gray-900">$2,450.50</td>
              <td className="px-6 py-4 text-sm text-gray-900">$1,200.00</td>
              <td className="px-6 py-4 text-sm text-gray-900">$1,250.50</td>
              <td className="px-6 py-4 text-sm text-red-600">-$5.00</td>
              <td className="px-6 py-4 text-sm">
                <button className="text-indigo-600 hover:text-indigo-900">Edit</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Sheets;
