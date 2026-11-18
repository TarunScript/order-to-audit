import React, { useState, useEffect } from 'react';
import { Customer, CustomerOutstanding, Invoice } from '../../types';
import {
  apiGetCustomers,
  apiGetInvoices,
  apiCreatePayment,
  apiGetCustomerOutstanding,
  paiseToRs,
  rsToPaise,
} from '../../services/api';
import {
  DollarSign,
  PlusCircle,
  Clock,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  TrendingDown,
} from 'lucide-react';

export const Payments: React.FC = () => {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [outstandingList, setOutstandingList] = useState<CustomerOutstanding[]>([]);
  const [loading, setLoading] = useState(true);

  // Form State
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | ''>('');
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<number | ''>('');
  const [amountRupees, setAmountRupees] = useState('');
  const [paymentMode, setPaymentMode] = useState('NEFT');
  const [reference, setReference] = useState('');
  const [receivedDate, setReceivedDate] = useState(new Date().toISOString().split('T')[0]);
  const [submitting, setSubmitting] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [custList, invList] = await Promise.all([
        apiGetCustomers(),
        apiGetInvoices(),
      ]);
      setCustomers(custList);
      setInvoices(invList.filter((i) => i.status === 'POSTED'));

      if (custList.length > 0 && !selectedCustomerId) {
        setSelectedCustomerId(custList[0].id);
      }

      // Fetch outstanding for each customer
      const outstandings = await Promise.all(
        custList.map((c) => apiGetCustomerOutstanding(c.id).catch(() => null))
      );
      setOutstandingList(outstandings.filter(Boolean) as CustomerOutstanding[]);
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Failed to load payments data' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRecordPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustomerId || !amountRupees || parseFloat(amountRupees) <= 0) {
      setFeedbackMsg({ type: 'error', text: 'Valid customer and payment amount are required' });
      return;
    }

    setSubmitting(true);
    setFeedbackMsg(null);
    try {
      await apiCreatePayment({
        customer_id: Number(selectedCustomerId),
        invoice_id: selectedInvoiceId ? Number(selectedInvoiceId) : undefined,
        amount_paise: rsToPaise(parseFloat(amountRupees)),
        mode: paymentMode,
        reference: reference.trim() || undefined,
        received_on: receivedDate,
      });

      setFeedbackMsg({
        type: 'success',
        text: `Payment of ₹${parseFloat(amountRupees).toFixed(2)} recorded successfully!`,
      });
      setAmountRupees('');
      setReference('');
      await loadData();
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Failed to record payment' });
    } finally {
      setSubmitting(false);
    }
  };

  const customerInvoices = invoices.filter(
    (i) => i.customer_id === Number(selectedCustomerId)
  );

  const grandTotalOutstandingRs = outstandingList.reduce(
    (acc, c) => acc + c.outstanding_rs,
    0
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Payments & Customer Ageing</h1>
          <p className="text-sm text-slate-500">
            Record collections, track receivables, and analyze overdue ageing buckets
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

      {/* Top Cards: Total Outstanding Overview */}
      <div className="bg-gradient-to-r from-blue-800 to-indigo-900 text-white rounded-2xl p-6 shadow-md flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <span className="text-xs uppercase tracking-wider text-blue-200 font-bold">
            Total Market Receivables
          </span>
          <div className="text-3xl font-extrabold mt-1">
            ₹{grandTotalOutstandingRs.toFixed(2)}
          </div>
          <p className="text-xs text-blue-200 mt-1">
            Net of all tax invoices, credit notes, and realized customer payments
          </p>
        </div>
        <TrendingDown className="w-12 h-12 text-blue-300 opacity-70" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Record Payment Form */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4 pb-3 border-b border-slate-100">
            <PlusCircle className="w-5 h-5 text-blue-600" />
            <h2 className="text-base font-bold text-slate-900">Record New Payment</h2>
          </div>

          <form onSubmit={handleRecordPayment} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Customer *
              </label>
              <select
                value={selectedCustomerId}
                onChange={(e) => setSelectedCustomerId(Number(e.target.value))}
                className="w-full p-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm font-medium"
              >
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.type})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Link to Invoice (Optional)
              </label>
              <select
                value={selectedInvoiceId}
                onChange={(e) => setSelectedInvoiceId(e.target.value ? Number(e.target.value) : '')}
                className="w-full p-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm"
              >
                <option value="">On Account / General Receipt</option>
                {customerInvoices.map((inv) => (
                  <option key={inv.id} value={inv.id}>
                    {inv.invoice_no} ({inv.invoice_date}) - {paiseToRs(inv.total_paise)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Amount Received (₹) *
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                placeholder="e.g. 4000.00"
                value={amountRupees}
                onChange={(e) => setAmountRupees(e.target.value)}
                className="w-full p-2.5 border border-slate-300 rounded-lg text-sm font-bold text-slate-900 focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Payment Mode
                </label>
                <select
                  value={paymentMode}
                  onChange={(e) => setPaymentMode(e.target.value)}
                  className="w-full p-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm"
                >
                  <option value="NEFT">NEFT / RTGS</option>
                  <option value="UPI">UPI</option>
                  <option value="CHEQUE">Cheque</option>
                  <option value="CASH">Cash</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Date Received
                </label>
                <input
                  type="date"
                  value={receivedDate}
                  onChange={(e) => setReceivedDate(e.target.value)}
                  className="w-full p-2.5 border border-slate-300 rounded-lg text-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Reference / UTR / Cheque No.
              </label>
              <input
                type="text"
                placeholder="e.g. UTR12345678"
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                className="w-full p-2.5 border border-slate-300 rounded-lg text-sm"
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full btn-primary text-sm py-2.5 mt-2"
            >
              <DollarSign className="w-4 h-4" />
              <span>{submitting ? 'Recording...' : 'Record Payment'}</span>
            </button>
          </form>
        </div>

        {/* Right: Customer Outstanding with Ageing */}
        <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200 shadow-sm p-6 overflow-hidden">
          <div className="flex items-center gap-2 mb-4 pb-3 border-b border-slate-100">
            <Clock className="w-5 h-5 text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">Customer Outstanding & Ageing Analysis</h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
                <tr>
                  <th className="p-2.5">Customer</th>
                  <th className="p-2.5 text-right">Invoiced</th>
                  <th className="p-2.5 text-right">Paid</th>
                  <th className="p-2.5 text-right">Outstanding</th>
                  <th className="p-2.5 text-right">0-30d</th>
                  <th className="p-2.5 text-right">31-60d</th>
                  <th className="p-2.5 text-right">61-90d</th>
                  <th className="p-2.5 text-right">90+d</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {outstandingList.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-6 text-center text-slate-400">
                      No customer outstanding data
                    </td>
                  </tr>
                ) : (
                  outstandingList.map((item) => (
                    <tr key={item.customer_id} className="hover:bg-slate-50">
                      <td className="p-2.5">
                        <div className="font-bold text-slate-900">{item.customer_name}</div>
                        <div className="text-[11px] text-slate-400 font-mono">
                          Credit: {item.credit_days} days
                        </div>
                      </td>
                      <td className="p-2.5 text-right text-slate-600">
                        ₹{item.invoiced_rs.toFixed(2)}
                      </td>
                      <td className="p-2.5 text-right text-emerald-600 font-medium">
                        ₹{item.payments_rs.toFixed(2)}
                      </td>
                      <td className="p-2.5 text-right font-extrabold text-slate-900">
                        ₹{item.outstanding_rs.toFixed(2)}
                      </td>
                      <td className="p-2.5 text-right text-slate-700">
                        ₹{item.ageing.bucket_0_30_rs.toFixed(2)}
                      </td>
                      <td className="p-2.5 text-right text-amber-700 font-medium">
                        ₹{item.ageing.bucket_31_60_rs.toFixed(2)}
                      </td>
                      <td className="p-2.5 text-right text-orange-700 font-semibold">
                        ₹{item.ageing.bucket_61_90_rs.toFixed(2)}
                      </td>
                      <td className="p-2.5 text-right text-red-700 font-bold">
                        ₹{item.ageing.bucket_90_plus_rs.toFixed(2)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
