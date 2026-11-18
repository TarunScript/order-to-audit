"""Full schema for Order-to-Audit system.

Revision ID: 0001_full_schema
Revises: None
Create Date: 2026-11-18
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_full_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── settings ───────────────────────────────────────────────────────
    op.create_table(
        "settings",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── users ──────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('salesman','admin','production','auditor','owner')", name="ck_users_role"),
    )

    # ── items ──────────────────────────────────────────────────────────
    op.create_table(
        "items",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("sku", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("base_unit", sa.String(10), nullable=False),
        sa.Column("display_unit", sa.String(10), nullable=False),
        sa.Column("hsn_code", sa.String(20)),
        sa.Column("gst_rate_bp", sa.Integer, server_default=sa.text("500"), nullable=False),
        sa.Column("reorder_level_base", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("type IN ('RAW','PACKAGING','FINISHED')", name="ck_items_type"),
        sa.CheckConstraint("base_unit IN ('g','ml','piece')", name="ck_items_base_unit"),
        sa.CheckConstraint("gst_rate_bp >= 0", name="ck_items_gst_rate"),
        sa.CheckConstraint("reorder_level_base >= 0", name="ck_items_reorder"),
    )

    # ── item_units ─────────────────────────────────────────────────────
    op.create_table(
        "item_units",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("factor_to_base", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("factor_to_base > 0", name="ck_item_units_factor"),
        sa.UniqueConstraint("item_id", "unit", name="uq_item_units_item_unit"),
    )

    # ── suppliers ──────────────────────────────────────────────────────
    op.create_table(
        "suppliers",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("gstin", sa.String(15)),
        sa.Column("phone", sa.String(20)),
        sa.Column("address", sa.Text),
        sa.Column("active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── customers ──────────────────────────────────────────────────────
    op.create_table(
        "customers",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("gstin", sa.String(15)),
        sa.Column("state_code", sa.Integer, nullable=False),
        sa.Column("state_name", sa.String(50), nullable=False),
        sa.Column("address", sa.Text),
        sa.Column("phone", sa.String(20)),
        sa.Column("salesman_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("credit_days", sa.Integer, server_default=sa.text("30"), nullable=False),
        sa.Column("active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("type IN ('RETAILER','DISTRIBUTOR')", name="ck_customers_type"),
        sa.CheckConstraint("credit_days >= 0", name="ck_customers_credit_days"),
    )

    # ── price_list ─────────────────────────────────────────────────────
    op.create_table(
        "price_list",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("price_paise", sa.BigInteger, nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("price_paise >= 0", name="ck_price_list_price"),
    )

    # ── customer_prices ────────────────────────────────────────────────
    op.create_table(
        "customer_prices",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("customer_id", sa.BigInteger, sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("price_paise", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("price_paise >= 0", name="ck_customer_prices_price"),
        sa.UniqueConstraint("customer_id", "item_id", name="uq_customer_prices_cust_item"),
    )

    # ── boms ───────────────────────────────────────────────────────────
    op.create_table(
        "boms",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("product_item_id", sa.BigInteger, sa.ForeignKey("items.id"), nullable=False),
        sa.Column("version", sa.Integer, server_default=sa.text("1"), nullable=False),
        sa.Column("yield_packets", sa.Integer, nullable=False),
        sa.Column("active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("yield_packets > 0", name="ck_boms_yield"),
    )

    # ── bom_lines ──────────────────────────────────────────────────────
    op.create_table(
        "bom_lines",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("bom_id", sa.BigInteger, sa.ForeignKey("boms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty_base", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("qty_base > 0", name="ck_bom_lines_qty"),
    )

    # ── purchases ──────────────────────────────────────────────────────
    op.create_table(
        "purchases",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("supplier_id", sa.BigInteger, sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("bill_no", sa.String(50)),
        sa.Column("purchase_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'POSTED'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('POSTED','CANCELLED')", name="ck_purchases_status"),
    )

    # ── purchase_lines ─────────────────────────────────────────────────
    op.create_table(
        "purchase_lines",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("purchase_id", sa.BigInteger, sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty_base", sa.BigInteger, nullable=False),
        sa.Column("rate_paise_per_display_unit", sa.BigInteger, nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("value_paise", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("qty_base > 0", name="ck_purchase_lines_qty"),
        sa.CheckConstraint("value_paise >= 0", name="ck_purchase_lines_value"),
    )

    # ── production_runs ────────────────────────────────────────────────
    op.create_table(
        "production_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("run_no", sa.String(50), unique=True, nullable=False),
        sa.Column("bom_id", sa.BigInteger, sa.ForeignKey("boms.id"), nullable=False),
        sa.Column("product_id", sa.BigInteger, sa.ForeignKey("items.id"), nullable=False),
        sa.Column("run_date", sa.Date, nullable=False),
        sa.Column("batch_factor", sa.Numeric(8, 4), server_default=sa.text("1"), nullable=False),
        sa.Column("expected_output", sa.Integer, nullable=False),
        sa.Column("actual_good_output", sa.Integer),
        sa.Column("status", sa.String(20), server_default=sa.text("'DRAFT'"), nullable=False),
        sa.Column("labour_paise", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("power_gas_paise", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("other_overhead_paise", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("tolerance_bp", sa.Integer),
        sa.Column("material_cost_paise", sa.BigInteger),
        sa.Column("cost_per_packet_paise", sa.BigInteger),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id")),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('DRAFT','POSTED','CANCELLED')", name="ck_runs_status"),
        sa.CheckConstraint("expected_output > 0", name="ck_runs_expected"),
        sa.CheckConstraint("labour_paise >= 0", name="ck_runs_labour"),
        sa.CheckConstraint("power_gas_paise >= 0", name="ck_runs_power"),
        sa.CheckConstraint("other_overhead_paise >= 0", name="ck_runs_other"),
    )

    # ── production_run_lines ───────────────────────────────────────────
    op.create_table(
        "production_run_lines",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger, sa.ForeignKey("production_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id"), nullable=False),
        sa.Column("planned_qty_base", sa.BigInteger, nullable=False),
        sa.Column("actual_qty_base", sa.BigInteger),
        sa.Column("wastage_qty_base", sa.BigInteger, server_default=sa.text("0")),
        sa.Column("variance_bp", sa.Integer),
        sa.Column("flagged", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("planned_qty_base >= 0", name="ck_run_lines_planned"),
    )

    # ── orders ─────────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("order_no", sa.String(50), unique=True, nullable=False),
        sa.Column("client_uuid", sa.String(36), unique=True, nullable=False),
        sa.Column("customer_id", sa.BigInteger, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("salesman_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'SUBMITTED'"), nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('SUBMITTED','APPROVED','INVOICED','DISPATCHED','REJECTED')",
            name="ck_orders_status",
        ),
    )

    # ── order_lines ────────────────────────────────────────────────────
    op.create_table(
        "order_lines",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty", sa.Integer, nullable=False),
        sa.Column("unit_price_paise", sa.BigInteger, nullable=False),
        sa.Column("approved_qty", sa.Integer),
        sa.Column("approved_price_paise", sa.BigInteger),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_order_lines_qty"),
        sa.CheckConstraint("unit_price_paise >= 0", name="ck_order_lines_price"),
    )

    # ── invoices ───────────────────────────────────────────────────────
    op.create_table(
        "invoices",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("invoice_no", sa.String(30), unique=True, nullable=False),
        sa.Column("fy", sa.String(10), nullable=False),
        sa.Column("order_id", sa.BigInteger, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("customer_id", sa.BigInteger, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("supply_type", sa.String(10), nullable=False),
        sa.Column("place_of_supply", sa.String(50), nullable=False),
        sa.Column("taxable_paise", sa.BigInteger, nullable=False),
        sa.Column("cgst_paise", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("sgst_paise", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("igst_paise", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("total_paise", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'POSTED'"), nullable=False),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("pdf_path", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("supply_type IN ('INTRA','INTER')", name="ck_invoices_supply_type"),
        sa.CheckConstraint("status IN ('POSTED','CANCELLED')", name="ck_invoices_status"),
        sa.CheckConstraint("taxable_paise >= 0", name="ck_invoices_taxable"),
        sa.CheckConstraint("total_paise >= 0", name="ck_invoices_total"),
    )

    # ── invoice_lines ──────────────────────────────────────────────────
    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("invoice_id", sa.BigInteger, sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id"), nullable=False),
        sa.Column("hsn_code", sa.String(20)),
        sa.Column("qty", sa.Integer, nullable=False),
        sa.Column("rate_paise", sa.BigInteger, nullable=False),
        sa.Column("taxable_paise", sa.BigInteger, nullable=False),
        sa.Column("gst_rate_bp", sa.Integer, nullable=False),
        sa.Column("cgst_paise", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("sgst_paise", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("igst_paise", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_invoice_lines_qty"),
        sa.CheckConstraint("taxable_paise >= 0", name="ck_invoice_lines_taxable"),
    )

    # ── credit_notes ───────────────────────────────────────────────────
    op.create_table(
        "credit_notes",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("cn_no", sa.String(30), unique=True, nullable=False),
        sa.Column("invoice_id", sa.BigInteger, sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("taxable_paise", sa.BigInteger, nullable=False),
        sa.Column("cgst_paise", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("sgst_paise", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("igst_paise", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("total_paise", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── dispatches ─────────────────────────────────────────────────────
    op.create_table(
        "dispatches",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("invoice_id", sa.BigInteger, sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("dispatched_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── payments ───────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("customer_id", sa.BigInteger, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("invoice_id", sa.BigInteger, sa.ForeignKey("invoices.id"), nullable=True),
        sa.Column("amount_paise", sa.BigInteger, nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("reference", sa.String(100)),
        sa.Column("received_on", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount_paise > 0", name="ck_payments_amount"),
    )

    # ── stock_ledger ───────────────────────────────────────────────────
    op.create_table(
        "stock_ledger",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id"), nullable=False),
        sa.Column("movement_type", sa.String(30), nullable=False),
        sa.Column("qty_base", sa.BigInteger, nullable=False),  # signed
        sa.Column("unit_cost", sa.Numeric(18, 6)),
        sa.Column("value_paise", sa.BigInteger, nullable=False),  # signed
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", sa.BigInteger, nullable=False),
        sa.Column("batch_id", sa.BigInteger),
        sa.Column("posted_by", sa.BigInteger, sa.ForeignKey("users.id")),
        sa.Column("posted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "movement_type IN ('OPENING','PURCHASE_RECEIPT','PRODUCTION_ISSUE','PRODUCTION_OUTPUT',"
            "'SALES_DISPATCH','SALES_RETURN','ADJUSTMENT','REVERSAL')",
            name="ck_stock_ledger_movement_type",
        ),
    )

    # Indexes on stock_ledger
    op.create_index("ix_stock_ledger_item_posted", "stock_ledger", ["item_id", "posted_at"])
    op.create_index("ix_stock_ledger_source", "stock_ledger", ["source_type", "source_id"])

    # ── item_balances ──────────────────────────────────────────────────
    op.create_table(
        "item_balances",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id"), unique=True, nullable=False),
        sa.Column("qty_base", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("value_paise", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── audit_log ──────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.BigInteger),
        sa.Column("before_json", sa.Text),
        sa.Column("after_json", sa.Text),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"])

    # ── sequences ──────────────────────────────────────────────────────
    op.create_table(
        "sequences",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column("fy", sa.String(10), nullable=False),
        sa.Column("next_value", sa.Integer, server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("name", "fy", name="uq_sequences_name_fy"),
    )

    # ── Database triggers ──────────────────────────────────────────────

    # Trigger: block UPDATE and DELETE on stock_ledger
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_block_stock_ledger_modify()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'stock_ledger rows are immutable: UPDATE and DELETE are blocked';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_block_stock_ledger_update
        BEFORE UPDATE ON stock_ledger
        FOR EACH ROW EXECUTE FUNCTION fn_block_stock_ledger_modify();
    """)
    op.execute("""
        CREATE TRIGGER trg_block_stock_ledger_delete
        BEFORE DELETE ON stock_ledger
        FOR EACH ROW EXECUTE FUNCTION fn_block_stock_ledger_modify();
    """)

    # Trigger: block modification of POSTED invoices (except status -> CANCELLED)
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_block_posted_invoice_modify()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND OLD.status = 'POSTED' THEN
                RAISE EXCEPTION 'Cannot delete a POSTED invoice';
            END IF;
            IF TG_OP = 'UPDATE' AND OLD.status = 'POSTED' THEN
                -- Allow only status change from POSTED to CANCELLED
                IF NEW.status = 'CANCELLED' AND
                   OLD.invoice_no = NEW.invoice_no AND
                   OLD.fy = NEW.fy AND
                   OLD.order_id = NEW.order_id AND
                   OLD.customer_id = NEW.customer_id AND
                   OLD.taxable_paise = NEW.taxable_paise AND
                   OLD.cgst_paise = NEW.cgst_paise AND
                   OLD.sgst_paise = NEW.sgst_paise AND
                   OLD.igst_paise = NEW.igst_paise AND
                   OLD.total_paise = NEW.total_paise THEN
                    RETURN NEW;
                ELSE
                    RAISE EXCEPTION 'Cannot modify a POSTED invoice except to cancel it';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_block_posted_invoice
        BEFORE UPDATE OR DELETE ON invoices
        FOR EACH ROW EXECUTE FUNCTION fn_block_posted_invoice_modify();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_block_posted_invoice ON invoices")
    op.execute("DROP FUNCTION IF EXISTS fn_block_posted_invoice_modify()")
    op.execute("DROP TRIGGER IF EXISTS trg_block_stock_ledger_delete ON stock_ledger")
    op.execute("DROP TRIGGER IF EXISTS trg_block_stock_ledger_update ON stock_ledger")
    op.execute("DROP FUNCTION IF EXISTS fn_block_stock_ledger_modify()")

    tables = [
        "sequences", "audit_log", "item_balances", "stock_ledger",
        "payments", "dispatches", "credit_notes", "invoice_lines", "invoices",
        "order_lines", "orders", "production_run_lines", "production_runs",
        "purchase_lines", "purchases", "bom_lines", "boms",
        "customer_prices", "price_list", "customers", "suppliers",
        "item_units", "items", "users", "settings",
    ]
    for t in tables:
        op.drop_table(t)
