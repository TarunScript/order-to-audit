"""Purchases and Production Runs router."""
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, require_roles
from app.core.database import get_db
from app.core.money import round_half_up, rupees_to_paise, compute_line_value
from app.core.sequences import allocate_sequence
from app.core.units import to_base_units, from_base_units
from app.core.audit import record_audit
from app.models import (
    User,
    Item,
    ItemUnit,
    ItemBalance,
    Bom,
    BomLine,
    Supplier,
    Purchase,
    PurchaseLine,
    ProductionRun,
    ProductionRunLine,
    PriceList,
    Setting,
    StockLedger,
)
from app.posting.engine import (
    post_purchase,
    post_production_run,
    cancel_production_run,
    _get_or_create_balance,
    _get_wac,
)
from app.modules.production.schemas import (
    PurchaseCreate,
    PurchaseOut,
    PurchaseLineOut,
    ProductionRunCreate,
    ProductionRunOut,
    ProductionRunLineOut,
    OverheadsUpdate,
    ProductionRunCancelRequest,
    BomPrefillResponse,
    BomPrefillLine,
)

router = APIRouter(tags=["Purchases & Production"])


# ─────────────────────────────────────────────────────────────────────
# PURCHASES ENDPOINTS
# ─────────────────────────────────────────────────────────────────────

@router.post("/purchases", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    data: PurchaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production")),
):
    """Post raw material or packaging purchase receipt into stock and update WAC."""
    # Check supplier
    supp = await db.get(Supplier, data.supplier_id)
    if not supp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SUPPLIER_NOT_FOUND", "message": f"Supplier with ID {data.supplier_id} not found", "details": None},
        )

    purchase_date = data.purchase_date or date.today()
    prepared_lines = []

    for l_idx, line in enumerate(data.lines):
        item = await db.get(Item, line.item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ITEM_NOT_FOUND", "message": f"Item {line.item_id} not found", "details": None},
            )

        # Fetch unit conversion
        unit_name = line.unit or item.display_unit
        factor_stmt = select(ItemUnit.factor_to_base).where(
            ItemUnit.item_id == item.id, ItemUnit.unit == unit_name
        )
        factor = (await db.execute(factor_stmt)).scalar_one_or_none() or 1

        # Determine qty_base
        if line.qty_base is not None and line.qty_base > 0:
            qty_base = line.qty_base
        elif line.qty is not None and line.qty > 0:
            try:
                qty_base = to_base_units(line.qty, factor)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "INVALID_QUANTITY", "message": str(e), "details": None},
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_QUANTITY", "message": f"Line {l_idx + 1}: quantity must be positive", "details": None},
            )

        # Determine rate per display unit in paise
        display_factor_stmt = select(ItemUnit.factor_to_base).where(
            ItemUnit.item_id == item.id, ItemUnit.unit == item.display_unit
        )
        display_factor = (await db.execute(display_factor_stmt)).scalar_one_or_none() or factor

        if line.rate_paise_per_display_unit is not None:
            rate_paise = line.rate_paise_per_display_unit
        elif line.rate_rupees_per_display_unit is not None:
            rate_paise = rupees_to_paise(line.rate_rupees_per_display_unit)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_RATE", "message": f"Line {l_idx + 1}: rate must be provided", "details": None},
            )

        unit_cost = (Decimal(rate_paise) / Decimal(display_factor)).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        value_paise = compute_line_value(qty_base, unit_cost)

        prepared_lines.append({
            "item_id": item.id,
            "qty_base": qty_base,
            "rate_paise_per_display_unit": rate_paise,
            "unit_cost": unit_cost,
            "value_paise": value_paise,
        })

    purchase = await post_purchase(
        session=db,
        supplier_id=supp.id,
        purchase_date=purchase_date,
        bill_no=data.bill_no,
        lines=prepared_lines,
        posted_by=current_user.id,
    )
    await db.commit()

    return await get_purchase_by_id(purchase.id, db, current_user)


@router.get("/purchases", response_model=List[PurchaseOut])
async def list_purchases(
    supplier_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    """List all purchases with supplier name and line totals."""
    stmt = (
        select(Purchase)
        .options(selectinload(Purchase.supplier), selectinload(Purchase.lines).selectinload(PurchaseLine.item))
        .order_by(Purchase.id.desc())
    )
    if supplier_id:
        stmt = stmt.where(Purchase.supplier_id == supplier_id)

    purchases = (await db.execute(stmt)).scalars().all()

    result = []
    for p in purchases:
        lines_out = []
        tot_val = 0
        for pl in p.lines:
            tot_val += pl.value_paise
            # Get display factor
            f_stmt = select(ItemUnit.factor_to_base).where(
                ItemUnit.item_id == pl.item.id, ItemUnit.unit == pl.item.display_unit
            )
            factor = (await db.execute(f_stmt)).scalar_one_or_none() or 1
            lines_out.append(
                PurchaseLineOut(
                    id=pl.id,
                    item_id=pl.item_id,
                    sku=pl.item.sku,
                    item_name=pl.item.name,
                    display_unit=pl.item.display_unit,
                    base_unit=pl.item.base_unit,
                    qty_base=pl.qty_base,
                    qty_display=from_base_units(pl.qty_base, factor),
                    rate_paise_per_display_unit=pl.rate_paise_per_display_unit,
                    unit_cost=pl.unit_cost,
                    value_paise=pl.value_paise,
                )
            )

        result.append(
            PurchaseOut(
                id=p.id,
                supplier_id=p.supplier_id,
                supplier_name=p.supplier.name if p.supplier else "Unknown",
                bill_no=p.bill_no,
                purchase_date=p.purchase_date,
                status=p.status,
                total_value_paise=tot_val,
                lines=lines_out,
                created_at=p.created_at,
            )
        )
    return result


@router.get("/purchases/{purchase_id}", response_model=PurchaseOut)
async def get_purchase_by_id(
    purchase_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    """Get single purchase by ID."""
    stmt = (
        select(Purchase)
        .where(Purchase.id == purchase_id)
        .options(selectinload(Purchase.supplier), selectinload(Purchase.lines).selectinload(PurchaseLine.item))
    )
    p = (await db.execute(stmt)).scalar_one_or_none()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Purchase {purchase_id} not found", "details": None},
        )

    lines_out = []
    tot_val = 0
    for pl in p.lines:
        tot_val += pl.value_paise
        f_stmt = select(ItemUnit.factor_to_base).where(
            ItemUnit.item_id == pl.item.id, ItemUnit.unit == pl.item.display_unit
        )
        factor = (await db.execute(f_stmt)).scalar_one_or_none() or 1
        lines_out.append(
            PurchaseLineOut(
                id=pl.id,
                item_id=pl.item_id,
                sku=pl.item.sku,
                item_name=pl.item.name,
                display_unit=pl.item.display_unit,
                base_unit=pl.item.base_unit,
                qty_base=pl.qty_base,
                qty_display=from_base_units(pl.qty_base, factor),
                rate_paise_per_display_unit=pl.rate_paise_per_display_unit,
                unit_cost=pl.unit_cost,
                value_paise=pl.value_paise,
            )
        )

    return PurchaseOut(
        id=p.id,
        supplier_id=p.supplier_id,
        supplier_name=p.supplier.name if p.supplier else "Unknown",
        bill_no=p.bill_no,
        purchase_date=p.purchase_date,
        status=p.status,
        total_value_paise=tot_val,
        lines=lines_out,
        created_at=p.created_at,
    )


# ─────────────────────────────────────────────────────────────────────
# PRODUCTION RUNS PRE-FILL & FORM HELPERS
# ─────────────────────────────────────────────────────────────────────

@router.get("/production-runs/prefill", response_model=BomPrefillResponse)
async def prefill_production_run(
    bom_id: int,
    batch_factor: Decimal = Query(Decimal("1.0"), gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    """Pre-fill planned quantities and current stock balances for a given BOM and batch factor."""
    bom_stmt = (
        select(Bom)
        .where(Bom.id == bom_id)
        .options(selectinload(Bom.product), selectinload(Bom.lines).selectinload(BomLine.item))
    )
    bom = (await db.execute(bom_stmt)).scalar_one_or_none()
    if not bom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "BOM_NOT_FOUND", "message": f"BOM {bom_id} not found", "details": None},
        )

    expected_output = int(round(Decimal(bom.yield_packets) * batch_factor))
    lines_prefill = []

    for bl in bom.lines:
        item = bl.item
        planned_qty_base = int(round(Decimal(bl.qty_base) * batch_factor))

        # Get display factor
        f_stmt = select(ItemUnit.factor_to_base).where(
            ItemUnit.item_id == item.id, ItemUnit.unit == item.display_unit
        )
        factor = (await db.execute(f_stmt)).scalar_one_or_none() or 1

        # Current balance
        bal = await _get_or_create_balance(db, item.id)
        current_wac = _get_wac(bal)

        lines_prefill.append(
            BomPrefillLine(
                item_id=item.id,
                sku=item.sku,
                item_name=item.name,
                item_type=item.type,
                base_unit=item.base_unit,
                display_unit=item.display_unit,
                factor_to_base=factor,
                planned_qty_base=planned_qty_base,
                planned_qty_display=from_base_units(planned_qty_base, factor),
                available_qty_base=bal.qty_base,
                available_qty_display=from_base_units(bal.qty_base, factor),
                current_wac_paise=current_wac,
            )
        )

    return BomPrefillResponse(
        bom_id=bom.id,
        product_id=bom.product_item_id,
        product_sku=bom.product.sku,
        product_name=bom.product.name,
        batch_factor=batch_factor,
        expected_output=expected_output,
        lines=lines_prefill,
    )


# ─────────────────────────────────────────────────────────────────────
# PRODUCTION RUNS ENDPOINTS
# ─────────────────────────────────────────────────────────────────────

@router.post("/production-runs", response_model=ProductionRunOut, status_code=status.HTTP_201_CREATED)
async def create_production_run(
    data: ProductionRunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production")),
):
    """Post production run consuming raw materials/packaging and producing finished goods."""
    # 1. Fetch BOM
    bom_stmt = (
        select(Bom)
        .where(Bom.id == data.bom_id)
        .options(selectinload(Bom.lines).selectinload(BomLine.item), selectinload(Bom.product))
    )
    bom = (await db.execute(bom_stmt)).scalar_one_or_none()
    if not bom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "BOM_NOT_FOUND", "message": f"BOM {data.bom_id} not found", "details": None},
        )

    run_date = data.run_date or date.today()
    batch_factor = data.batch_factor
    expected_output = data.expected_output or int(round(Decimal(bom.yield_packets) * batch_factor))

    # 2. Get tolerance from setting or input
    if data.tolerance_bp is not None:
        tolerance_bp = data.tolerance_bp
    else:
        tol_setting = await db.execute(select(Setting.value).where(Setting.key == "tolerance_bp"))
        tol_val = tol_setting.scalar_one_or_none()
        tolerance_bp = int(tol_val) if tol_val else 300

    # Map input lines by item_id
    input_line_map = {}
    if data.lines:
        for il in data.lines:
            input_line_map[il.item_id] = il

    # 3. Build lines from BOM lines
    prepared_lines = []
    for bl in bom.lines:
        item = bl.item
        planned_qty_base = int(round(Decimal(bl.qty_base) * batch_factor))

        # Factor to base
        f_stmt = select(ItemUnit.factor_to_base).where(
            ItemUnit.item_id == item.id, ItemUnit.unit == item.display_unit
        )
        factor = (await db.execute(f_stmt)).scalar_one_or_none() or 1

        actual_qty_base = None
        wastage_qty_base = 0

        # Check explicit input line
        if item.id in input_line_map:
            il = input_line_map[item.id]
            if il.actual_qty_base is not None:
                actual_qty_base = il.actual_qty_base
            elif il.actual_qty is not None:
                actual_qty_base = to_base_units(il.actual_qty, factor)

            if il.wastage_qty_base is not None:
                wastage_qty_base = il.wastage_qty_base
            elif il.wastage_qty is not None:
                wastage_qty_base = to_base_units(il.wastage_qty, factor)

        # Fallbacks for packaging items if not explicitly provided
        if actual_qty_base is None:
            if "pouch" in item.name.lower() or "pouch" in item.sku.lower():
                damaged = data.damaged_pouches or 0
                actual_qty_base = data.actual_good_output + damaged
                wastage_qty_base = damaged
            elif "carton" in item.name.lower() or "carton" in item.sku.lower():
                if data.cartons_used is not None:
                    actual_qty_base = data.cartons_used
                else:
                    actual_qty_base = planned_qty_base
            else:
                # Default to planned if not provided
                actual_qty_base = planned_qty_base

        # Calculate variance in basis points
        if planned_qty_base > 0:
            diff = Decimal(actual_qty_base - planned_qty_base)
            var_dec = (diff / Decimal(planned_qty_base)) * Decimal("10000")
            variance_bp = int(round(var_dec))
        else:
            variance_bp = 0

        # Flag strictly greater than tolerance
        flagged = abs(variance_bp) > tolerance_bp

        prepared_lines.append({
            "item_id": item.id,
            "planned_qty_base": planned_qty_base,
            "actual_qty_base": actual_qty_base,
            "wastage_qty_base": wastage_qty_base,
            "variance_bp": variance_bp,
            "flagged": flagged,
        })

    # 4. Generate run_no
    run_no = data.run_no
    if not run_no:
        run_no = await allocate_sequence(db, "PR", target_date=run_date)

    # 5. Call posting engine
    run = await post_production_run(
        session=db,
        run_no=run_no,
        bom_id=bom.id,
        product_id=bom.product_item_id,
        run_date=run_date,
        batch_factor=batch_factor,
        expected_output=expected_output,
        actual_good_output=data.actual_good_output,
        lines=prepared_lines,
        labour_paise=data.labour_paise or 0,
        power_gas_paise=data.power_gas_paise or 0,
        other_overhead_paise=data.other_overhead_paise or 0,
        tolerance_bp=tolerance_bp,
        posted_by=current_user.id,
    )
    await db.commit()

    return await get_production_run_by_id(run.id, db, current_user)


@router.get("/production-runs", response_model=List[ProductionRunOut])
async def list_production_runs(
    product_id: Optional[int] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    """List production runs with costing and variance details."""
    stmt = (
        select(ProductionRun)
        .options(
            selectinload(ProductionRun.product),
            selectinload(ProductionRun.lines).selectinload(ProductionRunLine.item),
        )
        .order_by(ProductionRun.id.desc())
    )
    if product_id:
        stmt = stmt.where(ProductionRun.product_id == product_id)
    if status:
        stmt = stmt.where(ProductionRun.status == status)

    runs = (await db.execute(stmt)).scalars().all()
    results = []
    for r in runs:
        out = await _build_production_run_out(r, db)
        results.append(out)
    return results


@router.get("/production-runs/{run_id}", response_model=ProductionRunOut)
async def get_production_run_by_id(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    """Get single production run with planned vs actual, variances, and cost breakdown."""
    stmt = (
        select(ProductionRun)
        .where(ProductionRun.id == run_id)
        .options(
            selectinload(ProductionRun.product),
            selectinload(ProductionRun.lines).selectinload(ProductionRunLine.item),
        )
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Production run {run_id} not found", "details": None},
        )
    return await _build_production_run_out(run, db)


@router.patch("/production-runs/{run_id}/overheads", response_model=ProductionRunOut)
async def update_production_run_overheads(
    run_id: int,
    data: OverheadsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production")),
):
    """Update overheads on a posted production run and recalculate cost per packet."""
    stmt = (
        select(ProductionRun)
        .where(ProductionRun.id == run_id)
        .with_for_update()
        .options(
            selectinload(ProductionRun.product),
            selectinload(ProductionRun.lines).selectinload(ProductionRunLine.item),
        )
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Production run {run_id} not found", "details": None},
        )
    if run.status != "POSTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": f"Cannot update overheads on run with status {run.status}", "details": None},
        )

    before_state = {
        "labour_paise": run.labour_paise,
        "power_gas_paise": run.power_gas_paise,
        "other_overhead_paise": run.other_overhead_paise,
        "cost_per_packet_paise": run.cost_per_packet_paise,
    }

    if data.labour_paise is not None:
        run.labour_paise = data.labour_paise
    if data.power_gas_paise is not None:
        run.power_gas_paise = data.power_gas_paise
    if data.other_overhead_paise is not None:
        run.other_overhead_paise = data.other_overhead_paise

    total_overheads = run.labour_paise + run.power_gas_paise + run.other_overhead_paise
    material_cost = run.material_cost_paise or 0
    total_cost = material_cost + total_overheads

    if run.actual_good_output and run.actual_good_output > 0:
        run.cost_per_packet_paise = round_half_up(
            Decimal(total_cost) / Decimal(run.actual_good_output)
        )

    await db.flush()

    await record_audit(
        session=db,
        action="UPDATE_OVERHEADS",
        entity_type="production_runs",
        entity_id=run.id,
        user_id=current_user.id,
        before=before_state,
        after={
            "labour_paise": run.labour_paise,
            "power_gas_paise": run.power_gas_paise,
            "other_overhead_paise": run.other_overhead_paise,
            "cost_per_packet_paise": run.cost_per_packet_paise,
        },
    )
    await db.commit()

    return await _build_production_run_out(run, db)


@router.post("/production-runs/{run_id}/cancel", response_model=ProductionRunOut)
async def cancel_run(
    run_id: int,
    data: ProductionRunCancelRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production")),
):
    """Cancel a posted production run and reverse all stock ledger movements."""
    reason = data.reason if data and data.reason else "Production run cancelled"
    run = await cancel_production_run(
        session=db,
        run_id=run_id,
        user_id=current_user.id,
        reason=reason,
    )
    await db.commit()
    return await get_production_run_by_id(run.id, db, current_user)


# ─────────────────────────────────────────────────────────────────────
# HELPER TO BUILD DETAILED RUN OUTPUT
# ─────────────────────────────────────────────────────────────────────

async def _build_production_run_out(run: ProductionRun, db: AsyncSession) -> ProductionRunOut:
    """Build response model with calculated variances, costs, and margins."""
    # Yield variance
    yield_var_bp = None
    yield_flagged = None
    if run.expected_output > 0 and run.actual_good_output is not None:
        diff = Decimal(run.actual_good_output - run.expected_output)
        yield_var_bp = int(round((diff / Decimal(run.expected_output)) * Decimal("10000")))
        yield_flagged = abs(yield_var_bp) > (run.tolerance_bp or 300)

    # Overhead totals
    total_overheads = run.labour_paise + run.power_gas_paise + run.other_overhead_paise
    material_cost = run.material_cost_paise or 0
    total_cost = material_cost + total_overheads

    # Selling price for finished product
    price_stmt = (
        select(PriceList.price_paise)
        .where(PriceList.item_id == run.product_id)
        .order_by(PriceList.effective_from.desc())
        .limit(1)
    )
    price_res = await db.execute(price_stmt)
    selling_price = price_res.scalar_one_or_none()

    margin_per_packet = None
    if selling_price is not None and run.cost_per_packet_paise is not None:
        margin_per_packet = selling_price - run.cost_per_packet_paise

    # Lines output
    lines_out = []
    for l in run.lines:
        item = l.item
        f_stmt = select(ItemUnit.factor_to_base).where(
            ItemUnit.item_id == item.id, ItemUnit.unit == item.display_unit
        )
        factor = (await db.execute(f_stmt)).scalar_one_or_none() or 1

        # Fetch unit_cost and line_value from stock ledger issue row if available
        sl_stmt = (
            select(StockLedger.unit_cost, StockLedger.value_paise)
            .where(
                StockLedger.source_type == "PRODUCTION_RUN",
                StockLedger.source_id == run.id,
                StockLedger.item_id == item.id,
                StockLedger.movement_type == "PRODUCTION_ISSUE",
            )
            .limit(1)
        )
        sl_res = (await db.execute(sl_stmt)).one_or_none()
        unit_cost = sl_res[0] if sl_res else None
        line_val = abs(sl_res[1]) if sl_res else None

        actual_qty = l.actual_qty_base or 0
        wastage_qty = l.wastage_qty_base or 0

        lines_out.append(
            ProductionRunLineOut(
                id=l.id,
                item_id=l.item_id,
                sku=item.sku,
                item_name=item.name,
                item_type=item.type,
                base_unit=item.base_unit,
                display_unit=item.display_unit,
                planned_qty_base=l.planned_qty_base,
                planned_qty_display=from_base_units(l.planned_qty_base, factor),
                actual_qty_base=actual_qty,
                actual_qty_display=from_base_units(actual_qty, factor),
                wastage_qty_base=wastage_qty,
                wastage_qty_display=from_base_units(wastage_qty, factor),
                unit_cost=unit_cost,
                line_value_paise=line_val,
                variance_bp=l.variance_bp or 0,
                flagged=l.flagged or False,
            )
        )

    return ProductionRunOut(
        id=run.id,
        run_no=run.run_no,
        bom_id=run.bom_id,
        product_id=run.product_id,
        product_sku=run.product.sku if run.product else "",
        product_name=run.product.name if run.product else "",
        run_date=run.run_date,
        batch_factor=run.batch_factor,
        expected_output=run.expected_output,
        actual_good_output=run.actual_good_output,
        yield_variance_bp=yield_var_bp,
        yield_flagged=yield_flagged,
        status=run.status,
        tolerance_bp=run.tolerance_bp or 300,
        labour_paise=run.labour_paise,
        power_gas_paise=run.power_gas_paise,
        other_overhead_paise=run.other_overhead_paise,
        total_overheads_paise=total_overheads,
        material_cost_paise=material_cost,
        total_cost_paise=total_cost,
        cost_per_packet_paise=run.cost_per_packet_paise,
        selling_price_paise=selling_price,
        margin_per_packet_paise=margin_per_packet,
        created_by=run.created_by,
        posted_at=run.posted_at,
        created_at=run.created_at,
        lines=lines_out,
    )
