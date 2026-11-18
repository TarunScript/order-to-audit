import React, { useState, useEffect } from 'react';
import { Item, Supplier } from '../../types';
import {
  apiGetSuppliers,
  apiGetItems,
  apiGetPurchases,
  apiCreatePurchase,
  paiseToRs,
  rsToPaise,
} from '../../services/api';
import {
  Truck,
  PlusCircle,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Plus,
  Trash2,
} from 'lucide-react';

interface PurchaseLineForm {
  item_id: number;
  qty: string;
  rate: string;
}

export const Purchases: React.FC = () => {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [rawItems, setRawItems] = useState<Item[]>([]);
  const [purchases, setPurchases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Form State
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | ''>('');
  const [billNo, setBillNo] = useState('');
  const [purchaseDate, setPurchaseDate] = useState(new Date().toISOString().split('T')[0]);
  const [lines, setLines] = useState<PurchaseLineForm[]>([
    { item_id: 1, qty: '60', rate: '45.00' }, // Benchmark default (60 kg flour @ ₹45/kg)
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [sList, iList, pList] = await Promise.all([
        apiGetSuppliers(),
        apiGetItems(),
        apiGetPurchases(),
      ]);
      setSuppliers(sList);
      const rawAndPkg = iList.filter((i) => i.type === 'RAW' || i.type === 'PACKAGING');
      setRawItems(rawAndPkg);
      setPurchases(pList);

      if (sList.length > 0 && !selectedSupplierId) {
        setSelectedSupplierId(sList[0].id);
      }
      if (rawAndPkg.length > 0 && lines[0].item_id === 1) {
        setLines([{ item_id: rawAndPkg[0].id, qty: '60', rate: '45.00' }]);
      }
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Failed to load purchase data' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const addLine = () => {
    if (rawItems.length === 0) return;
    setLines([...lines, { item_id: rawItems[0].id, qty: '1', rate: '10.00' }]);
  };

  const removeLine = (idx: number) => {
    if (lines.length === 1) return;
    setLines(lines.filter((_, i) => i !== idx));
  };

  const updateLine = (idx: number, field: keyof PurchaseLineForm, val: any) => {
    setLines(lines.map((l, i) => (i === idx ? { ...l, [field]: val } : l)));
  };

  const handleCreatePurchase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSupplierId) {
      setFeedbackMsg({ type: 'error', text: 'Please select a supplier' });
      return;
    }

    setSubmitting(true);
    setFeedbackMsg(null);
    try {
      await apiCreatePurchase({
        supplier_id: Number(selectedSupplierId),
        bill_no: billNo.trim() || undefined,
        purchase_date: purchaseDate,
        lines: lines.map((l) => ({
          item_id: l.item_id,
          qty: parseFloat(l.qty) || 0,
          rate_rupees_per_display_unit: parseFloat(l.rate) || 0,
        })),
      });

      setFeedbackMsg({
        type: 'success',
        text: 'Purchase posted! Raw material inventory and moving WAC successfully updated.',
      });
      setBillNo('');
      await loadData();
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Purchase posting failed' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Raw Material Purchases</h1>
          <p className="text-sm text-slate-500">
            Supplier inward receipts and moving Weighted Average Cost (WAC) valuation
          </p>
        </div>
        <button onClick={loadData} className="btn-secondary self-start">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
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

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Purchase Entry Form */}
        <div className="lg:col-span-6 bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4 pb-3 border-b border-slate-100">
            <PlusCircle className="w-5 h-5 text-blue-600" />
            <h2 className="text-base font-bold text-slate-900">New Purchase Receipt</h2>
          </div>

          <form onSubmit={handleCreatePurchase} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="sm:col-span-2">
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Supplier *
                </label>
                <select
                  value={selectedSupplierId}
                  onChange={(e) => setSelectedSupplierId(Number(e.target.value))}
                  className="w-full p-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm"
                >
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Bill / Invoice No
                </label>
                <input
                  type="text"
                  placeholder="e.g. MAT-9812"
                  value={billNo}
                  onChange={(e) => setBillNo(e.target.value)}
                  className="w-full p-2.5 border border-slate-300 rounded-lg text-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Purchase Date
              </label>
              <input
                type="date"
                value={purchaseDate}
                onChange={(e) => setPurchaseDate(e.target.value)}
                className="w-full p-2.5 border border-slate-300 rounded-lg text-sm"
              />
            </div>

            {/* Line Items */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-xs font-bold text-slate-700 uppercase">
                  Material Lines
                </label>
                <button
                  type="button"
                  onClick={addLine}
                  className="text-xs text-blue-600 font-bold hover:underline flex items-center gap-1"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add Line</span>
                </button>
              </div>

              <div className="space-y-2">
                {lines.map((l, idx) => {
                  const item = rawItems.find((i) => i.id === l.item_id);
                  const displayUnit = item ? item.display_unit : 'unit';

                  return (
                    <div
                      key={idx}
                      className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex flex-col sm:flex-row items-center gap-2"
                    >
                      <select
                        value={l.item_id}
                        onChange={(e) => updateLine(idx, 'item_id', Number(e.target.value))}
                        className="w-full sm:w-1/2 p-2 bg-white border border-slate-300 rounded text-xs font-bold"
                      >
                        {rawItems.map((ri) => (
                          <option key={ri.id} value={ri.id}>
                            {ri.name} ({ri.sku}) [{ri.display_unit}]
                          </option>
                        ))}
                      </select>

                      <div className="flex items-center gap-1 w-full sm:w-1/4">
                        <input
                          type="number"
                          step="any"
                          min="0.01"
                          required
                          placeholder="Qty"
                          value={l.qty}
                          onChange={(e) => updateLine(idx, 'qty', e.target.value)}
                          className="w-full p-2 bg-white border border-slate-300 rounded text-xs font-bold text-right"
                        />
                        <span className="text-xs text-slate-500 w-8">{displayUnit}</span>
                      </div>

                      <div className="flex items-center gap-1 w-full sm:w-1/4">
                        <span className="text-xs text-slate-500">₹</span>
                        <input
                          type="number"
                          step="0.01"
                          min="0.01"
                          required
                          placeholder="Rate"
                          value={l.rate}
                          onChange={(e) => updateLine(idx, 'rate', e.target.value)}
                          className="w-full p-2 bg-white border border-slate-300 rounded text-xs font-bold text-right"
                        />
                        <span className="text-[11px] text-slate-400">/{displayUnit}</span>
                      </div>

                      {lines.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeLine(idx)}
                          className="text-red-500 hover:text-red-700 p-1"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full btn-primary text-sm py-2.5 mt-2"
            >
              <Truck className="w-4 h-4" />
              <span>{submitting ? 'Posting Purchase...' : 'Post Purchase Receipt'}</span>
            </button>
          </form>
        </div>

        {/* Right: Recent Purchases History */}
        <div className="lg:col-span-6 bg-white rounded-xl border border-slate-200 shadow-sm p-6 overflow-hidden">
          <h2 className="text-base font-bold text-slate-900 mb-4 pb-3 border-b border-slate-100">
            Recent Purchases History
          </h2>

          <div className="divide-y divide-slate-100 max-h-[600px] overflow-y-auto">
            {purchases.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">
                No purchases recorded yet
              </div>
            ) : (
              purchases.map((p) => (
                <div key={p.id} className="py-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-bold text-slate-900 text-sm">
                        {p.supplier_name}
                      </div>
                      <div className="text-xs text-slate-500">
                        Bill: <span className="font-mono">{p.bill_no || 'N/A'}</span> • Date: {p.purchase_date}
                      </div>
                    </div>
                    <span className="font-extrabold text-sm text-slate-900">
                      {paiseToRs(p.total_value_paise)}
                    </span>
                  </div>

                  <div className="mt-2 space-y-1">
                    {p.lines.map((l: any) => (
                      <div key={l.id} className="text-xs text-slate-600 flex justify-between bg-slate-50 px-2.5 py-1 rounded">
                        <span>
                          {l.item_name} ({l.qty_display} {l.display_unit})
                        </span>
                        <span>
                          @ {paiseToRs(l.rate_paise_per_display_unit)}/{l.display_unit} = <span className="font-semibold text-slate-800">{paiseToRs(l.value_paise)}</span>
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
