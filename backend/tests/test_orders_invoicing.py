"""Tests for Milestone 5: Orders, stock check, invoicing, dispatch, and credit notes."""
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
    Invoice,
)
from app.posting.engine import post_production_run


@pytest_asyncio.fixture
async def sales_test_env():
    """Setup test database with full benchmark state through step 3."""
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

        # Users
        admin = User(username="admin", password_hash=get_password_hash("pass"), role="admin", full_name="Admin Desk", active=True)
        sm_a = User(username="salesman_a", password_hash=get_password_hash("pass"), role="salesman", full_name="Salesman A", active=True)
        sm_b = User(username="salesman_b", password_hash=get_password_hash("pass"), role="salesman", full_name="Salesman B", active=True)
        session.add_all([admin, sm_a, sm_b])
        await session.flush()

        # Customers
        cust_a = Customer(
            name="Retailer A",
            type="RETAILER",
            gstin="33AAAAA0000A1Z5",
            state_code=33,
            state_name="Tamil Nadu",
            address="10 Bazaar Street, Trichy",
            phone="9443322110",
            salesman_id=sm_a.id,
            credit_days=30,
            active=True,
        )
        cust_b = Customer(
            name="Distributor B",
            type="DISTRIBUTOR",
            gstin="29BBBBB0000B1Z5",
            state_code=29,
            state_name="Karnataka",
            address="45 Commercial Road, Bengaluru",
            phone="9880011223",
            salesman_id=sm_b.id,
            credit_days=45,
            active=True,
        )
        session.add_all([cust_a, cust_b])
        await session.flush()

        # Items
        fg = Item(
            sku="FG-MURUKKU-200",
            name="Murukku 200 g",
            type="FINISHED",
            base_unit="piece",
            display_unit="packet",
            hsn_code="21069099",
            gst_rate_bp=500,  # 5%
            active=True,
        )
        session.add(fg)
        await session.flush()

        session.add(ItemUnit(item_id=fg.id, unit="packet", factor_to_base=1))
        # Initial Finished Goods Balance: 238 packets (50 opening + 188 output from step 3)
        session.add(ItemBalance(item_id=fg.id, qty_base=238, value_paise=735500))

        # Price List: ₹50.00 = 5000 paise
        session.add(PriceList(item_id=fg.id, price_paise=5000, effective_from=date(2026, 4, 1)))

        await session.commit()

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    yield {
        "admin": admin,
        "sm_a": sm_a,
        "sm_b": sm_b,
        "cust_a": cust_a,
        "cust_b": cust_b,
        "fg": fg,
        "session_maker": session_maker,
    }
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_benchmark_steps_4_5_6(sales_test_env):
    """Test Benchmark Steps 4, 5, and 6 end-to-end via API."""
    env = sales_test_env
    cust_a = env["cust_a"]
    cust_b = env["cust_b"]
    sm_a = env["sm_a"]
    sm_b = env["sm_b"]
    fg = env["fg"]

    token_a = create_access_token({"sub": sm_a.username, "role": sm_a.role, "user_id": sm_a.id})
    token_b = create_access_token({"sub": sm_b.username, "role": sm_b.role, "user_id": sm_b.id})
    token_admin = create_access_token({"sub": "admin", "role": "admin", "user_id": 1})

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── RBAC check: salesman_a cannot order for Distributor B ─────
        bad_order = await ac.post(
            "/api/orders",
            headers=headers_a,
            json={
                "client_uuid": "order-bad-uuid",
                "customer_id": cust_b.id,
                "lines": [{"item_id": fg.id, "qty": 10}],
            },
        )
        assert bad_order.status_code == 403

        # ── Step 4: salesman_a orders 150 packets for Retailer A ───────
        order_resp = await ac.post(
            "/api/orders",
            headers=headers_a,
            json={
                "client_uuid": "order-retailer-a-uuid",
                "customer_id": cust_a.id,
                "lines": [{"item_id": fg.id, "qty": 150}],
            },
        )
        assert order_resp.status_code == 201, order_resp.text
        order_a = order_resp.json()
        order_a_id = order_a["id"]
        assert order_a["status"] == "SUBMITTED"
        assert order_a["total_paise"] == 150 * 5000  # 750,000 paise

        # Test idempotency: repeat with same client_uuid
        order_dup = await ac.post(
            "/api/orders",
            headers=headers_a,
            json={
                "client_uuid": "order-retailer-a-uuid",
                "customer_id": cust_a.id,
                "lines": [{"item_id": fg.id, "qty": 150}],
            },
        )
        assert order_dup.status_code == 201
        assert order_dup.json()["id"] == order_a_id

        # ── Step 5: Admin approves, raises invoice, records dispatch ───
        # 5a. Stock check before approval (238 available, 150 requested -> OK)
        sc_resp = await ac.get(f"/api/orders/{order_a_id}/stock-check", headers=headers_admin)
        assert sc_resp.status_code == 200
        sc_data = sc_resp.json()
        assert sc_data["can_approve"] is True
        assert sc_data["lines"][0]["available_qty"] == 238
        assert sc_data["lines"][0]["requested_qty"] == 150
        assert sc_data["lines"][0]["shortage_qty"] == 0

        # 5b. Admin approves order
        appr_resp = await ac.post(f"/api/orders/{order_a_id}/approve", headers=headers_admin)
        assert appr_resp.status_code == 200
        assert appr_resp.json()["status"] == "APPROVED"

        # 5c. Admin raises invoice (CGST + SGST intra-state TN)
        inv_resp = await ac.post(
            f"/api/orders/{order_a_id}/invoice",
            headers=headers_admin,
            json={"invoice_date": "2026-04-03"},
        )
        assert inv_resp.status_code == 201, inv_resp.text
        inv_a = inv_resp.json()
        inv_a_id = inv_a["id"]

        # Retailer A invoice assertions:
        # Taxable: ₹7,500.00 = 750,000 paise
        # CGST: ₹187.50 = 18,750 paise (2.5%)
        # SGST: ₹187.50 = 18,750 paise (2.5%)
        # Total: ₹7,875.00 = 787,500 paise
        assert inv_a["supply_type"] == "INTRA"
        assert inv_a["taxable_paise"] == 750000
        assert inv_a["cgst_paise"] == 18750
        assert inv_a["sgst_paise"] == 18750
        assert inv_a["igst_paise"] == 0
        assert inv_a["total_paise"] == 787500

        # Verify PDF file was generated
        assert inv_a["pdf_path"] is not None

        # 5d. Record Dispatch
        disp_resp = await ac.post(f"/api/invoices/{inv_a_id}/dispatch", headers=headers_admin)
        assert disp_resp.status_code == 200, disp_resp.text

        # Verify Finished Goods Stock after dispatch: 238 - 150 = 88 packets!
        summary_resp = await ac.get("/api/stock/summary", headers=headers_admin)
        fg_stock = next(s for s in summary_resp.json() if s["sku"] == "FG-MURUKKU-200")
        assert fg_stock["closing_qty_base"] == 88

        # ── Step 6: salesman_b orders 120 packets for Distributor B ───
        order_b_resp = await ac.post(
            "/api/orders",
            headers=headers_b,
            json={
                "client_uuid": "order-distributor-b-uuid",
                "customer_id": cust_b.id,
                "lines": [{"item_id": fg.id, "qty": 120}],
            },
        )
        assert order_b_resp.status_code == 201, order_b_resp.text
        order_b = order_b_resp.json()
        order_b_id = order_b["id"]

        # 6a. Stock check shows shortage: requested 120, available 88, shortage 32 packets!
        sc_b_resp = await ac.get(f"/api/orders/{order_b_id}/stock-check", headers=headers_admin)
        assert sc_b_resp.status_code == 200
        sc_b = sc_b_resp.json()
        assert sc_b["can_approve"] is False
        assert sc_b["lines"][0]["requested_qty"] == 120
        assert sc_b["lines"][0]["available_qty"] == 88
        assert sc_b["lines"][0]["shortage_qty"] == 32
        assert sc_b["lines"][0]["is_shortage"] is True

        # Approve MUST fail while shortage exists
        appr_fail = await ac.post(f"/api/orders/{order_b_id}/approve", headers=headers_admin)
        assert appr_fail.status_code == 400
        assert appr_fail.json()["code"] == "INSUFFICIENT_STOCK"

        # 6b. Invoice preview: IGST 5% (Inter-state Karnataka)
        # Taxable: 120 * 50 = ₹6,000.00 = 600,000 paise
        # IGST: 5% of 600,000 = 30,000 paise (₹300.00)
        # Total: ₹6,300.00 = 630,000 paise
        prev_resp = await ac.get(f"/api/orders/{order_b_id}/invoice-preview", headers=headers_admin)
        assert prev_resp.status_code == 200
        prev_data = prev_resp.json()
        assert prev_data["supply_type"] == "INTER"
        assert prev_data["taxable_paise"] == 600000
        assert prev_data["igst_paise"] == 30000
        assert prev_data["total_paise"] == 630000

        # If edited to 88 packets:
        # Taxable: 88 * 50 = ₹4,400.00 = 440,000 paise
        # IGST: 22,000 paise (₹220.00)
        # Total: 462,000 paise (₹4,620.00)
        patch_b = await ac.patch(
            f"/api/orders/{order_b_id}",
            headers=headers_admin,
            json={"lines": [{"id": order_b["lines"][0]["id"], "approved_qty": 88}]},
        )
        assert patch_b.status_code == 200

        prev_88 = await ac.get(f"/api/orders/{order_b_id}/invoice-preview", headers=headers_admin)
        assert prev_88.status_code == 200
        p88 = prev_88.json()
        assert p88["taxable_paise"] == 440000
        assert p88["igst_paise"] == 22000
        assert p88["total_paise"] == 462000


@pytest.mark.asyncio
async def test_credit_note_reversal(sales_test_env):
    """Test credit note generation and stock reversal on cancellation of dispatched invoice."""
    env = sales_test_env
    cust_a = env["cust_a"]
    fg = env["fg"]

    token_admin = create_access_token({"sub": "admin", "role": "admin", "user_id": 1})
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create, approve, invoice, and dispatch an order of 20 packets
        ord_resp = await ac.post(
            "/api/orders",
            headers=headers_admin,
            json={
                "client_uuid": "cn-test-order-uuid",
                "customer_id": cust_a.id,
                "lines": [{"item_id": fg.id, "qty": 20}],
            },
        )
        ord_id = ord_resp.json()["id"]
        await ac.post(f"/api/orders/{ord_id}/approve", headers=headers_admin)
        inv_resp = await ac.post(f"/api/orders/{ord_id}/invoice", headers=headers_admin)
        inv_id = inv_resp.json()["id"]
        await ac.post(f"/api/invoices/{inv_id}/dispatch", headers=headers_admin)

        # Stock reduced by 20 (238 - 20 = 218)
        s1 = await ac.get("/api/stock/summary", headers=headers_admin)
        assert next(s for s in s1.json() if s["sku"] == "FG-MURUKKU-200")["closing_qty_base"] == 218

        # Cancel invoice via credit note
        cn_resp = await ac.post(
            f"/api/invoices/{inv_id}/cancel",
            headers=headers_admin,
            json={"reason": "Customer returned batch"},
        )
        assert cn_resp.status_code == 200
        cn_data = cn_resp.json()
        assert cn_data["cn_no"].startswith("CN/")

        # Verify stock returned: 218 + 20 = 238
        s2 = await ac.get("/api/stock/summary", headers=headers_admin)
        assert next(s for s in s2.json() if s["sku"] == "FG-MURUKKU-200")["closing_qty_base"] == 238
