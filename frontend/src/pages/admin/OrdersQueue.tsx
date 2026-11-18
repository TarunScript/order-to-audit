import React, { useState, useEffect } from 'react';
import { Order, StockCheckResponse, InvoicePreview } from '../../types';
import {
  apiGetOrders,
  apiGetOrder,
  apiStockCheck,
  apiInvoicePreview,
  apiApproveOrder,
  apiRejectOrder,
  apiCreateInvoice,
  apiUpdateOrder,
  paiseToRs,
  rsToPaise,
} from '../../services/api';
import { StatusChip } from '../../components/StatusChip';
import {
  ClipboardList,
  CheckCircle2,
  XCircle,
  FileText,
  AlertTriangle,
  RefreshCw,
  Edit2,
  Eye,
  Check,
  X,
} from 'lucide-react';

export const OrdersQueue: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [stockCheck, setStockCheck] = useState<StockCheckResponse | null>(null);
  const [invoicePreview, setInvoicePreview] = useState<InvoicePreview | null>(null);

  // Edit State
  const [isEditing, setIsEditing] = useState(false);
  const [editLines, setEditLines] = useState<Array<{ id: number; qty: number; unit_price_paise: number }>>([]);

  // Modals
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadOrders = async () => {
    setLoading(true);
    try {
      const data = await apiGetOrders();
      setOrders(data);
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Failed to fetch orders' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrders();
  }, []);

  const openOrderDetail = async (orderId: number) => {
    setActionLoading(true);
    setFeedbackMsg(null);
    setIsEditing(false);
    setInvoicePreview(null);
    try {
      const ord = await apiGetOrder(orderId);
      setSelectedOrder(ord);
      setEditLines(
        ord.lines.map((l) => ({
          id: l.id,
          qty: l.approved_qty ?? l.qty,
          unit_price_paise: l.approved_price_paise ?? l.unit_price_paise,
        }))
      );

      // Perform live stock check
      if (['SUBMITTED', 'APPROVED'].includes(ord.status)) {
        const check = await apiStockCheck(ord.id);
        setStockCheck(check);
      } else {
        setStockCheck(null);
      }
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Failed to load order detail' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveEdits = async () => {
    if (!selectedOrder) return;
    setActionLoading(true);
    try {
      await apiUpdateOrder(selectedOrder.id, {
        lines: editLines.map((l) => ({
          id: l.id,
          approved_qty: l.qty,
          approved_price_paise: l.unit_price_paise,
        })),
      });
      setIsEditing(false);
      await openOrderDetail(selectedOrder.id);
      setFeedbackMsg({ type: 'success', text: 'Order lines updated successfully' });
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Failed to update order' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!selectedOrder) return;
    setActionLoading(true);
    try {
      await apiApproveOrder(
        selectedOrder.id,
        editLines.map((l) => ({
          id: l.id,
          approved_qty: l.qty,
          approved_price_paise: l.unit_price_paise,
        }))
      );
      setFeedbackMsg({ type: 'success', text: `Order ${selectedOrder.order_no} approved!` });
      await openOrderDetail(selectedOrder.id);
      await loadOrders();
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Approval failed' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selectedOrder || !rejectReason.trim()) return;
    setActionLoading(true);
    try {
      await apiRejectOrder(selectedOrder.id, rejectReason.trim());
      setShowRejectModal(false);
      setRejectReason('');
      setFeedbackMsg({ type: 'success', text: `Order ${selectedOrder.order_no} rejected.` });
      await openOrderDetail(selectedOrder.id);
      await loadOrders();
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Rejection failed' });
    } finally {
      setActionLoading(false);
    }
  };

  const handlePreviewInvoice = async () => {
    if (!selectedOrder) return;
    setActionLoading(true);
    try {
      const preview = await apiInvoicePreview(selectedOrder.id);
      setInvoicePreview(preview);
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Preview generation failed' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleGenerateInvoice = async () => {
    if (!selectedOrder) return;
    setActionLoading(true);
    try {
      const inv = await apiCreateInvoice(selectedOrder.id);
      setFeedbackMsg({
        type: 'success',
        text: `Invoice ${inv.invoice_no} created successfully! Total: ${paiseToRs(inv.total_paise)}`,
      });
      await openOrderDetail(selectedOrder.id);
      await loadOrders();
    } catch (err: any) {
      setFeedbackMsg({ type: 'error', text: err.message || 'Invoice generation failed' });
    } finally {
      setActionLoading(false);
    }
  };

  const filteredOrders = statusFilter === 'ALL'
    ? orders
    : orders.filter((o) => o.status === statusFilter);

  // Has shortage flag
  const hasShortage = stockCheck?.lines.some((l) => l.is_shortage) ?? false;

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Incoming Orders Queue</h1>
          <p className="text-sm text-slate-500">
            Admin verification, real-time stock allocation & GST tax invoicing
          </p>
        </div>
        <button
          onClick={loadOrders}
          className="btn-secondary self-start"
          title="Reload Queue"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Queue</span>
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

      {/* Status Filters */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {['ALL', 'SUBMITTED', 'APPROVED', 'INVOICED', 'DISPATCHED', 'REJECTED'].map((st) => (
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

      {/* Grid: Left Orders Table, Right Order Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Orders List */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-slate-100 font-bold text-slate-800 text-sm">
            Orders ({filteredOrders.length})
          </div>
          <div className="divide-y divide-slate-100 max-h-[700px] overflow-y-auto">
            {filteredOrders.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">No orders matching filter</div>
            ) : (
              filteredOrders.map((ord) => (
                <div
                  key={ord.id}
                  onClick={() => openOrderDetail(ord.id)}
                  className={`p-4 cursor-pointer hover:bg-slate-50 transition-colors ${
                    selectedOrder?.id === ord.id ? 'bg-blue-50/60 border-l-4 border-blue-600' : ''
                  }`}
                >
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-mono text-xs font-bold text-blue-700">
                      {ord.order_no}
                    </span>
                    <StatusChip status={ord.status} />
                  </div>
                  <h4 className="text-sm font-bold text-slate-900">{ord.customer_name}</h4>
                  <div className="flex justify-between items-center mt-2 text-xs text-slate-500">
                    <span>By: {ord.salesman_name}</span>
                    <span className="font-extrabold text-slate-900 text-sm">
                      {paiseToRs(ord.approved_total_paise ?? ord.total_paise)}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Column: Order Detail & Actions */}
        <div className="lg:col-span-7">
          {selectedOrder ? (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-extrabold text-slate-900 font-mono">
                      {selectedOrder.order_no}
                    </h2>
                    <StatusChip status={selectedOrder.status} />
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Customer: <span className="font-semibold text-slate-800">{selectedOrder.customer_name}</span> ({selectedOrder.customer_state_name}, Code: {selectedOrder.customer_state_code})
                  </p>
                </div>

                {selectedOrder.status === 'SUBMITTED' && (
                  <button
                    onClick={() => setIsEditing(!isEditing)}
                    className="btn-secondary text-xs self-start"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                    <span>{isEditing ? 'Cancel Edit' : 'Edit Lines'}</span>
                  </button>
                )}
              </div>

              {/* Stock Check Warning (Shortage in RED) */}
              {stockCheck && (
                <div
                  className={`p-4 rounded-xl border text-sm ${
                    stockCheck.can_approve
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                      : 'bg-red-50 border-red-300 text-red-900'
                  }`}
                >
                  <div className="flex items-center gap-2 font-bold mb-1">
                    {stockCheck.can_approve ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="w-5 h-5 text-red-600" />
                    )}
                    <span>
                      {stockCheck.can_approve
                        ? 'Stock Available: Ready for Approval'
                        : 'STOCK SHORTAGE: Approval Blocked until Quantity Edited'}
                    </span>
                  </div>
                  <div className="mt-2 space-y-1 text-xs">
                    {stockCheck.lines.map((l) => (
                      <div
                        key={l.item_id}
                        className={`flex justify-between py-1 px-2 rounded ${
                          l.is_shortage ? 'bg-red-100 font-bold text-red-800 border border-red-200' : ''
                        }`}
                      >
                        <span>{l.item_name} ({l.sku})</span>
                        <span>
                          Requested: {l.requested_qty} | Available: {l.available_qty}
                          {l.is_shortage && (
                            <span className="ml-2 text-red-700 underline">
                              Shortage: {l.shortage_qty} pkts!
                            </span>
                          )}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Order Lines Table */}
              <div>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                  Order Items
                </h3>
                <div className="border border-slate-200 rounded-lg overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
                      <tr>
                        <th className="p-3">Product</th>
                        <th className="p-3 text-right">Qty</th>
                        <th className="p-3 text-right">Price</th>
                        <th className="p-3 text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {selectedOrder.lines.map((line, idx) => {
                        const editState = editLines.find((el) => el.id === line.id);
                        const qty = editState ? editState.qty : (line.approved_qty ?? line.qty);
                        const price = editState ? editState.unit_price_paise : (line.approved_price_paise ?? line.unit_price_paise);

                        return (
                          <tr key={line.id} className="hover:bg-slate-50">
                            <td className="p-3 font-medium text-slate-900">
                              {line.item_name}
                              <div className="text-[11px] text-slate-400 font-mono">{line.sku}</div>
                            </td>
                            <td className="p-3 text-right">
                              {isEditing ? (
                                <input
                                  type="number"
                                  min="1"
                                  value={qty}
                                  onChange={(e) => {
                                    const val = Math.max(1, parseInt(e.target.value) || 1);
                                    setEditLines((prev) =>
                                      prev.map((el) => (el.id === line.id ? { ...el, qty: val } : el))
                                    );
                                  }}
                                  className="w-20 px-2 py-1 border rounded text-right bg-white font-bold"
                                />
                              ) : (
                                <span className="font-bold text-slate-900">{qty} pkts</span>
                              )}
                            </td>
                            <td className="p-3 text-right">
                              {isEditing ? (
                                <input
                                  type="number"
                                  step="0.01"
                                  value={(price / 100).toFixed(2)}
                                  onChange={(e) => {
                                    const val = Math.round(parseFloat(e.target.value || '0') * 100);
                                    setEditLines((prev) =>
                                      prev.map((el) => (el.id === line.id ? { ...el, unit_price_paise: val } : el))
                                    );
                                  }}
                                  className="w-24 px-2 py-1 border rounded text-right bg-white font-bold"
                                />
                              ) : (
                                <span>{paiseToRs(price)}</span>
                              )}
                            </td>
                            <td className="p-3 text-right font-bold text-slate-900">
                              {paiseToRs(qty * price)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                    <tfoot className="bg-slate-50 font-bold border-t border-slate-200">
                      <tr>
                        <td colSpan={3} className="p-3 text-right text-slate-600">Total (Pre-Tax):</td>
                        <td className="p-3 text-right text-sm text-slate-900">
                          {paiseToRs(
                            isEditing
                              ? editLines.reduce((acc, el) => acc + el.qty * el.unit_price_paise, 0)
                              : (selectedOrder.approved_total_paise ?? selectedOrder.total_paise)
                          )}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>

                {isEditing && (
                  <div className="mt-3 flex justify-end gap-2">
                    <button onClick={handleSaveEdits} className="btn-success text-xs">
                      <Check className="w-3.5 h-3.5" />
                      <span>Save Changes</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Invoice Preview View */}
              {invoicePreview && (
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                      Tax Invoice Preview ({invoicePreview.supply_type} State Supply)
                    </span>
                    <button
                      onClick={() => setInvoicePreview(null)}
                      className="text-slate-400 hover:text-slate-600 text-xs"
                    >
                      Close Preview
                    </button>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div className="p-2 bg-white rounded border">
                      <div className="text-slate-400">Taxable</div>
                      <div className="font-bold">{paiseToRs(invoicePreview.taxable_paise)}</div>
                    </div>
                    {invoicePreview.supply_type === 'INTRA' ? (
                      <>
                        <div className="p-2 bg-white rounded border">
                          <div className="text-slate-400">CGST (2.5%)</div>
                          <div className="font-bold">{paiseToRs(invoicePreview.cgst_paise)}</div>
                        </div>
                        <div className="p-2 bg-white rounded border">
                          <div className="text-slate-400">SGST (2.5%)</div>
                          <div className="font-bold">{paiseToRs(invoicePreview.sgst_paise)}</div>
                        </div>
                      </>
                    ) : (
                      <div className="p-2 bg-white rounded border">
                        <div className="text-slate-400">IGST (5%)</div>
                        <div className="font-bold">{paiseToRs(invoicePreview.igst_paise)}</div>
                      </div>
                    )}
                    <div className="p-2 bg-blue-50 border border-blue-200 rounded">
                      <div className="text-blue-600 font-semibold">Total Invoice</div>
                      <div className="font-extrabold text-blue-900">{paiseToRs(invoicePreview.total_paise)}</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Actions Footer */}
              <div className="pt-4 border-t border-slate-200 flex flex-wrap gap-3 justify-end">
                {selectedOrder.status === 'SUBMITTED' && (
                  <>
                    <button
                      onClick={() => setShowRejectModal(true)}
                      disabled={actionLoading}
                      className="btn-danger text-xs"
                    >
                      <XCircle className="w-4 h-4" />
                      <span>Reject Order</span>
                    </button>

                    <button
                      onClick={handleApprove}
                      disabled={actionLoading || hasShortage}
                      className="btn-success text-xs disabled:opacity-40 disabled:cursor-not-allowed"
                      title={hasShortage ? 'Cannot approve with stock shortage. Edit quantities first.' : ''}
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      <span>{hasShortage ? 'Shortage: Edit Qty to Approve' : 'Approve Order'}</span>
                    </button>
                  </>
                )}

                {selectedOrder.status === 'APPROVED' && (
                  <>
                    <button
                      onClick={handlePreviewInvoice}
                      disabled={actionLoading}
                      className="btn-secondary text-xs"
                    >
                      <Eye className="w-4 h-4" />
                      <span>Preview Invoice</span>
                    </button>

                    <button
                      onClick={handleGenerateInvoice}
                      disabled={actionLoading}
                      className="btn-primary text-xs"
                    >
                      <FileText className="w-4 h-4" />
                      <span>Generate GST Invoice</span>
                    </button>
                  </>
                )}

                {selectedOrder.invoice_no && (
                  <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-200 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Invoiced: {selectedOrder.invoice_no}</span>
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-400">
              <ClipboardList className="w-12 h-12 mx-auto text-slate-300 mb-3" />
              <p className="text-base font-semibold text-slate-700">Select an order from the queue</p>
              <p className="text-xs text-slate-400 mt-1">
                View requested quantities, verify stock, edit lines and raise tax invoices.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-slate-900/60 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Reject Order</h3>
            <p className="text-xs text-slate-500">
              Please enter the mandatory reason for rejecting this order.
            </p>
            <textarea
              rows={3}
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. Credit limit exceeded, invalid address..."
              className="w-full p-2.5 text-sm border rounded-lg focus:ring-2 focus:ring-red-500 focus:outline-none"
            />
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowRejectModal(false)}
                className="btn-secondary text-xs"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={!rejectReason.trim() || actionLoading}
                className="btn-danger text-xs"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
