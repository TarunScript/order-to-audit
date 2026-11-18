"""Owner and Executive Dashboard endpoint."""
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import require_roles
from app.core.database import get_db
from app.core.money import paise_to_rupees
from app.core.units import from_base_units
from app.models import (
    User,
    Order,
    OrderLine,
    Customer,
    Item,
    ItemBalance,
    ItemUnit,
    ProductionRun,
    ProductionRunLine,
    PriceList,
    Invoice,
)
from app.modules.sales.payments_router import get_customer_outstanding

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class TodaysOrdersCard(BaseModel):
    count: int
    total_paise: int
    total_rs: float


class PendingOrderSummary(BaseModel):
    id: int
    order_no: str
    customer_name: str
    total_paise: int
    created_at: datetime


class StockLevelItem(BaseModel):
    item_id: int
    sku: str
    name: str
    type: str
    display_unit: str
    closing_qty_display: float
    reorder_level_display: float
    is_low_stock: bool


class VarianceAlertItem(BaseModel):
    run_id: int
    run_no: str
    run_date: date
    product_name: str
    item_sku: str
    alert_type: str  # "YIELD" or "MATERIAL"
    message: str
    variance_bp: int
    variance_pct: str


class ProductCostCard(BaseModel):
    product_id: int
    sku: str
    name: str
    cost_per_packet_paise: Optional[int]
    cost_per_packet_rs: Optional[float]
    selling_price_paise: Optional[int]
    selling_price_rs: Optional[float]
    margin_paise: Optional[int]
    margin_rs: Optional[float]


class DebtorItem(BaseModel):
    customer_id: int
    customer_name: str
    credit_days: int
    outstanding_paise: int
    outstanding_rs: float
    oldest_bucket: str


class OwnerDashboardResponse(BaseModel):
    todays_orders: TodaysOrdersCard
    orders_pending_approval: List[PendingOrderSummary]
    pending_approval_count: int
    stock_levels: List[StockLevelItem]
    low_stock_count: int
    variance_alerts: List[VarianceAlertItem]
    open_alerts_count: int
    cost_per_packet: List[ProductCostCard]
    total_outstanding_paise: int
    total_outstanding_rs: float
    top_debtors: List[DebtorItem]


@router.get("", response_model=OwnerDashboardResponse)
async def get_owner_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "owner", "auditor")),
):
    """Owner & Executive Dashboard containing key business KPIs, stock levels, variance alerts, and top debtors."""
    today = date.today()

    # 1. Today's Orders
    todays_orders_stmt = (
        select(Order)
        .options(selectinload(Order.lines))
        .where(func.date(Order.created_at) == today)
    )
    todays_orders = (await db.execute(todays_orders_stmt)).scalars().all()
    today_count = len(todays_orders)
    today_total = 0
    for o in todays_orders:
        for l in o.lines:
            today_total += l.qty * l.unit_price_paise

    # 2. Orders Pending Approval
    pending_stmt = (
        select(Order)
        .options(selectinload(Order.customer), selectinload(Order.lines))
        .where(Order.status == "SUBMITTED")
        .order_by(Order.created_at.asc())
    )
    pending_orders = (await db.execute(pending_stmt)).scalars().all()
    pending_list = []
    for po in pending_orders:
        o_val = sum(l.qty * l.unit_price_paise for l in po.lines)
        pending_list.append(
            PendingOrderSummary(
                id=po.id,
                order_no=po.order_no,
                customer_name=po.customer.name if po.customer else "",
                total_paise=o_val,
                created_at=po.created_at,
            )
        )

    # 3. Stock Levels & Low Stock Markers
    items_stmt = select(Item).options(selectinload(Item.balance), selectinload(Item.units)).where(Item.active.is_(True))
    items = (await db.execute(items_stmt)).scalars().all()
    stock_levels = []
    low_stock_count = 0

    for it in items:
        f_stmt = select(ItemUnit.factor_to_base).where(ItemUnit.item_id == it.id, ItemUnit.unit == it.display_unit)
        factor = (await db.execute(f_stmt)).scalar_one_or_none() or 1
        qty_base = it.balance.qty_base if it.balance else 0
        is_low = (qty_base <= it.reorder_level_base) if it.reorder_level_base > 0 else False
        if is_low:
            low_stock_count += 1

        stock_levels.append(
            StockLevelItem(
                item_id=it.id,
                sku=it.sku,
                name=it.name,
                type=it.type,
                display_unit=it.display_unit,
                closing_qty_display=float(from_base_units(qty_base, factor)),
                reorder_level_display=float(from_base_units(it.reorder_level_base, factor)),
                is_low_stock=is_low,
            )
        )

    # 4. Open Variance Alerts (Runs with flagged lines or flagged yield)
    runs_stmt = (
        select(ProductionRun)
        .options(selectinload(ProductionRun.product), selectinload(ProductionRun.lines).selectinload(ProductionRunLine.item))
        .where(ProductionRun.status == "POSTED")
        .order_by(ProductionRun.run_date.desc(), ProductionRun.id.desc())
        .limit(20)
    )
    posted_runs = (await db.execute(runs_stmt)).scalars().all()
    alerts = []

    for r in posted_runs:
        # Check yield
        if r.expected_output > 0 and r.actual_good_output is not None:
            diff = r.actual_good_output - r.expected_output
            var_bp = int(round((diff / r.expected_output) * 10000))
            if abs(var_bp) > (r.tolerance_bp or 300):
                alerts.append(
                    VarianceAlertItem(
                        run_id=r.id,
                        run_no=r.run_no,
                        run_date=r.run_date,
                        product_name=r.product.name if r.product else "",
                        item_sku="YIELD",
                        alert_type="YIELD",
                        message=f"Yield variance {var_bp / 100:.2f}% exceeds tolerance { (r.tolerance_bp or 300) / 100:.1f}%",
                        variance_bp=var_bp,
                        variance_pct=f"{var_bp / 100:.2f}%",
                    )
                )

        # Check lines
        for l in r.lines:
            if l.flagged:
                alerts.append(
                    VarianceAlertItem(
                        run_id=r.id,
                        run_no=r.run_no,
                        run_date=r.run_date,
                        product_name=r.product.name if r.product else "",
                        item_sku=l.item.sku,
                        alert_type="MATERIAL",
                        message=f"{l.item.name} variance {(l.variance_bp or 0) / 100:.2f}% exceeds tolerance { (r.tolerance_bp or 300) / 100:.1f}%",
                        variance_bp=l.variance_bp or 0,
                        variance_pct=f"{(l.variance_bp or 0) / 100:.2f}%",
                    )
                )

    # 5. Cost Per Packet & Margin
    fg_items = [it for it in items if it.type == "FINISHED"]
    product_costs = []
    for fg in fg_items:
        price_stmt = (
            select(PriceList.price_paise)
            .where(PriceList.item_id == fg.id, PriceList.effective_from <= today)
            .order_by(PriceList.effective_from.desc())
            .limit(1)
        )
        price_val = (await db.execute(price_stmt)).scalar_one_or_none()

        latest_run_stmt = (
            select(ProductionRun.cost_per_packet_paise)
            .where(ProductionRun.product_id == fg.id, ProductionRun.status == "POSTED")
            .order_by(ProductionRun.run_date.desc(), ProductionRun.id.desc())
            .limit(1)
        )
        cost_val = (await db.execute(latest_run_stmt)).scalar_one_or_none()
        margin = (price_val - cost_val) if (price_val and cost_val) else None

        product_costs.append(
            ProductCostCard(
                product_id=fg.id,
                sku=fg.sku,
                name=fg.name,
                cost_per_packet_paise=cost_val,
                cost_per_packet_rs=float(paise_to_rupees(cost_val)) if cost_val else None,
                selling_price_paise=price_val,
                selling_price_rs=float(paise_to_rupees(price_val)) if price_val else None,
                margin_paise=margin,
                margin_rs=float(paise_to_rupees(margin)) if margin else None,
            )
        )

    # 6. Total Outstanding Dues & Top 5 Debtors
    cust_stmt = select(Customer).where(Customer.active.is_(True))
    all_custs = (await db.execute(cust_stmt)).scalars().all()

    class DummyUser:
        id = 1
        role = "admin"

    debtor_list = []
    tot_out_paise = 0

    for c in all_custs:
        out_res = await get_customer_outstanding(c.id, today, db, DummyUser())
        tot_out_paise += out_res.total_outstanding_paise
        if out_res.total_outstanding_paise > 0:
            # Determine oldest overdue bucket
            oldest_bucket = "0-30"
            if out_res.bucket_90_plus_paise > 0:
                oldest_bucket = "90+"
            elif out_res.bucket_61_90_paise > 0:
                oldest_bucket = "61-90"
            elif out_res.bucket_31_60_paise > 0:
                oldest_bucket = "31-60"

            debtor_list.append(
                DebtorItem(
                    customer_id=c.id,
                    customer_name=c.name,
                    credit_days=c.credit_days,
                    outstanding_paise=out_res.total_outstanding_paise,
                    outstanding_rs=float(paise_to_rupees(out_res.total_outstanding_paise)),
                    oldest_bucket=oldest_bucket,
                )
            )

    debtor_list.sort(key=lambda d: d.outstanding_paise, reverse=True)
    top_5_debtors = debtor_list[:5]

    return OwnerDashboardResponse(
        todays_orders=TodaysOrdersCard(
            count=today_count,
            total_paise=today_total,
            total_rs=float(paise_to_rupees(today_total)),
        ),
        orders_pending_approval=pending_list,
        pending_approval_count=len(pending_list),
        stock_levels=stock_levels,
        low_stock_count=low_stock_count,
        variance_alerts=alerts,
        open_alerts_count=len(alerts),
        cost_per_packet=product_costs,
        total_outstanding_paise=tot_out_paise,
        total_outstanding_rs=float(paise_to_rupees(tot_out_paise)),
        top_debtors=top_5_debtors,
    )
