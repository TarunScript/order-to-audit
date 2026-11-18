import React, { useState, useEffect } from 'react';
import { Item, StockLedgerEntry } from '../../types';
import { apiGetItems, apiGetStockLedger, paiseToRs } from '../../services/api';
import {
  ClipboardList,
  Filter,
  RefreshCw,
  ArrowUpRight,
  ArrowDownLeft,
} from 'lucide-react';

export const StockLedger: React.FC = () => {
  const [items, setItems] = useState<Item[]>([]);
  const [ledger, setLedger] = useState<StockLedgerEntry[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [selectedItemId, setSelectedItemId] = useState<string>('');
  const [fromDate, setFromDate] = useState<string>('');
  const [toDate, setToDate] = useState<string>('');
  const [movementType, setMovementType] = useState<string>('');

  const loadItems = async () => {
    try {
      const data = await apiGetItems();
      setItems(data);
    } catch (err) {
      console.error('Failed to load items:', err);
    }
  };

  const loadLedger = async () => {
    setLoading(true);
    try {
      const data = await apiGetStockLedger({
        item_id: selectedItemId ? Number(selectedItemId) : undefined,
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
        movement_type: movementType || undefined,
      });
      setLedger(data);
    } catch (err) {
      console.error('Failed to load stock ledger:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItems();
    loadLedger();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Stock Movement Ledger</h1>
          <p className="text-sm text-slate-500">
            Append-only audit trail: every inventory inflow and outflow with source document links
          </p>
        </div>
        <button onClick={loadLedger} className="btn-secondary self-start">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filters Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm grid grid-cols-1 sm:grid-cols-4 gap-3">
        <div>
          <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
            Filter by Item
          </label>
          <select
            value={selectedItemId}
            onChange={(e) => setSelectedItemId(e.target.value)}
            className="w-full p-2 bg-slate-50 border rounded-lg text-xs"
          >
            <option value="">All Items</option>
            {items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name} ({i.sku})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
            Movement Type
          </label>
          <select
            value={movementType}
            onChange={(e) => setMovementType(e.target.value)}
            className="w-full p-2 bg-slate-50 border rounded-lg text-xs"
          >
            <option value="">All Movement Types</option>
            <option value="OPENING">OPENING</option>
            <option value="PURCHASE_RECEIPT">PURCHASE_RECEIPT</option>
            <option value="PRODUCTION_ISSUE">PRODUCTION_ISSUE</option>
            <option value="PRODUCTION_OUTPUT">PRODUCTION_OUTPUT</option>
            <option value="SALES_DISPATCH">SALES_DISPATCH</option>
            <option value="SALES_RETURN">SALES_RETURN</option>
            <option value="ADJUSTMENT">ADJUSTMENT</option>
            <option value="REVERSAL">REVERSAL</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
            From Date
          </label>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="w-full p-2 border rounded-lg text-xs"
          />
        </div>

        <div className="flex items-end gap-2">
          <div className="flex-1">
            <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
              To Date
            </label>
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="w-full p-2 border rounded-lg text-xs"
            />
          </div>
          <button onClick={loadLedger} className="btn-primary text-xs py-2">
            <Filter className="w-3.5 h-3.5" />
            <span>Apply</span>
          </button>
        </div>
      </div>

      {/* Ledger Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
              <tr>
                <th className="p-3">Timestamp</th>
                <th className="p-3">Item</th>
                <th className="p-3">Movement Type</th>
                <th className="p-3 text-right">Signed Qty (Display)</th>
                <th className="p-3 text-right">Signed Qty (Base)</th>
                <th className="p-3 text-right">Value (₹)</th>
                <th className="p-3 text-right">Running Balance</th>
                <th className="p-3">Source Document</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {ledger.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400">
                    No ledger entries found
                  </td>
                </tr>
              ) : (
                ledger.map((row) => {
                  const isPositive = row.qty_base >= 0;

                  return (
                    <tr key={row.id} className="hover:bg-slate-50">
                      <td className="p-3 text-slate-500 font-mono text-[11px] whitespace-nowrap">
                        {new Date(row.posted_at).toLocaleString()}
                      </td>
                      <td className="p-3">
                        <div className="font-bold text-slate-900">{row.item_name}</div>
                        <div className="text-[11px] text-slate-400 font-mono">{row.item_sku}</div>
                      </td>
                      <td className="p-3">
                        <span className="inline-flex items-center gap-1 font-mono text-[11px] px-2 py-0.5 rounded bg-slate-100 text-slate-800 font-semibold border">
                          {isPositive ? (
                            <ArrowDownLeft className="w-3 h-3 text-emerald-600" />
                          ) : (
                            <ArrowUpRight className="w-3 h-3 text-red-600" />
                          )}
                          <span>{row.movement_type}</span>
                        </span>
                      </td>
                      <td
                        className={`p-3 text-right font-bold text-sm ${
                          isPositive ? 'text-emerald-700' : 'text-red-700'
                        }`}
                      >
                        {isPositive ? `+${row.qty_display}` : row.qty_display} {row.display_unit}
                      </td>
                      <td className="p-3 text-right font-mono text-slate-500">
                        {isPositive ? `+${row.qty_base}` : row.qty_base}
                      </td>
                      <td
                        className={`p-3 text-right font-semibold ${
                          row.value_paise >= 0 ? 'text-emerald-700' : 'text-red-700'
                        }`}
                      >
                        {paiseToRs(row.value_paise)}
                      </td>
                      <td className="p-3 text-right font-extrabold text-slate-900 text-sm">
                        {row.running_qty_display} {row.display_unit}
                      </td>
                      <td className="p-3 text-slate-600">
                        <span className="font-mono text-xs font-semibold text-blue-700">
                          {row.source_type} #{row.source_id}
                        </span>
                        {row.note && (
                          <div className="text-[11px] text-slate-400 truncate max-w-xs">
                            {row.note}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
