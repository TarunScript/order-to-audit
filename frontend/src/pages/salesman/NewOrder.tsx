import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Customer, Item, PriceListItem } from '../../types';
import {
  apiGetCustomers,
  apiGetItems,
  apiGetPriceList,
  apiCreateOrder,
  paiseToRs,
} from '../../services/api';
import { queueOrder } from '../../services/outbox';
import {
  Plus,
  Minus,
  CheckCircle2,
  AlertCircle,
  Search,
  ShoppingCart,
  Send,
  WifiOff,
} from 'lucide-react';

export const NewOrder: React.FC = () => {
  const { user, isOnline, triggerSync } = useAuth();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [priceList, setPriceList] = useState<PriceListItem[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | ''>('');
  const [customerSearch, setCustomerSearch] = useState('');
  const [quantities, setQuantities] = useState<Record<number, number>>({});
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [cList, iList, pList] = await Promise.all([
          apiGetCustomers(),
          apiGetItems(),
          apiGetPriceList(),
        ]);
        // Filter only finished goods
        const finishedGoods = iList.filter((item) => item.type === 'FINISHED');
        setCustomers(cList);
        setItems(finishedGoods);
        setPriceList(pList);

        if (cList.length > 0) {
          setSelectedCustomerId(cList[0].id);
        }
      } catch (err: any) {
        console.error('Failed to load order taking data:', err);
      }
    }
    loadData();
  }, []);

  const filteredCustomers = customers.filter(
    (c) =>
      c.name.toLowerCase().includes(customerSearch.toLowerCase()) ||
      c.state_name.toLowerCase().includes(customerSearch.toLowerCase())
  );

  const getItemPricePaise = (itemId: number): number => {
    const pl = priceList.find((p) => p.item_id === itemId);
    return pl ? pl.price_paise : 5000; // default ₹50.00 if unlisted
  };

  const handleQtyChange = (itemId: number, delta: number) => {
    setQuantities((prev) => {
      const current = prev[itemId] || 0;
      const next = Math.max(0, current + delta);
      return { ...prev, [itemId]: next };
    });
  };

  // Compute Order Summary
  const orderLines = items
    .filter((item) => (quantities[item.id] || 0) > 0)
    .map((item) => {
      const qty = quantities[item.id];
      const unit_price_paise = getItemPricePaise(item.id);
      return {
        item_id: item.id,
        sku: item.sku,
        item_name: item.name,
        qty,
        unit_price_paise,
        line_total_paise: qty * unit_price_paise,
      };
    });

  const totalPaise = orderLines.reduce((acc, l) => acc + l.line_total_paise, 0);
  const totalItemsCount = orderLines.reduce((acc, l) => acc + l.qty, 0);

  const handleSubmitOrder = async () => {
    if (!selectedCustomerId) {
      setErrorMsg('Please select a customer');
      return;
    }
    if (orderLines.length === 0) {
      setErrorMsg('Please select at least one item');
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    const clientUuid = crypto.randomUUID();
    const selectedCust = customers.find((c) => c.id === selectedCustomerId);

    const orderPayload = {
      client_uuid: clientUuid,
      customer_id: Number(selectedCustomerId),
      notes: notes.trim() || undefined,
      lines: orderLines.map((l) => ({
        item_id: l.item_id,
        qty: l.qty,
        unit_price_paise: l.unit_price_paise,
      })),
    };

    try {
      if (!isOnline) {
        // Save to IndexedDB Outbox
        await queueOrder({
          ...orderPayload,
          customer_name: selectedCust?.name || 'Customer',
          lines: orderLines,
          total_paise: totalPaise,
          created_at: new Date().toISOString(),
          sync_status: 'PENDING',
        });
        setSuccessMsg('Offline: Order saved to Outbox! Will sync automatically when back online.');
        setQuantities({});
        setNotes('');
      } else {
        // Direct API submit
        const res = await apiCreateOrder(orderPayload);
        setSuccessMsg(`Order ${res.order_no} submitted successfully to factory desk!`);
        setQuantities({});
        setNotes('');
      }
    } catch (err: any) {
      // If network failed during online attempt, fallback to outbox
      try {
        await queueOrder({
          ...orderPayload,
          customer_name: selectedCust?.name || 'Customer',
          lines: orderLines,
          total_paise: totalPaise,
          created_at: new Date().toISOString(),
          sync_status: 'PENDING',
        });
        setSuccessMsg('Network error: Order safely preserved in Outbox!');
        setQuantities({});
        setNotes('');
      } catch {
        setErrorMsg(err.message || 'Submission failed');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-md mx-auto pb-20">
      {/* Salesman Top Banner */}
      <div className="bg-blue-800 text-white p-4 rounded-xl shadow mb-4">
        <h1 className="text-xl font-bold tracking-tight">New Sales Order</h1>
        <p className="text-xs text-blue-200 mt-0.5">
          Fast mobile booking for {user?.full_name}
        </p>
      </div>

      {successMsg && (
        <div className="mb-4 bg-emerald-50 border border-emerald-300 text-emerald-800 p-3 rounded-lg text-sm flex items-start gap-2 shadow-sm">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5 text-emerald-600" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="mb-4 bg-red-50 border border-red-300 text-red-800 p-3 rounded-lg text-sm flex items-start gap-2 shadow-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5 text-red-600" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* 1. Customer Picker */}
      <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 mb-4">
        <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
          Step 1: Select Customer
        </label>
        <div className="relative mb-2">
          <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
          <input
            type="text"
            placeholder="Search customer..."
            value={customerSearch}
            onChange={(e) => setCustomerSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select
          value={selectedCustomerId}
          onChange={(e) => setSelectedCustomerId(Number(e.target.value))}
          className="w-full py-2.5 px-3 bg-white border border-slate-300 rounded-lg text-sm font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {filteredCustomers.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.type} - {c.state_name})
            </option>
          ))}
        </select>
      </div>

      {/* 2. Product List with Steppers (>= 44px tap targets) */}
      <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 mb-4">
        <div className="flex justify-between items-center mb-3">
          <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">
            Step 2: Add Products
          </label>
          <span className="text-xs text-slate-500 font-medium">
            {totalItemsCount} pkts selected
          </span>
        </div>

        <div className="divide-y divide-slate-100">
          {items.map((item) => {
            const price = getItemPricePaise(item.id);
            const qty = quantities[item.id] || 0;
            const lineTotal = qty * price;

            return (
              <div key={item.id} className="py-3 flex items-center justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-bold text-slate-900 truncate">
                    {item.name}
                  </h4>
                  <div className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                    <span className="font-semibold text-slate-700">
                      {paiseToRs(price)}/pkt
                    </span>
                    {qty > 0 && (
                      <span className="text-blue-600 font-bold">
                        = {paiseToRs(lineTotal)}
                      </span>
                    )}
                  </div>
                </div>

                {/* Quantity Stepper (large 44px tap targets for mobile) */}
                <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-xl">
                  <button
                    type="button"
                    onClick={() => handleQtyChange(item.id, -10)}
                    disabled={qty <= 0}
                    className="w-9 h-11 flex items-center justify-center rounded-lg bg-white text-slate-600 hover:bg-slate-200 disabled:opacity-30 disabled:cursor-not-allowed shadow-sm text-xs font-bold"
                    title="-10"
                  >
                    -10
                  </button>
                  <button
                    type="button"
                    onClick={() => handleQtyChange(item.id, -1)}
                    disabled={qty <= 0}
                    className="w-11 h-11 flex items-center justify-center rounded-lg bg-white text-slate-700 hover:bg-slate-200 disabled:opacity-30 disabled:cursor-not-allowed shadow-sm"
                  >
                    <Minus className="w-4 h-4" />
                  </button>

                  <span className="w-10 text-center font-bold text-sm text-slate-900">
                    {qty}
                  </span>

                  <button
                    type="button"
                    onClick={() => handleQtyChange(item.id, 1)}
                    className="w-11 h-11 flex items-center justify-center rounded-lg bg-blue-600 text-white hover:bg-blue-700 shadow-sm"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleQtyChange(item.id, 10)}
                    className="w-9 h-11 flex items-center justify-center rounded-lg bg-blue-100 text-blue-800 hover:bg-blue-200 shadow-sm text-xs font-bold"
                    title="+10"
                  >
                    +10
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. Notes */}
      <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 mb-4">
        <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
          Order Notes (Optional)
        </label>
        <textarea
          rows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Delivery instructions, urgent timing..."
          className="w-full p-2.5 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* 4. Bottom Order Summary & Sticky Submit Button */}
      <div className="bg-white p-4 rounded-xl shadow-lg border border-slate-200 sticky bottom-20">
        <div className="flex justify-between items-center mb-3">
          <div>
            <span className="text-xs text-slate-500 font-medium">Pre-tax Total</span>
            <div className="text-2xl font-extrabold text-slate-900">
              {paiseToRs(totalPaise)}
            </div>
          </div>
          <div className="text-right">
            <span className="text-xs text-slate-500 font-medium">Packets</span>
            <div className="text-lg font-bold text-blue-700">
              {totalItemsCount}
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={handleSubmitOrder}
          disabled={submitting || orderLines.length === 0}
          className="w-full h-12 btn-primary rounded-xl text-base font-bold shadow-md"
        >
          {submitting ? (
            'Submitting...'
          ) : isOnline ? (
            <>
              <Send className="w-5 h-5" />
              <span>Submit Order to Factory</span>
            </>
          ) : (
            <>
              <WifiOff className="w-5 h-5" />
              <span>Save to Offline Outbox</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
