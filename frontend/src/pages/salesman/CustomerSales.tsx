import React, { useState, useEffect } from 'react';
import { Customer, Order } from '../../types';
import { apiGetCustomers, apiGetOrders, paiseToRs } from '../../services/api';
import { Users, Calendar, TrendingUp } from 'lucide-react';

export const CustomerSales: React.FC = () => {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedMonth, setSelectedMonth] = useState<string>('ALL');

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [cList, oList] = await Promise.all([
          apiGetCustomers(),
          apiGetOrders(),
        ]);
        setCustomers(cList);
        setOrders(oList);
      } catch (err) {
        console.error('Failed to load customer sales:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  // Compute metrics per customer
  const customerStats = customers.map((c) => {
    const custOrders = orders.filter((o) => {
      if (o.customer_id !== c.id) return false;
      if (selectedMonth === 'ALL') return true;
      const orderDate = new Date(o.created_at);
      const m = `${orderDate.getFullYear()}-${String(orderDate.getMonth() + 1).padStart(2, '0')}`;
      return m === selectedMonth;
    });

    const totalOrders = custOrders.length;
    const totalPaise = custOrders.reduce((acc, o) => acc + (o.approved_total_paise || o.total_paise), 0);

    return {
      id: c.id,
      name: c.name,
      type: c.type,
      state: c.state_name,
      totalOrders,
      totalPaise,
    };
  });

  const grandTotalPaise = customerStats.reduce((acc, c) => acc + c.totalPaise, 0);

  return (
    <div className="max-w-md mx-auto pb-20">
      <div className="mb-4">
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">
          Customer-wise Sales
        </h1>
        <p className="text-xs text-slate-500">Sales performance and customer volume</p>
      </div>

      {/* Month Filter */}
      <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-sm mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
          <Calendar className="w-4 h-4 text-slate-400" />
          <span>Period:</span>
        </div>
        <select
          value={selectedMonth}
          onChange={(e) => setSelectedMonth(e.target.value)}
          className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 font-medium text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="ALL">All Time</option>
          <option value="2026-11">November 2026</option>
          <option value="2026-10">October 2026</option>
        </select>
      </div>

      {/* Top Banner Metric */}
      <div className="bg-gradient-to-r from-blue-700 to-indigo-800 text-white p-4 rounded-xl shadow-md mb-4 flex justify-between items-center">
        <div>
          <span className="text-xs text-blue-200 font-medium">Total Assigned Volume</span>
          <div className="text-2xl font-extrabold">{paiseToRs(grandTotalPaise)}</div>
        </div>
        <TrendingUp className="w-8 h-8 text-blue-200 opacity-80" />
      </div>

      {/* Customers List */}
      {loading ? (
        <div className="text-center py-10 text-slate-400 text-sm">Loading data...</div>
      ) : (
        <div className="space-y-3">
          {customerStats.map((c) => (
            <div
              key={c.id}
              className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm"
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">{c.name}</h3>
                  <div className="text-xs text-slate-500">{c.type} • {c.state}</div>
                </div>
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                  {c.totalOrders} order{c.totalOrders === 1 ? '' : 's'}
                </span>
              </div>

              <div className="mt-2 pt-2 border-t border-slate-100 flex justify-between items-center text-xs">
                <span className="text-slate-500 font-medium">Booked Revenue</span>
                <span className="text-base font-bold text-slate-900">
                  {paiseToRs(c.totalPaise)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
