"""Integration and unit tests for Posting Engine and Stock Ledger."""
import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


from app.core.database import Base
from app.models import (
    Item,
    ItemUnit,
    ItemBalance,
    Supplier,
    Customer,
    User,
    Bom,
    BomLine,
    Invoice,
    InvoiceLine,
    Order,
    StockLedger,
)
from app.posting.engine import (
    post_purchase,
    post_adjustment,
    post_production_run,
    cancel_production_run,
    post_dispatch,
    post_credit_note,
)


@pytest_asyncio.fixture
async def test_session():
    """Create in-memory SQLite async database session for isolated testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        # Create base test user
        user = User(
            username="admin_test",
            password_hash="secret",
            role="admin",
            full_name="Admin Tester",
            active=True,
        )
        session.add(user)

        # Create test supplier & customer
        supplier = Supplier(name="Test Supplier", active=True)
        customer = Customer(
            name="Retailer Test",
            type="RETAILER",
            state_code=33,
            state_name="Tamil Nadu",
            active=True,
        )
        session.add(supplier)
        session.add(customer)

        # Create Items
        flour = Item(
            sku="RM-FLOUR",
            name="Flour",
            type="RAW",
            base_unit="g",
            display_unit="kg",
            active=True,
        )
        oil = Item(
            sku="RM-OIL",
            name="Cooking Oil",
            type="RAW",
            base_unit="ml",
            display_unit="L",
            active=True,
        )
        fg_murukku = Item(
            sku="FG-MURUKKU",
            name="Murukku 200 g",
            type="FINISHED",
            base_unit="piece",
            display_unit="packet",
            active=True,
        )
        session.add_all([flour, oil, fg_murukku])
        await session.flush()

        # Initialize balances
        for it in [flour, oil, fg_murukku]:
            session.add(ItemBalance(item_id=it.id, qty_base=0, value_paise=0))

        await session.commit()
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_post_purchase_and_wac(test_session: AsyncSession):
    """Test purchase receipt updates stock ledger, balance, and WAC."""
    from sqlalchemy import select
    flour = (await test_session.execute(select(Item).where(Item.sku == "RM-FLOUR"))).scalar_one()
    supplier = (await test_session.execute(select(Supplier))).scalars().first()
    admin_user = (await test_session.execute(select(User))).scalars().first()

    # Initial opening: 100 kg flour @ ₹42/kg = 100,000 g, 420,000 paise (4.2 p/g)
    entry1 = StockLedger(
        item_id=flour.id,
        movement_type="OPENING",
        qty_base=100000,
        unit_cost=Decimal("4.200000"),
        value_paise=420000,
        source_type="OPENING",
        source_id=0,
        posted_by=admin_user.id,
    )
    test_session.add(entry1)
    bal = (await test_session.execute(select(ItemBalance).where(ItemBalance.item_id == flour.id))).scalar_one()
    bal.qty_base += 100000
    bal.value_paise += 420000
    await test_session.commit()

    # Purchase 60 kg flour at ₹45/kg (60,000 g, 270,000 paise, unit_cost = 4.5 p/g)
    purchase = await post_purchase(
        session=test_session,
        supplier_id=supplier.id,
        purchase_date=date(2026, 4, 1),
        bill_no="BILL-101",
        lines=[
            {
                "item_id": flour.id,
                "qty_base": 60000,
                "rate_paise_per_display_unit": 4500,
                "unit_cost": Decimal("4.500000"),
                "value_paise": 270000,
            }
        ],
        posted_by=admin_user.id,
    )
    await test_session.commit()

    # Verify balance & WAC
    await test_session.refresh(bal)
    assert bal.qty_base == 160000  # 160 kg = 160,000 g
    assert bal.value_paise == 690000  # 420,000 + 270,000 = 690,000 paise
    # WAC = 690000 / 160000 = 4.3125 paise/g = 43.125 paise/kg
    wac = Decimal(bal.value_paise) / Decimal(bal.qty_base)
    assert wac == Decimal("4.3125")


@pytest.mark.asyncio
async def test_post_adjustment(test_session: AsyncSession):
    """Test stock adjustments positive and negative."""
    from sqlalchemy import select
    flour = (await test_session.execute(select(Item).where(Item.sku == "RM-FLOUR"))).scalar_one()
    admin_user = (await test_session.execute(select(User))).scalars().first()

    # Initial stock via adjustment
    await post_adjustment(
        session=test_session,
        item_id=flour.id,
        qty_base=5000,
        reason="Stock audit surplus",
        user_id=admin_user.id,
        unit_cost=Decimal("4.000000"),
    )
    await test_session.commit()

    bal = (await test_session.execute(select(ItemBalance).where(ItemBalance.item_id == flour.id))).scalar_one()
    assert bal.qty_base == 5000
    assert bal.value_paise == 20000

    # Negative adjustment
    await post_adjustment(
        session=test_session,
        item_id=flour.id,
        qty_base=-1000,
        reason="Damage in storage",
        user_id=admin_user.id,
    )
    await test_session.commit()

    await test_session.refresh(bal)
    assert bal.qty_base == 4000
    assert bal.value_paise == 16000


@pytest.mark.asyncio
async def test_production_run_and_reversal(test_session: AsyncSession):
    """Test full production run posting and cancellation reversal."""
    from sqlalchemy import select
    flour = (await test_session.execute(select(Item).where(Item.sku == "RM-FLOUR"))).scalar_one()
    oil = (await test_session.execute(select(Item).where(Item.sku == "RM-OIL"))).scalar_one()
    fg = (await test_session.execute(select(Item).where(Item.sku == "FG-MURUKKU"))).scalar_one()
    admin_user = (await test_session.execute(select(User))).scalars().first()

    # Add initial stock
    bal_flour = (await test_session.execute(select(ItemBalance).where(ItemBalance.item_id == flour.id))).scalar_one()
    bal_flour.qty_base = 50000
    bal_flour.value_paise = 200000  # 4 p/g

    bal_oil = (await test_session.execute(select(ItemBalance).where(ItemBalance.item_id == oil.id))).scalar_one()
    bal_oil.qty_base = 20000
    bal_oil.value_paise = 280000  # 14 p/ml

    bal_fg = (await test_session.execute(select(ItemBalance).where(ItemBalance.item_id == fg.id))).scalar_one()
    bal_fg.qty_base = 0
    bal_fg.value_paise = 0

    # Create dummy BOM
    bom = Bom(product_item_id=fg.id, version=1, yield_packets=200, active=True)
    test_session.add(bom)
    await test_session.commit()

    # Post production run
    run = await post_production_run(
        session=test_session,
        run_no="PR-TEST-001",
        bom_id=bom.id,
        product_id=fg.id,
        run_date=date(2026, 4, 2),
        batch_factor=Decimal("1"),
        expected_output=200,
        actual_good_output=190,
        lines=[
            {
                "item_id": flour.id,
                "planned_qty_base": 40000,
                "actual_qty_base": 40000,
                "wastage_qty_base": 0,
                "variance_bp": 0,
                "flagged": False,
            },
            {
                "item_id": oil.id,
                "planned_qty_base": 10000,
                "actual_qty_base": 10000,
                "wastage_qty_base": 0,
                "variance_bp": 0,
                "flagged": False,
            },
        ],
        labour_paise=10000,  # ₹100
        power_gas_paise=5000,  # ₹50
        posted_by=admin_user.id,
    )
    await test_session.commit()

    # Check stock reductions
    await test_session.refresh(bal_flour)
    await test_session.refresh(bal_oil)
    await test_session.refresh(bal_fg)

    assert bal_flour.qty_base == 10000  # 50,000 - 40,000
    assert bal_oil.qty_base == 10000  # 20,000 - 10,000
    assert bal_fg.qty_base == 190

    # Total cost = (40,000 * 4) + (10,000 * 14) + 10,000 + 5,000 = 160,000 + 140,000 + 15,000 = 315,000 paise
    assert bal_fg.value_paise == 315000

    # Now cancel run and verify reversal
    await cancel_production_run(
        session=test_session,
        run_id=run.id,
        user_id=admin_user.id,
        reason="Test cancellation",
    )
    await test_session.commit()

    await test_session.refresh(bal_flour)
    await test_session.refresh(bal_oil)
    await test_session.refresh(bal_fg)

    assert bal_flour.qty_base == 50000
    assert bal_oil.qty_base == 20000
    assert bal_fg.qty_base == 0
    assert bal_fg.value_paise == 0


@pytest.mark.asyncio
async def test_reconciliation(test_session: AsyncSession):
    """Test that SUM(stock_ledger) perfectly matches item_balances for all items."""
    from sqlalchemy import select, func
    items = (await test_session.execute(select(Item))).scalars().all()

    for item in items:
        # Sum from ledger
        sum_stmt = select(
            func.coalesce(func.sum(StockLedger.qty_base), 0),
            func.coalesce(func.sum(StockLedger.value_paise), 0),
        ).where(StockLedger.item_id == item.id)
        res = (await test_session.execute(sum_stmt)).one()
        ledger_qty, ledger_val = res[0], res[1]

        # Balance cache
        bal = (await test_session.execute(select(ItemBalance).where(ItemBalance.item_id == item.id))).scalar_one()
        assert ledger_qty == bal.qty_base, f"Qty mismatch for item {item.sku}: ledger {ledger_qty} vs bal {bal.qty_base}"
        assert ledger_val == bal.value_paise, f"Val mismatch for item {item.sku}: ledger {ledger_val} vs bal {bal.value_paise}"
