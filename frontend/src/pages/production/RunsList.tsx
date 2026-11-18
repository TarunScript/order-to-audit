import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ProductionRun } from '../../types';
import { apiGetProductionRuns, paiseToRs } from '../../services/api';
import { StatusChip } from '../../components/StatusChip';
import { VarianceBadge } from '../../components/VarianceBadge';
import {
  Layers,
  PlusCircle,
  RefreshCw,
  AlertTriangle,
  Eye,
} from 'lucide-react';

export const RunsList: React.FC = () => {
  const [runs, setRuns] = useState<ProductionRun[]>([]);
  const [loading, setLoading] = useState(true);

  const loadRuns = async () => {
    setLoading(true);
    try {
      const data = await apiGetProductionRuns();
      setRuns(data);
    } catch (err) {
      console.error('Failed to load production runs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRuns();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Production Runs</h1>
          <p className="text-sm text-slate-500">
            Batch manufacturing, issue valuation, and packet unit costing
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadRuns} className="btn-secondary">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <Link to="/production/new-run" className="btn-primary">
            <PlusCircle className="w-4 h-4" />
            <span>New Run</span>
          </Link>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
              <tr>
                <th className="p-3">Run No</th>
                <th className="p-3">Date</th>
                <th className="p-3">Product</th>
                <th className="p-3 text-right">Good Output</th>
                <th className="p-3 text-right">Yield Variance</th>
                <th className="p-3 text-right">Material Cost</th>
                <th className="p-3 text-right">Overheads</th>
                <th className="p-3 text-right">Cost / Packet</th>
                <th className="p-3 text-right">Margin / Packet</th>
                <th className="p-3 text-center">Status</th>
                <th className="p-3 text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={11} className="p-8 text-center text-slate-400">
                    No production runs recorded
                  </td>
                </tr>
              ) : (
                runs.map((run) => (
                  <tr key={run.id} className="hover:bg-slate-50">
                    <td className="p-3 font-mono font-bold text-blue-700">
                      {run.run_no}
                    </td>
                    <td className="p-3 text-slate-600">{run.run_date}</td>
                    <td className="p-3">
                      <div className="font-bold text-slate-900">{run.product_name}</div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        {run.product_sku} (Factor: {run.batch_factor})
                      </div>
                    </td>
                    <td className="p-3 text-right font-extrabold text-slate-900">
                      {run.actual_good_output} pkts
                    </td>
                    <td className="p-3 text-right">
                      <VarianceBadge
                        variancePct={run.yield_variance_pct}
                        varianceBp={run.yield_variance_bp}
                        flagged={run.yield_flagged}
                      />
                    </td>
                    <td className="p-3 text-right font-medium">
                      {paiseToRs(run.material_cost_paise)}
                    </td>
                    <td className="p-3 text-right text-slate-600">
                      {paiseToRs(run.overheads_total_paise)}
                    </td>
                    <td className="p-3 text-right font-bold text-blue-800">
                      {paiseToRs(run.cost_per_packet_paise)}
                    </td>
                    <td className="p-3 text-right font-bold text-emerald-700">
                      {paiseToRs(run.margin_paise)}
                    </td>
                    <td className="p-3 text-center">
                      <StatusChip status={run.status} />
                    </td>
                    <td className="p-3 text-center">
                      <Link
                        to={`/production/runs/${run.id}`}
                        className="btn-secondary text-[11px] py-1 px-2.5 inline-flex"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>View</span>
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
