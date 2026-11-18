"""Posting engine for all stock movements and inventory ledger transactions.

CRITICAL ARCHITECTURE RULES:
1. This is the ONLY place in the entire codebase that writes to `stock_ledger`.
2. Every business event runs in an atomic database transaction:
   validate -> write business document -> append ledger rows -> update item_balances & WAC -> write audit log.
3. No floats for money or quantities. Money = integer paise (BIGINT).
   Stock = integers in base units. Unit cost = NUMERIC(18,6).
"""
from datetime import datetime, date, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.audit import record_audit
from app.core.money import round_half_up, compute_line_value
from app.core.units import to_base_units, from_base_units
from app.models import (
    StockLedger,
    ItemBalance,
    Item,
    Purchase,
    PurchaseLine,
    ProductionRun,
    ProductionRunLine,
    Invoice,
    InvoiceLine,
    Dispatch,
    CreditNote,
    Order,
)


async def _get_or_create_balance(session: AsyncSession, item_id: int) -> ItemBalance:
    """Fetch item balance locked for update, creating if not present."""
    stmt = (
        select(ItemBalance)
        .where(ItemBalance.item_id == item_id)
        .with_for_update()
    )
    res = await session.execute(stmt)
    bal = res.scalar_one_or_none()
    if bal is None:
        bal = ItemBalance(item_id=item_id, qty_base=0, value_paise=0)
        session.add(bal)
        await session.flush()
    return bal


def _get_wac(balance: ItemBalance) -> Decimal:
    """Calculate moving weighted average cost in paise per base unit."""
    if balance.qty_base <= 0 or balance.value_paise <= 0:
        return Decimal("0.000000")
    return (Decimal(balance.value_paise) / Decimal(balance.qty_base)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )


# ─────────────────────────────────────────────────────────────────────
# 1. POST PURCHASE
# ─────────────────────────────────────────────────────────────────────

async def post_purchase(
    session: AsyncSession,
    supplier_id: int,
    purchase_date: date,
    bill_no: Optional[str],
    lines: List[Dict[str, Any]],
    posted_by: int,
) -> Purchase:
    """Post raw material or packaging purchase.

    Each line:
    {
        "item_id": int,
        "qty_base": int,
        "rate_paise_per_display_unit": int,
        "unit_cost": Decimal,  # paise per base unit
        "value_paise": int
    }
    """
    if not lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_PURCHASE", "message": "Purchase must contain at least one line", "details": None},
        )

    now = datetime.now(timezone.utc)

    # 1. Create Purchase business document
    purchase = Purchase(
        supplier_id=supplier_id,
        bill_no=bill_no,
        purchase_date=purchase_date,
        status="POSTED",
    )
    session.add(purchase)
    await session.flush()

    for line in lines:
        item_id = line["item_id"]
        qty_base = line["qty_base"]
        rate_display = line["rate_paise_per_display_unit"]
        unit_cost = Decimal(str(line["unit_cost"])).quantize(Decimal("0.000001"))
        value_paise = line["value_paise"]

        if qty_base <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_QUANTITY", "message": f"Purchase qty must be > 0, got {qty_base}", "details": None},
            )

        p_line = PurchaseLine(
            purchase_id=purchase.id,
            item_id=item_id,
            qty_base=qty_base,
            rate_paise_per_display_unit=rate_display,
            unit_cost=unit_cost,
            value_paise=value_paise,
        )
        session.add(p_line)

        # 2. Append StockLedger row
        ledger_entry = StockLedger(
            item_id=item_id,
            movement_type="PURCHASE_RECEIPT",
            qty_base=qty_base,
            unit_cost=unit_cost,
            value_paise=value_paise,
            source_type="PURCHASE",
            source_id=purchase.id,
            posted_by=posted_by,
            posted_at=now,
            note=f"Purchase bill #{bill_no or purchase.id}",
        )
        session.add(ledger_entry)

        # 3. Update ItemBalance & WAC
        bal = await _get_or_create_balance(session, item_id)
        bal.qty_base += qty_base
        bal.value_paise += value_paise

    await session.flush()

    # 4. Audit Log
    await record_audit(
        session=session,
        action="POST_PURCHASE",
        entity_type="purchases",
        entity_id=purchase.id,
        user_id=posted_by,
        after={"purchase_id": purchase.id, "lines_count": len(lines), "bill_no": bill_no},
    )

    return purchase


# ─────────────────────────────────────────────────────────────────────
# 2. POST PRODUCTION RUN
# ─────────────────────────────────────────────────────────────────────

async def post_production_run(
    session: AsyncSession,
    run_no: str,
    bom_id: int,
    product_id: int,
    run_date: date,
    batch_factor: Decimal,
    expected_output: int,
    actual_good_output: int,
    lines: List[Dict[str, Any]],
    labour_paise: int = 0,
    power_gas_paise: int = 0,
    other_overhead_paise: int = 0,
    tolerance_bp: int = 300,
    posted_by: Optional[int] = None,
) -> ProductionRun:
    """Post production run consuming raw materials/packaging and producing finished goods.

    Each line in lines:
    {
        "item_id": int,
        "planned_qty_base": int,
        "actual_qty_base": int,
        "wastage_qty_base": int,
        "variance_bp": int,
        "flagged": bool
    }
    """
    if actual_good_output <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_OUTPUT", "message": "Actual good output must be greater than 0", "details": None},
        )

    now = datetime.now(timezone.utc)

    # 1. Create ProductionRun record
    run = ProductionRun(
        run_no=run_no,
        bom_id=bom_id,
        product_id=product_id,
        run_date=run_date,
        batch_factor=batch_factor,
        expected_output=expected_output,
        actual_good_output=actual_good_output,
        status="POSTED",
        labour_paise=labour_paise,
        power_gas_paise=power_gas_paise,
        other_overhead_paise=other_overhead_paise,
        tolerance_bp=tolerance_bp,
        created_by=posted_by,
        posted_at=now,
    )
    session.add(run)
    await session.flush()

    total_material_cost_paise = 0

    # 2. Issue lines (raw materials and packaging)
    for line_spec in lines:
        item_id = line_spec["item_id"]
        actual_qty = line_spec["actual_qty_base"]

        bal = await _get_or_create_balance(session, item_id)
        if bal.qty_base < actual_qty:
            item_res = await session.execute(select(Item).where(Item.id == item_id))
            item_obj = item_res.scalar_one_or_none()
            sku = item_obj.sku if item_obj else str(item_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INSUFFICIENT_STOCK",
                    "message": f"Insufficient stock for item {sku}. Required: {actual_qty}, Available: {bal.qty_base}",
                    "details": None,
                },
            )

        wac = _get_wac(bal)
        line_value_paise = compute_line_value(actual_qty, wac)
        total_material_cost_paise += line_value_paise

        # Add Run Line
        run_line = ProductionRunLine(
            run_id=run.id,
            item_id=item_id,
            planned_qty_base=line_spec["planned_qty_base"],
            actual_qty_base=actual_qty,
            wastage_qty_base=line_spec.get("wastage_qty_base", 0),
            variance_bp=line_spec.get("variance_bp", 0),
            flagged=line_spec.get("flagged", False),
        )
        session.add(run_line)

        # Append StockLedger row for PRODUCTION_ISSUE
        issue_ledger = StockLedger(
            item_id=item_id,
            movement_type="PRODUCTION_ISSUE",
            qty_base=-actual_qty,  # signed negative
            unit_cost=wac,
            value_paise=-line_value_paise,  # signed negative
            source_type="PRODUCTION_RUN",
            source_id=run.id,
            posted_by=posted_by,
            posted_at=now,
            note=f"Issued to production run {run_no}",
        )
        session.add(issue_ledger)

        # Update balance
        bal.qty_base -= actual_qty
        bal.value_paise -= line_value_paise

    # 3. Finished Goods Receipt
    total_overheads = labour_paise + power_gas_paise + other_overhead_paise
    total_run_cost_paise = total_material_cost_paise + total_overheads
    cost_per_packet_paise = round_half_up(
        Decimal(total_run_cost_paise) / Decimal(actual_good_output)
    )

    run.material_cost_paise = total_material_cost_paise
    run.cost_per_packet_paise = cost_per_packet_paise

    fg_unit_cost = (
        Decimal(total_run_cost_paise) / Decimal(actual_good_output)
    ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    fg_ledger = StockLedger(
        item_id=product_id,
        movement_type="PRODUCTION_OUTPUT",
        qty_base=actual_good_output,
        unit_cost=fg_unit_cost,
        value_paise=total_run_cost_paise,
        source_type="PRODUCTION_RUN",
        source_id=run.id,
        posted_by=posted_by,
        posted_at=now,
        note=f"Output from production run {run_no}",
    )
    session.add(fg_ledger)

    fg_bal = await _get_or_create_balance(session, product_id)
    fg_bal.qty_base += actual_good_output
    fg_bal.value_paise += total_run_cost_paise

    await session.flush()

    # 4. Audit Log
    await record_audit(
        session=session,
        action="POST_PRODUCTION_RUN",
        entity_type="production_runs",
        entity_id=run.id,
        user_id=posted_by,
        after={
            "run_no": run_no,
            "good_output": actual_good_output,
            "material_cost_paise": total_material_cost_paise,
            "cost_per_packet_paise": cost_per_packet_paise,
        },
    )

    return run


# ─────────────────────────────────────────────────────────────────────
# 3. CANCEL PRODUCTION RUN
# ─────────────────────────────────────────────────────────────────────

async def cancel_production_run(
    session: AsyncSession,
    run_id: int,
    user_id: int,
    reason: str = "Production run cancelled",
) -> ProductionRun:
    """Cancel a posted production run and reverse all ledger movements."""
    stmt = (
        select(ProductionRun)
        .where(ProductionRun.id == run_id)
        .with_for_update()
    )
    res = await session.execute(stmt)
    run = res.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Production run not found", "details": None},
        )
    if run.status != "POSTED":
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_STATE", "message": f"Cannot cancel run with status '{run.status}'", "details": None},
        )

    # Fetch original ledger rows for this run
    ledger_stmt = select(StockLedger).where(
        StockLedger.source_type == "PRODUCTION_RUN",
        StockLedger.source_id == run.id,
    )
    ledger_rows = (await session.execute(ledger_stmt)).scalars().all()

    now = datetime.now(timezone.utc)

    # Reverse each ledger row
    for orig in ledger_rows:
        reversal = StockLedger(
            item_id=orig.item_id,
            movement_type="REVERSAL",
            qty_base=-orig.qty_base,  # invert sign
            unit_cost=orig.unit_cost,
            value_paise=-orig.value_paise,  # invert sign
            source_type="PRODUCTION_RUN",
            source_id=run.id,
            posted_by=user_id,
            posted_at=now,
            note=f"Reversal of run {run.run_no}: {reason}",
        )
        session.add(reversal)

        bal = await _get_or_create_balance(session, orig.item_id)
        bal.qty_base += (-orig.qty_base)
        bal.value_paise += (-orig.value_paise)

    run.status = "CANCELLED"
    await session.flush()

    await record_audit(
        session=session,
        action="CANCEL_PRODUCTION_RUN",
        entity_type="production_runs",
        entity_id=run.id,
        user_id=user_id,
        before={"status": "POSTED"},
        after={"status": "CANCELLED", "reason": reason},
    )

    return run


# ─────────────────────────────────────────────────────────────────────
# 4. POST DISPATCH
# ─────────────────────────────────────────────────────────────────────

async def post_dispatch(
    session: AsyncSession,
    invoice_id: int,
    dispatched_by: int,
) -> Dispatch:
    """Post sales dispatch for an invoiced order, relieving finished goods stock at WAC."""
    inv_stmt = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .with_for_update()
    )
    invoice = (await session.execute(inv_stmt)).scalar_one_or_none()
    if not invoice:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Invoice not found", "details": None},
        )
    if invoice.status != "POSTED":
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_STATE", "message": f"Cannot dispatch invoice with status '{invoice.status}'", "details": None},
        )

    # Check if already dispatched
    disp_existing = await session.execute(
        select(Dispatch).where(Dispatch.invoice_id == invoice_id)
    )
    if disp_existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail={"code": "ALREADY_DISPATCHED", "message": "Invoice has already been dispatched", "details": None},
        )

    # Fetch invoice lines
    lines_stmt = select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)
    lines = (await session.execute(lines_stmt)).scalars().all()

    now = datetime.now(timezone.utc)

    # Relieve stock for each line
    for line in lines:
        bal = await _get_or_create_balance(session, line.item_id)
        if bal.qty_base < line.qty:
            item_res = await session.execute(select(Item).where(Item.id == line.item_id))
            item_obj = item_res.scalar_one_or_none()
            sku = item_obj.sku if item_obj else str(line.item_id)
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INSUFFICIENT_STOCK",
                    "message": f"Insufficient stock for item {sku}. Required: {line.qty}, Available: {bal.qty_base}",
                    "details": None,
                },
            )

        wac = _get_wac(bal)
        dispatch_cost_paise = compute_line_value(line.qty, wac)

        ledger_row = StockLedger(
            item_id=line.item_id,
            movement_type="SALES_DISPATCH",
            qty_base=-line.qty,  # signed negative
            unit_cost=wac,
            value_paise=-dispatch_cost_paise,  # signed negative
            source_type="INVOICE",
            source_id=invoice.id,
            posted_by=dispatched_by,
            posted_at=now,
            note=f"Dispatch for invoice {invoice.invoice_no}",
        )
        session.add(ledger_row)

        bal.qty_base -= line.qty
        bal.value_paise -= dispatch_cost_paise

    dispatch = Dispatch(
        invoice_id=invoice.id,
        dispatched_at=now,
        dispatched_by=dispatched_by,
    )
    session.add(dispatch)

    # Update order status to DISPATCHED
    if invoice.order_id:
        order_stmt = select(Order).where(Order.id == invoice.order_id)
        order = (await session.execute(order_stmt)).scalar_one_or_none()
        if order:
            order.status = "DISPATCHED"

    await session.flush()

    await record_audit(
        session=session,
        action="POST_DISPATCH",
        entity_type="invoices",
        entity_id=invoice.id,
        user_id=dispatched_by,
        after={"dispatch_id": dispatch.id, "invoice_no": invoice.invoice_no},
    )

    return dispatch


# ─────────────────────────────────────────────────────────────────────
# 5. POST CREDIT NOTE
# ─────────────────────────────────────────────────────────────────────

async def post_credit_note(
    session: AsyncSession,
    invoice_id: int,
    cn_no: str,
    reason: str,
    user_id: int,
) -> CreditNote:
    """Issue a credit note to cancel an invoice, returning stock if dispatched."""
    inv_stmt = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .with_for_update()
    )
    invoice = (await session.execute(inv_stmt)).scalar_one_or_none()
    if not invoice:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Invoice not found", "details": None},
        )
    if invoice.status == "CANCELLED":
        raise HTTPException(
            status_code=400,
            detail={"code": "ALREADY_CANCELLED", "message": "Invoice is already cancelled", "details": None},
        )

    # Check if dispatched
    disp_res = await session.execute(
        select(Dispatch).where(Dispatch.invoice_id == invoice_id)
    )
    was_dispatched = disp_res.scalar_one_or_none() is not None

    now = datetime.now(timezone.utc)

    # If dispatched, return stock via SALES_RETURN
    if was_dispatched:
        lines_stmt = select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)
        lines = (await session.execute(lines_stmt)).scalars().all()

        for line in lines:
            bal = await _get_or_create_balance(session, line.item_id)
            wac = _get_wac(bal)
            return_value_paise = compute_line_value(line.qty, wac)

            ret_ledger = StockLedger(
                item_id=line.item_id,
                movement_type="SALES_RETURN",
                qty_base=line.qty,  # positive return
                unit_cost=wac,
                value_paise=return_value_paise,
                source_type="CREDIT_NOTE",
                source_id=invoice.id,
                posted_by=user_id,
                posted_at=now,
                note=f"Sales return for CN {cn_no} on invoice {invoice.invoice_no}",
            )
            session.add(ret_ledger)

            bal.qty_base += line.qty
            bal.value_paise += return_value_paise

    # Create credit note record
    cn = CreditNote(
        cn_no=cn_no,
        invoice_id=invoice.id,
        reason=reason,
        taxable_paise=invoice.taxable_paise,
        cgst_paise=invoice.cgst_paise,
        sgst_paise=invoice.sgst_paise,
        igst_paise=invoice.igst_paise,
        total_paise=invoice.total_paise,
    )
    session.add(cn)

    # Cancel invoice
    invoice.status = "CANCELLED"
    await session.flush()

    await record_audit(
        session=session,
        action="POST_CREDIT_NOTE",
        entity_type="credit_notes",
        entity_id=cn.id,
        user_id=user_id,
        after={"cn_no": cn_no, "invoice_no": invoice.invoice_no, "was_dispatched": was_dispatched},
    )

    return cn


# ─────────────────────────────────────────────────────────────────────
# 6. POST ADJUSTMENT
# ─────────────────────────────────────────────────────────────────────

async def post_adjustment(
    session: AsyncSession,
    item_id: int,
    qty_base: int,
    reason: str,
    user_id: int,
    unit_cost: Optional[Decimal] = None,
) -> StockLedger:
    """Post manual stock adjustment with mandatory reason."""
    if not reason or not reason.strip():
        raise HTTPException(
            status_code=400,
            detail={"code": "REASON_REQUIRED", "message": "Adjustment reason is mandatory", "details": None},
        )
    if qty_base == 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "ZERO_QUANTITY", "message": "Adjustment quantity cannot be 0", "details": None},
        )

    bal = await _get_or_create_balance(session, item_id)
    if qty_base < 0 and bal.qty_base < abs(qty_base):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INSUFFICIENT_STOCK",
                "message": f"Cannot adjust down by {abs(qty_base)}, available: {bal.qty_base}",
                "details": None,
            },
        )

    if unit_cost is None:
        cost = _get_wac(bal)
    else:
        cost = Decimal(str(unit_cost)).quantize(Decimal("0.000001"))

    val_paise = compute_line_value(abs(qty_base), cost)
    signed_val = val_paise if qty_base > 0 else -val_paise

    now = datetime.now(timezone.utc)

    ledger_entry = StockLedger(
        item_id=item_id,
        movement_type="ADJUSTMENT",
        qty_base=qty_base,
        unit_cost=cost,
        value_paise=signed_val,
        source_type="ADJUSTMENT",
        source_id=0,
        posted_by=user_id,
        posted_at=now,
        note=reason,
    )
    session.add(ledger_entry)

    bal.qty_base += qty_base
    bal.value_paise += signed_val

    await session.flush()

    await record_audit(
        session=session,
        action="POST_ADJUSTMENT",
        entity_type="stock_ledger",
        entity_id=ledger_entry.id,
        user_id=user_id,
        after={"item_id": item_id, "qty_base": qty_base, "reason": reason, "signed_val": signed_val},
    )

    return ledger_entry
