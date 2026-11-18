"""Pydantic schemas for Purchases and Production Runs."""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────
# PURCHASES SCHEMAS
# ─────────────────────────────────────────────────────────────────────

class PurchaseLineInput(BaseModel):
    item_id: int
    qty: Optional[Decimal] = None  # in display unit or specified unit
    qty_base: Optional[int] = None  # in base units directly
    unit: Optional[str] = None  # e.g., 'kg', 'L', 'piece'
    rate_paise_per_display_unit: Optional[int] = None  # e.g., 4500 paise/kg
    rate_rupees_per_display_unit: Optional[Decimal] = None  # e.g., 45.00


class PurchaseCreate(BaseModel):
    supplier_id: int
    bill_no: Optional[str] = None
    purchase_date: Optional[date] = None
    lines: List[PurchaseLineInput]


class PurchaseLineOut(BaseModel):
    id: int
    item_id: int
    sku: str
    item_name: str
    display_unit: str
    base_unit: str
    qty_base: int
    qty_display: Decimal
    rate_paise_per_display_unit: int
    unit_cost: Decimal
    value_paise: int


class PurchaseOut(BaseModel):
    id: int
    supplier_id: int
    supplier_name: str
    bill_no: Optional[str]
    purchase_date: date
    status: str
    total_value_paise: int
    lines: List[PurchaseLineOut]
    created_at: datetime


# ─────────────────────────────────────────────────────────────────────
# PRODUCTION RUNS SCHEMAS
# ─────────────────────────────────────────────────────────────────────

class ProductionRunLineInput(BaseModel):
    item_id: int
    planned_qty_base: Optional[int] = None
    actual_qty_base: Optional[int] = None
    actual_qty: Optional[Decimal] = None  # in display unit
    unit: Optional[str] = None
    wastage_qty_base: Optional[int] = 0
    wastage_qty: Optional[Decimal] = None


class ProductionRunCreate(BaseModel):
    run_no: Optional[str] = None
    bom_id: int
    run_date: Optional[date] = None
    batch_factor: Decimal = Field(default=Decimal("1.0"), gt=0)
    expected_output: Optional[int] = None
    actual_good_output: int = Field(gt=0)
    damaged_pouches: Optional[int] = 0
    cartons_used: Optional[int] = None
    labour_paise: Optional[int] = 0
    power_gas_paise: Optional[int] = 0
    other_overhead_paise: Optional[int] = 0
    tolerance_bp: Optional[int] = None
    lines: Optional[List[ProductionRunLineInput]] = None


class OverheadsUpdate(BaseModel):
    labour_paise: Optional[int] = None
    power_gas_paise: Optional[int] = None
    other_overhead_paise: Optional[int] = None


class ProductionRunCancelRequest(BaseModel):
    reason: Optional[str] = "Production run cancelled"


class ProductionRunLineOut(BaseModel):
    id: int
    item_id: int
    sku: str
    item_name: str
    item_type: str
    base_unit: str
    display_unit: str
    planned_qty_base: int
    planned_qty_display: Decimal
    actual_qty_base: int
    actual_qty_display: Decimal
    wastage_qty_base: int
    wastage_qty_display: Decimal
    unit_cost: Optional[Decimal]
    line_value_paise: Optional[int]
    variance_bp: int
    flagged: bool


class ProductionRunOut(BaseModel):
    id: int
    run_no: str
    bom_id: int
    product_id: int
    product_sku: str
    product_name: str
    run_date: date
    batch_factor: Decimal
    expected_output: int
    actual_good_output: Optional[int]
    yield_variance_bp: Optional[int]
    yield_flagged: Optional[bool]
    status: str
    tolerance_bp: int
    labour_paise: int
    power_gas_paise: int
    other_overhead_paise: int
    total_overheads_paise: int
    material_cost_paise: Optional[int]
    total_cost_paise: Optional[int]
    cost_per_packet_paise: Optional[int]
    selling_price_paise: Optional[int]
    margin_per_packet_paise: Optional[int]
    created_by: Optional[int]
    posted_at: Optional[datetime]
    created_at: datetime
    lines: List[ProductionRunLineOut]


class BomPrefillLine(BaseModel):
    item_id: int
    sku: str
    item_name: str
    item_type: str
    base_unit: str
    display_unit: str
    factor_to_base: int
    planned_qty_base: int
    planned_qty_display: Decimal
    available_qty_base: int
    available_qty_display: Decimal
    current_wac_paise: Decimal


class BomPrefillResponse(BaseModel):
    bom_id: int
    product_id: int
    product_sku: str
    product_name: str
    batch_factor: Decimal
    expected_output: int
    lines: List[BomPrefillLine]
