"""Tests for Milestone 6: Payments, customer outstanding, and ageing."""
from datetime import date, timedelta
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
    Customer,
    Order,
    Invoice,
    Payment,
    CreditNote,
)


@pytest_asyncio.fixture
async def payments_test_env():
    """Setup test database with Retailer A invoice matching Benchmark step 5."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        admin = User(username="admin", password_hash=get_password_hash("pass"), role="admin", full_name="Admin", active=True)
        session.add(admin)
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
        await session.flush()

        order = Order(
            order_no="ORD/2026-27/0001",
            client_uuid="uuid-1",
            customer_id=cust.id,
            salesman_id=admin.id,
            status="INVOICED",
        )
        session.add(order)
        await session.flush()

        # Benchmark Retailer A invoice:
        # Taxable: 750,000 paise (₹7,500.00)
        # CGST: 18,750 paise (₹187.50)
        # SGST: 18,750 paise (₹187.50)
        # Total: 787,500 paise (₹7,875.00)
        inv = Invoice(
            invoice_no="INV/2026-27/0001",
            fy="2026-27",
            order_id=order.id,
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
        await session.commit()

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    yield {"cust": cust, "inv": inv}
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_benchmark_step_7_and_ageing(payments_test_env):
    """Test Benchmark Step 7: Record ₹4,000 payment from Retailer A; outstanding is ₹3,875.00."""
    env = payments_test_env
    cust = env["cust"]
    inv = env["inv"]

    token = create_access_token({"sub": "admin", "role": "admin", "user_id": 1})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Before payment: outstanding is 787,500 paise
        out_before = await ac.get(f"/api/customers/{cust.id}/outstanding", headers=headers)
        assert out_before.status_code == 200
        assert out_before.json()["total_outstanding_paise"] == 787500

        # Step 7: Record ₹4,000 payment from Retailer A (400,000 paise)
        pay_resp = await ac.post(
            "/api/payments",
            headers=headers,
            json={
                "customer_id": cust.id,
                "invoice_id": inv.id,
                "amount_paise": 400000,
                "mode": "NEFT",
                "reference": "UTR12345678",
                "received_on": date.today().isoformat(),
            },
        )
        assert pay_resp.status_code == 201, pay_resp.text
        pay_data = pay_resp.json()
        assert pay_data["amount_paise"] == 400000
        assert pay_data["invoice_no"] == "INV/2026-27/0001"

        # Verify Retailer A outstanding: ₹3,875.00 = 387,500 paise!
        out_after = await ac.get(f"/api/customers/{cust.id}/outstanding", headers=headers)
        assert out_after.status_code == 200
        data = out_after.json()
        assert data["total_invoiced_paise"] == 787500
        assert data["total_payments_paise"] == 400000
        assert data["total_credit_notes_paise"] == 0
        assert data["total_outstanding_paise"] == 387500

        # Verify Ageing bucket: since invoice is today, it falls in bucket 0-30
        assert data["bucket_0_30_paise"] == 387500
        assert data["bucket_31_60_paise"] == 0
        assert data["bucket_61_90_paise"] == 0
        assert data["bucket_90_plus_paise"] == 0

        # Verify list payments
        list_resp = await ac.get(f"/api/payments?customer_id={cust.id}", headers=headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1
