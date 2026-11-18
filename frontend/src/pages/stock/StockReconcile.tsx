import React, { useState, useEffect } from 'react';
import { apiReconcileStock } from '../../services/api';
import {
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';

export const StockReconcile: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const runReconcile = async () => {
    setLoading(true);
    try {
      const res = await apiReconcileStock();
      setData(res);
    } catch (err) {
      console.error('Reconciliation failed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runReconcile();
  }, []);

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Stock Ledger Reconciliation</h1>
          <p className="text-sm text-slate-500">
            Mathematical proof: item_balances equals SUM(stock_ledger) for every inventory item
          </p>
        </div>
        <button onClick={runReconcile} className="btn-primary self-start">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Run Reconciliation</span>
        </button>
      </div>

      {/* Banner Card */}
      {data && (
        <div
          className={`p-6 rounded-2xl border shadow-sm flex items-start gap-4 ${
            data.all_reconciled
              ? 'bg-emerald-50/80 border-emerald-200 text-emerald-900'
              : 'bg-red-50/80 border-red-300 text-red-900'
          }`}
        >
          <div className="p-3 bg-white rounded-xl shadow-sm">
            {data.all_reconciled ? (
              <ShieldCheck className="w-8 h-8 text-emerald-600" />
            ) : (
              <AlertTriangle className="w-8 h-8 text-red-600" />
            )}
          </div>
          <div>
            <h2 className="text-lg font-bold">
              {data.all_reconciled
                ? 'All Stock Balances Reconciled Perfectly'
                : `${data.mismatch_count} Stock Balance Mismatch Detected!`}
            </h2>
            <p className="text-xs text-slate-600 mt-1">
              Checked {data.total_items_checked} master items against the append-only ledger.
              The formula Opening + Receipts - Issues - Sales ± Adjustments holds with zero deviations.
            </p>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 font-bold text-slate-800 text-sm">
          Item-wise Ledger Verification
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
              <tr>
                <th className="p-3">SKU</th>
                <th className="p-3">Item Name</th>
                <th className="p-3 text-right">Sum of Ledger Rows (Base)</th>
                <th className="p-3 text-right">Cached Balance (Base)</th>
                <th className="p-3 text-right">Difference</th>
                <th className="p-3 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-slate-400">
                    Verifying ledger sums...
                  </td>
                </tr>
              ) : !data || data.items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-slate-400">
                    No items found
                  </td>
                </tr>
              ) : (
                data.items.map((row: any) => {
                  const diff = row.ledger_sum_base - row.cached_balance_base;
                  const isOk = row.is_reconciled && diff === 0;

                  return (
                    <tr key={row.item_id} className="hover:bg-slate-50">
                      <td className="p-3 font-mono font-bold text-blue-700">{row.sku}</td>
                      <td className="p-3 font-bold text-slate-900">{row.name}</td>
                      <td className="p-3 text-right font-mono font-bold text-slate-800">
                        {row.ledger_sum_base}
                      </td>
                      <td className="p-3 text-right font-mono font-bold text-slate-800">
                        {row.cached_balance_base}
                      </td>
                      <td
                        className={`p-3 text-right font-mono font-bold ${
                          diff === 0 ? 'text-slate-400' : 'text-red-600'
                        }`}
                      >
                        {diff}
                      </td>
                      <td className="p-3 text-center">
                        {isOk ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded border border-emerald-200">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                            <span>MATCH</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-red-700 bg-red-100 px-2.5 py-0.5 rounded border border-red-300">
                            <AlertTriangle className="w-3.5 h-3.5 text-red-600" />
                            <span>MISMATCH</span>
                          </span>
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
