import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  apiGetReportData,
  apiDownloadReport,
  paiseToRs,
} from '../../services/api';
import {
  BarChart3,
  Download,
  Calendar,
  FileSpreadsheet,
  FileText,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react';

interface ReportOption {
  id: string;
  name: string;
  desc: string;
}

export const Reports: React.FC = () => {
  const { role } = useAuth();
  const isProduction = role === 'production';

  const reportOptions: ReportOption[] = isProduction
    ? [
        {
          id: 'production',
          name: 'Production & Costing Report',
          desc: 'Planned vs actual issues, output yields, variance flags & packet unit cost',
        },
      ]
    : [
        {
          id: 'sales-register',
          name: 'Sales Register',
          desc: 'Chronological list of all B2B outward GST tax invoices',
        },
        {
          id: 'customer-sales',
          name: 'Customer-wise Sales',
          desc: 'Sales aggregation by customer accounts and volume',
        },
        {
          id: 'product-sales',
          name: 'Product-wise Sales',
          desc: 'Quantities and revenues generated per product SKU',
        },
        {
          id: 'gst-summary',
          name: 'GST Summary (GSTR-1 & 3B)',
          desc: 'B2B table, CGST/SGST/IGST breakdown, HSN summary & 3.1(a) tax totals',
        },
        {
          id: 'purchase-register',
          name: 'Purchase Register',
          desc: 'Inward raw and packaging material receipts with vendor rates',
        },
        {
          id: 'stock-summary',
          name: 'Inventory Valuation Report',
          desc: 'Closing stock by category and weighted average valuation',
        },
        {
          id: 'production',
          name: 'Production & Variance Report',
          desc: 'Batch runs, BOM issues, variance flags, yield & packet cost',
        },
        {
          id: 'outstanding',
          name: 'Customer Outstanding & Ageing',
          desc: 'Accounts receivable ledger with 0-30, 31-60, 61-90, 90+ days ageing',
        },
      ];

  const [selectedReport, setSelectedReport] = useState<string>(reportOptions[0].id);
  const [fromDate, setFromDate] = useState<string>('');
  const [toDate, setToDate] = useState<string>('');
  const [reportData, setReportData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchReport = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await apiGetReportData(selectedReport, fromDate || undefined, toDate || undefined);
      setReportData(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to generate report');
      setReportData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [selectedReport]);

  const handleExport = async (format: 'csv' | 'xlsx' | 'pdf') => {
    setExporting(format);
    try {
      await apiDownloadReport(selectedReport, format, fromDate || undefined, toDate || undefined);
    } catch (err: any) {
      alert(`Export failed: ${err.message}`);
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Statutory & Operational Reports</h1>
          <p className="text-sm text-slate-500">
            Auditor-ready reports with one-click export to CSV, Excel (XLSX), and PDF
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleExport('csv')}
            disabled={exporting !== null}
            className="btn-secondary text-xs"
            title="Export as CSV"
          >
            <Download className="w-3.5 h-3.5" />
            <span>{exporting === 'csv' ? 'Exporting...' : 'Export CSV'}</span>
          </button>
          <button
            onClick={() => handleExport('xlsx')}
            disabled={exporting !== null}
            className="btn-secondary text-xs"
            title="Export as Excel"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
            <span>{exporting === 'xlsx' ? 'Exporting...' : 'Export XLSX'}</span>
          </button>
          <button
            onClick={() => handleExport('pdf')}
            disabled={exporting !== null}
            className="btn-secondary text-xs"
            title="Export as PDF"
          >
            <FileText className="w-3.5 h-3.5 text-red-600" />
            <span>{exporting === 'pdf' ? 'Exporting...' : 'Export PDF'}</span>
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-800 rounded-xl text-sm flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-600" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Report Selector & Date Filter */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm grid grid-cols-1 sm:grid-cols-12 gap-4 items-end">
        <div className="sm:col-span-5">
          <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
            Select Report Type
          </label>
          <select
            value={selectedReport}
            onChange={(e) => setSelectedReport(e.target.value)}
            className="w-full p-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm font-bold text-slate-900"
          >
            {reportOptions.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.name}
              </option>
            ))}
          </select>
        </div>

        <div className="sm:col-span-3">
          <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
            From Date
          </label>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="w-full p-2 bg-slate-50 border rounded-lg text-xs"
          />
        </div>

        <div className="sm:col-span-3">
          <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
            To Date
          </label>
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="w-full p-2 bg-slate-50 border rounded-lg text-xs"
          />
        </div>

        <div className="sm:col-span-1">
          <button onClick={fetchReport} className="btn-primary w-full text-xs py-2.5">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Report Data Preview Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden p-4">
        {loading ? (
          <div className="p-12 text-center text-slate-400">Loading report data...</div>
        ) : !reportData ? (
          <div className="p-12 text-center text-slate-400">No data available for this report</div>
        ) : (
          <div className="space-y-4">
            <div className="flex justify-between items-center pb-2 border-b border-slate-100">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  {reportData.report_name || reportData.title || selectedReport}
                </h3>
                <p className="text-xs text-slate-500">
                  Generated {new Date().toLocaleDateString()}
                </p>
              </div>
              {reportData.summary && (
                <div className="text-right text-xs">
                  {Object.entries(reportData.summary).map(([k, v]) => (
                    <span key={k} className="ml-3 font-semibold text-slate-700">
                      {k}: <span className="font-extrabold text-blue-900">{String(v)}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Render Rows if present */}
            {reportData.rows && Array.isArray(reportData.rows) && reportData.rows.length > 0 ? (
              <div className="overflow-x-auto max-h-[500px]">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200 sticky top-0">
                    <tr>
                      {Object.keys(reportData.rows[0])
                        .filter((k) => !k.endsWith('_paise') && !k.endsWith('_id'))
                        .map((k) => (
                          <th key={k} className="p-2.5 capitalize whitespace-nowrap">
                            {k.replace(/_/g, ' ')}
                          </th>
                        ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {reportData.rows.map((row: any, idx: number) => (
                      <tr key={idx} className="hover:bg-slate-50">
                        {Object.entries(row)
                          .filter(([k]) => !k.endsWith('_paise') && !k.endsWith('_id'))
                          .map(([k, v], cellIdx) => (
                            <td key={cellIdx} className="p-2.5 whitespace-nowrap text-slate-800">
                              {typeof v === 'boolean'
                                ? v ? 'YES' : 'NO'
                                : typeof v === 'number' && (k.includes('price') || k.includes('rs') || k.includes('total') || k.includes('amount'))
                                ? `₹${v.toFixed(2)}`
                                : String(v ?? '—')}
                            </td>
                          ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : reportData.invoices && Array.isArray(reportData.invoices) ? (
              /* GST Summary shape */
              <div className="space-y-4">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
                      <tr>
                        <th className="p-2.5">Invoice No</th>
                        <th className="p-2.5">Date</th>
                        <th className="p-2.5">Customer</th>
                        <th className="p-2.5">GSTIN</th>
                        <th className="p-2.5 text-right">Taxable</th>
                        <th className="p-2.5 text-right">CGST</th>
                        <th className="p-2.5 text-right">SGST</th>
                        <th className="p-2.5 text-right">IGST</th>
                        <th className="p-2.5 text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {reportData.invoices.map((inv: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50">
                          <td className="p-2.5 font-mono font-bold text-blue-700">{inv.invoice_no}</td>
                          <td className="p-2.5">{inv.invoice_date}</td>
                          <td className="p-2.5 font-bold">{inv.customer_name}</td>
                          <td className="p-2.5 font-mono text-slate-400">{inv.customer_gstin || 'Unregistered'}</td>
                          <td className="p-2.5 text-right">₹{inv.taxable_rs.toFixed(2)}</td>
                          <td className="p-2.5 text-right">₹{inv.cgst_rs.toFixed(2)}</td>
                          <td className="p-2.5 text-right">₹{inv.sgst_rs.toFixed(2)}</td>
                          <td className="p-2.5 text-right">₹{inv.igst_rs.toFixed(2)}</td>
                          <td className="p-2.5 text-right font-bold">₹{inv.total_rs.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {reportData.gstr_3b_totals && (
                  <div className="bg-blue-50 p-4 rounded-xl border border-blue-200 text-xs">
                    <div className="font-bold text-blue-900 mb-2">GSTR-3B Table 3.1(a) Outward Taxable Supplies Summary:</div>
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                      <div>Taxable: <b>₹{reportData.gstr_3b_totals.total_taxable_rs.toFixed(2)}</b></div>
                      <div>CGST: <b>₹{reportData.gstr_3b_totals.total_cgst_rs.toFixed(2)}</b></div>
                      <div>SGST: <b>₹{reportData.gstr_3b_totals.total_sgst_rs.toFixed(2)}</b></div>
                      <div>IGST: <b>₹{reportData.gstr_3b_totals.total_igst_rs.toFixed(2)}</b></div>
                      <div>Total Tax: <b>₹{reportData.gstr_3b_totals.total_tax_rs.toFixed(2)}</b></div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <pre className="p-4 bg-slate-50 rounded-lg text-xs overflow-x-auto text-slate-700">
                {JSON.stringify(reportData, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
