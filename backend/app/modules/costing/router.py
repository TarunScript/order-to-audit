"""Costing module router."""
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import require_roles
from app.core.database import get_db
from app.models import Item, ProductionRun, PriceList, User

router = APIRouter(prefix="/costing", tags=["Costing"])


class ProductCostingSummary(BaseModel):
    product_id: int
    sku: str
    name: str
    valuation_method: str = "Moving Weighted Average Cost (WAC)"
    overhead_rule: str = "Direct allocation per run to good output packets"
    selling_price_paise: Optional[int]
    latest_cost_per_packet_paise: Optional[int]
    margin_per_packet_paise: Optional[int]
    total_runs_count: int


@router.get("/products", response_model=List[ProductCostingSummary])
async def get_products_costing(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    """Costing summary per finished good product."""
    items_stmt = select(Item).where(Item.type == "FINISHED", Item.active.is_(True))
    items = (await db.execute(items_stmt)).scalars().all()

    summaries = []
    for item in items:
        # Selling price
        price_stmt = (
            select(PriceList.price_paise)
            .where(PriceList.item_id == item.id)
            .order_by(PriceList.effective_from.desc())
            .limit(1)
        )
        selling_price = (await db.execute(price_stmt)).scalar_one_or_none()

        # Latest posted run
        run_stmt = (
            select(ProductionRun)
            .where(ProductionRun.product_id == item.id, ProductionRun.status == "POSTED")
            .order_by(ProductionRun.run_date.desc(), ProductionRun.id.desc())
        )
        runs = (await db.execute(run_stmt)).scalars().all()

        latest_run = runs[0] if runs else None
        latest_cost = latest_run.cost_per_packet_paise if latest_run else None
        margin = (selling_price - latest_cost) if (selling_price and latest_cost) else None

        summaries.append(
            ProductCostingSummary(
                product_id=item.id,
                sku=item.sku,
                name=item.name,
                selling_price_paise=selling_price,
                latest_cost_per_packet_paise=latest_cost,
                margin_per_packet_paise=margin,
                total_runs_count=len(runs),
            )
        )

    return summaries
