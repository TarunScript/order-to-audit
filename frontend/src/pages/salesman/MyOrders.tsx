import React, { useState, useEffect } from 'react';
import { Order } from '../../types';
import { apiGetOrders, paiseToRs } from '../../services/api';
import { StatusChip } from '../../components/StatusChip';
import { getQueuedOrders, QueuedOrder } from '../../services/outbox';
import { Clock, RefreshCw, ShoppingCart, AlertCircle } from 'lucide-react';

export const MyOrders: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [offlineOrders, setOfflineOrders] = useState<QueuedOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const [fetchedOrders, queued] = await Promise.all([
        apiGetOrders(),
        getQueuedOrders(),
      ]);
      setOrders(fetchedOrders);
      setOfflineOrders(queued);
    } catch (err) {
      console.error('Failed to load my orders:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, []);

  const filteredOrders = statusFilter === 'ALL'
    ? orders
    : orders.filter((o) => o.status === statusFilter);

  return (
    <div className="max-w-md mx-auto pb-20">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">My Orders</h1>
          <p className="text-xs text-slate-500">Live order tracking and dispatch status</p>
        </div>
        <button
          onClick={fetchOrders}
          className="p-2 text-slate-600 hover:text-blue-600 rounded-lg bg-white border border-slate-200 shadow-sm"
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Status Filter Chips */}
      <div className="flex gap-1.5 overflow-x-auto pb-2 mb-3">
        {['ALL', 'SUBMITTED', 'APPROVED', 'INVOICED', 'DISPATCHED', 'REJECTED'].map((st) => (
          <button
            key={st}
            onClick={() => setStatusFilter(st)}
            className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition-colors ${
              statusFilter === st
                ? 'bg-blue-600 text-white'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
            }`}
          >
            {st}
          </button>
        ))}
      </div>

      {/* Offline Pending Orders Banner */}
      {offlineOrders.length > 0 && (
        <div className="mb-4 bg-amber-50 border border-amber-300 rounded-xl p-3">
          <div className="flex items-center gap-1.5 text-xs font-bold text-amber-800 mb-2">
            <Clock className="w-4 h-4" />
            <span>{offlineOrders.length} Offline Order(s) Pending Sync</span>
          </div>
          <div className="space-y-2">
            {offlineOrders.map((o) => (
              <div key={o.client_uuid} className="bg-white p-2.5 rounded-lg border border-amber-200 text-xs shadow-sm">
                <div className="flex justify-between font-bold text-slate-800">
                  <span>{o.customer_name}</span>
                  <span className="text-amber-700">{paiseToRs(o.total_paise)}</span>
                </div>
                <div className="text-slate-500 mt-1">
                  {o.lines.map((l) => `${l.qty}x ${l.item_name}`).join(', ')}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Orders List */}
      {loading ? (
        <div className="text-center py-10 text-slate-400 text-sm">Loading orders...</div>
      ) : filteredOrders.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border border-slate-200 p-6">
          <ShoppingCart className="w-10 h-10 mx-auto text-slate-300 mb-2" />
          <p className="text-sm font-semibold text-slate-700">No orders found</p>
          <p className="text-xs text-slate-400 mt-1">Orders you book will appear here</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredOrders.map((order) => (
            <div
              key={order.id}
              className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm"
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <span className="text-xs font-mono font-bold text-blue-700">
                    {order.order_no}
                  </span>
                  <h3 className="text-sm font-bold text-slate-900 mt-0.5">
                    {order.customer_name}
                  </h3>
                  <div className="text-[11px] text-slate-400">
                    {new Date(order.created_at).toLocaleDateString()} {new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
                <StatusChip status={order.status} />
              </div>

              {/* Order Lines */}
              <div className="mt-2 pt-2 border-t border-slate-100 text-xs text-slate-600 space-y-1">
                {order.lines.map((l) => (
                  <div key={l.id} className="flex justify-between">
                    <span>
                      {l.qty} {l.display_unit} {l.item_name}
                    </span>
                    <span className="font-medium text-slate-800">
                      {paiseToRs(l.line_total_paise)}
                    </span>
                  </div>
                ))}
              </div>

              {/* Footer Total */}
              <div className="mt-3 pt-2 border-t border-slate-100 flex justify-between items-center text-xs">
                <span className="font-medium text-slate-500">Order Value (pre-tax)</span>
                <span className="text-base font-extrabold text-slate-900">
                  {paiseToRs(order.total_paise)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
