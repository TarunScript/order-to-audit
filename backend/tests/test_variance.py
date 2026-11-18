"""Unit and integration tests for Milestone 4: Purchases, BOM, Production Runs, Variance, and Costing."""
from datetime import date
from decimal import Decimal
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.database import Base, get_db
from app.core.auth import get_password_hash, create_access_token
from app.main import app
from app.models import (
    User,
    Item,
    ItemUnit,
    ItemBalance,
    Supplier,
    Customer,
    Bom,
    BomLine,
    PriceList,
    StockLedger,
    Setting,
)


@pytest_asyncio.fixture
async def seeded_test_env():
    """Setup in-memory SQLite database populated with Section 10 seed data."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        # Settings
        session.add(Setting(key="tolerance_bp", value="300"))
        session.add(Setting(key="seller_state_code", value="33"))
        session.add(Setting(key="seller_gstin", value="33AABCD1234E1Z5"))

        # Users
        admin = User(username="admin", password_hash=get_password_hash("pass"), role="admin", full_name="Admin", active=True)
        prod = User(username="production", password_hash=get_password_hash("pass"), role="production", full_name="Prod", active=True)
        session.add_all([admin, prod])
        await session.flush()

        # Supplier
        supp = Supplier(name="Madurai Agro Traders", active=True)
        session.add(supp)

        # Items
        items_def = [
            ("RM-FLOUR", "Flour", "RAW", "g", "kg", 0, [("kg", 1000), ("g", 1)]),
            ("RM-OIL", "Cooking oil", "RAW", "ml", "L", 500, [("L", 1000), ("ml", 1)]),
            ("RM-SPICE", "Salt and spice mix", "RAW", "g", "kg", 500, [("kg", 1000), ("g", 1)]),
            ("PKG-POUCH-200", "200 g pouch", "PACKAGING", "piece", "piece", 1800, [("piece", 1)]),
            ("PKG-CARTON", "Carton", "PACKAGING", "piece", "piece", 1200, [("piece", 1)]),
            ("FG-MURUKKU-200", "Murukku 200 g", "FINISHED", "piece", "packet", 500, [("packet", 1), ("carton", 20)]),
        ]
        item_map = {}
        for sku, name, itype, b_unit, d_unit, gst_bp, units in items_def:
            item = Item(
                sku=sku,
                name=name,
                type=itype,
                base_unit=b_unit,
                display_unit=d_unit,
                gst_rate_bp=gst_bp,
                active=True,
            )
            session.add(item)
            await session.flush()
            item_map[sku] = item

            for u_name, fac in units:
                session.add(ItemUnit(item_id=item.id, unit=u_name, factor_to_base=fac))
            session.add(ItemBalance(item_id=item.id, qty_base=0, value_paise=0))

        # Price list for Murukku: ₹50.00 = 5000 paise
        session.add(PriceList(item_id=item_map["FG-MURUKKU-200"].id, price_paise=5000, effective_from=date(2026, 4, 1)))

        # BOM Murukku 200 g, yield 200 packets
        bom = Bom(product_item_id=item_map["FG-MURUKKU-200"].id, version=1, yield_packets=200, active=True)
        session.add(bom)
        await session.flush()

        bom_lines = [
            ("RM-FLOUR", 40000),
            ("RM-OIL", 10000),
            ("RM-SPICE", 1200),
            ("PKG-POUCH-200", 200),
            ("PKG-CARTON", 10),
        ]
        for sku, qty in bom_lines:
            session.add(BomLine(bom_id=bom.id, item_id=item_map[sku].id, qty_base=qty))

        # Opening balances from Section 10:
        # flour 100 kg at ₹42/kg (100,000 g, 420,000 paise)
        # oil 30 L at ₹140/L (30,000 ml, 420,000 paise)
        # spice 5 kg at ₹200/kg (5,000 g, 100,000 paise)
        # pouches 500 at ₹2.50 (500 piece, 125,000 paise)
        # cartons 30 at ₹15 (30 piece, 45,000 paise)
        # finished Murukku 50 packets (50 piece, 150,000 paise)
        opening_data = [
            ("RM-FLOUR", 100000, Decimal("4.200000"), 420000),
            ("RM-OIL", 30000, Decimal("14.000000"), 420000),
            ("RM-SPICE", 5000, Decimal("20.000000"), 100000),
            ("PKG-POUCH-200", 500, Decimal("250.000000"), 125000),
            ("PKG-CARTON", 30, Decimal("1500.000000"), 45000),
            ("FG-MURUKKU-200", 50, Decimal("3000.000000"), 150000),
        ]
        for sku, q, cost, val in opening_data:
            it = item_map[sku]
            session.add(
                StockLedger(
                    item_id=it.id,
                    movement_type="OPENING",
                    qty_base=q,
                    unit_cost=cost,
                    value_paise=val,
                    source_type="OPENING_BALANCE",
                    source_id=0,
                    posted_by=admin.id,
                )
            )
            # Update ItemBalance
            bal_stmt = await session.execute(
                session.query(ItemBalance).filter(ItemBalance.item_id == it.id)
                if hasattr(session, "query")
                else Base.metadata.tables["item_balances"].select().where(Base.metadata.tables["item_balances"].c.item_id == it.id)
            )
            from sqlalchemy import select
            ib = (await session.execute(select(ItemBalance).where(ItemBalance.item_id == it.id))).scalar_one()
            ib.qty_base = q
            ib.value_paise = val

        await session.commit()

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    yield {"session_maker": session_maker, "item_map": item_map, "supplier": supp, "bom": bom}
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_benchmark_steps_1_2_3_8(seeded_test_env):
    """Test Benchmark Steps 1, 2, 3, and 8 end-to-end via API."""
    env = seeded_test_env
    supplier = env["supplier"]
    bom = env["bom"]
    item_map = env["item_map"]

    token = create_access_token({"sub": "admin", "role": "admin", "user_id": 1})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── Step 1: Purchase 60 kg flour at ₹45/kg ────────────────────
        flour_id = item_map["RM-FLOUR"].id
        purch_resp = await ac.post(
            "/api/purchases",
            headers=headers,
            json={
                "supplier_id": supplier.id,
                "bill_no": "BILL-001",
                "purchase_date": "2026-04-01",
                "lines": [
                    {
                        "item_id": flour_id,
                        "qty": 60,
                        "unit": "kg",
                        "rate_paise_per_display_unit": 4500,  # ₹45/kg
                    }
                ],
            },
        )
        assert purch_resp.status_code == 201, purch_resp.text
        purch_data = purch_resp.json()
        assert len(purch_data["lines"]) == 1
        assert purch_data["lines"][0]["qty_base"] == 60000
        assert purch_data["lines"][0]["value_paise"] == 270000

        # Verify Flour WAC after purchase:
        # Total qty: 100,000 + 60,000 = 160,000 g
        # Total val: 420,000 + 270,000 = 690,000 paise
        # WAC = 690,000 / 160,000 = 4.3125 paise/g = 43125 paise/kg
        summary_resp = await ac.get("/api/stock/summary", headers=headers)
        assert summary_resp.status_code == 200
        flour_summary = next(s for s in summary_resp.json() if s["sku"] == "RM-FLOUR")
        assert flour_summary["closing_qty_base"] == 160000
        assert Decimal(flour_summary["wac_paise_per_base_unit"]) == Decimal("4.312500")

        # ── Step 2 & 3: Production Run ────────────────────────────────
        # Murukku 200 g, batch factor 1.
        # Issue flour 40 kg, oil 10.5 L, spice mix 1.2 kg.
        # Actual good output 188 packets, 6 pouches damaged (pouches used 194), 9 cartons used.
        oil_id = item_map["RM-OIL"].id
        spice_id = item_map["RM-SPICE"].id
        pouch_id = item_map["PKG-POUCH-200"].id
        carton_id = item_map["PKG-CARTON"].id

        run_resp = await ac.post(
            "/api/production-runs",
            headers=headers,
            json={
                "bom_id": bom.id,
                "batch_factor": 1.0,
                "run_date": "2026-04-02",
                "actual_good_output": 188,
                "damaged_pouches": 6,
                "cartons_used": 9,
                "lines": [
                    {"item_id": flour_id, "actual_qty": 40, "unit": "kg"},
                    {"item_id": oil_id, "actual_qty": 10.5, "unit": "L"},
                    {"item_id": spice_id, "actual_qty": 1.2, "unit": "kg"},
                    {"item_id": pouch_id, "actual_qty_base": 194, "wastage_qty_base": 6},
                    {"item_id": carton_id, "actual_qty_base": 9},
                ],
            },
        )
        assert run_resp.status_code == 201, run_resp.text
        run_data = run_resp.json()
        run_id = run_data["id"]

        # Assert Expected Variances & Flags:
        # Yield variance: 188 vs 200 = -6% (-600 bp), flagged True
        assert run_data["yield_variance_bp"] == -600
        assert run_data["yield_flagged"] is True

        lines_by_sku = {l["sku"]: l for l in run_data["lines"]}

        # Flour: 40 kg vs 40 kg planned -> 0% variance, NOT flagged
        assert lines_by_sku["RM-FLOUR"]["variance_bp"] == 0
        assert lines_by_sku["RM-FLOUR"]["flagged"] is False

        # Oil: 10.5 L vs 10 L planned -> +5% (+500 bp), flagged True (> 300 bp)
        assert lines_by_sku["RM-OIL"]["variance_bp"] == 500
        assert lines_by_sku["RM-OIL"]["flagged"] is True

        # Spice: 1.2 kg vs 1.2 kg planned -> 0% variance, NOT flagged
        assert lines_by_sku["RM-SPICE"]["variance_bp"] == 0
        assert lines_by_sku["RM-SPICE"]["flagged"] is False

        # Pouch: 194 vs 200 = -3% (-300 bp). | -300 | == 300 bp tolerance.
        # Rule: strictly greater! So NOT flagged!
        assert lines_by_sku["PKG-POUCH-200"]["variance_bp"] == -300
        assert lines_by_sku["PKG-POUCH-200"]["flagged"] is False

        # Carton: 9 vs 10 = -10% (-1000 bp), flagged True
        assert lines_by_sku["PKG-CARTON"]["variance_bp"] == -1000
        assert lines_by_sku["PKG-CARTON"]["flagged"] is True

        # Material cost of run:
        # flour: 40,000 * 4.3125 = 172,500
        # oil: 10,500 * 14.0 = 147,000
        # spice: 1,200 * 20.0 = 24,000
        # pouch: 194 * 2.50 = 48,500
        # carton: 9 * 15.00 = 13,500
        # Total material cost = 405,500 paise (₹4,055.00)
        assert run_data["material_cost_paise"] == 405500

        # Closing stock after run:
        # Flour: 160 - 40 = 120 kg (120,000 g)
        # Oil: 30 - 10.5 = 19.5 L (19,500 ml)
        # Spice: 5 - 1.2 = 3.8 kg (3,800 g)
        # Pouches: 500 - 194 = 306 piece
        # Cartons: 30 - 9 = 21 piece
        # FG: 50 opening + 188 output = 238 packets
        stock_resp = await ac.get("/api/stock/summary", headers=headers)
        stock_map = {s["sku"]: s["closing_qty_base"] for s in stock_resp.json()}
        assert stock_map["RM-FLOUR"] == 120000
        assert stock_map["RM-OIL"] == 19500
        assert stock_map["RM-SPICE"] == 3800
        assert stock_map["PKG-POUCH-200"] == 306
        assert stock_map["PKG-CARTON"] == 21
        assert stock_map["FG-MURUKKU-200"] == 238

        # ── Step 8: Add labour ₹1,200 and gas/power ₹600 to the run ───
        patch_resp = await ac.patch(
            f"/api/production-runs/{run_id}/overheads",
            headers=headers,
            json={
                "labour_paise": 120000,     # ₹1,200.00
                "power_gas_paise": 60000,   # ₹600.00
            },
        )
        assert patch_resp.status_code == 200, patch_resp.text
        patched_run = patch_resp.json()

        # Expected Overheads: ₹1,800.00 = 180,000 paise
        assert patched_run["total_overheads_paise"] == 180000

        # Cost per packet:
        # Total cost: 405,500 + 180,000 = 585,500 paise
        # Cost per packet = 585,500 / 188 = 3114.36... -> 3114 paise (₹31.14)
        assert patched_run["cost_per_packet_paise"] == 3114

        # Margin: Selling price 5000 paise - 3114 paise = 1886 paise (₹18.86)
        assert patched_run["selling_price_paise"] == 5000
        assert patched_run["margin_per_packet_paise"] == 1886
