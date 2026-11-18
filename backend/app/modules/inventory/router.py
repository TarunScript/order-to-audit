"""Stock and inventory endpoints."""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, require_roles
from app.core.database import get_db
from app.core.units import from_base_units
from app.models import Item, ItemBalance, StockLedger, ItemUnit, User
from app.posting.engine import post_adjustment

router = APIRouter(prefix="/stock", tags=["Stock & Inventory"])


class StockSummaryItem(BaseModel):
    item_id: int
    sku: str
    name: str
    type: str
    base_unit: str
    display_unit: str
    factor_to_base: int
    closing_qty_base: int
    closing_qty_display: Decimal
    total_value_paise: int
    wac_paise_per_base_unit: Decimal
    wac_paise_per_display_unit: Decimal
    reorder_level_base: int
    is_low_stock: bool


class StockLedgerItem(BaseModel):
    id: int
    item_id: int
    sku: str
    item_name: str
    movement_type: str
    qty_base: int
    unit_cost: Optional[Decimal]
    value_paise: int
    source_type: str
    source_id: int
    posted_by: Optional[int]
    posted_at: datetime
    note: Optional[str]


class AdjustmentCreate(BaseModel):
    item_id: int
    qty_base: int
    reason: str = Field(min_length=3)
    unit_cost: Optional[Decimal] = None


class ReconcileItemResult(BaseModel):
    item_id: int
    sku: str
    name: str
    ledger_qty: int
    balance_qty: int
    qty_diff: int
    ledger_val_paise: int
    balance_val_paise: int
    val_diff_paise: int
    is_reconciled: bool


class ReconcileResponse(BaseModel):
    all_reconciled: bool
    total_items: int
    reconciled_count: int
    items: List[ReconcileItemResult]


@router.get("/summary", response_model=List[StockSummaryItem])
async def get_stock_summary(
    type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    """Stock summary for raw materials, packaging, and finished goods."""
    stmt = (
        select(Item, ItemBalance)
        .join(ItemBalance, Item.id == ItemBalance.item_id, isouter=True)
        .options(selectinload(Item.units))
        .where(Item.active.is_(True))
    )
    if type:
        stmt = stmt.where(Item.type == type)

    res = await db.execute(stmt)
    rows = res.all()

    summary = []
    for item, bal in rows:
        qty_base = bal.qty_base if bal else 0
        val_paise = bal.value_paise if bal else 0

        # Find factor to display unit
        factor = 1
        for u in item.units:
            if u.unit == item.display_unit:
                factor = u.factor_to_base
                break

        qty_display = from_base_units(qty_base, factor)
        wac_base = (
            (Decimal(val_paise) / Decimal(qty_base)).quantize(Decimal("0.000001"))
            if qty_base > 0
            else Decimal("0.000000")
        )
        wac_display = (wac_base * Decimal(factor)).quantize(Decimal("0.000001"))

        is_low = item.reorder_level_base > 0 and qty_base <= item.reorder_level_base

        summary.append(
            StockSummaryItem(
                item_id=item.id,
                sku=item.sku,
                name=item.name,
                type=item.type,
                base_unit=item.base_unit,
                display_unit=item.display_unit,
                factor_to_base=factor,
                closing_qty_base=qty_base,
                closing_qty_display=qty_display,
                total_value_paise=val_paise,
                wac_paise_per_base_unit=wac_base,
                wac_paise_per_display_unit=wac_display,
                reorder_level_base=item.reorder_level_base,
                is_low_stock=is_low,
            )
        )
    return summary


@router.get("/ledger", response_model=List[StockLedgerItem])
async def get_stock_ledger(
    item_id: Optional[int] = None,
    movement_type: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    """Retrieve filtered stock ledger movements."""
    stmt = (
        select(StockLedger, Item.sku, Item.name)
        .join(Item, StockLedger.item_id == Item.id)
        .order_by(StockLedger.posted_at.desc(), StockLedger.id.desc())
    )
    if item_id:
        stmt = stmt.where(StockLedger.item_id == item_id)
    if movement_type:
        stmt = stmt.where(StockLedger.movement_type == movement_type)
    if from_date:
        stmt = stmt.where(func.date(StockLedger.posted_at) >= from_date)
    if to_date:
        stmt = stmt.where(func.date(StockLedger.posted_at) <= to_date)

    stmt = stmt.limit(limit).offset(offset)
    res = await db.execute(stmt)
    rows = res.all()

    items = []
    for ledger, sku, name in rows:
        items.append(
            StockLedgerItem(
                id=ledger.id,
                item_id=ledger.item_id,
                sku=sku,
                item_name=name,
                movement_type=ledger.movement_type,
                qty_base=ledger.qty_base,
                unit_cost=ledger.unit_cost,
                value_paise=ledger.value_paise,
                source_type=ledger.source_type,
                source_id=ledger.source_id,
                posted_by=ledger.posted_by,
                posted_at=ledger.posted_at,
                note=ledger.note,
            )
        )
    return items


@router.post("/adjustments", status_code=status.HTTP_201_CREATED)
async def create_stock_adjustment(
    payload: AdjustmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Create manual stock adjustment via the posting engine."""
    entry = await post_adjustment(
        session=db,
        item_id=payload.item_id,
        qty_base=payload.qty_base,
        reason=payload.reason,
        user_id=current_user.id,
        unit_cost=payload.unit_cost,
    )
    await db.commit()
    return {
        "status": "success",
        "message": f"Adjustment posted: {payload.qty_base} units for item {payload.item_id}",
        "ledger_id": entry.id,
    }


@router.get("/reconcile", response_model=ReconcileResponse)
async def reconcile_stock(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    """Prove item_balances equals the exact sum of stock_ledger for all items."""
    # 1. Fetch all items
    items_stmt = select(Item).where(Item.active.is_(True)).order_by(Item.sku)
    items = (await db.execute(items_stmt)).scalars().all()

    # 2. Compute ledger sums per item
    ledger_sum_stmt = (
        select(
            StockLedger.item_id,
            func.coalesce(func.sum(StockLedger.qty_base), 0).label("sum_qty"),
            func.coalesce(func.sum(StockLedger.value_paise), 0).label("sum_val"),
        )
        .group_by(StockLedger.item_id)
    )
    ledger_sums = {row.item_id: (row.sum_qty, row.sum_val) for row in (await db.execute(ledger_sum_stmt)).all()}

    # 3. Fetch item balances
    balances_stmt = select(ItemBalance)
    balances = {bal.item_id: (bal.qty_base, bal.value_paise) for bal in (await db.execute(balances_stmt)).scalars().all()}

    results = []
    all_ok = True
    reconciled_count = 0

    for item in items:
        l_qty, l_val = ledger_sums.get(item.id, (0, 0))
        b_qty, b_val = balances.get(item.id, (0, 0))

        qty_diff = l_qty - b_qty
        val_diff = l_val - b_val
        is_rec = (qty_diff == 0 and val_diff == 0)

        if not is_rec:
            all_ok = False
        else:
            reconciled_count += 1

        results.append(
            ReconcileItemResult(
                item_id=item.id,
                sku=item.sku,
                name=item.name,
                ledger_qty=l_qty,
                balance_qty=b_qty,
                qty_diff=qty_diff,
                ledger_val_paise=l_val,
                balance_val_paise=b_val,
                val_diff_paise=val_diff,
                is_reconciled=is_rec,
            )
        )

    return ReconcileResponse(
        all_reconciled=all_ok,
        total_items=len(items),
        reconciled_count=reconciled_count,
        items=results,
    )
