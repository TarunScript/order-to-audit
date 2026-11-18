"""Pydantic schemas for Orders, Invoices, Dispatches, and Credit Notes."""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────
# ORDER SCHEMAS
# ─────────────────────────────────────────────────────────────────────

class OrderLineInput(BaseModel):
    item_id: int
    qty: int = Field(gt=0)
    unit_price_paise: Optional[int] = None


class OrderLineUpdateInput(BaseModel):
    id: Optional[int] = None
    item_id: Optional[int] = None
    qty: Optional[int] = None
    unit_price_paise: Optional[int] = None
    approved_qty: Optional[int] = None
    approved_price_paise: Optional[int] = None


class OrderCreate(BaseModel):
    client_uuid: str
    customer_id: int
    notes: Optional[str] = None
    lines: List[OrderLineInput]


class OrderUpdate(BaseModel):
    notes: Optional[str] = None
    lines: Optional[List[OrderLineUpdateInput]] = None


class OrderLineOut(BaseModel):
    id: int
    item_id: int
    sku: str
    item_name: str
    display_unit: str
    qty: int
    unit_price_paise: int
    line_total_paise: int
    approved_qty: Optional[int]
    approved_price_paise: Optional[int]
    approved_total_paise: Optional[int]


class OrderOut(BaseModel):
    id: int
    order_no: str
    client_uuid: str
    customer_id: int
    customer_name: str
    customer_state_code: int
    customer_state_name: str
    salesman_id: int
    salesman_name: str
    status: str
    notes: Optional[str]
    total_paise: int
    approved_total_paise: Optional[int]
    lines: List[OrderLineOut]
    invoice_id: Optional[int] = None
    invoice_no: Optional[str] = None
    created_at: datetime


class StockCheckLineOut(BaseModel):
    item_id: int
    sku: str
    item_name: str
    requested_qty: int
    available_qty: int
    shortage_qty: int
    is_shortage: bool


class StockCheckResponse(BaseModel):
    order_id: int
    order_no: str
    can_approve: bool
    lines: List[StockCheckLineOut]


class OrderApproveRequest(BaseModel):
    lines: Optional[List[OrderLineUpdateInput]] = None


class OrderRejectRequest(BaseModel):
    reason: str = Field(min_length=2)


# ─────────────────────────────────────────────────────────────────────
# INVOICE SCHEMAS
# ─────────────────────────────────────────────────────────────────────

class InvoiceCreate(BaseModel):
    invoice_date: Optional[date] = None


class InvoicePreviewLineOut(BaseModel):
    item_id: int
    sku: str
    item_name: str
    hsn_code: Optional[str]
    qty: int
    rate_paise: int
    taxable_paise: int
    gst_rate_bp: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_paise: int


class InvoicePreviewResponse(BaseModel):
    order_id: int
    customer_id: int
    customer_name: str
    customer_state_code: int
    supply_type: str
    place_of_supply: str
    taxable_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_paise: int
    lines: List[InvoicePreviewLineOut]


class InvoiceLineOut(BaseModel):
    id: int
    item_id: int
    sku: str
    item_name: str
    hsn_code: Optional[str]
    qty: int
    rate_paise: int
    taxable_paise: int
    gst_rate_bp: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_paise: int


class InvoiceOut(BaseModel):
    id: int
    invoice_no: str
    fy: str
    order_id: int
    order_no: Optional[str]
    customer_id: int
    customer_name: str
    customer_gstin: Optional[str]
    supply_type: str
    place_of_supply: str
    taxable_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_paise: int
    status: str
    invoice_date: date
    pdf_path: Optional[str]
    whatsapp_url: Optional[str]
    mailto_url: Optional[str]
    dispatched_at: Optional[datetime]
    credit_note_no: Optional[str]
    lines: List[InvoiceLineOut]
    created_at: datetime


class DispatchOut(BaseModel):
    id: int
    invoice_id: int
    invoice_no: str
    dispatched_at: datetime
    dispatched_by: int


class InvoiceCancelRequest(BaseModel):
    reason: str = Field(min_length=3)


class CreditNoteOut(BaseModel):
    id: int
    cn_no: str
    invoice_id: int
    invoice_no: str
    reason: str
    taxable_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_paise: int
    created_at: datetime
