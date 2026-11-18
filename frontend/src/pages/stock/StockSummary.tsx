import React, { useState, useEffect } from 'react';
import { StockSummaryItem } from '../../types';
import {
  apiGetStockSummary,
  apiCreateAdjustment,
  paiseToRs,
} from '../../services/api';
import {
  Package,
  AlertTriangle,
  RefreshCw,
  PlusCircle,
  CheckCircle2,
} from 'lucide-react';

export const StockSummary: React.FC = () => {
  const [items, setItems] = useState<StockSummaryItem[]>([]);
  const [activeTab, setActiveTab] = useState<'RAW' | 'PACKAGING' | 'FINISHED'>('RAW');
  const [loading, setLoading] = useState(true);

  // Stock Adjustment Modal
  const [showAdjModal, setShowAdjModal] = useState(false);
  const [adjItemId, setAdjItemId] = useState<number | ''>('');
  const [adjQty, setAdjQty] = useState('');
  const [adjReason, setAdjReason] = useState('');
  const [adjLoading, setAdjLoading] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadSummary = async () => {
    setLoading(true);
    try {
      const data = await apiGetStockSummary();
      setItems(data);
      if (data.length > 0 && !adjItemId) {
        setAdjItemId(data[0].item_id);
      }
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Failed to load stock summary' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSummary();
  }, []);

  const handleCreateAdjustment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adjItemId || !adjQty || !adjReason.trim()) {
      setFeedbackMsg({ type: 'error', text: 'All adjustment fields and mandatory reason are required' });
      return;
    }

    const item = items.find((i) => i.item_id === Number(adjItemId));
    if (!item) return;

    setAdjLoading(true);
    setFeedbackMsg(null);
    try {
      await apiCreateAdjustment({
        item_id: item.item_id,
        qty: parseFloat(adjQty),
        unit: item.display_unit,
        reason: adjReason.trim(),
      });
      setShowAdjModal(false);
      setAdjQty('');
      setAdjReason('');
      setFeedbackMsg({ type: 'success', text: 'Stock adjustment posted to append-only ledger!' });
      await loadSummary();
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Stock adjustment failed' });
    } finally {
      setAdjLoading(false);
    }
  };

  const filteredItems = items.filter((i) => i.type === activeTab);

  const totalTabValuePaise = filteredItems.reduce((acc, i) => acc + i.value_paise, 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Stock Summary & Valuation</h1>
          <p className="text-sm text-slate-500">
            Real-time ledger-backed inventory balances with Weighted Average Cost (WAC)
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadSummary} className="btn-secondary">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <button onClick={() => setShowAdjModal(true)} className="btn-primary">
            <PlusCircle className="w-4 h-4" />
            <span>Stock Adjustment</span>
          </button>
        </div>
      </div>

      {feedbackMsg && (
        <div
          className={`p-4 rounded-xl text-sm border flex items-center gap-2 ${
            feedbackMsg.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-red-50 border-red-200 text-red-800'
          }`}
        >
          {feedbackMsg.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 flex-shrink-0 text-emerald-600" />
          ) : (
            <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-600" />
          )}
          <span>{feedbackMsg.text}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex justify-between items-center border-b border-slate-200 pb-2">
        <div className="flex gap-2">
          {(['RAW', 'PACKAGING', 'FINISHED'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                activeTab === tab
                  ? 'bg-blue-700 text-white shadow-sm'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
              }`}
            >
              {tab === 'RAW' ? 'Raw Materials' : tab === 'PACKAGING' ? 'Packaging Materials' : 'Finished Goods'}
            </button>
          ))}
        </div>
        <div className="text-xs text-slate-500 font-medium">
          Category Valuation:{' '}
          <span className="font-extrabold text-slate-900 text-sm">
            {paiseToRs(totalTabValuePaise)}
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
              <tr>
                <th className="p-3">SKU</th>
                <th className="p-3">Item Name</th>
                <th className="p-3 text-right">Closing Qty (Display)</th>
                <th className="p-3 text-right">Base Unit Qty</th>
                <th className="p-3 text-right">Unit Cost (WAC)</th>
                <th className="p-3 text-right">Valuation (₹)</th>
                <th className="p-3 text-right">Reorder Level</th>
                <th className="p-3 text-center">Stock Alert</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400">
                    No items in this category
                  </td>
                </tr>
              ) : (
                filteredItems.map((item) => (
                  <tr key={item.item_id} className="hover:bg-slate-50">
                    <td className="p-3 font-mono font-bold text-blue-700">{item.sku}</td>
                    <td className="p-3 font-bold text-slate-900">{item.name}</td>
                    <td className="p-3 text-right font-extrabold text-slate-900 text-sm">
                      {item.closing_qty_display} {item.display_unit}
                    </td>
                    <td className="p-3 text-right font-mono text-slate-500">
                      {item.closing_qty_base} {item.base_unit}
                    </td>
                    <td className="p-3 text-right font-medium text-slate-700">
                      {item.unit_cost ? `${item.unit_cost.toFixed(3)} p/${item.base_unit}` : '—'}
                    </td>
                    <td className="p-3 text-right font-bold text-slate-900">
                      {paiseToRs(item.value_paise)}
                    </td>
                    <td className="p-3 text-right text-slate-500">
                      {item.reorder_level_display} {item.display_unit}
                    </td>
                    <td className="p-3 text-center">
                      {item.is_low_stock ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                          <AlertTriangle className="w-3 h-3 text-amber-600" />
                          <span>LOW STOCK</span>
                        </span>
                      ) : (
                        <span className="text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                          Healthy
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Stock Adjustment Modal */}
      {showAdjModal && (
        <div className="fixed inset-0 bg-slate-900/60 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Stock Adjustment</h3>
            <p className="text-xs text-slate-500">
              Post physical stock verification discrepancy. Positive (+) to increase, negative (-) to decrease.
            </p>

            <form onSubmit={handleCreateAdjustment} className="space-y-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Item *
                </label>
                <select
                  value={adjItemId}
                  onChange={(e) => setAdjItemId(Number(e.target.value))}
                  className="w-full p-2 bg-slate-50 border rounded-lg text-sm"
                >
                  {items.map((i) => (
                    <option key={i.item_id} value={i.item_id}>
                      {i.name} ({i.sku}) [{i.display_unit}]
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Quantity (+ or -) *
                </label>
                <input
                  type="number"
                  step="any"
                  required
                  placeholder="e.g. -5 or 10"
                  value={adjQty}
                  onChange={(e) => setAdjQty(e.target.value)}
                  className="w-full p-2 border rounded-lg text-sm font-bold"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Mandatory Reason *
                </label>
                <textarea
                  rows={2}
                  required
                  placeholder="e.g. Physical inventory count variance, spillage..."
                  value={adjReason}
                  onChange={(e) => setAdjReason(e.target.value)}
                  className="w-full p-2 border rounded-lg text-sm"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAdjModal(false)}
                  className="btn-secondary text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={adjLoading}
                  className="btn-primary text-xs"
                >
                  Post Adjustment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
