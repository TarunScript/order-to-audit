"""Tests for Milestone 7: Section 7.6 Reports with multi-format exports and Owner Dashboard."""
from datetime import date
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
    Customer,
    Order,
    OrderLine,
    Invoice,
    InvoiceLine,
    ProductionRun,
    ProductionRunLine,
    PriceList,
    Setting,
    StockLedger,
)


@pytest_asyncio.fixture
async def reports_test_env():
    """Setup test database with full business cycle data."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        # Settings
        session.add(Setting(key="tolerance_bp", value="300"))
        session.add(Setting(key="seller_state_code", value="33"))
        session.add(Setting(key="seller_gstin", value="33AABCD1234E1Z5"))
        session.add(Setting(key="company_name", value="Demo Snacks Pvt Ltd"))

        admin = User(username="admin", password_hash=get_password_hash("pass"), role="admin", full_name="Admin", active=True)
        owner = User(username="owner", password_hash=get_password_hash("pass"), role="owner", full_name="Managing Director", active=True)
        session.add_all([admin, owner])
        await session.flush()

        cust = Customer(
            name="Retailer A",
            type="RETAILER",
            gstin="33AAAAA0000A1Z5",
            state_code=33,
            state_name="Tamil Nadu",
            credit_days=30,
            active=True,
        )
        session.add(cust)

        fg = Item(
            sku="FG-MURUKKU-200",
            name="Murukku 200 g",
            type="FINISHED",
            base_unit="piece",
            display_unit="packet",
            hsn_code="21069099",
            gst_rate_bp=500,
            reorder_level_base=100,
            active=True,
        )
        session.add(fg)
        await session.flush()

        session.add(ItemUnit(item_id=fg.id, unit="packet", factor_to_base=1))
        session.add(ItemBalance(item_id=fg.id, qty_base=88, value_paise=274000))
        session.add(PriceList(item_id=fg.id, price_paise=5000, effective_from=date(2026, 4, 1)))

        # Invoice
        inv = Invoice(
            invoice_no="INV/2026-27/0001",
            fy="2026-27",
            order_id=1,
            customer_id=cust.id,
            supply_type="INTRA",
            place_of_supply="Tamil Nadu",
            taxable_paise=750000,
            cgst_paise=18750,
            sgst_paise=18750,
            igst_paise=0,
            total_paise=787500,
            status="POSTED",
            invoice_date=date.today(),
        )
        session.add(inv)
        await session.flush()

        inv_line = InvoiceLine(
            invoice_id=inv.id,
            item_id=fg.id,
            hsn_code="21069099",
            qty=150,
            rate_paise=5000,
            taxable_paise=750000,
            gst_rate_bp=500,
            cgst_paise=18750,
            sgst_paise=18750,
            igst_paise=0,
        )
        session.add(inv_line)

        # Production Run with variance alert
        run = ProductionRun(
            run_no="PR/2026-27/0001",
            bom_id=1,
            product_id=fg.id,
            run_date=date.today(),
            batch_factor=1.0,
            expected_output=200,
            actual_good_output=188,
            status="POSTED",
            labour_paise=120000,
            power_gas_paise=60000,
            other_overhead_paise=0,
            tolerance_bp=300,
            material_cost_paise=405500,
            cost_per_packet_paise=3114,
        )
        session.add(run)
        await session.flush()

        run_line = ProductionRunLine(
            run_id=run.id,
            item_id=fg.id,
            planned_qty_base=200,
            actual_qty_base=188,
            variance_bp=-600,
            flagged=True,
        )
        session.add(run_line)

        await session.commit()

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_all_reports_and_formats(reports_test_env):
    """Test all Section 7.6 reports in JSON, CSV, XLSX, and PDF formats."""
    token = create_access_token({"sub": "admin", "role": "admin", "user_id": 1})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        report_names = [
            "sales-register",
            "customer-sales",
            "product-sales",
            "gst-summary",
            "purchase-register",
            "stock-summary",
            "production",
            "outstanding",
        ]

        for rep in report_names:
            # 1. JSON
            r_json = await ac.get(f"/api/reports/{rep}?format=json", headers=headers)
            assert r_json.status_code == 200, f"{rep} JSON failed: {r_json.text}"
            data = r_json.json()
            assert "report_name" in data

            # 2. CSV
            r_csv = await ac.get(f"/api/reports/{rep}?format=csv", headers=headers)
            assert r_csv.status_code == 200, f"{rep} CSV failed"
            assert "text/csv" in r_csv.headers["content-type"]
            assert len(r_csv.text) > 0

            # 3. XLSX
            r_xlsx = await ac.get(f"/api/reports/{rep}?format=xlsx", headers=headers)
            assert r_xlsx.status_code == 200, f"{rep} XLSX failed"
            assert "spreadsheetml" in r_xlsx.headers["content-type"]
            assert len(r_xlsx.content) > 0

            # 4. PDF
            r_pdf = await ac.get(f"/api/reports/{rep}?format=pdf", headers=headers)
            assert r_pdf.status_code == 200, f"{rep} PDF failed"
            assert "application/pdf" in r_pdf.headers["content-type"]
            assert len(r_pdf.content) > 0


@pytest.mark.asyncio
async def test_owner_dashboard(reports_test_env):
    """Test owner dashboard KPIs, stock levels, variance alerts, and top debtors."""
    token = create_access_token({"sub": "owner", "role": "owner", "user_id": 1})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        d_resp = await ac.get("/api/dashboard", headers=headers)
        assert d_resp.status_code == 200, d_resp.text
        dash = d_resp.json()

        # Stock levels: Murukku has 88 closing vs 100 reorder level -> low stock (amber)
        assert dash["low_stock_count"] == 1
        murukku_stock = next(s for s in dash["stock_levels"] if s["sku"] == "FG-MURUKKU-200")
        assert murukku_stock["is_low_stock"] is True

        # Variance alerts: Yield variance -6% flagged
        assert dash["open_alerts_count"] >= 1
        alert = dash["variance_alerts"][0]
        assert "Yield variance" in alert["message"] or alert["alert_type"] in ["YIELD", "MATERIAL"]

        # Cost per packet: Murukku cost is 3114 paise (₹31.14), margin is 1886 paise (₹18.86)
        cost_card = next(c for c in dash["cost_per_packet"] if c["sku"] == "FG-MURUKKU-200")
        assert cost_card["cost_per_packet_paise"] == 3114
        assert cost_card["selling_price_paise"] == 5000
        assert cost_card["margin_paise"] == 1886

        # Top Debtors: Retailer A has 787500 outstanding
        assert dash["total_outstanding_paise"] == 787500
        assert len(dash["top_debtors"]) == 1
        assert dash["top_debtors"][0]["customer_name"] == "Retailer A"
        assert dash["top_debtors"][0]["outstanding_paise"] == 787500
