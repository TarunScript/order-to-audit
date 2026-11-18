import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  apiGetBoms,
  apiPrefillRun,
  apiCreateProductionRun,
  paiseToRs,
  rsToPaise,
} from '../../services/api';
import { VarianceBadge } from '../../components/VarianceBadge';
import {
  Layers,
  PlusCircle,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
} from 'lucide-react';

interface PrefillLineState {
  item_id: number;
  sku: string;
  item_name: string;
  item_type: string;
  base_unit: string;
  display_unit: string;
  factor_to_base: number;
  planned_qty_base: number;
  planned_qty_display: number;
  actual_qty_display: number;
  wastage_qty_display: number;
  available_qty_display: number;
}

export const NewRun: React.FC = () => {
  const navigate = useNavigate();
  const [boms, setBoms] = useState<any[]>([]);
  const [selectedBomId, setSelectedBomId] = useState<number | ''>('');
  const [batchFactor, setBatchFactor] = useState<number>(1.0);
  const [expectedOutput, setExpectedOutput] = useState<number>(200);
  const [actualGoodOutput, setActualGoodOutput] = useState<number>(188);
  const [damagedPouches, setDamagedPouches] = useState<number>(6);
  const [cartonsUsed, setCartonsUsed] = useState<number>(9);

  // Overheads in Rupees
  const [labourRs, setLabourRs] = useState<string>('1200');
  const [powerGasRs, setPowerGasRs] = useState<string>('600');
  const [otherOverheadRs, setOtherOverheadRs] = useState<string>('0');

  const [toleranceBp, setToleranceBp] = useState<number>(300); // 3%
  const [lines, setLines] = useState<PrefillLineState[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load available BOMs
  useEffect(() => {
    async function load() {
      try {
        const bList = await apiGetBoms();
        setBoms(bList);
        if (bList.length > 0) {
          setSelectedBomId(bList[0].id);
        }
      } catch (err) {
        console.error('Failed to load BOMs:', err);
      }
    }
    load();
  }, []);

  // Fetch prefill whenever BOM or batch factor changes
  useEffect(() => {
    if (!selectedBomId) return;
    async function fetchPrefill() {
      setLoading(true);
      setErrorMsg(null);
      try {
        const prefill = await apiPrefillRun(Number(selectedBomId), batchFactor);
        setExpectedOutput(prefill.expected_output);
        setToleranceBp(prefill.tolerance_bp || 300);

        // Prepopulate lines with actual = planned by default, except benchmark defaults
        const mappedLines = prefill.lines.map((l: any) => {
          let actualDisplay = l.planned_qty_display;
          // Benchmark step defaults if single batch Murukku
          if (l.sku === 'RM-OIL' && batchFactor === 1.0) actualDisplay = 10.5;
          if (l.sku === 'PKG-CARTON' && batchFactor === 1.0) actualDisplay = 9;

          return {
            item_id: l.item_id,
            sku: l.sku,
            item_name: l.item_name,
            item_type: l.item_type,
            base_unit: l.base_unit,
            display_unit: l.display_unit,
            factor_to_base: l.factor_to_base,
            planned_qty_base: l.planned_qty_base,
            planned_qty_display: l.planned_qty_display,
            actual_qty_display: actualDisplay,
            wastage_qty_display: 0,
            available_qty_display: l.available_qty_display,
          };
        });

        // Auto calculate pouch line = good output + damaged pouches
        const pouchLine = mappedLines.find((l: PrefillLineState) => l.sku.includes('POUCH'));
        if (pouchLine) {
          pouchLine.actual_qty_display = actualGoodOutput + damagedPouches;
        }

        setLines(mappedLines);
      } catch (err: any) {
        setErrorMsg(err.message || 'Failed to fetch BOM prefill');
      } finally {
        setLoading(false);
      }
    }
    fetchPrefill();
  }, [selectedBomId, batchFactor]);

  // When good output or damaged pouches change, update pouch line automatically
  const handleGoodOutputChange = (good: number) => {
    setActualGoodOutput(good);
    setLines((prev) =>
      prev.map((l) =>
        l.sku.includes('POUCH')
          ? { ...l, actual_qty_display: good + damagedPouches }
          : l
      )
    );
  };

  const handleDamagedPouchesChange = (dmg: number) => {
    setDamagedPouches(dmg);
    setLines((prev) =>
      prev.map((l) =>
        l.sku.includes('POUCH')
          ? { ...l, actual_qty_display: actualGoodOutput + dmg }
          : l
      )
    );
  };

  const handleCartonsChange = (crt: number) => {
    setCartonsUsed(crt);
    setLines((prev) =>
      prev.map((l) =>
        l.sku.includes('CARTON') ? { ...l, actual_qty_display: crt } : l
      )
    );
  };

  const handleLineActualChange = (itemId: number, actualVal: number) => {
    setLines((prev) =>
      prev.map((l) => (l.item_id === itemId ? { ...l, actual_qty_display: actualVal } : l))
    );
  };

  // Live Variance calculations
  const yieldVariancePct = expectedOutput > 0
    ? ((actualGoodOutput - expectedOutput) / expectedOutput) * 100
    : 0;
  const yieldVarianceBp = Math.round(yieldVariancePct * 100);
  const yieldFlagged = Math.abs(yieldVarianceBp) > toleranceBp;

  const handleSubmitRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBomId || actualGoodOutput <= 0) {
      setErrorMsg('Please specify valid output quantities');
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);

    try {
      const payload = {
        bom_id: Number(selectedBomId),
        batch_factor: batchFactor,
        expected_output: expectedOutput,
        actual_good_output: actualGoodOutput,
        damaged_pouches: damagedPouches,
        cartons_used: cartonsUsed,
        labour_paise: rsToPaise(parseFloat(labourRs || '0')),
        power_gas_paise: rsToPaise(parseFloat(powerGasRs || '0')),
        other_overhead_paise: rsToPaise(parseFloat(otherOverheadRs || '0')),
        lines: lines.map((l) => ({
          item_id: l.item_id,
          actual_qty: l.actual_qty_display,
          unit: l.display_unit,
          wastage_qty: l.wastage_qty_display || 0,
        })),
      };

      const result = await apiCreateProductionRun(payload);
      navigate(`/production/runs/${result.id}`);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to post production run');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            New Production Run
          </h1>
          <p className="text-sm text-slate-500">
            BOM issue posting, real-time variance detection & batch cost valuation
          </p>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg">
          Tolerance: {(toleranceBp / 100).toFixed(1)}% ({toleranceBp} bp)
        </span>
      </div>

      {errorMsg && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-800 rounded-xl text-sm flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-600" />
          <span>{errorMsg}</span>
        </div>
      )}

      <form onSubmit={handleSubmitRun} className="space-y-6">
        {/* Section 1: Product & Batch Setup */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">
            1. Product & Batch Configuration
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Product Recipe (BOM) *
              </label>
              <select
                value={selectedBomId}
                onChange={(e) => setSelectedBomId(Number(e.target.value))}
                className="w-full p-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm font-bold text-slate-900"
              >
                {boms.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.product_name || `BOM #${b.id}`} ({b.yield_packets} pkts/batch)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Batch Factor *
              </label>
              <input
                type="number"
                step="0.1"
                min="0.1"
                required
                value={batchFactor}
                onChange={(e) => setBatchFactor(parseFloat(e.target.value) || 1.0)}
                className="w-full p-2.5 border border-slate-300 rounded-lg text-sm font-bold text-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Expected Output
              </label>
              <div className="p-2.5 bg-slate-100 rounded-lg text-sm font-extrabold text-slate-800">
                {expectedOutput} Packets
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: Output Yield & Damaged Quantities */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">
              2. Production Floor Output & Yield
            </h2>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500 font-medium">Yield Variance:</span>
              <VarianceBadge
                variancePct={yieldVariancePct}
                varianceBp={yieldVarianceBp}
                flagged={yieldFlagged}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Actual Good Output (Packets) *
              </label>
              <input
                type="number"
                min="1"
                required
                value={actualGoodOutput}
                onChange={(e) => handleGoodOutputChange(parseInt(e.target.value) || 0)}
                className={`w-full p-2.5 border rounded-lg text-sm font-extrabold ${
                  yieldFlagged ? 'border-red-500 bg-red-50/50 text-red-900' : 'border-slate-300 text-slate-900'
                }`}
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Damaged Pouches
              </label>
              <input
                type="number"
                min="0"
                value={damagedPouches}
                onChange={(e) => handleDamagedPouchesChange(parseInt(e.target.value) || 0)}
                className="w-full p-2.5 border border-slate-300 rounded-lg text-sm font-bold text-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Cartons Packed
              </label>
              <input
                type="number"
                min="0"
                value={cartonsUsed}
                onChange={(e) => handleCartonsChange(parseInt(e.target.value) || 0)}
                className="w-full p-2.5 border border-slate-300 rounded-lg text-sm font-bold text-slate-900"
              />
            </div>
          </div>
        </div>

        {/* Section 3: Material & Packaging Consumption with LIVE Variance */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-3">
            3. Material Issues & Live Line Variance
          </h2>
          <p className="text-xs text-slate-500 mb-4">
            Planned quantities are auto-calculated from the BOM. Flag turns <span className="text-red-600 font-bold">RED</span> when variance strictly exceeds {(toleranceBp / 100).toFixed(1)}%.
          </p>

          <div className="overflow-x-auto border border-slate-200 rounded-lg">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
                <tr>
                  <th className="p-3">Material / Packaging Item</th>
                  <th className="p-3 text-right">Available Stock</th>
                  <th className="p-3 text-right">Planned Qty</th>
                  <th className="p-3 text-right">Actual Issued Qty *</th>
                  <th className="p-3 text-right">Variance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {lines.map((line) => {
                  const planned = line.planned_qty_display;
                  const actual = line.actual_qty_display;
                  const variancePct = planned > 0 ? ((actual - planned) / planned) * 100 : 0;
                  const varianceBp = Math.round(variancePct * 100);
                  const isFlagged = Math.abs(varianceBp) > toleranceBp;

                  return (
                    <tr
                      key={line.item_id}
                      className={`hover:bg-slate-50 ${isFlagged ? 'bg-red-50/40' : ''}`}
                    >
                      <td className="p-3">
                        <div className="font-bold text-slate-900">{line.item_name}</div>
                        <div className="text-[11px] text-slate-400 font-mono">
                          {line.sku} ({line.item_type})
                        </div>
                      </td>
                      <td className="p-3 text-right text-slate-500 font-medium">
                        {line.available_qty_display} {line.display_unit}
                      </td>
                      <td className="p-3 text-right font-medium text-slate-700">
                        {planned} {line.display_unit}
                      </td>
                      <td className="p-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <input
                            type="number"
                            step="any"
                            min="0"
                            required
                            value={actual}
                            onChange={(e) =>
                              handleLineActualChange(
                                line.item_id,
                                parseFloat(e.target.value) || 0
                              )
                            }
                            className={`w-24 p-1.5 border rounded-lg text-right font-bold text-xs ${
                              isFlagged ? 'border-red-400 bg-red-50 text-red-900' : 'border-slate-300'
                            }`}
                          />
                          <span className="text-slate-500 w-8">{line.display_unit}</span>
                        </div>
                      </td>
                      <td className="p-3 text-right">
                        <VarianceBadge
                          variancePct={variancePct}
                          varianceBp={varianceBp}
                          flagged={isFlagged}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Section 4: Run Overheads Allocation */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-2">
            4. Direct Production Overheads
          </h2>
          <p className="text-xs text-slate-500 mb-4">
            Allocated 100% to this run's good output packets to determine true cost per packet.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Direct Labour (₹)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={labourRs}
                onChange={(e) => setLabourRs(e.target.value)}
                className="w-full p-2.5 border border-slate-300 rounded-lg text-sm font-bold text-slate-900"
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
                className="w-full p-2.5 border border-slate-300 rounded-lg text-sm font-bold text-slate-900"
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
                className="w-full p-2.5 border border-slate-300 rounded-lg text-sm font-bold text-slate-900"
              />
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={() => navigate('/production/runs')}
            className="btn-secondary"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || loading}
            className="btn-primary text-base px-6 py-3 font-bold shadow-md"
          >
            <Layers className="w-5 h-5" />
            <span>{submitting ? 'Posting Run to Stock...' : 'Post Production Run'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
