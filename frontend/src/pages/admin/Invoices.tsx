import React, { useState, useEffect } from 'react';
import { Invoice } from '../../types';
import {
  apiGetInvoices,
  apiDownloadInvoicePdf,
  apiDispatchInvoice,
  apiCancelInvoice,
  paiseToRs,
} from '../../services/api';
import { StatusChip } from '../../components/StatusChip';
import {
  FileText,
  Download,
  Share2,
  Mail,
  Truck,
  Ban,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';

export const Invoices: React.FC = () => {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);

  // Modals
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadInvoices = async () => {
    setLoading(true);
    try {
      const data = await apiGetInvoices();
      setInvoices(data);
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Failed to load invoices' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInvoices();
  }, []);

  const handleDownloadPdf = async (inv: Invoice) => {
    try {
      await apiDownloadInvoicePdf(inv.id, inv.invoice_no);
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Failed to download PDF' });
    }
  };

  const handleDispatch = async (inv: Invoice) => {
    if (!window.confirm(`Confirm dispatch for ${inv.invoice_no}? Finished goods stock will be relieved.`)) {
      return;
    }
    setActionLoading(true);
    try {
      await apiDispatchInvoice(inv.id);
      setFeedbackMsg({ type: 'success', text: `Invoice ${inv.invoice_no} dispatched! Stock updated.` });
      await loadInvoices();
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Dispatch failed' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancelInvoice = async () => {
    if (!selectedInvoice || !cancelReason.trim()) return;
    setActionLoading(true);
    try {
      const cn = await apiCancelInvoice(selectedInvoice.id, cancelReason.trim());
      setShowCancelModal(false);
      setCancelReason('');
      setFeedbackMsg({
        type: 'success',
        text: `Invoice cancelled. Credit Note ${cn.cn_no} generated and stock restored if dispatched.`,
      });
      await loadInvoices();
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Invoice cancellation failed' });
    } finally {
      setActionLoading(false);
    }
  };

  const filteredInvoices = statusFilter === 'ALL'
    ? invoices
    : invoices.filter((i) => i.status === statusFilter);

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">GST Tax Invoices & Dispatch</h1>
          <p className="text-sm text-slate-500">
            GST compliance, PDF documents, WhatsApp sharing & dispatch stock relief
          </p>
        </div>
        <button onClick={loadInvoices} className="btn-secondary self-start">
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

      {/* Filter Tabs */}
      <div className="flex gap-2">
        {['ALL', 'POSTED', 'CANCELLED'].map((st) => (
          <button
            key={st}
            onClick={() => setStatusFilter(st)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
              statusFilter === st
                ? 'bg-blue-700 text-white shadow-sm'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
            }`}
          >
            {st}
          </button>
        ))}
      </div>

      {/* Invoices Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
              <tr>
                <th className="p-3">Invoice No</th>
                <th className="p-3">Date</th>
                <th className="p-3">Customer</th>
                <th className="p-3">Place of Supply</th>
                <th className="p-3 text-right">Taxable</th>
                <th className="p-3 text-right">CGST</th>
                <th className="p-3 text-right">SGST</th>
                <th className="p-3 text-right">IGST</th>
                <th className="p-3 text-right">Total</th>
                <th className="p-3 text-center">Dispatch</th>
                <th className="p-3 text-center">Status</th>
                <th className="p-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredInvoices.length === 0 ? (
                <tr>
                  <td colSpan={12} className="p-8 text-center text-slate-400">
                    No invoices matching filter
                  </td>
                </tr>
              ) : (
                filteredInvoices.map((inv) => {
                  const isDispatched = !!inv.dispatched_at;
                  const isCancelled = inv.status === 'CANCELLED';

                  return (
                    <tr key={inv.id} className="hover:bg-slate-50">
                      <td className="p-3 font-mono font-bold text-blue-700">
                        {inv.invoice_no}
                      </td>
                      <td className="p-3 text-slate-600">{inv.invoice_date}</td>
                      <td className="p-3">
                        <div className="font-bold text-slate-900">{inv.customer_name}</div>
                        <div className="text-[11px] text-slate-400 font-mono">
                          {inv.customer_gstin || 'Unregistered'}
                        </div>
                      </td>
                      <td className="p-3 text-slate-600">
                        {inv.place_of_supply} ({inv.supply_type})
                      </td>
                      <td className="p-3 text-right font-medium">
                        {paiseToRs(inv.taxable_paise)}
                      </td>
                      <td className="p-3 text-right text-slate-600">
                        {paiseToRs(inv.cgst_paise)}
                      </td>
                      <td className="p-3 text-right text-slate-600">
                        {paiseToRs(inv.sgst_paise)}
                      </td>
                      <td className="p-3 text-right text-slate-600">
                        {paiseToRs(inv.igst_paise)}
                      </td>
                      <td className="p-3 text-right font-extrabold text-slate-900 text-sm">
                        {paiseToRs(inv.total_paise)}
                      </td>
                      <td className="p-3 text-center">
                        {isDispatched ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                            <Truck className="w-3 h-3" />
                            <span>Dispatched</span>
                          </span>
                        ) : isCancelled ? (
                          <span className="text-[11px] text-slate-400">—</span>
                        ) : (
                          <button
                            onClick={() => handleDispatch(inv)}
                            disabled={actionLoading}
                            className="btn-primary text-[11px] px-2 py-1"
                            title="Relieve Finished Goods Stock"
                          >
                            <Truck className="w-3 h-3" />
                            <span>Dispatch</span>
                          </button>
                        )}
                      </td>
                      <td className="p-3 text-center">
                        <StatusChip status={inv.status} />
                        {inv.credit_note_no && (
                          <div className="text-[10px] text-red-600 font-mono mt-0.5">
                            CN: {inv.credit_note_no}
                          </div>
                        )}
                      </td>
                      <td className="p-3 text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          {/* PDF Download */}
                          <button
                            onClick={() => handleDownloadPdf(inv)}
                            className="p-1.5 rounded hover:bg-slate-200 text-slate-700"
                            title="Download PDF"
                          >
                            <Download className="w-4 h-4" />
                          </button>

                          {/* WhatsApp Share Link */}
                          {inv.whatsapp_url && (
                            <a
                              href={inv.whatsapp_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="p-1.5 rounded hover:bg-emerald-100 text-emerald-700"
                              title="Share on WhatsApp"
                            >
                              <Share2 className="w-4 h-4" />
                            </a>
                          )}

                          {/* Mailto Link */}
                          {inv.mailto_url && (
                            <a
                              href={inv.mailto_url}
                              className="p-1.5 rounded hover:bg-blue-100 text-blue-700"
                              title="Send Email"
                            >
                              <Mail className="w-4 h-4" />
                            </a>
                          )}

                          {/* Cancel (Credit Note) */}
                          {!isCancelled && (
                            <button
                              onClick={() => {
                                setSelectedInvoice(inv);
                                setShowCancelModal(true);
                              }}
                              className="p-1.5 rounded hover:bg-red-100 text-red-600"
                              title="Cancel & Issue Credit Note"
                            >
                              <Ban className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Cancel & Credit Note Modal */}
      {showCancelModal && selectedInvoice && (
        <div className="fixed inset-0 bg-slate-900/60 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-slate-900">
              Cancel Invoice & Issue Credit Note
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              Cancelling <span className="font-mono font-bold text-slate-800">{selectedInvoice.invoice_no}</span> will issue an official GST Credit Note, reverse tax liabilities, and restore finished goods into stock if already dispatched.
            </p>
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Reason for Cancellation
              </label>
              <textarea
                rows={3}
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="e.g. Goods damaged in transit, order cancelled by buyer..."
                className="w-full p-2.5 text-sm border rounded-lg focus:ring-2 focus:ring-red-500 focus:outline-none"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowCancelModal(false)}
                className="btn-secondary text-xs"
              >
                Dismiss
              </button>
              <button
                onClick={handleCancelInvoice}
                disabled={!cancelReason.trim() || actionLoading}
                className="btn-danger text-xs"
              >
                Confirm Cancellation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
