"""Pydantic schemas for master data management."""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Items & Units ───────────────────────────────────────────────────
class ItemUnitBase(BaseModel):
    unit: str
    factor_to_base: int = Field(gt=0)


class ItemUnitOut(ItemUnitBase):
    id: int

    class Config:
        from_attributes = True


class ItemBase(BaseModel):
    sku: str
    name: str
    type: str  # RAW, PACKAGING, FINISHED
    base_unit: str  # g, ml, piece
    display_unit: str
    hsn_code: Optional[str] = None
    gst_rate_bp: int = Field(default=500, ge=0)
    reorder_level_base: int = Field(default=0, ge=0)
    active: bool = True


class ItemCreate(ItemBase):
    units: Optional[List[ItemUnitBase]] = None


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    base_unit: Optional[str] = None
    display_unit: Optional[str] = None
    hsn_code: Optional[str] = None
    gst_rate_bp: Optional[int] = None
    reorder_level_base: Optional[int] = None
    active: Optional[bool] = None


class ItemOut(ItemBase):
    id: int
    created_at: datetime
    updated_at: datetime
    units: List[ItemUnitOut] = []

    class Config:
        from_attributes = True


# ── Customers ───────────────────────────────────────────────────────
class CustomerBase(BaseModel):
    name: str
    type: str  # RETAILER, DISTRIBUTOR
    gstin: Optional[str] = None
    state_code: int
    state_name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    salesman_id: Optional[int] = None
    credit_days: int = Field(default=30, ge=0)
    active: bool = True


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    gstin: Optional[str] = None
    state_code: Optional[int] = None
    state_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    salesman_id: Optional[int] = None
    credit_days: Optional[int] = None
    active: Optional[bool] = None


class CustomerOut(CustomerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Suppliers ───────────────────────────────────────────────────────
class SupplierBase(BaseModel):
    name: str
    gstin: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    active: bool = True


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    gstin: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    active: Optional[bool] = None


class SupplierOut(SupplierBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Price List ──────────────────────────────────────────────────────
class PriceListBase(BaseModel):
    item_id: int
    price_paise: int = Field(ge=0)
    effective_from: date


class PriceListCreate(PriceListBase):
    pass


class PriceListOut(PriceListBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── BOM & Lines ─────────────────────────────────────────────────────
class BomLineBase(BaseModel):
    item_id: int
    qty_base: int = Field(gt=0)


class BomLineOut(BomLineBase):
    id: int

    class Config:
        from_attributes = True


class BomBase(BaseModel):
    product_item_id: int
    version: int = 1
    yield_packets: int = Field(gt=0)
    active: bool = True


class BomCreate(BomBase):
    lines: List[BomLineBase]


class BomOut(BomBase):
    id: int
    created_at: datetime
    updated_at: datetime
    lines: List[BomLineOut] = []

    class Config:
        from_attributes = True


# ── Users ───────────────────────────────────────────────────────────
class UserBase(BaseModel):
    username: str
    role: str
    full_name: str
    active: bool = True


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    role: Optional[str] = None
    full_name: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None


class UserProfileOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
