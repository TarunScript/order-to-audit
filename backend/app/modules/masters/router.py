"""Master data endpoints for items, customers, suppliers, BOMs, price list, and users."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, require_roles, get_password_hash
from app.core.database import get_db
from app.models import (
    User,
    Item,
    ItemUnit,
    Customer,
    Supplier,
    PriceList,
    Bom,
    BomLine,
    ItemBalance,
)
from app.modules.masters.schemas import (
    ItemCreate,
    ItemUpdate,
    ItemOut,
    ItemUnitBase,
    CustomerCreate,
    CustomerUpdate,
    CustomerOut,
    SupplierCreate,
    SupplierUpdate,
    SupplierOut,
    PriceListCreate,
    PriceListOut,
    BomCreate,
    BomOut,
    UserCreate,
    UserUpdate,
    UserProfileOut,
)

router = APIRouter(tags=["Masters"])

# ─────────────────────────────────────────────────────────────────────
# ITEMS
# ─────────────────────────────────────────────────────────────────────

@router.get("/items", response_model=List[ItemOut])
async def list_items(
    type: Optional[str] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner", "salesman")),
):
    stmt = select(Item).options(selectinload(Item.units))
    if active_only:
        stmt = stmt.where(Item.active.is_(True))
    if type:
        stmt = stmt.where(Item.type == type)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    existing = await db.execute(select(Item).where(Item.sku == payload.sku))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail={"code": "DUPLICATE_SKU", "message": f"SKU '{payload.sku}' already exists", "details": None},
        )

    item = Item(
        sku=payload.sku,
        name=payload.name,
        type=payload.type,
        base_unit=payload.base_unit,
        display_unit=payload.display_unit,
        hsn_code=payload.hsn_code,
        gst_rate_bp=payload.gst_rate_bp,
        reorder_level_base=payload.reorder_level_base,
        active=payload.active,
    )
    db.add(item)
    await db.flush()

    # Always ensure base unit is in item_units with factor 1
    has_base = False
    if payload.units:
        for u in payload.units:
            if u.unit == payload.base_unit:
                has_base = True
            unit_row = ItemUnit(item_id=item.id, unit=u.unit, factor_to_base=u.factor_to_base)
            db.add(unit_row)
    if not has_base:
        db.add(ItemUnit(item_id=item.id, unit=payload.base_unit, factor_to_base=1))

    # Initialize item_balances row
    bal = ItemBalance(item_id=item.id, qty_base=0, value_paise=0)
    db.add(bal)

    await db.commit()
    # reload
    stmt = select(Item).options(selectinload(Item.units)).where(Item.id == item.id)
    res = await db.execute(stmt)
    return res.scalar_one()


@router.get("/items/{item_id}", response_model=ItemOut)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    stmt = select(Item).options(selectinload(Item.units)).where(Item.id == item_id)
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Item not found", "details": None})
    return item


@router.patch("/items/{item_id}", response_model=ItemOut)
async def update_item(
    item_id: int,
    payload: ItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    stmt = select(Item).where(Item.id == item_id)
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Item not found", "details": None})

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(item, k, v)

    await db.commit()
    stmt = select(Item).options(selectinload(Item.units)).where(Item.id == item_id)
    res = await db.execute(stmt)
    return res.scalar_one()


@router.delete("/items/{item_id}")
async def soft_delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    stmt = select(Item).where(Item.id == item_id)
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Item not found", "details": None})
    item.active = False
    await db.commit()
    return {"status": "success", "message": f"Item {item.sku} deactivated"}


# ─────────────────────────────────────────────────────────────────────
# CUSTOMERS
# ─────────────────────────────────────────────────────────────────────

@router.get("/customers", response_model=List[CustomerOut])
async def list_customers(
    active_only: bool = True,
    salesman_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "auditor", "owner", "salesman")),
):
    stmt = select(Customer)
    if active_only:
        stmt = stmt.where(Customer.active.is_(True))
    if current_user.role == "salesman":
        # PRD rule: salesman can only see their own assigned customers
        stmt = stmt.where(Customer.salesman_id == current_user.id)
    elif salesman_id:
        stmt = stmt.where(Customer.salesman_id == salesman_id)

    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    cust = Customer(**payload.model_dump())
    db.add(cust)
    await db.commit()
    await db.refresh(cust)
    return cust


@router.get("/customers/{customer_id}", response_model=CustomerOut)
async def get_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "auditor", "owner", "salesman")),
):
    stmt = select(Customer).where(Customer.id == customer_id)
    if current_user.role == "salesman":
        stmt = stmt.where(Customer.salesman_id == current_user.id)
    res = await db.execute(stmt)
    cust = res.scalar_one_or_none()
    if not cust:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Customer not found", "details": None})
    return cust


@router.patch("/customers/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    stmt = select(Customer).where(Customer.id == customer_id)
    res = await db.execute(stmt)
    cust = res.scalar_one_or_none()
    if not cust:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Customer not found", "details": None})

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(cust, k, v)

    await db.commit()
    await db.refresh(cust)
    return cust


@router.delete("/customers/{customer_id}")
async def soft_delete_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    stmt = select(Customer).where(Customer.id == customer_id)
    res = await db.execute(stmt)
    cust = res.scalar_one_or_none()
    if not cust:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Customer not found", "details": None})
    cust.active = False
    await db.commit()
    return {"status": "success", "message": f"Customer {cust.name} deactivated"}


# ─────────────────────────────────────────────────────────────────────
# SUPPLIERS
# ─────────────────────────────────────────────────────────────────────

@router.get("/suppliers", response_model=List[SupplierOut])
async def list_suppliers(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    stmt = select(Supplier)
    if active_only:
        stmt = stmt.where(Supplier.active.is_(True))
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/suppliers", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    payload: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    supp = Supplier(**payload.model_dump())
    db.add(supp)
    await db.commit()
    await db.refresh(supp)
    return supp


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
async def get_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    stmt = select(Supplier).where(Supplier.id == supplier_id)
    res = await db.execute(stmt)
    supp = res.scalar_one_or_none()
    if not supp:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Supplier not found", "details": None})
    return supp


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
async def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    stmt = select(Supplier).where(Supplier.id == supplier_id)
    res = await db.execute(stmt)
    supp = res.scalar_one_or_none()
    if not supp:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Supplier not found", "details": None})

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(supp, k, v)

    await db.commit()
    await db.refresh(supp)
    return supp


@router.delete("/suppliers/{supplier_id}")
async def soft_delete_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    stmt = select(Supplier).where(Supplier.id == supplier_id)
    res = await db.execute(stmt)
    supp = res.scalar_one_or_none()
    if not supp:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Supplier not found", "details": None})
    supp.active = False
    await db.commit()
    return {"status": "success", "message": f"Supplier {supp.name} deactivated"}


# ─────────────────────────────────────────────────────────────────────
# PRICE LIST
# ─────────────────────────────────────────────────────────────────────

@router.get("/price-list", response_model=List[PriceListOut])
async def list_prices(
    item_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "salesman", "auditor", "owner")),
):
    stmt = select(PriceList).order_by(PriceList.effective_from.desc())
    if item_id:
        stmt = stmt.where(PriceList.item_id == item_id)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/price-list", response_model=PriceListOut, status_code=status.HTTP_201_CREATED)
async def create_price(
    payload: PriceListCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    pl = PriceList(**payload.model_dump())
    db.add(pl)
    await db.commit()
    await db.refresh(pl)
    return pl


# ─────────────────────────────────────────────────────────────────────
# BOMS
# ─────────────────────────────────────────────────────────────────────

@router.get("/boms", response_model=List[BomOut])
async def list_boms(
    product_item_id: Optional[int] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    stmt = select(Bom).options(selectinload(Bom.lines))
    if active_only:
        stmt = stmt.where(Bom.active.is_(True))
    if product_item_id:
        stmt = stmt.where(Bom.product_item_id == product_item_id)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/boms", response_model=BomOut, status_code=status.HTTP_201_CREATED)
async def create_bom(
    payload: BomCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    bom = Bom(
        product_item_id=payload.product_item_id,
        version=payload.version,
        yield_packets=payload.yield_packets,
        active=payload.active,
    )
    db.add(bom)
    await db.flush()

    for line in payload.lines:
        b_line = BomLine(bom_id=bom.id, item_id=line.item_id, qty_base=line.qty_base)
        db.add(b_line)

    await db.commit()
    stmt = select(Bom).options(selectinload(Bom.lines)).where(Bom.id == bom.id)
    res = await db.execute(stmt)
    return res.scalar_one()


@router.get("/boms/{bom_id}", response_model=BomOut)
async def get_bom(
    bom_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    stmt = select(Bom).options(selectinload(Bom.lines)).where(Bom.id == bom_id)
    res = await db.execute(stmt)
    bom = res.scalar_one_or_none()
    if not bom:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "BOM not found", "details": None})
    return bom


# ─────────────────────────────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=List[UserProfileOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "owner")),
):
    res = await db.execute(select(User))
    return res.scalars().all()


@router.post("/users", response_model=UserProfileOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    existing = await db.execute(select(User).where(User.username == payload.username))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail={"code": "DUPLICATE_USERNAME", "message": f"Username '{payload.username}' already exists", "details": None},
        )

    user = User(
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        full_name=payload.full_name,
        active=payload.active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserProfileOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found", "details": None})

    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        user.password_hash = get_password_hash(data.pop("password"))
    for k, v in data.items():
        setattr(user, k, v)

    await db.commit()
    await db.refresh(user)
    return user
