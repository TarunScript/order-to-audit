export type Role = 'salesman' | 'admin' | 'production' | 'auditor' | 'owner';

export interface User {
  id: number;
  username: string;
  role: Role;
  full_name: string;
  active: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  role: Role;
  username: string;
  user_id: number;
}

export interface Item {
  id: number;
  sku: string;
  name: string;
  type: 'RAW' | 'PACKAGING' | 'FINISHED';
  base_unit: string;
  display_unit: string;
  hsn_code?: string;
  gst_rate_bp: number;
  reorder_level_base: number;
  active: boolean;
}

export interface Customer {
  id: number;
  name: string;
  type: 'RETAILER' | 'DISTRIBUTOR';
  gstin?: string;
  state_code: number;
  state_name: string;
  address?: string;
  phone?: string;
  salesman_id?: number;
  credit_days: number;
  active: boolean;
}

export interface Supplier {
  id: number;
  name: string;
  gstin?: string;
  phone?: string;
  address?: string;
  active: boolean;
}

export interface PriceListItem {
  id: number;
  item_id: number;
  item_sku?: string;
  item_name?: string;
  price_paise: number;
  effective_from: string;
}

export interface OrderLine {
  id: number;
  item_id: number;
  sku: string;
  item_name: string;
  display_unit: string;
  qty: number;
  unit_price_paise: number;
  line_total_paise: number;
  approved_qty?: number;
  approved_price_paise?: number;
  approved_total_paise?: number;
}

export interface Order {
  id: number;
  order_no: string;
  client_uuid: string;
  customer_id: number;
  customer_name: string;
  customer_state_code: number;
  customer_state_name: string;
  salesman_id: number;
  salesman_name: string;
  status: 'SUBMITTED' | 'APPROVED' | 'INVOICED' | 'DISPATCHED' | 'REJECTED';
  notes?: string;
  total_paise: number;
  approved_total_paise?: number;
  lines: OrderLine[];
  invoice_id?: number;
  invoice_no?: string;
  created_at: string;
}

export interface StockCheckLine {
  item_id: number;
  sku: string;
  item_name: string;
  requested_qty: number;
  available_qty: number;
  shortage_qty: number;
  is_shortage: boolean;
}

export interface StockCheckResponse {
  order_id: number;
  order_no: string;
  can_approve: boolean;
  lines: StockCheckLine[];
}

export interface InvoicePreviewLine {
  item_id: number;
  sku: string;
  item_name: string;
  hsn_code?: string;
  qty: number;
  rate_paise: number;
  taxable_paise: number;
  gst_rate_bp: number;
  cgst_paise: number;
  sgst_paise: number;
  igst_paise: number;
  total_paise: number;
}

export interface InvoicePreview {
  order_id: number;
  customer_id: number;
  customer_name: string;
  customer_state_code: number;
  supply_type: 'INTRA' | 'INTER';
  place_of_supply: string;
  taxable_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  igst_paise: number;
  total_paise: number;
  lines: InvoicePreviewLine[];
}

export interface Invoice {
  id: number;
  invoice_no: string;
  fy: string;
  order_id: number;
  order_no?: string;
  customer_id: number;
  customer_name: string;
  customer_gstin?: string;
  supply_type: 'INTRA' | 'INTER';
  place_of_supply: string;
  taxable_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  igst_paise: number;
  total_paise: number;
  status: 'POSTED' | 'CANCELLED';
  invoice_date: string;
  pdf_path?: string;
  whatsapp_url?: string;
  mailto_url?: string;
  dispatched_at?: string;
  credit_note_no?: string;
  lines: InvoicePreviewLine[];
  created_at: string;
}

export interface CustomerOutstanding {
  customer_id: number;
  customer_name: string;
  gstin?: string;
  state_name: string;
  credit_days: number;
  invoiced_paise: number;
  credit_notes_paise: number;
  payments_paise: number;
  outstanding_paise: number;
  invoiced_rs: number;
  credit_notes_rs: number;
  payments_rs: number;
  outstanding_rs: number;
  ageing: {
    bucket_0_30_rs: number;
    bucket_31_60_rs: number;
    bucket_61_90_rs: number;
    bucket_90_plus_rs: number;
  };
}

export interface ProductionRunLine {
  id: number;
  item_id: number;
  sku: string;
  item_name: string;
  item_type: string;
  base_unit: string;
  display_unit: string;
  factor_to_base: number;
  planned_qty_base: number;
  actual_qty_base: number;
  wastage_qty_base: number;
  planned_qty_display: number;
  actual_qty_display: number;
  wastage_qty_display: number;
  variance_bp: number;
  variance_pct: number;
  flagged: boolean;
}

export interface ProductionRun {
  id: number;
  run_no: string;
  bom_id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  run_date: string;
  batch_factor: number;
  expected_output: number;
  actual_good_output: number;
  damaged_pouches: number;
  cartons_used?: number;
  status: 'DRAFT' | 'POSTED' | 'CANCELLED';
  labour_paise: number;
  power_gas_paise: number;
  other_overhead_paise: number;
  overheads_total_paise: number;
  tolerance_bp: number;
  material_cost_paise: number;
  total_cost_paise: number;
  cost_per_packet_paise: number;
  selling_price_paise: number;
  margin_paise: number;
  yield_variance_bp: number;
  yield_variance_pct: number;
  yield_flagged: boolean;
  lines: ProductionRunLine[];
  created_at: string;
  posted_at?: string;
}

export interface StockSummaryItem {
  item_id: number;
  sku: string;
  name: string;
  type: 'RAW' | 'PACKAGING' | 'FINISHED';
  base_unit: string;
  display_unit: string;
  closing_qty_base: number;
  closing_qty_display: number;
  unit_cost: number;
  value_paise: number;
  value_rs: number;
  reorder_level_base: number;
  reorder_level_display: number;
  is_low_stock: boolean;
}

export interface StockLedgerEntry {
  id: number;
  item_id: number;
  item_sku: string;
  item_name: string;
  movement_type: string;
  qty_base: number;
  qty_display: number;
  display_unit: string;
  unit_cost: number;
  value_paise: number;
  value_rs: number;
  source_type: string;
  source_id: number;
  running_qty_base: number;
  running_qty_display: number;
  note?: string;
  posted_at: string;
}

export interface DashboardData {
  as_of: string;
  todays_orders: {
    count: number;
    total_paise: number;
    total_rs: number;
  };
  pending_approvals: {
    count: number;
    orders: Array<{
      id: number;
      order_no: string;
      customer_name: string;
      total_paise: number;
      created_at: string;
    }>;
  };
  stock_levels: Array<{
    item_id: number;
    sku: string;
    name: string;
    type: string;
    display_unit: string;
    closing_qty_display: number;
    reorder_level_display: number;
    is_low_stock: boolean;
  }>;
  variance_alerts: Array<{
    run_id: number;
    run_no: string;
    run_date: string;
    product_name: string;
    line_name: string;
    variance_pct: number;
    tolerance_pct: number;
  }>;
  costing_margins: Array<{
    product_id: number;
    sku: string;
    name: string;
    cost_per_packet_paise: number;
    cost_per_packet_rs: number;
    selling_price_paise: number;
    selling_price_rs: number;
    margin_paise: number;
    margin_rs: number;
    last_run_no?: string;
  }>;
  top_debtors: Array<{
    customer_id: number;
    customer_name: string;
    outstanding_paise: number;
    outstanding_rs: number;
    credit_days: number;
  }>;
  total_outstanding_rs: number;
}
