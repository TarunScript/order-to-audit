"""Payments and Customer Outstanding with Ageing Analysis."""
from datetime import date, datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, require_roles
from app.core.database import get_db
from app.core.audit import record_audit
from app.models import (
    User,
    Customer,
    Invoice,
    Payment,
    CreditNote,
)

router = APIRouter(tags=["Payments & Outstanding"])


class PaymentCreate(BaseModel):
    customer_id: int
    invoice_id: Optional[int] = None
    amount_paise: int = Field(gt=0)
    mode: str = Field(default="NEFT")
    reference: Optional[str] = None
    received_on: Optional[date] = None


class PaymentOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    invoice_id: Optional[int]
    invoice_no: Optional[str]
    amount_paise: int
    mode: str
    reference: Optional[str]
    received_on: date
    created_at: datetime


class InvoiceAgeingItem(BaseModel):
    invoice_id: int
    invoice_no: str
    invoice_date: date
    total_paise: int
    paid_paise: int
    credit_note_paise: int
    outstanding_paise: int
    days_old: int
    bucket: str


class CustomerOutstandingResponse(BaseModel):
    customer_id: int
    customer_name: str
    credit_days: int
    total_invoiced_paise: int
    total_credit_notes_paise: int
    total_payments_paise: int
    total_outstanding_paise: int
    bucket_0_30_paise: int
    bucket_31_60_paise: int
    bucket_61_90_paise: int
    bucket_90_plus_paise: int
    invoices: List[InvoiceAgeingItem]


# ─────────────────────────────────────────────────────────────────────
# PAYMENTS ENDPOINTS
# ─────────────────────────────────────────────────────────────────────

@router.post("/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
async def record_payment(
    data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Record payment received from a customer against an invoice or on account."""
    cust = await db.get(Customer, data.customer_id)
    if not cust:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CUSTOMER_NOT_FOUND", "message": f"Customer {data.customer_id} not found", "details": None},
        )

    inv = None
    if data.invoice_id:
        inv = await db.get(Invoice, data.invoice_id)
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "INVOICE_NOT_FOUND", "message": f"Invoice {data.invoice_id} not found", "details": None},
            )
        if inv.customer_id != cust.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "CUSTOMER_MISMATCH", "message": "Invoice does not belong to specified customer", "details": None},
            )

    received_on = data.received_on or date.today()

    payment = Payment(
        customer_id=cust.id,
        invoice_id=inv.id if inv else None,
        amount_paise=data.amount_paise,
        mode=data.mode.upper(),
        reference=data.reference,
        received_on=received_on,
    )
    db.add(payment)
    await db.flush()

    await record_audit(
        session=db,
        action="RECORD_PAYMENT",
        entity_type="payments",
        entity_id=payment.id,
        user_id=current_user.id,
        after={
            "customer_id": cust.id,
            "invoice_id": inv.id if inv else None,
            "amount_paise": data.amount_paise,
            "mode": data.mode,
            "received_on": received_on.isoformat(),
        },
    )
    await db.commit()

    return PaymentOut(
        id=payment.id,
        customer_id=cust.id,
        customer_name=cust.name,
        invoice_id=payment.invoice_id,
        invoice_no=inv.invoice_no if inv else None,
        amount_paise=payment.amount_paise,
        mode=payment.mode,
        reference=payment.reference,
        received_on=payment.received_on,
        created_at=payment.created_at,
    )


@router.get("/payments", response_model=List[PaymentOut])
async def list_payments(
    customer_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "auditor", "owner")),
):
    """List recorded payments."""
    stmt = (
        select(Payment)
        .options(selectinload(Payment.customer), selectinload(Payment.invoice))
        .order_by(Payment.received_on.desc(), Payment.id.desc())
    )
    if customer_id:
        stmt = stmt.where(Payment.customer_id == customer_id)
    if invoice_id:
        stmt = stmt.where(Payment.invoice_id == invoice_id)
    if from_date:
        stmt = stmt.where(Payment.received_on >= from_date)
    if to_date:
        stmt = stmt.where(Payment.received_on <= to_date)

    payments = (await db.execute(stmt)).scalars().all()
    results = []
    for p in payments:
        results.append(
            PaymentOut(
                id=p.id,
                customer_id=p.customer_id,
                customer_name=p.customer.name if p.customer else "",
                invoice_id=p.invoice_id,
                invoice_no=p.invoice.invoice_no if p.invoice else None,
                amount_paise=p.amount_paise,
                mode=p.mode,
                reference=p.reference,
                received_on=p.received_on,
                created_at=p.created_at,
            )
        )
    return results


# ─────────────────────────────────────────────────────────────────────
# CUSTOMER OUTSTANDING & AGEING ANALYSIS
# ─────────────────────────────────────────────────────────────────────

@router.get("/customers/{customer_id}/outstanding", response_model=CustomerOutstandingResponse)
async def get_customer_outstanding(
    customer_id: int,
    as_of: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "salesman", "auditor", "owner")),
):
    """Calculate customer total outstanding (Invoiced - Credit Notes - Payments) and ageing buckets."""
    cust = await db.get(Customer, customer_id)
    if not cust:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CUSTOMER_NOT_FOUND", "message": f"Customer {customer_id} not found", "details": None},
        )
    if current_user.role == "salesman" and cust.salesman_id and cust.salesman_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Access denied to customer outstanding", "details": None},
        )

    target_date = as_of or date.today()

    # 1. Fetch all customer invoices
    inv_stmt = (
        select(Invoice)
        .where(Invoice.customer_id == cust.id)
        .order_by(Invoice.invoice_date.asc(), Invoice.id.asc())
    )
    invoices = (await db.execute(inv_stmt)).scalars().all()

    # 2. Fetch all credit notes for customer invoices
    cn_stmt = (
        select(CreditNote)
        .join(Invoice, CreditNote.invoice_id == Invoice.id)
        .where(Invoice.customer_id == cust.id)
    )
    credit_notes = (await db.execute(cn_stmt)).scalars().all()
    cn_by_invoice = {}
    for cn in credit_notes:
        cn_by_invoice[cn.invoice_id] = cn_by_invoice.get(cn.invoice_id, 0) + cn.total_paise

    # 3. Fetch all payments for customer
    pay_stmt = (
        select(Payment)
        .where(Payment.customer_id == cust.id)
        .order_by(Payment.received_on.asc(), Payment.id.asc())
    )
    payments = (await db.execute(pay_stmt)).scalars().all()

    # Direct invoice payments vs on-account payments
    direct_payments = {}
    unallocated_payments = 0

    for p in payments:
        if p.invoice_id:
            direct_payments[p.invoice_id] = direct_payments.get(p.invoice_id, 0) + p.amount_paise
        else:
            unallocated_payments += p.amount_paise

    # Calculate totals
    total_invoiced = sum(i.total_paise for i in invoices)
    total_credit_notes = sum(cn.total_paise for cn in credit_notes)
    total_payments = sum(p.amount_paise for p in payments)
    total_outstanding = total_invoiced - total_credit_notes - total_payments

    # Bucket counters
    b_0_30 = 0
    b_31_60 = 0
    b_61_90 = 0
    b_90_plus = 0

    invoice_ageing_items = []

    # Allocate unallocated payments FIFO across invoices
    remaining_unallocated = unallocated_payments

    for inv in invoices:
        cn_amount = cn_by_invoice.get(inv.id, 0)
        direct_paid = direct_payments.get(inv.id, 0)

        # Net after credit notes and direct payments
        net_after_direct = max(0, inv.total_paise - cn_amount - direct_paid)

        # Apply unallocated payments FIFO
        fifo_applied = 0
        if remaining_unallocated > 0 and net_after_direct > 0:
            fifo_applied = min(remaining_unallocated, net_after_direct)
            remaining_unallocated -= fifo_applied

        total_paid_for_inv = direct_paid + fifo_applied
        inv_outstanding = max(0, inv.total_paise - cn_amount - total_paid_for_inv)

        # Days old
        days_old = max(0, (target_date - inv.invoice_date).days)
        if days_old <= 30:
            bucket = "0-30"
            b_0_30 += inv_outstanding
        elif days_old <= 60:
            bucket = "31-60"
            b_31_60 += inv_outstanding
        elif days_old <= 90:
            bucket = "61-90"
            b_61_90 += inv_outstanding
        else:
            bucket = "90+"
            b_90_plus += inv_outstanding

        invoice_ageing_items.append(
            InvoiceAgeingItem(
                invoice_id=inv.id,
                invoice_no=inv.invoice_no,
                invoice_date=inv.invoice_date,
                total_paise=inv.total_paise,
                paid_paise=total_paid_for_inv,
                credit_note_paise=cn_amount,
                outstanding_paise=inv_outstanding,
                days_old=days_old,
                bucket=bucket,
            )
        )

    return CustomerOutstandingResponse(
        customer_id=cust.id,
        customer_name=cust.name,
        credit_days=cust.credit_days,
        total_invoiced_paise=total_invoiced,
        total_credit_notes_paise=total_credit_notes,
        total_payments_paise=total_payments,
        total_outstanding_paise=total_outstanding,
        bucket_0_30_paise=b_0_30,
        bucket_31_60_paise=b_31_60,
        bucket_61_90_paise=b_61_90,
        bucket_90_plus_paise=b_90_plus,
        invoices=invoice_ageing_items,
    )
