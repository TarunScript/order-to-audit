// Centralized API Client with JWT Auth and Typed Requests
import {
  AuthResponse,
  Customer,
  CustomerOutstanding,
  DashboardData,
  Invoice,
  InvoicePreview,
  Item,
  Order,
  PriceListItem,
  ProductionRun,
  StockCheckResponse,
  StockLedgerEntry,
  StockSummaryItem,
  Supplier,
  User,
} from '../types';

const API_BASE = '/api';

export function getAuthToken(): string | null {
  return localStorage.getItem('ota_token');
}

export function setAuthToken(token: string) {
  localStorage.setItem('ota_token', token);
}

export function clearAuthToken() {
  localStorage.removeItem('ota_token');
  localStorage.removeItem('ota_user');
}

export function paiseToRs(paise: number | undefined | null): string {
  if (paise === undefined || paise === null) return '₹0.00';
  return `₹${(paise / 100).toFixed(2)}`;
}

export function rsToPaise(rs: number): number {
  return Math.round(rs * 100);
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    clearAuthToken();
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
    throw new Error('Unauthorized');
  }

  if (!response.ok) {
    let errBody: any;
    try {
      errBody = await response.json();
    } catch {
      errBody = { message: response.statusText };
    }
    const message = errBody.message || errBody.detail || 'An error occurred';
    throw new Error(typeof message === 'object' ? JSON.stringify(message) : message);
  }

  // Check if response is JSON
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return response.json();
  }
  return response as unknown as T;
}

// ── Auth ──
export async function apiLogin(username: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export async function apiGetMe(): Promise<User> {
  return request<User>('/auth/me');
}

// ── Masters ──
export async function apiGetItems(): Promise<Item[]> {
  return request<Item[]>('/items');
}

export async function apiGetCustomers(): Promise<Customer[]> {
  return request<Customer[]>('/customers');
}

export async function apiGetSuppliers(): Promise<Supplier[]> {
  return request<Supplier[]>('/suppliers');
}

export async function apiGetPriceList(): Promise<PriceListItem[]> {
  return request<PriceListItem[]>('/price-list');
}

export async function apiGetBoms(): Promise<any[]> {
  return request<any[]>('/boms');
}

// ── Orders ──
export async function apiGetOrders(status?: string): Promise<Order[]> {
  const q = status ? `?status=${status}` : '';
  return request<Order[]>(`/orders${q}`);
}

export async function apiGetOrder(id: number): Promise<Order> {
  return request<Order>(`/orders/${id}`);
}

export async function apiCreateOrder(orderData: {
  client_uuid: string;
  customer_id: number;
  notes?: string;
  lines: Array<{ item_id: number; qty: number; unit_price_paise?: number }>;
}): Promise<Order> {
  return request<Order>('/orders', {
    method: 'POST',
    body: JSON.stringify(orderData),
  });
}

export async function apiUpdateOrder(id: number, updateData: {
  notes?: string;
  lines?: Array<{ id?: number; item_id?: number; qty?: number; unit_price_paise?: number; approved_qty?: number; approved_price_paise?: number }>;
}): Promise<Order> {
  return request<Order>(`/orders/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(updateData),
  });
}

export async function apiStockCheck(orderId: number): Promise<StockCheckResponse> {
  return request<StockCheckResponse>(`/orders/${orderId}/stock-check`);
}

export async function apiInvoicePreview(orderId: number): Promise<InvoicePreview> {
  return request<InvoicePreview>(`/orders/${orderId}/invoice-preview`);
}

export async function apiApproveOrder(orderId: number, lines?: Array<{ id?: number; approved_qty?: number; approved_price_paise?: number }>): Promise<Order> {
  return request<Order>(`/orders/${orderId}/approve`, {
    method: 'POST',
    body: JSON.stringify(lines ? { lines } : {}),
  });
}

export async function apiRejectOrder(orderId: number, reason: string): Promise<Order> {
  return request<Order>(`/orders/${orderId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

// ── Invoices ──
export async function apiCreateInvoice(orderId: number, invoiceDate?: string): Promise<Invoice> {
  return request<Invoice>(`/orders/${orderId}/invoice`, {
    method: 'POST',
    body: JSON.stringify(invoiceDate ? { invoice_date: invoiceDate } : {}),
  });
}

export async function apiGetInvoices(status?: string): Promise<Invoice[]> {
  const q = status ? `?status=${status}` : '';
  return request<Invoice[]>(`/invoices${q}`);
}

export async function apiGetInvoice(id: number): Promise<Invoice> {
  return request<Invoice>(`/invoices/${id}`);
}

export async function apiDispatchInvoice(invoiceId: number): Promise<any> {
  return request<any>(`/invoices/${invoiceId}/dispatch`, {
    method: 'POST',
  });
}

export async function apiCancelInvoice(invoiceId: number, reason: string): Promise<any> {
  return request<any>(`/invoices/${invoiceId}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export async function apiDownloadInvoicePdf(invoiceId: number, invoiceNo: string) {
  const token = getAuthToken();
  const resp = await fetch(`${API_BASE}/invoices/${invoiceId}/pdf`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) throw new Error('Failed to download PDF');
  const blob = await resp.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${invoiceNo.replace(/\//g, '_')}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

// ── Payments & Outstanding ──
export async function apiGetPayments(): Promise<any[]> {
  return request<any[]>('/payments');
}

export async function apiCreatePayment(data: {
  customer_id: number;
  invoice_id?: number | null;
  amount_paise: number;
  mode: string;
  reference?: string;
  received_on?: string;
}): Promise<any> {
  return request<any>('/payments', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function apiGetCustomerOutstanding(customerId: number): Promise<CustomerOutstanding> {
  return request<CustomerOutstanding>(`/customers/${customerId}/outstanding`);
}

// ── Purchases ──
export async function apiGetPurchases(): Promise<any[]> {
  return request<any[]>('/purchases');
}

export async function apiCreatePurchase(data: {
  supplier_id: number;
  bill_no?: string;
  purchase_date?: string;
  lines: Array<{
    item_id: number;
    qty?: number;
    qty_base?: number;
    unit?: string;
    rate_paise_per_display_unit?: number;
    rate_rupees_per_display_unit?: number;
  }>;
}): Promise<any> {
  return request<any>('/purchases', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ── Production Runs ──
export async function apiGetProductionRuns(): Promise<ProductionRun[]> {
  return request<ProductionRun[]>('/production-runs');
}

export async function apiGetProductionRun(id: number): Promise<ProductionRun> {
  return request<ProductionRun>(`/production-runs/${id}`);
}

export async function apiPrefillRun(bomId: number, batchFactor: number = 1.0): Promise<any> {
  return request<any>(`/production-runs/prefill?bom_id=${bomId}&batch_factor=${batchFactor}`);
}

export async function apiCreateProductionRun(data: any): Promise<ProductionRun> {
  return request<ProductionRun>('/production-runs', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function apiUpdateOverheads(runId: number, overheads: {
  labour_paise?: number;
  power_gas_paise?: number;
  other_overhead_paise?: number;
}): Promise<ProductionRun> {
  return request<ProductionRun>(`/production-runs/${runId}/overheads`, {
    method: 'PATCH',
    body: JSON.stringify(overheads),
  });
}

export async function apiCancelProductionRun(runId: number, reason?: string): Promise<any> {
  return request<any>(`/production-runs/${runId}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ reason: reason || 'Cancelled' }),
  });
}

// ── Stock ──
export async function apiGetStockSummary(type?: string): Promise<StockSummaryItem[]> {
  const q = type ? `?type=${type}` : '';
  return request<StockSummaryItem[]>(`/stock/summary${q}`);
}

export async function apiGetStockLedger(filters: {
  item_id?: number;
  from_date?: string;
  to_date?: string;
  movement_type?: string;
}): Promise<StockLedgerEntry[]> {
  const params = new URLSearchParams();
  if (filters.item_id) params.append('item_id', filters.item_id.toString());
  if (filters.from_date) params.append('from_date', filters.from_date);
  if (filters.to_date) params.append('to_date', filters.to_date);
  if (filters.movement_type) params.append('movement_type', filters.movement_type);
  const q = params.toString() ? `?${params.toString()}` : '';
  return request<StockLedgerEntry[]>(`/stock/ledger${q}`);
}

export async function apiCreateAdjustment(data: {
  item_id: number;
  qty: number;
  unit: string;
  reason: string;
}): Promise<any> {
  return request<any>('/stock/adjustments', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function apiReconcileStock(): Promise<{
  all_reconciled: boolean;
  total_items_checked: number;
  mismatch_count: number;
  mismatches: any[];
  items: Array<{
    item_id: number;
    sku: string;
    name: string;
    ledger_sum_base: number;
    cached_balance_base: number;
    is_reconciled: boolean;
  }>;
}> {
  return request<any>('/stock/reconcile');
}

// ── Reports ──
export async function apiGetReportData(name: string, from?: string, to?: string): Promise<any> {
  const params = new URLSearchParams();
  if (from) params.append('from', from);
  if (to) params.append('to', to);
  params.append('format', 'json');
  return request<any>(`/reports/${name}?${params.toString()}`);
}

export async function apiDownloadReport(name: string, format: 'csv' | 'xlsx' | 'pdf', from?: string, to?: string) {
  const token = getAuthToken();
  const params = new URLSearchParams();
  if (from) params.append('from', from);
  if (to) params.append('to', to);
  params.append('format', format);

  const resp = await fetch(`${API_BASE}/reports/${name}?${params.toString()}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) throw new Error(`Failed to download report as ${format.toUpperCase()}`);
  const blob = await resp.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${name}_report.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

// ── Dashboard ──
export async function apiGetDashboard(): Promise<DashboardData> {
  return request<DashboardData>('/dashboard');
}
