"""RBAC and Multi-Role Access Control Tests."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.database import Base, get_db
from app.core.auth import get_password_hash, create_access_token
from app.main import app
from app.models import User, Customer, Order, OrderLine, Item, Setting


@pytest_asyncio.fixture
async def rbac_test_env():
    """Setup test database with users for all 5 roles."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        session.add(Setting(key="tolerance_bp", value="300"))
        session.add(Setting(key="seller_state_code", value="33"))
        session.add(Setting(key="seller_gstin", value="33AABCD1234E1Z5"))

        sm_a = User(username="salesman_a", password_hash=get_password_hash("pass"), role="salesman", full_name="Salesman A", active=True)
        sm_b = User(username="salesman_b", password_hash=get_password_hash("pass"), role="salesman", full_name="Salesman B", active=True)
        admin = User(username="admin", password_hash=get_password_hash("pass"), role="admin", full_name="Admin", active=True)
        prod = User(username="production", password_hash=get_password_hash("pass"), role="production", full_name="Prod", active=True)
        auditor = User(username="auditor", password_hash=get_password_hash("pass"), role="auditor", full_name="Auditor", active=True)
        owner = User(username="owner", password_hash=get_password_hash("pass"), role="owner", full_name="Owner", active=True)

        session.add_all([sm_a, sm_b, admin, prod, auditor, owner])
        await session.flush()

        item = Item(sku="FG-MURUKKU", name="Murukku 200g", type="FINISHED", base_unit="piece", display_unit="packet", gst_rate_bp=500, active=True)
        session.add(item)

        cust_a = Customer(name="Retailer A", type="RETAILER", state_code=33, state_name="Tamil Nadu", salesman_id=sm_a.id, credit_days=30, active=True)
        cust_b = Customer(name="Distributor B", type="DISTRIBUTOR", state_code=29, state_name="Karnataka", salesman_id=sm_b.id, credit_days=45, active=True)
        session.add_all([cust_a, cust_b])
        await session.flush()

        order_b = Order(
            order_no="ORD/2026-27/0001",
            client_uuid="uuid-b-1",
            customer_id=cust_b.id,
            salesman_id=sm_b.id,
            status="SUBMITTED",
        )
        session.add(order_b)
        await session.flush()

        line = OrderLine(
            order_id=order_b.id,
            item_id=item.id,
            qty=120,
            unit_price_paise=5000,
        )
        session.add(line)
        await session.commit()

        users = {
            "salesman_a": sm_a,
            "salesman_b": sm_b,
            "admin": admin,
            "production": prod,
            "auditor": auditor,
            "owner": owner,
        }
        order_b_id = order_b.id

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    yield users, order_b_id
    app.dependency_overrides.clear()
    await engine.dispose()


def auth_header(user: User):
    token = create_access_token(data={"sub": user.username, "role": user.role, "user_id": user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_salesman_cannot_read_another_salesman_order(rbac_test_env):
    """PRD 2: A salesman can only read their own orders."""
    users, order_b_id = rbac_test_env

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Salesman A tries to view Salesman B's order
        resp = await client.get(f"/api/orders/{order_b_id}", headers=auth_header(users["salesman_a"]))
        assert resp.status_code in [403, 404]

        # Salesman B can view their own order
        resp_b = await client.get(f"/api/orders/{order_b_id}", headers=auth_header(users["salesman_b"]))
        assert resp_b.status_code == 200
        assert resp_b.json()["order_no"] == "ORD/2026-27/0001"


@pytest.mark.asyncio
async def test_salesman_cannot_approve_or_reject_orders(rbac_test_env):
    """PRD 2: Salesman cannot approve or reject orders."""
    users, order_b_id = rbac_test_env

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Salesman attempts to approve
        resp = await client.post(f"/api/orders/{order_b_id}/approve", json={}, headers=auth_header(users["salesman_a"]))
        assert resp.status_code == 403

        # Salesman attempts to reject
        resp_rej = await client.post(f"/api/orders/{order_b_id}/reject", json={"reason": "Test"}, headers=auth_header(users["salesman_a"]))
        assert resp_rej.status_code == 403


@pytest.mark.asyncio
async def test_auditor_read_only_access(rbac_test_env):
    """PRD 2: Auditor has read-only access to stock and reports, cannot write orders or runs."""
    users, order_b_id = rbac_test_env

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Auditor tries to create order
        resp = await client.post("/api/orders", json={
            "client_uuid": "auditor-uuid",
            "customer_id": 1,
            "lines": [{"item_id": 1, "qty": 10}]
        }, headers=auth_header(users["auditor"]))
        assert resp.status_code == 403

        # Auditor can read stock summary
        resp_stock = await client.get("/api/stock/summary", headers=auth_header(users["auditor"]))
        assert resp_stock.status_code == 200


@pytest.mark.asyncio
async def test_production_role_report_scoping(rbac_test_env):
    """PRD 7.6: Production role may only access production report, not sales or GST reports."""
    users, _ = rbac_test_env

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Production tries to access sales register -> 403
        resp_sales = await client.get("/api/reports/sales-register", headers=auth_header(users["production"]))
        assert resp_sales.status_code == 403

        # Production can access production report
        resp_prod = await client.get("/api/reports/production", headers=auth_header(users["production"]))
        assert resp_prod.status_code == 200
