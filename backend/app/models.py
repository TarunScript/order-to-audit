"""SQLAlchemy ORM models matching section 5 of the PRD."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Setting(Base):
    __tablename__ = "settings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    full_name = Column(String(200), nullable=False)
    active = Column(Boolean, server_default="true", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('salesman','admin','production','auditor','owner')", name="ck_users_role"),
    )


class Item(Base):
    __tablename__ = "items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sku = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    type = Column(String(20), nullable=False)
    base_unit = Column(String(10), nullable=False)
    display_unit = Column(String(10), nullable=False)
    hsn_code = Column(String(20), nullable=True)
    gst_rate_bp = Column(Integer, server_default="500", nullable=False)
    reorder_level_base = Column(BigInteger, server_default="0", nullable=False)
    active = Column(Boolean, server_default="true", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    units = relationship("ItemUnit", back_populates="item", cascade="all, delete-orphan")
    prices = relationship("PriceList", back_populates="item", cascade="all, delete-orphan")
    balance = relationship("ItemBalance", back_populates="item", uselist=False)

    __table_args__ = (
        CheckConstraint("type IN ('RAW','PACKAGING','FINISHED')", name="ck_items_type"),
        CheckConstraint("base_unit IN ('g','ml','piece')", name="ck_items_base_unit"),
        CheckConstraint("gst_rate_bp >= 0", name="ck_items_gst_rate"),
        CheckConstraint("reorder_level_base >= 0", name="ck_items_reorder"),
    )


class ItemUnit(Base):
    __tablename__ = "item_units"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    item_id = Column(BigInteger, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    unit = Column(String(20), nullable=False)
    factor_to_base = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    item = relationship("Item", back_populates="units")

    __table_args__ = (
        CheckConstraint("factor_to_base > 0", name="ck_item_units_factor"),
        UniqueConstraint("item_id", "unit", name="uq_item_units_item_unit"),
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    gstin = Column(String(15), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    active = Column(Boolean, server_default="true", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    type = Column(String(20), nullable=False)
    gstin = Column(String(15), nullable=True)
    state_code = Column(Integer, nullable=False)
    state_name = Column(String(50), nullable=False)
    address = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    salesman_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    credit_days = Column(Integer, server_default="30", nullable=False)
    active = Column(Boolean, server_default="true", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    salesman = relationship("User", foreign_keys=[salesman_id])

    __table_args__ = (
        CheckConstraint("type IN ('RETAILER','DISTRIBUTOR')", name="ck_customers_type"),
        CheckConstraint("credit_days >= 0", name="ck_customers_credit_days"),
    )


class PriceList(Base):
    __tablename__ = "price_list"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    item_id = Column(BigInteger, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    price_paise = Column(BigInteger, nullable=False)
    effective_from = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    item = relationship("Item", back_populates="prices")

    __table_args__ = (
        CheckConstraint("price_paise >= 0", name="ck_price_list_price"),
    )


class CustomerPrice(Base):
    __tablename__ = "customer_prices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    customer_id = Column(BigInteger, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(BigInteger, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    price_paise = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    customer = relationship("Customer")
    item = relationship("Item")

    __table_args__ = (
        CheckConstraint("price_paise >= 0", name="ck_customer_prices_price"),
        UniqueConstraint("customer_id", "item_id", name="uq_customer_prices_cust_item"),
    )


class Bom(Base):
    __tablename__ = "boms"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    product_item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    version = Column(Integer, server_default="1", nullable=False)
    yield_packets = Column(Integer, nullable=False)
    active = Column(Boolean, server_default="true", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    product = relationship("Item", foreign_keys=[product_item_id])
    lines = relationship("BomLine", back_populates="bom", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("yield_packets > 0", name="ck_boms_yield"),
    )


class BomLine(Base):
    __tablename__ = "bom_lines"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    bom_id = Column(BigInteger, ForeignKey("boms.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    qty_base = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    bom = relationship("Bom", back_populates="lines")
    item = relationship("Item", foreign_keys=[item_id])

    __table_args__ = (
        CheckConstraint("qty_base > 0", name="ck_bom_lines_qty"),
    )


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    supplier_id = Column(BigInteger, ForeignKey("suppliers.id"), nullable=False)
    bill_no = Column(String(50), nullable=True)
    purchase_date = Column(Date, nullable=False)
    status = Column(String(20), server_default="POSTED", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    supplier = relationship("Supplier", foreign_keys=[supplier_id])
    lines = relationship("PurchaseLine", back_populates="purchase", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('POSTED','CANCELLED')", name="ck_purchases_status"),
    )


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    purchase_id = Column(BigInteger, ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    qty_base = Column(BigInteger, nullable=False)
    rate_paise_per_display_unit = Column(BigInteger, nullable=False)
    unit_cost = Column(Numeric(18, 6), nullable=False)
    value_paise = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    purchase = relationship("Purchase", back_populates="lines")
    item = relationship("Item", foreign_keys=[item_id])

    __table_args__ = (
        CheckConstraint("qty_base > 0", name="ck_purchase_lines_qty"),
        CheckConstraint("value_paise >= 0", name="ck_purchase_lines_value"),
    )


class ProductionRun(Base):
    __tablename__ = "production_runs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_no = Column(String(50), unique=True, nullable=False)
    bom_id = Column(BigInteger, ForeignKey("boms.id"), nullable=False)
    product_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    run_date = Column(Date, nullable=False)
    batch_factor = Column(Numeric(8, 4), server_default="1", nullable=False)
    expected_output = Column(Integer, nullable=False)
    actual_good_output = Column(Integer, nullable=True)
    status = Column(String(20), server_default="DRAFT", nullable=False)
    labour_paise = Column(BigInteger, server_default="0", nullable=False)
    power_gas_paise = Column(BigInteger, server_default="0", nullable=False)
    other_overhead_paise = Column(BigInteger, server_default="0", nullable=False)
    tolerance_bp = Column(Integer, nullable=True)
    material_cost_paise = Column(BigInteger, nullable=True)
    cost_per_packet_paise = Column(BigInteger, nullable=True)
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    bom = relationship("Bom", foreign_keys=[bom_id])
    product = relationship("Item", foreign_keys=[product_id])
    creator = relationship("User", foreign_keys=[created_by])
    lines = relationship("ProductionRunLine", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','POSTED','CANCELLED')", name="ck_runs_status"),
        CheckConstraint("expected_output > 0", name="ck_runs_expected"),
        CheckConstraint("labour_paise >= 0", name="ck_runs_labour"),
        CheckConstraint("power_gas_paise >= 0", name="ck_runs_power"),
        CheckConstraint("other_overhead_paise >= 0", name="ck_runs_other"),
    )


class ProductionRunLine(Base):
    __tablename__ = "production_run_lines"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(BigInteger, ForeignKey("production_runs.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    planned_qty_base = Column(BigInteger, nullable=False)
    actual_qty_base = Column(BigInteger, nullable=True)
    wastage_qty_base = Column(BigInteger, server_default="0", nullable=True)
    variance_bp = Column(Integer, nullable=True)
    flagged = Column(Boolean, server_default="false", nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    run = relationship("ProductionRun", back_populates="lines")
    item = relationship("Item", foreign_keys=[item_id])

    __table_args__ = (
        CheckConstraint("planned_qty_base >= 0", name="ck_run_lines_planned"),
    )


class Order(Base):
    __tablename__ = "orders"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_no = Column(String(50), unique=True, nullable=False)
    client_uuid = Column(String(36), unique=True, nullable=False)
    customer_id = Column(BigInteger, ForeignKey("customers.id"), nullable=False)
    salesman_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), server_default="SUBMITTED", nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    customer = relationship("Customer", foreign_keys=[customer_id])
    salesman = relationship("User", foreign_keys=[salesman_id])
    lines = relationship("OrderLine", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('SUBMITTED','APPROVED','INVOICED','DISPATCHED','REJECTED')",
            name="ck_orders_status",
        ),
    )


class OrderLine(Base):
    __tablename__ = "order_lines"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    qty = Column(Integer, nullable=False)
    unit_price_paise = Column(BigInteger, nullable=False)
    approved_qty = Column(Integer, nullable=True)
    approved_price_paise = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    order = relationship("Order", back_populates="lines")
    item = relationship("Item", foreign_keys=[item_id])

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_order_lines_qty"),
        CheckConstraint("unit_price_paise >= 0", name="ck_order_lines_price"),
    )


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    invoice_no = Column(String(30), unique=True, nullable=False)
    fy = Column(String(10), nullable=False)
    order_id = Column(BigInteger, ForeignKey("orders.id"), nullable=False)
    customer_id = Column(BigInteger, ForeignKey("customers.id"), nullable=False)
    supply_type = Column(String(10), nullable=False)
    place_of_supply = Column(String(50), nullable=False)
    taxable_paise = Column(BigInteger, nullable=False)
    cgst_paise = Column(BigInteger, server_default="0", nullable=False)
    sgst_paise = Column(BigInteger, server_default="0", nullable=False)
    igst_paise = Column(BigInteger, server_default="0", nullable=False)
    total_paise = Column(BigInteger, nullable=False)
    status = Column(String(20), server_default="POSTED", nullable=False)
    invoice_date = Column(Date, nullable=False)
    pdf_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    order = relationship("Order", foreign_keys=[order_id])
    customer = relationship("Customer", foreign_keys=[customer_id])
    lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("supply_type IN ('INTRA','INTER')", name="ck_invoices_supply_type"),
        CheckConstraint("status IN ('POSTED','CANCELLED')", name="ck_invoices_status"),
        CheckConstraint("taxable_paise >= 0", name="ck_invoices_taxable"),
        CheckConstraint("total_paise >= 0", name="ck_invoices_total"),
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    invoice_id = Column(BigInteger, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    hsn_code = Column(String(20), nullable=True)
    qty = Column(Integer, nullable=False)
    rate_paise = Column(BigInteger, nullable=False)
    taxable_paise = Column(BigInteger, nullable=False)
    gst_rate_bp = Column(Integer, nullable=False)
    cgst_paise = Column(BigInteger, server_default="0", nullable=False)
    sgst_paise = Column(BigInteger, server_default="0", nullable=False)
    igst_paise = Column(BigInteger, server_default="0", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    invoice = relationship("Invoice", back_populates="lines")
    item = relationship("Item", foreign_keys=[item_id])

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_invoice_lines_qty"),
        CheckConstraint("taxable_paise >= 0", name="ck_invoice_lines_taxable"),
    )


class CreditNote(Base):
    __tablename__ = "credit_notes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    cn_no = Column(String(30), unique=True, nullable=False)
    invoice_id = Column(BigInteger, ForeignKey("invoices.id"), nullable=False)
    reason = Column(Text, nullable=False)
    taxable_paise = Column(BigInteger, nullable=False)
    cgst_paise = Column(BigInteger, server_default="0", nullable=False)
    sgst_paise = Column(BigInteger, server_default="0", nullable=False)
    igst_paise = Column(BigInteger, server_default="0", nullable=False)
    total_paise = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    invoice = relationship("Invoice", foreign_keys=[invoice_id])


class Dispatch(Base):
    __tablename__ = "dispatches"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    invoice_id = Column(BigInteger, ForeignKey("invoices.id"), nullable=False)
    dispatched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    dispatched_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    invoice = relationship("Invoice", foreign_keys=[invoice_id])
    dispatcher = relationship("User", foreign_keys=[dispatched_by])


class Payment(Base):
    __tablename__ = "payments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    customer_id = Column(BigInteger, ForeignKey("customers.id"), nullable=False)
    invoice_id = Column(BigInteger, ForeignKey("invoices.id"), nullable=True)
    amount_paise = Column(BigInteger, nullable=False)
    mode = Column(String(20), nullable=False)
    reference = Column(String(100), nullable=True)
    received_on = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    customer = relationship("Customer", foreign_keys=[customer_id])
    invoice = relationship("Invoice", foreign_keys=[invoice_id])

    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="ck_payments_amount"),
    )


class StockLedger(Base):
    __tablename__ = "stock_ledger"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    movement_type = Column(String(30), nullable=False)
    qty_base = Column(BigInteger, nullable=False)  # signed
    unit_cost = Column(Numeric(18, 6), nullable=True)
    value_paise = Column(BigInteger, nullable=False)  # signed
    source_type = Column(String(30), nullable=False)
    source_id = Column(BigInteger, nullable=False)
    batch_id = Column(BigInteger, nullable=True)
    posted_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    posted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    item = relationship("Item", foreign_keys=[item_id])
    user = relationship("User", foreign_keys=[posted_by])

    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('OPENING','PURCHASE_RECEIPT','PRODUCTION_ISSUE','PRODUCTION_OUTPUT',"
            "'SALES_DISPATCH','SALES_RETURN','ADJUSTMENT','REVERSAL')",
            name="ck_stock_ledger_movement_type",
        ),
        Index("ix_stock_ledger_item_posted", "item_id", "posted_at"),
        Index("ix_stock_ledger_source", "source_type", "source_id"),
    )


class ItemBalance(Base):
    __tablename__ = "item_balances"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    item_id = Column(BigInteger, ForeignKey("items.id"), unique=True, nullable=False)
    qty_base = Column(BigInteger, server_default="0", nullable=False)
    value_paise = Column(BigInteger, server_default="0", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    item = relationship("Item", back_populates="balance")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(BigInteger, nullable=True)
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
    )


class Sequence(Base):
    __tablename__ = "sequences"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(20), nullable=False)
    fy = Column(String(10), nullable=False)
    next_value = Column(Integer, server_default="1", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("name", "fy", name="uq_sequences_name_fy"),
    )
