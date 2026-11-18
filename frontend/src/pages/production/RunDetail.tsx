import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ProductionRun } from '../../types';
import {
  apiGetProductionRun,
  apiUpdateOverheads,
  apiCancelProductionRun,
  paiseToRs,
  rsToPaise,
} from '../../services/api';
import { StatusChip } from '../../components/StatusChip';
import { VarianceBadge } from '../../components/VarianceBadge';
import {
  Layers,
  ArrowLeft,
  DollarSign,
  AlertTriangle,
  CheckCircle2,
  Edit2,
  Ban,
  Package,
} from 'lucide-react';

export const RunDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<ProductionRun | null>(null);
  const [loading, setLoading] = useState(true);

  // Edit Overheads Modal
  const [showOverheadsModal, setShowOverheadsModal] = useState(false);
  const [labourRs, setLabourRs] = useState('');
  const [powerGasRs, setPowerGasRs] = useState('');
  const [otherOverheadRs, setOtherOverheadRs] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadRun = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await apiGetProductionRun(Number(id));
      setRun(data);
      setLabourRs((data.labour_paise / 100).toFixed(2));
      setPowerGasRs((data.power_gas_paise / 100).toFixed(2));
      setOtherOverheadRs((data.other_overhead_paise / 100).toFixed(2));
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Failed to load run details' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRun();
  }, [id]);

  const handleSaveOverheads = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!run) return;
    setActionLoading(true);
    try {
      await apiUpdateOverheads(run.id, {
        labour_paise: rsToPaise(parseFloat(labourRs || '0')),
        power_gas_paise: rsToPaise(parseFloat(powerGasRs || '0')),
        other_overhead_paise: rsToPaise(parseFloat(otherOverheadRs || '0')),
      });
      setShowOverheadsModal(false);
      setFeedbackMsg({ type: 'success', text: 'Overheads updated and unit cost recomputed!' });
      await loadRun();
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Failed to update overheads' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancelRun = async () => {
    if (!run) return;
    if (!window.confirm('Are you sure you want to cancel this run? Reversal entries will be posted to restore issued stock and remove finished packets.')) {
      return;
    }
    setActionLoading(true);
    try {
      await apiCancelProductionRun(run.id, 'Cancelled by production supervisor');
      setFeedbackMsg({ type: 'success', text: 'Production run reversed in stock ledger!' });
      await loadRun();
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Cancellation failed' });
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return <div className="text-center py-12 text-slate-400">Loading production run...</div>;
  }

  if (!run) {
    return <div className="text-center py-12 text-slate-400">Production run not found</div>;
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link to="/production/runs" className="p-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-100">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-extrabold text-slate-900 font-mono">
                {run.run_no}
              </h1>
              <StatusChip status={run.status} />
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Run Date: <span className="font-semibold text-slate-800">{run.run_date}</span> | Product: <span className="font-semibold text-slate-800">{run.product_name}</span> ({run.product_sku})
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          {run.status === 'POSTED' && (
            <>
              <button
                onClick={() => setShowOverheadsModal(true)}
                className="btn-secondary text-xs"
              >
                <Edit2 className="w-3.5 h-3.5" />
                <span>Adjust Overheads</span>
              </button>
              <button
                onClick={handleCancelRun}
                disabled={actionLoading}
                className="btn-danger text-xs"
              >
                <Ban className="w-3.5 h-3.5" />
                <span>Cancel / Reverse Run</span>
              </button>
            </>
          )}
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

      {/* Costing & Unit Economics Cards (Section 11 Benchmark Verification) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs text-slate-500 font-medium">Material Cost</span>
          <div className="text-xl font-extrabold text-slate-900 mt-1">
            {paiseToRs(run.material_cost_paise)}
          </div>
          <span className="text-[11px] text-slate-400">At WAC issue valuation</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs text-slate-500 font-medium">Run Overheads</span>
          <div className="text-xl font-extrabold text-slate-900 mt-1">
            {paiseToRs(run.overheads_total_paise)}
          </div>
          <span className="text-[11px] text-slate-400">Labour + Power/Gas</span>
        </div>

        <div className="bg-blue-50/70 p-4 rounded-xl border border-blue-200 shadow-sm">
          <span className="text-xs text-blue-700 font-bold">Cost Per Packet</span>
          <div className="text-2xl font-black text-blue-900 mt-1">
            {paiseToRs(run.cost_per_packet_paise)}
          </div>
          <span className="text-[11px] text-blue-600">
            {run.actual_good_output} good packets
          </span>
        </div>

        <div className="bg-emerald-50/70 p-4 rounded-xl border border-emerald-200 shadow-sm">
          <span className="text-xs text-emerald-700 font-bold">Unit Margin</span>
          <div className="text-2xl font-black text-emerald-900 mt-1">
            {paiseToRs(run.margin_paise)}
          </div>
          <span className="text-[11px] text-emerald-600">
            vs {paiseToRs(run.selling_price_paise)} retail price
          </span>
        </div>
      </div>

      {/* Output Yield Summary */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">
            Output Yield & Packaging Wastage
          </h2>
          <VarianceBadge
            variancePct={run.yield_variance_pct}
            varianceBp={run.yield_variance_bp}
            flagged={run.yield_flagged}
          />
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-slate-500">Expected Yield</span>
            <div className="font-extrabold text-sm text-slate-800 mt-0.5">
              {run.expected_output} pkts
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-slate-500">Actual Good Output</span>
            <div className="font-extrabold text-sm text-slate-900 mt-0.5">
              {run.actual_good_output} pkts
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-slate-500">Damaged Pouches</span>
            <div className="font-extrabold text-sm text-red-600 mt-0.5">
              {run.damaged_pouches} pouches
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-slate-500">Cartons Used</span>
            <div className="font-extrabold text-sm text-slate-800 mt-0.5">
              {run.cartons_used ?? '—'} cartons
            </div>
          </div>
        </div>
      </div>

      {/* Planned vs Actual Consumption Table */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">
          Material & Packaging Issue Lines (Planned vs Actual)
        </h2>

        <div className="overflow-x-auto border border-slate-200 rounded-lg">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
              <tr>
                <th className="p-3">Item</th>
                <th className="p-3">Type</th>
                <th className="p-3 text-right">Planned (Display)</th>
                <th className="p-3 text-right">Actual Issued (Display)</th>
                <th className="p-3 text-right">Actual (Base Units)</th>
                <th className="p-3 text-right">Variance %</th>
                <th className="p-3 text-center">Tolerance Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {run.lines.map((l) => (
                <tr key={l.id} className={l.flagged ? 'bg-red-50/40' : 'hover:bg-slate-50'}>
                  <td className="p-3">
                    <div className="font-bold text-slate-900">{l.item_name}</div>
                    <div className="text-[11px] text-slate-400 font-mono">{l.sku}</div>
                  </td>
                  <td className="p-3 text-slate-600">{l.item_type}</td>
                  <td className="p-3 text-right text-slate-600 font-medium">
                    {l.planned_qty_display} {l.display_unit}
                  </td>
                  <td className="p-3 text-right font-extrabold text-slate-900">
                    {l.actual_qty_display} {l.display_unit}
                  </td>
                  <td className="p-3 text-right font-mono text-slate-500">
                    {l.actual_qty_base} {l.base_unit}
                  </td>
                  <td className="p-3 text-right">
                    <VarianceBadge
                      variancePct={l.variance_pct}
                      varianceBp={l.variance_bp}
                      flagged={l.flagged}
                    />
                  </td>
                  <td className="p-3 text-center">
                    {l.flagged ? (
                      <span className="text-[11px] font-bold text-red-700 bg-red-100 px-2 py-0.5 rounded border border-red-300">
                        FLAGGED (&gt; 3%)
                      </span>
                    ) : (
                      <span className="text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                        OK
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Overheads Modal */}
      {showOverheadsModal && (
        <div className="fixed inset-0 bg-slate-900/60 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-slate-900">
              Adjust Direct Production Overheads
            </h3>
            <p className="text-xs text-slate-500">
              This action will be audit-logged and will automatically recalculate the cost per packet.
            </p>

            <form onSubmit={handleSaveOverheads} className="space-y-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Labour Overheads (₹)
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={labourRs}
                  onChange={(e) => setLabourRs(e.target.value)}
                  className="w-full p-2 border rounded-lg text-sm font-bold"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Gas & Power (₹)
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={powerGasRs}
                  onChange={(e) => setPowerGasRs(e.target.value)}
                  className="w-full p-2 border rounded-lg text-sm font-bold"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Other Overheads (₹)
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={otherOverheadRs}
                  onChange={(e) => setOtherOverheadRs(e.target.value)}
                  className="w-full p-2 border rounded-lg text-sm font-bold"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowOverheadsModal(false)}
                  className="btn-secondary text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="btn-primary text-xs"
                >
                  Save & Recalculate
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
