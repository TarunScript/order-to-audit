"""Sales module router: Orders, Stock Checks, Invoices, Dispatches, and Credit Notes."""
import os
import urllib.parse
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, require_roles
from app.core.database import get_db
from app.core.money import format_inr
from app.core.gst import calculate_line_tax, DEFAULT_SELLER_STATE_CODE
from app.core.sequences import allocate_sequence, get_current_fy
from app.core.audit import record_audit
from app.core.pdf import generate_invoice_html, render_pdf_from_html
from app.models import (
    User,
    Customer,
    Item,
    ItemUnit,
    ItemBalance,
    Order,
    OrderLine,
    Invoice,
    InvoiceLine,
    Dispatch,
    CreditNote,
    PriceList,
    CustomerPrice,
    Setting,
    StockLedger,
)
from app.posting.engine import (
    post_dispatch,
    post_credit_note,
    _get_or_create_balance,
)
from app.modules.sales.schemas import (
    OrderCreate,
    OrderUpdate,
    OrderOut,
    OrderLineOut,
    StockCheckResponse,
    StockCheckLineOut,
    OrderApproveRequest,
    OrderRejectRequest,
    InvoicePreviewResponse,
    InvoicePreviewLineOut,
    InvoiceCreate,
    InvoiceOut,
    InvoiceLineOut,
    DispatchOut,
    InvoiceCancelRequest,
    CreditNoteOut,
)

router = APIRouter(tags=["Sales & Billing"])


# ─────────────────────────────────────────────────────────────────────
# ORDERS ENDPOINTS
# ─────────────────────────────────────────────────────────────────────

@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("salesman", "admin")),
):
    """Submit a sales order. Idempotent by client_uuid."""
    # 1. Idempotency check
    existing_stmt = select(Order).where(Order.client_uuid == data.client_uuid)
    existing_order = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing_order:
        return await _build_order_out(existing_order.id, db)

    # 2. Fetch customer & validate salesman boundary
    cust = await db.get(Customer, data.customer_id)
    if not cust or not cust.active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CUSTOMER_NOT_FOUND", "message": f"Customer {data.customer_id} not found or inactive", "details": None},
        )

    if current_user.role == "salesman":
        if cust.salesman_id and cust.salesman_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "You can only place orders for your assigned customers", "details": None},
            )

    if not data.lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_ORDER", "message": "Order must contain at least one line item", "details": None},
        )

    # 3. Allocate order_no
    order_no = await allocate_sequence(db, "ORD")

    order = Order(
        order_no=order_no,
        client_uuid=data.client_uuid,
        customer_id=cust.id,
        salesman_id=current_user.id if current_user.role == "salesman" else (cust.salesman_id or current_user.id),
        status="SUBMITTED",
        notes=data.notes,
    )
    db.add(order)
    await db.flush()

    # 4. Resolve prices and save lines
    for line in data.lines:
        item = await db.get(Item, line.item_id)
        if not item or not item.active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ITEM_NOT_FOUND", "message": f"Item {line.item_id} not found", "details": None},
            )

        # Price determination: 1. CustomerPrice, 2. PriceList
        unit_price_paise = line.unit_price_paise
        if unit_price_paise is None:
            # Check customer override
            cp_stmt = select(CustomerPrice.price_paise).where(
                CustomerPrice.customer_id == cust.id, CustomerPrice.item_id == item.id
            )
            cp_res = (await db.execute(cp_stmt)).scalar_one_or_none()
            if cp_res is not None:
                unit_price_paise = cp_res
            else:
                # Check PriceList
                pl_stmt = (
                    select(PriceList.price_paise)
                    .where(PriceList.item_id == item.id, PriceList.effective_from <= date.today())
                    .order_by(PriceList.effective_from.desc())
                    .limit(1)
                )
                pl_res = (await db.execute(pl_stmt)).scalar_one_or_none()
                if pl_res is not None:
                    unit_price_paise = pl_res
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"code": "PRICE_MISSING", "message": f"No price configured for item {item.sku}", "details": None},
                    )

        order_line = OrderLine(
            order_id=order.id,
            item_id=item.id,
            qty=line.qty,
            unit_price_paise=unit_price_paise,
        )
        db.add(order_line)

    await db.flush()

    # 5. Audit log
    await record_audit(
        session=db,
        action="CREATE_ORDER",
        entity_type="orders",
        entity_id=order.id,
        user_id=current_user.id,
        after={"order_no": order.order_no, "customer_id": cust.id, "lines_count": len(data.lines)},
    )
    await db.commit()

    return await _build_order_out(order.id, db)


@router.get("/orders", response_model=List[OrderOut])
async def list_orders(
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("salesman", "admin", "auditor", "owner")),
):
    """List orders. Salesman only sees own orders; admin/auditor/owner sees all."""
    stmt = (
        select(Order)
        .options(
            selectinload(Order.customer),
            selectinload(Order.salesman),
            selectinload(Order.lines).selectinload(OrderLine.item),
        )
        .order_by(Order.id.desc())
    )

    if current_user.role == "salesman":
        stmt = stmt.where(Order.salesman_id == current_user.id)
    if status:
        stmt = stmt.where(Order.status == status)
    if customer_id:
        stmt = stmt.where(Order.customer_id == customer_id)
    if from_date:
        stmt = stmt.where(func.date(Order.created_at) >= from_date)
    if to_date:
        stmt = stmt.where(func.date(Order.created_at) <= to_date)

    orders = (await db.execute(stmt)).scalars().all()
    results = []
    for o in orders:
        out = await _build_order_out_from_obj(o, db)
        results.append(out)
    return results


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order_by_id(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("salesman", "admin", "auditor", "owner")),
):
    """Get single order details."""
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Order {order_id} not found", "details": None},
        )
    if current_user.role == "salesman" and order.salesman_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Access denied to order", "details": None},
        )
    return await _build_order_out(order_id, db)


@router.patch("/orders/{order_id}", response_model=OrderOut)
async def update_order(
    order_id: int,
    data: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Admin edits order quantities, approved quantities, or prices."""
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Order {order_id} not found", "details": None},
        )
    if order.status not in ["SUBMITTED", "APPROVED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": f"Cannot edit order in status '{order.status}'", "details": None},
        )

    before_snapshot = {"notes": order.notes}

    if data.notes is not None:
        order.notes = data.notes

    if data.lines:
        for l_in in data.lines:
            if l_in.id:
                ol = await db.get(OrderLine, l_in.id)
                if ol and ol.order_id == order.id:
                    if l_in.qty is not None:
                        ol.qty = l_in.qty
                    if l_in.unit_price_paise is not None:
                        ol.unit_price_paise = l_in.unit_price_paise
                    if l_in.approved_qty is not None:
                        ol.approved_qty = l_in.approved_qty
                    if l_in.approved_price_paise is not None:
                        ol.approved_price_paise = l_in.approved_price_paise

    await db.flush()
    await record_audit(
        session=db,
        action="EDIT_ORDER",
        entity_type="orders",
        entity_id=order.id,
        user_id=current_user.id,
        before=before_snapshot,
        after={"notes": order.notes},
    )
    await db.commit()
    return await _build_order_out(order_id, db)


# ─────────────────────────────────────────────────────────────────────
# STOCK CHECK & INVOICE PREVIEW
# ─────────────────────────────────────────────────────────────────────

@router.get("/orders/{order_id}/stock-check", response_model=StockCheckResponse)
async def get_order_stock_check(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "salesman", "owner")),
):
    """Stock check at approval: available = finished-goods ledger balance - quantity reserved by approved-but-undispatched orders."""
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.lines).selectinload(OrderLine.item))
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Order {order_id} not found", "details": None},
        )

    lines_out = []
    can_approve = True

    for ol in order.lines:
        item = ol.item
        requested_qty = ol.approved_qty if ol.approved_qty is not None else ol.qty

        # 1. Total ledger balance
        bal = await _get_or_create_balance(db, item.id)
        ledger_balance = bal.qty_base

        # 2. Reserved by other approved-but-undispatched orders (status in APPROVED, INVOICED)
        reserved_stmt = (
            select(
                func.coalesce(
                    func.sum(func.coalesce(OrderLine.approved_qty, OrderLine.qty)), 0
                )
            )
            .join(Order, Order.id == OrderLine.order_id)
            .where(
                Order.id != order.id,
                Order.status.in_(["APPROVED", "INVOICED"]),
                OrderLine.item_id == item.id,
            )
        )
        reserved_qty = (await db.execute(reserved_stmt)).scalar_one()

        available_qty = max(0, ledger_balance - reserved_qty)
        shortage_qty = max(0, requested_qty - available_qty)
        is_shortage = shortage_qty > 0

        if is_shortage:
            can_approve = False

        lines_out.append(
            StockCheckLineOut(
                item_id=item.id,
                sku=item.sku,
                item_name=item.name,
                requested_qty=requested_qty,
                available_qty=available_qty,
                shortage_qty=shortage_qty,
                is_shortage=is_shortage,
            )
        )

    return StockCheckResponse(
        order_id=order.id,
        order_no=order.order_no,
        can_approve=can_approve,
        lines=lines_out,
    )


@router.get("/orders/{order_id}/invoice-preview", response_model=InvoicePreviewResponse)
async def get_invoice_preview(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "salesman", "owner")),
):
    """Preview GST invoice tax split without posting anything."""
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.customer), selectinload(Order.lines).selectinload(OrderLine.item))
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Order {order_id} not found", "details": None},
        )

    cust = order.customer
    seller_state_setting = await db.execute(
        select(Setting.value).where(Setting.key == "seller_state_code")
    )
    s_val = seller_state_setting.scalar_one_or_none()
    seller_state_code = int(s_val) if s_val else DEFAULT_SELLER_STATE_CODE

    is_intra = cust.state_code == seller_state_code
    supply_type = "INTRA" if is_intra else "INTER"
    place_of_supply = cust.state_name

    tot_taxable = 0
    tot_cgst = 0
    tot_sgst = 0
    tot_igst = 0
    tot_grand = 0

    preview_lines = []
    for ol in order.lines:
        item = ol.item
        qty = ol.approved_qty if ol.approved_qty is not None else ol.qty
        rate = ol.approved_price_paise if ol.approved_price_paise is not None else ol.unit_price_paise
        line_taxable = qty * rate

        line_tax = calculate_line_tax(
            taxable_paise=line_taxable,
            customer_state_code=cust.state_code,
            seller_state_code=seller_state_code,
            gst_rate_bp=item.gst_rate_bp,
        )

        tot_taxable += line_tax.taxable_paise
        tot_cgst += line_tax.cgst_paise
        tot_sgst += line_tax.sgst_paise
        tot_igst += line_tax.igst_paise
        tot_grand += line_tax.total_paise

        preview_lines.append(
            InvoicePreviewLineOut(
                item_id=item.id,
                sku=item.sku,
                item_name=item.name,
                hsn_code=item.hsn_code,
                qty=qty,
                rate_paise=rate,
                taxable_paise=line_tax.taxable_paise,
                gst_rate_bp=item.gst_rate_bp,
                cgst_paise=line_tax.cgst_paise,
                sgst_paise=line_tax.sgst_paise,
                igst_paise=line_tax.igst_paise,
                total_paise=line_tax.total_paise,
            )
        )

    return InvoicePreviewResponse(
        order_id=order.id,
        customer_id=cust.id,
        customer_name=cust.name,
        customer_state_code=cust.state_code,
        supply_type=supply_type,
        place_of_supply=place_of_supply,
        taxable_paise=tot_taxable,
        cgst_paise=tot_cgst,
        sgst_paise=tot_sgst,
        igst_paise=tot_igst,
        total_paise=tot_grand,
        lines=preview_lines,
    )


# ─────────────────────────────────────────────────────────────────────
# ORDER APPROVE & REJECT
# ─────────────────────────────────────────────────────────────────────

@router.post("/orders/{order_id}/approve", response_model=OrderOut)
async def approve_order(
    order_id: int,
    data: Optional[OrderApproveRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Admin approves an order after verifying stock availability."""
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Order {order_id} not found", "details": None},
        )
    if order.status != "SUBMITTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": f"Cannot approve order in status '{order.status}'", "details": None},
        )

    # Apply any edits passed in approve request
    if data and data.lines:
        for l_in in data.lines:
            if l_in.id:
                ol = await db.get(OrderLine, l_in.id)
                if ol and ol.order_id == order.id:
                    if l_in.approved_qty is not None:
                        ol.approved_qty = l_in.approved_qty
                    if l_in.approved_price_paise is not None:
                        ol.approved_price_paise = l_in.approved_price_paise
        await db.flush()

    # Perform stock check
    stock_check = await get_order_stock_check(order.id, db, current_user)
    if not stock_check.can_approve:
        shortages = [
            f"{l.sku}: requested {l.requested_qty}, available {l.available_qty}, short {l.shortage_qty}"
            for l in stock_check.lines
            if l.is_shortage
        ]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INSUFFICIENT_STOCK",
                "message": f"Cannot approve order due to stock shortage: {'; '.join(shortages)}. Edit quantity down to available stock first.",
                "details": [l.model_dump() for l in stock_check.lines if l.is_shortage],
            },
        )

    # Set approved defaults for any lines not explicitly edited
    lines_stmt = select(OrderLine).where(OrderLine.order_id == order.id)
    lines = (await db.execute(lines_stmt)).scalars().all()
    for l in lines:
        if l.approved_qty is None:
            l.approved_qty = l.qty
        if l.approved_price_paise is None:
            l.approved_price_paise = l.unit_price_paise

    order.status = "APPROVED"
    await db.flush()

    await record_audit(
        session=db,
        action="APPROVE_ORDER",
        entity_type="orders",
        entity_id=order.id,
        user_id=current_user.id,
        before={"status": "SUBMITTED"},
        after={"status": "APPROVED"},
    )
    await db.commit()

    return await _build_order_out(order.id, db)


@router.post("/orders/{order_id}/reject", response_model=OrderOut)
async def reject_order(
    order_id: int,
    data: OrderRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Admin rejects an order with mandatory reason."""
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Order {order_id} not found", "details": None},
        )
    if order.status not in ["SUBMITTED", "APPROVED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": f"Cannot reject order in status '{order.status}'", "details": None},
        )

    order.status = "REJECTED"
    order.notes = f"{order.notes or ''} [Rejected: {data.reason}]".strip()
    await db.flush()

    await record_audit(
        session=db,
        action="REJECT_ORDER",
        entity_type="orders",
        entity_id=order.id,
        user_id=current_user.id,
        before={"status": "SUBMITTED"},
        after={"status": "REJECTED", "reason": data.reason},
    )
    await db.commit()

    return await _build_order_out(order.id, db)


# ─────────────────────────────────────────────────────────────────────
# INVOICES ENDPOINTS
# ─────────────────────────────────────────────────────────────────────

@router.post("/orders/{order_id}/invoice", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    order_id: int,
    data: Optional[InvoiceCreate] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Generate GST Tax Invoice for an approved order with FY sequential numbering and PDF generation."""
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .with_for_update()
        .options(selectinload(Order.customer), selectinload(Order.lines).selectinload(OrderLine.item))
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Order {order_id} not found", "details": None},
        )
    if order.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": f"Only APPROVED orders can be invoiced, current status is '{order.status}'", "details": None},
        )

    # Check if already invoiced
    existing_inv = await db.execute(select(Invoice).where(Invoice.order_id == order.id, Invoice.status == "POSTED"))
    if existing_inv.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "ALREADY_INVOICED", "message": "Order is already invoiced", "details": None},
        )

    invoice_date = data.invoice_date if data and data.invoice_date else date.today()
    fy = get_current_fy(invoice_date)
    invoice_no = await allocate_sequence(db, "INV", fy=fy, target_date=invoice_date)

    cust = order.customer
    seller_state_setting = await db.execute(select(Setting.value).where(Setting.key == "seller_state_code"))
    s_val = seller_state_setting.scalar_one_or_none()
    seller_state_code = int(s_val) if s_val else DEFAULT_SELLER_STATE_CODE

    is_intra = cust.state_code == seller_state_code
    supply_type = "INTRA" if is_intra else "INTER"
    place_of_supply = cust.state_name

    # Create Invoice record
    invoice = Invoice(
        invoice_no=invoice_no,
        fy=fy,
        order_id=order.id,
        customer_id=cust.id,
        supply_type=supply_type,
        place_of_supply=place_of_supply,
        taxable_paise=0,
        cgst_paise=0,
        sgst_paise=0,
        igst_paise=0,
        total_paise=0,
        status="POSTED",
        invoice_date=invoice_date,
    )
    db.add(invoice)
    await db.flush()

    tot_taxable = 0
    tot_cgst = 0
    tot_sgst = 0
    tot_igst = 0
    tot_grand = 0

    lines_for_pdf = []

    for ol in order.lines:
        item = ol.item
        qty = ol.approved_qty if ol.approved_qty is not None else ol.qty
        rate = ol.approved_price_paise if ol.approved_price_paise is not None else ol.unit_price_paise
        line_taxable = qty * rate

        line_tax = calculate_line_tax(
            taxable_paise=line_taxable,
            customer_state_code=cust.state_code,
            seller_state_code=seller_state_code,
            gst_rate_bp=item.gst_rate_bp,
        )

        inv_line = InvoiceLine(
            invoice_id=invoice.id,
            item_id=item.id,
            hsn_code=item.hsn_code,
            qty=qty,
            rate_paise=rate,
            taxable_paise=line_tax.taxable_paise,
            gst_rate_bp=item.gst_rate_bp,
            cgst_paise=line_tax.cgst_paise,
            sgst_paise=line_tax.sgst_paise,
            igst_paise=line_tax.igst_paise,
        )
        db.add(inv_line)

        tot_taxable += line_tax.taxable_paise
        tot_cgst += line_tax.cgst_paise
        tot_sgst += line_tax.sgst_paise
        tot_igst += line_tax.igst_paise
        tot_grand += line_tax.total_paise

        lines_for_pdf.append({
            "item_name": item.name,
            "sku": item.sku,
            "hsn_code": item.hsn_code,
            "qty": qty,
            "display_unit": item.display_unit,
            "rate_paise": rate,
            "taxable_paise": line_tax.taxable_paise,
            "gst_rate_bp": item.gst_rate_bp,
            "cgst_paise": line_tax.cgst_paise,
            "sgst_paise": line_tax.sgst_paise,
            "igst_paise": line_tax.igst_paise,
        })

    invoice.taxable_paise = tot_taxable
    invoice.cgst_paise = tot_cgst
    invoice.sgst_paise = tot_sgst
    invoice.igst_paise = tot_igst
    invoice.total_paise = tot_grand

    # Transition order status to INVOICED
    order.status = "INVOICED"
    await db.flush()

    # Generate PDF via WeasyPrint
    seller_name = (await db.execute(select(Setting.value).where(Setting.key == "company_name"))).scalar_one_or_none() or "Demo Snacks Pvt Ltd"
    seller_gstin = (await db.execute(select(Setting.value).where(Setting.key == "seller_gstin"))).scalar_one_or_none() or "33AABCD1234E1Z5"
    seller_addr = (await db.execute(select(Setting.value).where(Setting.key == "seller_address"))).scalar_one_or_none() or "Tamil Nadu"

    pdf_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../static/invoices"))
    sanitized_num = invoice_no.replace("/", "_")
    pdf_filename = f"{sanitized_num}.pdf"
    pdf_full_path = os.path.join(pdf_dir, pdf_filename)

    pdf_data = {
        "invoice_no": invoice_no,
        "fy": fy,
        "order_no": order.order_no,
        "invoice_date": invoice_date.isoformat(),
        "status": invoice.status,
        "supply_type": supply_type,
        "place_of_supply": place_of_supply,
        "seller": {
            "name": seller_name,
            "gstin": seller_gstin,
            "address": seller_addr,
            "state_name": "Tamil Nadu",
            "state_code": seller_state_code,
        },
        "customer": {
            "name": cust.name,
            "address": cust.address or "",
            "gstin": cust.gstin or "",
            "state_name": cust.state_name,
            "state_code": cust.state_code,
            "phone": cust.phone or "",
        },
        "lines": lines_for_pdf,
        "taxable_paise": tot_taxable,
        "cgst_paise": tot_cgst,
        "sgst_paise": tot_sgst,
        "igst_paise": tot_igst,
        "total_paise": tot_grand,
    }
    html_content = generate_invoice_html(pdf_data)
    render_pdf_from_html(html_content, pdf_full_path)

    invoice.pdf_path = pdf_full_path
    await db.flush()

    # Audit log
    await record_audit(
        session=db,
        action="CREATE_INVOICE",
        entity_type="invoices",
        entity_id=invoice.id,
        user_id=current_user.id,
        after={"invoice_no": invoice_no, "total_paise": tot_grand, "order_id": order.id},
    )
    await db.commit()

    return await _build_invoice_out(invoice.id, db)


@router.get("/invoices", response_model=List[InvoiceOut])
async def list_invoices(
    customer_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "auditor", "owner")),
):
    """List all GST invoices with customer details and dispatch status."""
    stmt = (
        select(Invoice)
        .options(
            selectinload(Invoice.customer),
            selectinload(Invoice.order),
            selectinload(Invoice.lines).selectinload(InvoiceLine.item),
        )
        .order_by(Invoice.id.desc())
    )
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if from_date:
        stmt = stmt.where(Invoice.invoice_date >= from_date)
    if to_date:
        stmt = stmt.where(Invoice.invoice_date <= to_date)

    invoices = (await db.execute(stmt)).scalars().all()
    results = []
    for inv in invoices:
        out = await _build_invoice_out_from_obj(inv, db)
        results.append(out)
    return results


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
async def get_invoice_by_id(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "auditor", "owner", "salesman")),
):
    """Get invoice details by ID."""
    return await _build_invoice_out(invoice_id, db)


@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "auditor", "owner", "salesman")),
):
    """Download or view invoice PDF generated by WeasyPrint."""
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Invoice not found", "details": None})

    if invoice.pdf_path and os.path.exists(invoice.pdf_path):
        return FileResponse(
            path=invoice.pdf_path,
            filename=f"{invoice.invoice_no.replace('/', '_')}.pdf",
            media_type="application/pdf",
        )

    # Re-generate if file missing on disk
    inv_out = await _build_invoice_out(invoice_id, db)
    # regenerate
    pdf_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../static/invoices"))
    sanitized_num = invoice.invoice_no.replace("/", "_")
    pdf_full_path = os.path.join(pdf_dir, f"{sanitized_num}.pdf")

    seller_name = (await db.execute(select(Setting.value).where(Setting.key == "company_name"))).scalar_one_or_none() or "Demo Snacks Pvt Ltd"
    seller_gstin = (await db.execute(select(Setting.value).where(Setting.key == "seller_gstin"))).scalar_one_or_none() or "33AABCD1234E1Z5"
    seller_addr = (await db.execute(select(Setting.value).where(Setting.key == "seller_address"))).scalar_one_or_none() or "Tamil Nadu"

    pdf_data = {
        "invoice_no": invoice.invoice_no,
        "fy": invoice.fy,
        "order_no": inv_out.order_no or "",
        "invoice_date": invoice.invoice_date.isoformat(),
        "status": invoice.status,
        "supply_type": invoice.supply_type,
        "place_of_supply": invoice.place_of_supply,
        "seller": {
            "name": seller_name,
            "gstin": seller_gstin,
            "address": seller_addr,
            "state_name": "Tamil Nadu",
            "state_code": 33,
        },
        "customer": {
            "name": inv_out.customer_name,
            "address": "",
            "gstin": inv_out.customer_gstin or "",
            "state_name": invoice.place_of_supply,
            "state_code": 33 if invoice.supply_type == "INTRA" else 29,
        },
        "lines": [l.model_dump() for l in inv_out.lines],
        "taxable_paise": invoice.taxable_paise,
        "cgst_paise": invoice.cgst_paise,
        "sgst_paise": invoice.sgst_paise,
        "igst_paise": invoice.igst_paise,
        "total_paise": invoice.total_paise,
    }
    render_pdf_from_html(generate_invoice_html(pdf_data), pdf_full_path)
    return FileResponse(path=pdf_full_path, filename=f"{sanitized_num}.pdf", media_type="application/pdf")


# ─────────────────────────────────────────────────────────────────────
# DISPATCH & CANCEL (CREDIT NOTE)
# ─────────────────────────────────────────────────────────────────────

@router.post("/invoices/{invoice_id}/dispatch", response_model=DispatchOut)
async def dispatch_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Record dispatch of an invoiced order, relieving finished goods inventory via posting engine."""
    dispatch = await post_dispatch(
        session=db,
        invoice_id=invoice_id,
        dispatched_by=current_user.id,
    )
    await db.commit()

    inv = await db.get(Invoice, invoice_id)
    return DispatchOut(
        id=dispatch.id,
        invoice_id=dispatch.invoice_id,
        invoice_no=inv.invoice_no if inv else str(invoice_id),
        dispatched_at=dispatch.dispatched_at,
        dispatched_by=dispatch.dispatched_by,
    )


@router.post("/invoices/{invoice_id}/cancel", response_model=CreditNoteOut)
async def cancel_invoice(
    invoice_id: int,
    data: InvoiceCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Cancel a posted invoice by issuing a Credit Note (CN/<FY>/<seq>) and returning stock if dispatched."""
    fy = get_current_fy(date.today())
    cn_no = await allocate_sequence(db, "CN", fy=fy)

    cn = await post_credit_note(
        session=db,
        invoice_id=invoice_id,
        cn_no=cn_no,
        reason=data.reason,
        user_id=current_user.id,
    )
    await db.commit()

    inv = await db.get(Invoice, invoice_id)
    return CreditNoteOut(
        id=cn.id,
        cn_no=cn.cn_no,
        invoice_id=cn.invoice_id,
        invoice_no=inv.invoice_no if inv else "",
        reason=cn.reason,
        taxable_paise=cn.taxable_paise,
        cgst_paise=cn.cgst_paise,
        sgst_paise=cn.sgst_paise,
        igst_paise=cn.igst_paise,
        total_paise=cn.total_paise,
        created_at=cn.created_at,
    )


# ─────────────────────────────────────────────────────────────────────
# HELPER BUILDERS
# ─────────────────────────────────────────────────────────────────────

async def _build_order_out(order_id: int, db: AsyncSession) -> OrderOut:
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.customer),
            selectinload(Order.salesman),
            selectinload(Order.lines).selectinload(OrderLine.item),
        )
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    return await _build_order_out_from_obj(order, db)


async def _build_order_out_from_obj(order: Order, db: AsyncSession) -> OrderOut:
    # Check if an invoice exists
    inv_stmt = select(Invoice.id, Invoice.invoice_no).where(Invoice.order_id == order.id, Invoice.status == "POSTED").limit(1)
    inv_row = (await db.execute(inv_stmt)).one_or_none()
    inv_id = inv_row[0] if inv_row else None
    inv_no = inv_row[1] if inv_row else None

    tot_paise = 0
    appr_tot_paise = 0
    has_appr = False

    lines_out = []
    for l in order.lines:
        line_total = l.qty * l.unit_price_paise
        tot_paise += line_total

        appr_total = None
        if l.approved_qty is not None and l.approved_price_paise is not None:
            has_appr = True
            appr_total = l.approved_qty * l.approved_price_paise
            appr_tot_paise += appr_total

        lines_out.append(
            OrderLineOut(
                id=l.id,
                item_id=l.item_id,
                sku=l.item.sku,
                item_name=l.item.name,
                display_unit=l.item.display_unit,
                qty=l.qty,
                unit_price_paise=l.unit_price_paise,
                line_total_paise=line_total,
                approved_qty=l.approved_qty,
                approved_price_paise=l.approved_price_paise,
                approved_total_paise=appr_total,
            )
        )

    return OrderOut(
        id=order.id,
        order_no=order.order_no,
        client_uuid=order.client_uuid,
        customer_id=order.customer_id,
        customer_name=order.customer.name if order.customer else "",
        customer_state_code=order.customer.state_code if order.customer else 33,
        customer_state_name=order.customer.state_name if order.customer else "",
        salesman_id=order.salesman_id,
        salesman_name=order.salesman.full_name if order.salesman else "",
        status=order.status,
        notes=order.notes,
        total_paise=tot_paise,
        approved_total_paise=appr_tot_paise if has_appr else None,
        lines=lines_out,
        invoice_id=inv_id,
        invoice_no=inv_no,
        created_at=order.created_at,
    )


async def _build_invoice_out(invoice_id: int, db: AsyncSession) -> InvoiceOut:
    stmt = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.customer),
            selectinload(Invoice.order),
            selectinload(Invoice.lines).selectinload(InvoiceLine.item),
        )
    )
    inv = (await db.execute(stmt)).scalar_one_or_none()
    return await _build_invoice_out_from_obj(inv, db)


async def _build_invoice_out_from_obj(inv: Invoice, db: AsyncSession) -> InvoiceOut:
    # Check dispatch
    disp_stmt = select(Dispatch.dispatched_at).where(Dispatch.invoice_id == inv.id).limit(1)
    disp_row = (await db.execute(disp_stmt)).scalar_one_or_none()

    # Check credit note
    cn_stmt = select(CreditNote.cn_no).where(CreditNote.invoice_id == inv.id).limit(1)
    cn_row = (await db.execute(cn_stmt)).scalar_one_or_none()

    # Share links
    msg = f"Tax Invoice {inv.invoice_no} from Demo Snacks Pvt Ltd. Amount: {format_inr(inv.total_paise)}"
    whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(msg)}"
    mailto_url = f"mailto:{inv.customer.phone or ''}?subject={urllib.parse.quote(f'Invoice {inv.invoice_no}')}&body={urllib.parse.quote(msg)}"

    lines_out = []
    for l in inv.lines:
        lines_out.append(
            InvoiceLineOut(
                id=l.id,
                item_id=l.item_id,
                sku=l.item.sku,
                item_name=l.item.name,
                hsn_code=l.hsn_code,
                qty=l.qty,
                rate_paise=l.rate_paise,
                taxable_paise=l.taxable_paise,
                gst_rate_bp=l.gst_rate_bp,
                cgst_paise=l.cgst_paise,
                sgst_paise=l.sgst_paise,
                igst_paise=l.igst_paise,
                total_paise=l.taxable_paise + l.cgst_paise + l.sgst_paise + l.igst_paise,
            )
        )

    return InvoiceOut(
        id=inv.id,
        invoice_no=inv.invoice_no,
        fy=inv.fy,
        order_id=inv.order_id,
        order_no=inv.order.order_no if inv.order else None,
        customer_id=inv.customer_id,
        customer_name=inv.customer.name if inv.customer else "",
        customer_gstin=inv.customer.gstin if inv.customer else None,
        supply_type=inv.supply_type,
        place_of_supply=inv.place_of_supply,
        taxable_paise=inv.taxable_paise,
        cgst_paise=inv.cgst_paise,
        sgst_paise=inv.sgst_paise,
        igst_paise=inv.igst_paise,
        total_paise=inv.total_paise,
        status=inv.status,
        invoice_date=inv.invoice_date,
        pdf_path=inv.pdf_path,
        whatsapp_url=whatsapp_url,
        mailto_url=mailto_url,
        dispatched_at=disp_row,
        credit_note_no=cn_row,
        lines=lines_out,
        created_at=inv.created_at,
    )
