import React, { useState, useEffect } from 'react';
import { DashboardData } from '../../types';
import { apiGetDashboard, paiseToRs } from '../../services/api';
import {
  LayoutDashboard,
  ShoppingBag,
  Clock,
  Package,
  AlertTriangle,
  DollarSign,
  TrendingUp,
  RefreshCw,
  Users,
  Layers,
} from 'lucide-react';

export const OwnerDashboard: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const loadDashboard = async () => {
    setLoading(true);
    try {
      const res = await apiGetDashboard();
      setData(res);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  if (loading) {
    return <div className="text-center py-12 text-slate-400">Loading executive dashboard...</div>;
  }

  if (!data) {
    return <div className="text-center py-12 text-slate-400">Unable to load dashboard data</div>;
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Executive Dashboard</h1>
          <p className="text-sm text-slate-500">
            Real-time operations, stock alerts, production variances & working capital
          </p>
        </div>
        <button onClick={loadDashboard} className="btn-secondary self-start">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Top 4 KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. Today's Orders */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-blue-600 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Today's Orders</span>
            <div className="p-2 bg-blue-50 rounded-xl">
              <ShoppingBag className="w-5 h-5" />
            </div>
          </div>
          <div className="text-2xl font-black text-slate-900">
            {paiseToRs(data.todays_orders.total_paise)}
          </div>
          <p className="text-xs text-slate-500 mt-1">
            <span className="font-bold text-slate-800">{data.todays_orders.count}</span> orders placed today
          </p>
        </div>

        {/* 2. Pending Approval */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-amber-600 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Pending Approval</span>
            <div className="p-2 bg-amber-50 rounded-xl">
              <Clock className="w-5 h-5" />
            </div>
          </div>
          <div className="text-2xl font-black text-slate-900">
            {data.pending_approvals.count} Orders
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Awaiting stock check & billing
          </p>
        </div>

        {/* 3. Open Variance Alerts */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-red-600 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Variance Alerts</span>
            <div className="p-2 bg-red-50 rounded-xl">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="text-2xl font-black text-red-600">
            {data.variance_alerts.length} Flagged
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Consumption &gt; 3% tolerance
          </p>
        </div>

        {/* 4. Total Market Debtors */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-emerald-600 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Market Outstanding</span>
            <div className="p-2 bg-emerald-50 rounded-xl">
              <DollarSign className="w-5 h-5" />
            </div>
          </div>
          <div className="text-2xl font-black text-slate-900">
            ₹{data.total_outstanding_rs.toFixed(2)}
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Receivables net of payments
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (7 cols): Costing & Product Margins + Top Debtors */}
        <div className="lg:col-span-7 space-y-6">
          {/* Cost Per Packet & Margin by Product */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
            <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-100">
              <TrendingUp className="w-5 h-5 text-blue-600" />
              <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                Product Costing & Unit Margins
              </h2>
            </div>

            <div className="divide-y divide-slate-100">
              {data.costing_margins.map((p) => (
                <div key={p.product_id} className="py-3 flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-bold text-slate-900">{p.name}</h4>
                    <div className="text-xs text-slate-500 mt-0.5">
                      SKU: <span className="font-mono">{p.sku}</span> {p.last_run_no ? `• Last Run: ${p.last_run_no}` : ''}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-extrabold text-blue-900">
                      Cost: {paiseToRs(p.cost_per_packet_paise)} / pkt
                    </div>
                    <div className="text-xs text-emerald-700 font-bold mt-0.5">
                      Margin: +{paiseToRs(p.margin_paise)} (Sale: {paiseToRs(p.selling_price_paise)})
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Top 5 Debtors (Accounts Receivable) */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
            <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-100">
              <Users className="w-5 h-5 text-indigo-600" />
              <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                Top Debtors (Receivables)
              </h2>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 font-semibold border-b">
                  <tr>
                    <th className="p-2.5">Customer</th>
                    <th className="p-2.5">Credit Terms</th>
                    <th className="p-2.5 text-right">Outstanding (₹)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.top_debtors.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="p-4 text-center text-slate-400">
                        No outstanding dues
                      </td>
                    </tr>
                  ) : (
                    data.top_debtors.map((d) => (
                      <tr key={d.customer_id} className="hover:bg-slate-50">
                        <td className="p-2.5 font-bold text-slate-900">{d.customer_name}</td>
                        <td className="p-2.5 text-slate-500">{d.credit_days} days</td>
                        <td className="p-2.5 text-right font-extrabold text-slate-900 text-sm">
                          ₹{d.outstanding_rs.toFixed(2)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right Column (5 cols): Variance Alerts + Low Stock Levels */}
        <div className="lg:col-span-5 space-y-6">
          {/* Open Variance Alerts (Strict Red Flag) */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-red-600" />
                <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  Material & Yield Alerts
                </h2>
              </div>
              <span className="text-[11px] font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded border border-red-200">
                {data.variance_alerts.length} Breaches
              </span>
            </div>

            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {data.variance_alerts.length === 0 ? (
                <p className="text-xs text-slate-400 text-center py-4">
                  No open variance breaches recorded
                </p>
              ) : (
                data.variance_alerts.map((alert, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-red-50/60 border border-red-200 rounded-xl text-xs"
                  >
                    <div className="flex justify-between font-bold text-red-900">
                      <span>{alert.line_name}</span>
                      <span className="text-red-700">
                        {alert.variance_pct > 0 ? '+' : ''}{alert.variance_pct.toFixed(1)}%
                      </span>
                    </div>
                    <div className="text-slate-600 text-[11px] mt-1 flex justify-between">
                      <span>Run {alert.run_no} ({alert.run_date})</span>
                      <span className="text-slate-400">Limit: ±{alert.tolerance_pct}%</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Stock Levels with Low-Stock Amber Markers */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
            <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-100">
              <Package className="w-5 h-5 text-slate-700" />
              <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                Critical Inventory Levels
              </h2>
            </div>

            <div className="space-y-2 max-h-[300px] overflow-y-auto text-xs">
              {data.stock_levels.map((item) => (
                <div
                  key={item.item_id}
                  className={`p-2.5 rounded-xl border flex items-center justify-between ${
                    item.is_low_stock
                      ? 'bg-amber-50/70 border-amber-300'
                      : 'bg-slate-50 border-slate-200'
                  }`}
                >
                  <div>
                    <div className="font-bold text-slate-900">{item.name}</div>
                    <div className="text-[11px] text-slate-400 font-mono">
                      {item.sku} ({item.type})
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-extrabold text-slate-900 text-sm">
                      {item.closing_qty_display} {item.display_unit}
                    </div>
                    {item.is_low_stock && (
                      <span className="text-[10px] font-bold text-amber-700 uppercase">
                        Below Reorder
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
