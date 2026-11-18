"""Data generators for all PRD Section 7.6 reports."""
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.money import paise_to_rupees, format_inr
from app.core.units import from_base_units
from app.core.gst import DEFAULT_SELLER_STATE_CODE
from app.models import (
    Customer,
    Item,
    ItemUnit,
    ItemBalance,
    Order,
    OrderLine,
    Invoice,
    InvoiceLine,
    CreditNote,
    Purchase,
    PurchaseLine,
    ProductionRun,
    ProductionRunLine,
    StockLedger,
    Payment,
    PriceList,
    Setting,
)


# ─────────────────────────────────────────────────────────────────────
# 1. SALES REGISTER
# ─────────────────────────────────────────────────────────────────────

async def get_sales_register_data(
    db: AsyncSession, from_date: Optional[date] = None, to_date: Optional[date] = None
) -> Dict[str, Any]:
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.order))
        .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
    )
    if from_date:
        stmt = stmt.where(Invoice.invoice_date >= from_date)
    if to_date:
        stmt = stmt.where(Invoice.invoice_date <= to_date)

    invoices = (await db.execute(stmt)).scalars().all()

    rows = []
    tot_taxable = 0
    tot_cgst = 0
    tot_sgst = 0
    tot_igst = 0
    tot_grand = 0

    for inv in invoices:
        tot_taxable += inv.taxable_paise
        tot_cgst += inv.cgst_paise
        tot_sgst += inv.sgst_paise
        tot_igst += inv.igst_paise
        tot_grand += inv.total_paise

        rows.append({
            "invoice_no": inv.invoice_no,
            "invoice_date": inv.invoice_date.isoformat(),
            "customer_name": inv.customer.name if inv.customer else "",
            "customer_gstin": inv.customer.gstin or "Unregistered",
            "place_of_supply": inv.place_of_supply,
            "supply_type": inv.supply_type,
            "status": inv.status,
            "taxable_paise": inv.taxable_paise,
            "taxable_rs": float(paise_to_rupees(inv.taxable_paise)),
            "cgst_paise": inv.cgst_paise,
            "cgst_rs": float(paise_to_rupees(inv.cgst_paise)),
            "sgst_paise": inv.sgst_paise,
            "sgst_rs": float(paise_to_rupees(inv.sgst_paise)),
            "igst_paise": inv.igst_paise,
            "igst_rs": float(paise_to_rupees(inv.igst_paise)),
            "total_paise": inv.total_paise,
            "total_rs": float(paise_to_rupees(inv.total_paise)),
        })

    return {
        "report_name": "Sales Register",
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "summary": {
            "total_invoices": len(rows),
            "total_taxable_paise": tot_taxable,
            "total_taxable_rs": float(paise_to_rupees(tot_taxable)),
            "total_cgst_paise": tot_cgst,
            "total_sgst_paise": tot_sgst,
            "total_igst_paise": tot_igst,
            "grand_total_paise": tot_grand,
            "grand_total_rs": float(paise_to_rupees(tot_grand)),
        },
        "rows": rows,
    }


# ─────────────────────────────────────────────────────────────────────
# 2. CUSTOMER-WISE SALES
# ─────────────────────────────────────────────────────────────────────

async def get_customer_sales_data(
    db: AsyncSession, from_date: Optional[date] = None, to_date: Optional[date] = None
) -> Dict[str, Any]:
    stmt = (
        select(
            Customer.id,
            Customer.name,
            Customer.gstin,
            Customer.state_name,
            func.count(Invoice.id).label("invoice_count"),
            func.coalesce(func.sum(Invoice.taxable_paise), 0).label("taxable_paise"),
            func.coalesce(func.sum(Invoice.cgst_paise), 0).label("cgst_paise"),
            func.coalesce(func.sum(Invoice.sgst_paise), 0).label("sgst_paise"),
            func.coalesce(func.sum(Invoice.igst_paise), 0).label("igst_paise"),
            func.coalesce(func.sum(Invoice.total_paise), 0).label("total_paise"),
        )
        .join(Invoice, Customer.id == Invoice.customer_id)
        .group_by(Customer.id, Customer.name, Customer.gstin, Customer.state_name)
        .order_by(func.sum(Invoice.total_paise).desc())
    )
    if from_date:
        stmt = stmt.where(Invoice.invoice_date >= from_date)
    if to_date:
        stmt = stmt.where(Invoice.invoice_date <= to_date)

    results = (await db.execute(stmt)).all()

    rows = []
    tot_grand = 0
    for r in results:
        tot_grand += r.total_paise
        rows.append({
            "customer_id": r.id,
            "customer_name": r.name,
            "gstin": r.gstin or "Unregistered",
            "state_name": r.state_name,
            "invoice_count": r.invoice_count,
            "taxable_paise": r.taxable_paise,
            "taxable_rs": float(paise_to_rupees(r.taxable_paise)),
            "cgst_paise": r.cgst_paise,
            "cgst_rs": float(paise_to_rupees(r.cgst_paise)),
            "sgst_paise": r.sgst_paise,
            "sgst_rs": float(paise_to_rupees(r.sgst_paise)),
            "igst_paise": r.igst_paise,
            "igst_rs": float(paise_to_rupees(r.igst_paise)),
            "total_paise": r.total_paise,
            "total_rs": float(paise_to_rupees(r.total_paise)),
        })

    return {
        "report_name": "Customer-wise Sales",
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "summary": {
            "total_customers": len(rows),
            "grand_total_paise": tot_grand,
            "grand_total_rs": float(paise_to_rupees(tot_grand)),
        },
        "rows": rows,
    }


# ─────────────────────────────────────────────────────────────────────
# 3. PRODUCT-WISE SALES
# ─────────────────────────────────────────────────────────────────────

async def get_product_sales_data(
    db: AsyncSession, from_date: Optional[date] = None, to_date: Optional[date] = None
) -> Dict[str, Any]:
    stmt = (
        select(
            Item.id,
            Item.sku,
            Item.name,
            Item.display_unit,
            func.coalesce(func.sum(InvoiceLine.qty), 0).label("total_qty"),
            func.coalesce(func.sum(InvoiceLine.taxable_paise), 0).label("taxable_paise"),
            func.coalesce(func.sum(InvoiceLine.cgst_paise + InvoiceLine.sgst_paise + InvoiceLine.igst_paise), 0).label("tax_paise"),
        )
        .join(InvoiceLine, Item.id == InvoiceLine.item_id)
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .group_by(Item.id, Item.sku, Item.name, Item.display_unit)
        .order_by(func.sum(InvoiceLine.taxable_paise).desc())
    )
    if from_date:
        stmt = stmt.where(Invoice.invoice_date >= from_date)
    if to_date:
        stmt = stmt.where(Invoice.invoice_date <= to_date)

    results = (await db.execute(stmt)).all()

    rows = []
    tot_grand = 0
    for r in results:
        tot_line = r.taxable_paise + r.tax_paise
        tot_grand += tot_line
        rows.append({
            "item_id": r.id,
            "sku": r.sku,
            "item_name": r.name,
            "display_unit": r.display_unit,
            "total_qty": r.total_qty,
            "taxable_paise": r.taxable_paise,
            "taxable_rs": float(paise_to_rupees(r.taxable_paise)),
            "tax_paise": r.tax_paise,
            "tax_rs": float(paise_to_rupees(r.tax_paise)),
            "total_paise": tot_line,
            "total_rs": float(paise_to_rupees(tot_line)),
        })

    return {
        "report_name": "Product-wise Sales",
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "summary": {
            "total_products": len(rows),
            "grand_total_paise": tot_grand,
            "grand_total_rs": float(paise_to_rupees(tot_grand)),
        },
        "rows": rows,
    }


# ─────────────────────────────────────────────────────────────────────
# 4. GST SUMMARY (GSTR-1 & GSTR-3B SHAPE)
# ─────────────────────────────────────────────────────────────────────

async def get_gst_summary_data(
    db: AsyncSession, from_date: Optional[date] = None, to_date: Optional[date] = None
) -> Dict[str, Any]:
    # 1. B2B Table: Each invoice with customer details
    inv_stmt = (
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.lines))
        .where(Invoice.status == "POSTED")
        .order_by(Invoice.invoice_date.asc())
    )
    if from_date:
        inv_stmt = inv_stmt.where(Invoice.invoice_date >= from_date)
    if to_date:
        inv_stmt = inv_stmt.where(Invoice.invoice_date <= to_date)

    invoices = (await db.execute(inv_stmt)).scalars().all()

    b2b_rows = []
    tot_taxable = 0
    tot_cgst = 0
    tot_sgst = 0
    tot_igst = 0
    tot_grand = 0

    for inv in invoices:
        tot_taxable += inv.taxable_paise
        tot_cgst += inv.cgst_paise
        tot_sgst += inv.sgst_paise
        tot_igst += inv.igst_paise
        tot_grand += inv.total_paise

        # Typical rate for B2B table
        rate_bp = inv.lines[0].gst_rate_bp if inv.lines else 500

        b2b_rows.append({
            "gstin": inv.customer.gstin or "URP",
            "customer_name": inv.customer.name,
            "invoice_no": inv.invoice_no,
            "invoice_date": inv.invoice_date.isoformat(),
            "invoice_value_rs": float(paise_to_rupees(inv.total_paise)),
            "place_of_supply": inv.place_of_supply,
            "supply_type": inv.supply_type,
            "rate_pct": f"{rate_bp / 100:.1f}%",
            "taxable_rs": float(paise_to_rupees(inv.taxable_paise)),
            "cgst_rs": float(paise_to_rupees(inv.cgst_paise)),
            "sgst_rs": float(paise_to_rupees(inv.sgst_paise)),
            "igst_rs": float(paise_to_rupees(inv.igst_paise)),
        })

    # 2. HSN-wise Summary
    hsn_stmt = (
        select(
            InvoiceLine.hsn_code,
            Item.name.label("description"),
            Item.display_unit.label("uqc"),
            func.sum(InvoiceLine.qty).label("total_qty"),
            func.sum(InvoiceLine.taxable_paise).label("taxable_paise"),
            func.sum(InvoiceLine.cgst_paise).label("cgst_paise"),
            func.sum(InvoiceLine.sgst_paise).label("sgst_paise"),
            func.sum(InvoiceLine.igst_paise).label("igst_paise"),
        )
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .join(Item, Item.id == InvoiceLine.item_id)
        .where(Invoice.status == "POSTED")
        .group_by(InvoiceLine.hsn_code, Item.name, Item.display_unit)
    )
    if from_date:
        hsn_stmt = hsn_stmt.where(Invoice.invoice_date >= from_date)
    if to_date:
        hsn_stmt = hsn_stmt.where(Invoice.invoice_date <= to_date)

    hsn_res = (await db.execute(hsn_stmt)).all()

    hsn_rows = []
    for h in hsn_res:
        tot_val = h.taxable_paise + h.cgst_paise + h.sgst_paise + h.igst_paise
        hsn_rows.append({
            "hsn_code": h.hsn_code or "N/A",
            "description": h.description,
            "uqc": h.uqc.upper(),
            "total_qty": h.total_qty,
            "total_value_rs": float(paise_to_rupees(tot_val)),
            "taxable_rs": float(paise_to_rupees(h.taxable_paise)),
            "integrated_tax_rs": float(paise_to_rupees(h.igst_paise)),
            "central_tax_rs": float(paise_to_rupees(h.cgst_paise)),
            "state_tax_rs": float(paise_to_rupees(h.sgst_paise)),
        })

    # 3. GSTR-3B 3.1(a) Outward Taxable Supplies Summary
    gstr_3b_summary = {
        "nature_of_supplies": "(a) Outward taxable supplies (other than zero rated, nil rated and exempted)",
        "total_taxable_value_paise": tot_taxable,
        "total_taxable_value_rs": float(paise_to_rupees(tot_taxable)),
        "integrated_tax_paise": tot_igst,
        "integrated_tax_rs": float(paise_to_rupees(tot_igst)),
        "central_tax_paise": tot_cgst,
        "central_tax_rs": float(paise_to_rupees(tot_cgst)),
        "state_tax_paise": tot_sgst,
        "state_tax_rs": float(paise_to_rupees(tot_sgst)),
        "cess_rs": 0.0,
        "total_tax_paise": tot_cgst + tot_sgst + tot_igst,
        "total_tax_rs": float(paise_to_rupees(tot_cgst + tot_sgst + tot_igst)),
    }

    return {
        "report_name": "GST Summary (GSTR-1 & GSTR-3B)",
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "gstr_3b_table_3_1_a": gstr_3b_summary,
        "gstr_1_b2b_invoices": b2b_rows,
        "gstr_1_hsn_summary": hsn_rows,
    }


# ─────────────────────────────────────────────────────────────────────
# 5. PURCHASE REGISTER
# ─────────────────────────────────────────────────────────────────────

async def get_purchase_register_data(
    db: AsyncSession, from_date: Optional[date] = None, to_date: Optional[date] = None
) -> Dict[str, Any]:
    stmt = (
        select(Purchase)
        .options(selectinload(Purchase.supplier), selectinload(Purchase.lines).selectinload(PurchaseLine.item))
        .order_by(Purchase.purchase_date.desc(), Purchase.id.desc())
    )
    if from_date:
        stmt = stmt.where(Purchase.purchase_date >= from_date)
    if to_date:
        stmt = stmt.where(Purchase.purchase_date <= to_date)

    purchases = (await db.execute(stmt)).scalars().all()

    rows = []
    tot_grand = 0

    for p in purchases:
        line_items_str = ", ".join(f"{pl.item.name} ({pl.qty_base} {pl.item.base_unit})" for pl in p.lines)
        p_val = sum(pl.value_paise for pl in p.lines)
        tot_grand += p_val

        rows.append({
            "purchase_id": p.id,
            "bill_no": p.bill_no or "N/A",
            "purchase_date": p.purchase_date.isoformat(),
            "supplier_name": p.supplier.name if p.supplier else "",
            "supplier_gstin": p.supplier.gstin or "N/A",
            "items_summary": line_items_str,
            "status": p.status,
            "total_value_paise": p_val,
            "total_value_rs": float(paise_to_rupees(p_val)),
        })

    return {
        "report_name": "Purchase Register",
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "summary": {
            "total_purchases": len(rows),
            "grand_total_paise": tot_grand,
            "grand_total_rs": float(paise_to_rupees(tot_grand)),
        },
        "rows": rows,
    }


# ─────────────────────────────────────────────────────────────────────
# 6. STOCK SUMMARY & RECONCILIATION REPORT
# ─────────────────────────────────────────────────────────────────────

async def get_stock_report_data(
    db: AsyncSession, from_date: Optional[date] = None, to_date: Optional[date] = None
) -> Dict[str, Any]:
    stmt = select(Item).options(selectinload(Item.balance), selectinload(Item.units)).where(Item.active.is_(True))
    items = (await db.execute(stmt)).scalars().all()

    rows = []
    for it in items:
        # Opening
        op_stmt = select(
            func.coalesce(func.sum(StockLedger.qty_base), 0),
            func.coalesce(func.sum(StockLedger.value_paise), 0),
        ).where(StockLedger.item_id == it.id, StockLedger.movement_type == "OPENING")
        op_qty, op_val = (await db.execute(op_stmt)).one()

        # Receipts (Purchases + Production Output)
        rec_stmt = select(
            func.coalesce(func.sum(StockLedger.qty_base), 0),
            func.coalesce(func.sum(StockLedger.value_paise), 0),
        ).where(StockLedger.item_id == it.id, StockLedger.movement_type.in_(["PURCHASE_RECEIPT", "PRODUCTION_OUTPUT", "SALES_RETURN"]))
        rec_qty, rec_val = (await db.execute(rec_stmt)).one()

        # Issues (Production Issue + Dispatch)
        iss_stmt = select(
            func.coalesce(func.sum(StockLedger.qty_base), 0),
            func.coalesce(func.sum(StockLedger.value_paise), 0),
        ).where(StockLedger.item_id == it.id, StockLedger.movement_type.in_(["PRODUCTION_ISSUE", "SALES_DISPATCH"]))
        iss_qty, iss_val = (await db.execute(iss_stmt)).one()

        # Adjustments
        adj_stmt = select(
            func.coalesce(func.sum(StockLedger.qty_base), 0),
            func.coalesce(func.sum(StockLedger.value_paise), 0),
        ).where(StockLedger.item_id == it.id, StockLedger.movement_type.in_(["ADJUSTMENT", "REVERSAL"]))
        adj_qty, adj_val = (await db.execute(adj_stmt)).one()

        # Factor to base
        f_stmt = select(ItemUnit.factor_to_base).where(ItemUnit.item_id == it.id, ItemUnit.unit == it.display_unit)
        factor = (await db.execute(f_stmt)).scalar_one_or_none() or 1

        closing_qty = (it.balance.qty_base if it.balance else 0)
        closing_val = (it.balance.value_paise if it.balance else 0)

        rows.append({
            "sku": it.sku,
            "name": it.name,
            "type": it.type,
            "base_unit": it.base_unit,
            "display_unit": it.display_unit,
            "factor_to_base": factor,
            "opening_qty_base": op_qty,
            "opening_qty_display": float(from_base_units(op_qty, factor)),
            "receipts_qty_base": rec_qty,
            "receipts_qty_display": float(from_base_units(rec_qty, factor)),
            "issues_qty_base": abs(iss_qty),
            "issues_qty_display": float(from_base_units(abs(iss_qty), factor)),
            "adjustments_qty_base": adj_qty,
            "adjustments_qty_display": float(from_base_units(adj_qty, factor)),
            "closing_qty_base": closing_qty,
            "closing_qty_display": float(from_base_units(closing_qty, factor)),
            "closing_value_paise": closing_val,
            "closing_value_rs": float(paise_to_rupees(closing_val)),
            "reorder_level_base": it.reorder_level_base,
            "is_low_stock": closing_qty <= it.reorder_level_base if it.reorder_level_base > 0 else False,
        })

    return {
        "report_name": "Stock Summary & Movement",
        "rows": rows,
    }


# ─────────────────────────────────────────────────────────────────────
# 7. PRODUCTION REPORT (VARIANCE & COST)
# ─────────────────────────────────────────────────────────────────────

async def get_production_report_data(
    db: AsyncSession, from_date: Optional[date] = None, to_date: Optional[date] = None
) -> Dict[str, Any]:
    stmt = (
        select(ProductionRun)
        .options(selectinload(ProductionRun.product), selectinload(ProductionRun.lines).selectinload(ProductionRunLine.item))
        .order_by(ProductionRun.run_date.desc(), ProductionRun.id.desc())
    )
    if from_date:
        stmt = stmt.where(ProductionRun.run_date >= from_date)
    if to_date:
        stmt = stmt.where(ProductionRun.run_date <= to_date)

    runs = (await db.execute(stmt)).scalars().all()

    run_rows = []
    for r in runs:
        yield_var_bp = 0
        yield_flagged = False
        if r.expected_output > 0 and r.actual_good_output is not None:
            diff = r.actual_good_output - r.expected_output
            yield_var_bp = int(round((diff / r.expected_output) * 10000))
            yield_flagged = abs(yield_var_bp) > (r.tolerance_bp or 300)

        lines_detail = []
        for l in r.lines:
            lines_detail.append({
                "sku": l.item.sku,
                "name": l.item.name,
                "planned_qty_base": l.planned_qty_base,
                "actual_qty_base": l.actual_qty_base,
                "wastage_qty_base": l.wastage_qty_base,
                "variance_bp": l.variance_bp or 0,
                "variance_pct": f"{(l.variance_bp or 0) / 100:.2f}%",
                "flagged": l.flagged or False,
            })

        run_rows.append({
            "run_no": r.run_no,
            "run_date": r.run_date.isoformat(),
            "product_name": r.product.name if r.product else "",
            "batch_factor": float(r.batch_factor),
            "expected_output": r.expected_output,
            "actual_good_output": r.actual_good_output,
            "yield_variance_bp": yield_var_bp,
            "yield_variance_pct": f"{yield_var_bp / 100:.2f}%",
            "yield_flagged": yield_flagged,
            "material_cost_rs": float(paise_to_rupees(r.material_cost_paise or 0)),
            "overheads_rs": float(paise_to_rupees((r.labour_paise or 0) + (r.power_gas_paise or 0) + (r.other_overhead_paise or 0))),
            "cost_per_packet_rs": float(paise_to_rupees(r.cost_per_packet_paise or 0)),
            "cost_per_packet_paise": r.cost_per_packet_paise,
            "lines": lines_detail,
        })

    return {
        "report_name": "Production & Variance Report",
        "rows": run_rows,
    }


# ─────────────────────────────────────────────────────────────────────
# 8. OUTSTANDING WITH AGEING REPORT
# ─────────────────────────────────────────────────────────────────────

async def get_all_customers_outstanding_data(db: AsyncSession, as_of: Optional[date] = None) -> Dict[str, Any]:
    from app.modules.sales.payments_router import get_customer_outstanding

    cust_stmt = select(Customer).where(Customer.active.is_(True)).order_by(Customer.name.asc())
    customers = (await db.execute(cust_stmt)).scalars().all()

    class DummyUser:
        id = 1
        role = "admin"

    rows = []
    tot_out = 0
    tot_0_30 = 0
    tot_31_60 = 0
    tot_61_90 = 0
    tot_90_plus = 0

    for c in customers:
        resp = await get_customer_outstanding(customer_id=c.id, as_of=as_of, db=db, current_user=DummyUser())
        tot_out += resp.total_outstanding_paise
        tot_0_30 += resp.bucket_0_30_paise
        tot_31_60 += resp.bucket_31_60_paise
        tot_61_90 += resp.bucket_61_90_paise
        tot_90_plus += resp.bucket_90_plus_paise

        rows.append({
            "customer_id": c.id,
            "customer_name": c.name,
            "credit_days": c.credit_days,
            "total_invoiced_rs": float(paise_to_rupees(resp.total_invoiced_paise)),
            "total_paid_rs": float(paise_to_rupees(resp.total_payments_paise)),
            "total_cn_rs": float(paise_to_rupees(resp.total_credit_notes_paise)),
            "outstanding_paise": resp.total_outstanding_paise,
            "outstanding_rs": float(paise_to_rupees(resp.total_outstanding_paise)),
            "bucket_0_30_rs": float(paise_to_rupees(resp.bucket_0_30_paise)),
            "bucket_31_60_rs": float(paise_to_rupees(resp.bucket_31_60_paise)),
            "bucket_61_90_rs": float(paise_to_rupees(resp.bucket_61_90_paise)),
            "bucket_90_plus_rs": float(paise_to_rupees(resp.bucket_90_plus_paise)),
        })

    return {
        "report_name": "Customer Outstanding with Ageing",
        "as_of_date": (as_of or date.today()).isoformat(),
        "summary": {
            "total_customers": len(rows),
            "total_outstanding_paise": tot_out,
            "total_outstanding_rs": float(paise_to_rupees(tot_out)),
            "total_bucket_0_30_rs": float(paise_to_rupees(tot_0_30)),
            "total_bucket_31_60_rs": float(paise_to_rupees(tot_31_60)),
            "total_bucket_61_90_rs": float(paise_to_rupees(tot_61_90)),
            "total_bucket_90_plus_rs": float(paise_to_rupees(tot_90_plus)),
        },
        "rows": rows,
    }
