"""Mandatory Acceptance Benchmark Test (PRD Section 11).

Executes the complete 9-step business scenario through the API and asserts
every expected value specified in Section 11 of the PRD.
"""
from datetime import date
from decimal import Decimal
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.database import Base, get_db
from app.core.auth import get_password_hash, create_access_token
from app.main import app
from app.models import (
    User,
    Customer,
    Supplier,
    Item,
    ItemUnit,
    ItemBalance,
    PriceList,
    Bom,
    BomLine,
    Setting,
    StockLedger,
)


@pytest_asyncio.fixture
async def benchmark_env():
    """Setup clean in-memory database seeded with PRD Section 10 state."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        # Settings
        session.add(Setting(key="tolerance_bp", value="300"))
        session.add(Setting(key="company_name", value="Demo Snacks Pvt Ltd"))
        session.add(Setting(key="seller_gstin", value="33AABCD1234E1Z5"))
        session.add(Setting(key="seller_state_code", value="33"))
        session.add(Setting(key="seller_state_name", value="Tamil Nadu"))
        session.add(Setting(key="seller_address", value="42 Industrial Estate, Trichy"))

        # Users
        admin = User(username="admin", password_hash=get_password_hash("pass"), role="admin", full_name="Admin", active=True)
        sm_a = User(username="salesman_a", password_hash=get_password_hash("pass"), role="salesman", full_name="Salesman A", active=True)
        sm_b = User(username="salesman_b", password_hash=get_password_hash("pass"), role="salesman", full_name="Salesman B", active=True)
        prod = User(username="production", password_hash=get_password_hash("pass"), role="production", full_name="Production Supervisor", active=True)
        auditor = User(username="auditor", password_hash=get_password_hash("pass"), role="auditor", full_name="Auditor", active=True)
        owner = User(username="owner", password_hash=get_password_hash("pass"), role="owner", full_name="Owner", active=True)
        session.add_all([admin, sm_a, sm_b, prod, auditor, owner])
        await session.flush()

        # Supplier
        supp = Supplier(name="Madurai Agro Traders", gstin="33SUPPL0000S1Z1", active=True)
        session.add(supp)

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
        items_spec = [
            ("RM-FLOUR", "Flour", "RAW", "g", "kg", 0, [("kg", 1000), ("g", 1)]),
            ("RM-OIL", "Cooking oil", "RAW", "ml", "L", 500, [("L", 1000), ("ml", 1)]),
            ("RM-SPICE", "Salt and spice mix", "RAW", "g", "kg", 500, [("kg", 1000), ("g", 1)]),
            ("PKG-POUCH-200", "200 g pouch", "PACKAGING", "piece", "piece", 1800, [("piece", 1)]),
            ("PKG-CARTON", "Carton", "PACKAGING", "piece", "piece", 1200, [("piece", 1)]),
            ("FG-MURUKKU-200", "Murukku 200 g", "FINISHED", "piece", "packet", 500, [("packet", 1), ("carton", 20)]),
        ]

        item_map = {}
        for sku, name, itype, base_u, disp_u, gst_bp, units in items_spec:
            it = Item(
                sku=sku,
                name=name,
                type=itype,
                base_unit=base_u,
                display_unit=disp_u,
                gst_rate_bp=gst_bp,
                reorder_level_base=10,
                active=True,
            )
            session.add(it)
            await session.flush()
            for u_name, factor in units:
                session.add(ItemUnit(item_id=it.id, unit=u_name, factor_to_base=factor))
            session.add(ItemBalance(item_id=it.id, qty_base=0, value_paise=0))
            item_map[sku] = it
        await session.flush()

        # Price List: Murukku 200g = ₹50.00 (5000 paise)
        session.add(PriceList(item_id=item_map["FG-MURUKKU-200"].id, price_paise=5000, effective_from=date(2026, 4, 1)))

        # BOM Murukku 200 g: yield 200 pkts
        bom = Bom(product_item_id=item_map["FG-MURUKKU-200"].id, version=1, yield_packets=200, active=True)
        session.add(bom)
        await session.flush()

        bom_lines = [
            (item_map["RM-FLOUR"].id, 40000),
            (item_map["RM-OIL"].id, 10000),
            (item_map["RM-SPICE"].id, 1200),
            (item_map["PKG-POUCH-200"].id, 200),
            (item_map["PKG-CARTON"].id, 10),
        ]
        for item_id, q_base in bom_lines:
            session.add(BomLine(bom_id=bom.id, item_id=item_id, qty_base=q_base))
        await session.flush()

        # Opening Ledger Rows (Section 10)
        openings = [
            ("RM-FLOUR", 100000, Decimal("4.200000"), 420000),       # 100 kg @ ₹42/kg
            ("RM-OIL", 30000, Decimal("14.000000"), 420000),          # 30 L @ ₹140/L
            ("RM-SPICE", 5000, Decimal("20.000000"), 100000),         # 5 kg @ ₹200/kg
            ("PKG-POUCH-200", 500, Decimal("250.000000"), 125000),    # 500 @ ₹2.50
            ("PKG-CARTON", 30, Decimal("1500.000000"), 45000),        # 30 @ ₹15
            ("FG-MURUKKU-200", 50, Decimal("3000.000000"), 150000),   # 50 @ ₹30
        ]
        for sku, q_base, u_cost, val_paise in openings:
            it = item_map[sku]
            session.add(StockLedger(
                item_id=it.id,
                movement_type="OPENING",
                qty_base=q_base,
                unit_cost=u_cost,
                value_paise=val_paise,
                source_type="OPENING_BALANCE",
                source_id=0,
                posted_by=admin.id,
                note=f"Opening balance for {sku}",
            ))
            # Sync balance
            bal = (await session.execute(select(ItemBalance).where(ItemBalance.item_id == it.id))).scalar_one()
            bal.qty_base = q_base
            bal.value_paise = val_paise

        await session.commit()

        context = {
            "users": {"admin": admin, "sm_a": sm_a, "sm_b": sm_b, "prod": prod, "auditor": auditor, "owner": owner},
            "supplier": supp,
            "customers": {"a": cust_a, "b": cust_b},
            "items": item_map,
            "bom": bom,
        }

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    yield context
    app.dependency_overrides.clear()
    await engine.dispose()


def auth(user: User):
    token = create_access_token(data={"sub": user.username, "role": user.role, "user_id": user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_full_section_11_benchmark_scenario(benchmark_env):
    """Run through the 9 steps of PRD Section 11 and assert every expected number."""
    ctx = benchmark_env
    users = ctx["users"]
    items = ctx["items"]
    supp = ctx["supplier"]
    cust_a = ctx["customers"]["a"]
    cust_b = ctx["customers"]["b"]
    bom = ctx["bom"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ─────────────────────────────────────────────────────────────
        # STEP 1: Purchase 60 kg flour at ₹45/kg
        # ─────────────────────────────────────────────────────────────
        p_resp = await client.post(
            "/api/purchases",
            json={
                "supplier_id": supp.id,
                "bill_no": "MAT-001",
                "purchase_date": "2026-11-01",
                "lines": [
                    {
                        "item_id": items["RM-FLOUR"].id,
                        "qty": 60,
                        "rate_rupees_per_display_unit": 45.0,
                    }
                ],
            },
            headers=auth(users["prod"]),
        )
        assert p_resp.status_code == 201, p_resp.text
        # Assert Flour WAC after purchase:
        # (100 kg * 42 + 60 kg * 45) / 160 kg = 6900 / 160 = 4.3125 paise/g (43125 paise/kg = ₹43.125/kg)
        sum_p = await client.get("/api/stock/summary", headers=auth(users["admin"]))
        flour_sum = next(s for s in sum_p.json() if s["sku"] == "RM-FLOUR")
        assert flour_sum["closing_qty_base"] == 160000
        assert Decimal(flour_sum["wac_paise_per_base_unit"]) == Decimal("4.312500") or Decimal(flour_sum["wac_paise_per_base_unit"]) == Decimal("4.3125")

        # ─────────────────────────────────────────────────────────────
        # STEP 2 & 3: Production run Murukku 200g, batch factor 1
        # Issue: flour 40 kg, oil 10.5 L, spice 1.2 kg
        # Actual good output: 188 pkts, 6 damaged pouches (194 used), 9 cartons used
        # ─────────────────────────────────────────────────────────────
        run_resp = await client.post(
            "/api/production-runs",
            json={
                "bom_id": bom.id,
                "batch_factor": 1.0,
                "actual_good_output": 188,
                "damaged_pouches": 6,
                "cartons_used": 9,
                "lines": [
                    {"item_id": items["RM-FLOUR"].id, "actual_qty": 40, "unit": "kg"},
                    {"item_id": items["RM-OIL"].id, "actual_qty": 10.5, "unit": "L"},
                    {"item_id": items["RM-SPICE"].id, "actual_qty": 1.2, "unit": "kg"},
                    {"item_id": items["PKG-POUCH-200"].id, "actual_qty": 194, "unit": "piece"},
                    {"item_id": items["PKG-CARTON"].id, "actual_qty": 9, "unit": "piece"},
                ],
            },
            headers=auth(users["prod"]),
        )
        assert run_resp.status_code == 201, run_resp.text
        run_data = run_resp.json()
        run_id = run_data["id"]

        # Assert Section 11 Variances:
        # Yield variance: 188 vs 200 = -6% (-600 bp), flagged True
        assert run_data["yield_variance_bp"] == -600
        assert run_data["yield_flagged"] is True

        lines_by_sku = {l["sku"]: l for l in run_data["lines"]}
        # Oil: +5% (+500 bp), flagged (> 300 bp)
        assert lines_by_sku["RM-OIL"]["variance_bp"] == 500
        assert lines_by_sku["RM-OIL"]["flagged"] is True
        # Flour & Spice: 0% (0 bp), not flagged
        assert lines_by_sku["RM-FLOUR"]["variance_bp"] == 0
        assert lines_by_sku["RM-FLOUR"]["flagged"] is False
        assert lines_by_sku["RM-SPICE"]["variance_bp"] == 0
        assert lines_by_sku["RM-SPICE"]["flagged"] is False
        # Pouch: 194 vs 200 = -3% (-300 bp), NOT flagged (strictly greater check: 300 bp tolerance)
        assert lines_by_sku["PKG-POUCH-200"]["variance_bp"] == -300
        assert lines_by_sku["PKG-POUCH-200"]["flagged"] is False
        # Carton: 9 vs 10 = -10% (-1000 bp), flagged (> 300 bp)
        assert lines_by_sku["PKG-CARTON"]["variance_bp"] == -1000
        assert lines_by_sku["PKG-CARTON"]["flagged"] is True

        # Assert Material Cost of Run:
        # flour: 40000 * 4.3125 = 172500p
        # oil: 10500 * 14.0 = 147000p
        # spice: 1200 * 20.0 = 24000p
        # pouches: 194 * 250 = 48500p
        # cartons: 9 * 1500 = 13500p
        # Total = 405500 paise (₹4,055.00)
        assert run_data["material_cost_paise"] == 405500

        # Assert Finished Goods after run: 50 opening + 188 = 238 packets
        fg_sum = await client.get("/api/stock/summary", headers=auth(users["admin"]))
        fg_bal = next(i for i in fg_sum.json() if i["sku"] == "FG-MURUKKU-200")
        assert fg_bal["closing_qty_base"] == 238

        # ─────────────────────────────────────────────────────────────
        # STEP 4 & 5: Salesman A orders 150 packets for Retailer A
        # Admin approves, raises invoice (CGST+SGST), records dispatch
        # ─────────────────────────────────────────────────────────────
        ord_a_resp = await client.post(
            "/api/orders",
            json={
                "client_uuid": "bench-order-a",
                "customer_id": cust_a.id,
                "lines": [{"item_id": items["FG-MURUKKU-200"].id, "qty": 150}],
            },
            headers=auth(users["sm_a"]),
        )
        assert ord_a_resp.status_code == 201
        order_a_id = ord_a_resp.json()["id"]

        # Admin approves
        appr_resp = await client.post(f"/api/orders/{order_a_id}/approve", json={}, headers=auth(users["admin"]))
        assert appr_resp.status_code == 200

        # Admin generates invoice
        inv_resp = await client.post(f"/api/orders/{order_a_id}/invoice", json={}, headers=auth(users["admin"]))
        assert inv_resp.status_code == 201
        inv_a = inv_resp.json()
        invoice_a_id = inv_a["id"]

        # Assert Retailer A invoice:
        # Taxable: 150 * 5000 = 750000 paise (₹7,500.00)
        # CGST (2.5%): 18750 paise (₹187.50)
        # SGST (2.5%): 18750 paise (₹187.50)
        # Total: 787500 paise (₹7,875.00)
        assert inv_a["taxable_paise"] == 750000
        assert inv_a["cgst_paise"] == 18750
        assert inv_a["sgst_paise"] == 18750
        assert inv_a["igst_paise"] == 0
        assert inv_a["total_paise"] == 787500

        # Admin records dispatch
        disp_resp = await client.post(f"/api/invoices/{invoice_a_id}/dispatch", headers=auth(users["admin"]))
        assert disp_resp.status_code == 200

        # Assert FG after Retailer A dispatch: 238 - 150 = 88 packets
        fg_sum2 = await client.get("/api/stock/summary", headers=auth(users["admin"]))
        fg_bal2 = next(i for i in fg_sum2.json() if i["sku"] == "FG-MURUKKU-200")
        assert fg_bal2["closing_qty_base"] == 88

        # ─────────────────────────────────────────────────────────────
        # STEP 6: Salesman B orders 120 packets for Distributor B
        # Stock check shows the shortage
        # ─────────────────────────────────────────────────────────────
        ord_b_resp = await client.post(
            "/api/orders",
            json={
                "client_uuid": "bench-order-b",
                "customer_id": cust_b.id,
                "lines": [{"item_id": items["FG-MURUKKU-200"].id, "qty": 120}],
            },
            headers=auth(users["sm_b"]),
        )
        assert ord_b_resp.status_code == 201
        order_b_id = ord_b_resp.json()["id"]

        # Stock check: requested 120, available 88, shortage 32
        chk_resp = await client.get(f"/api/orders/{order_b_id}/stock-check", headers=auth(users["admin"]))
        assert chk_resp.status_code == 200
        chk_data = chk_resp.json()
        assert chk_data["can_approve"] is False
        fg_chk = chk_data["lines"][0]
        assert fg_chk["requested_qty"] == 120
        assert fg_chk["available_qty"] == 88
        assert fg_chk["shortage_qty"] == 32
        assert fg_chk["is_shortage"] is True

        # Distributor B invoice preview: IGST 5%: taxable ₹6,000.00 + IGST ₹300.00 = ₹6,300.00
        prev_resp = await client.get(f"/api/orders/{order_b_id}/invoice-preview", headers=auth(users["admin"]))
        assert prev_resp.status_code == 200
        prev_data = prev_resp.json()
        assert prev_data["supply_type"] == "INTER"
        assert prev_data["taxable_paise"] == 600000
        assert prev_data["igst_paise"] == 30000
        assert prev_data["total_paise"] == 630000

        # ─────────────────────────────────────────────────────────────
        # STEP 7: Record ₹4,000 (400,000 paise) payment from Retailer A
        # ─────────────────────────────────────────────────────────────
        pay_resp = await client.post(
            "/api/payments",
            json={
                "customer_id": cust_a.id,
                "invoice_id": invoice_a_id,
                "amount_paise": 400000,
                "mode": "NEFT",
                "reference": "UTR-RET-A-01",
            },
            headers=auth(users["admin"]),
        )
        assert pay_resp.status_code == 201

        # Assert Retailer A outstanding: ₹7,875.00 - ₹4,000.00 = ₹3,875.00 (387500 paise)
        out_resp = await client.get(f"/api/customers/{cust_a.id}/outstanding", headers=auth(users["admin"]))
        assert out_resp.status_code == 200
        out_data = out_resp.json()
        assert out_data["total_invoiced_paise"] == 787500
        assert out_data["total_payments_paise"] == 400000
        assert out_data["total_outstanding_paise"] == 387500

        # ─────────────────────────────────────────────────────────────
        # STEP 8: Add labour ₹1,200 and gas/power ₹600 to the run
        # ─────────────────────────────────────────────────────────────
        patch_resp = await client.patch(
            f"/api/production-runs/{run_id}/overheads",
            json={
                "labour_paise": 120000,
                "power_gas_paise": 60000,
            },
            headers=auth(users["prod"]),
        )
        assert patch_resp.status_code == 200
        run_patched = patch_resp.json()

        # Assert Section 11 Unit Costing:
        # Overheads: ₹1,800.00 (180000 paise)
        # Material Cost: 405500 paise
        # Total Cost: 405500 + 180000 = 585500 paise
        # Cost per packet: 585500 / 188 = 3114.36 -> rounded to 3114 paise (₹31.14)
        # Margin: 5000 - 3114 = 1886 paise (₹18.86) vs ₹50 selling price
        assert run_patched["total_overheads_paise"] == 180000
        assert run_patched["total_cost_paise"] == 585500
        assert run_patched["cost_per_packet_paise"] == 3114
        assert run_patched["margin_per_packet_paise"] == 1886

        # ─────────────────────────────────────────────────────────────
        # Closing Balances Assertions (Section 11 Table)
        # ─────────────────────────────────────────────────────────────
        sum_resp = await client.get("/api/stock/summary", headers=auth(users["admin"]))
        assert sum_resp.status_code == 200
        summary_by_sku = {s["sku"]: s for s in sum_resp.json()}

        # Flour closing: 120 kg = 120000 g (100 + 60 - 40)
        assert summary_by_sku["RM-FLOUR"]["closing_qty_base"] == 120000
        assert float(summary_by_sku["RM-FLOUR"]["closing_qty_display"]) == 120.0

        # Oil closing: 19.5 L = 19500 ml (30 - 10.5)
        assert summary_by_sku["RM-OIL"]["closing_qty_base"] == 19500
        assert float(summary_by_sku["RM-OIL"]["closing_qty_display"]) == 19.5

        # Spice mix closing: 3.8 kg = 3800 g (5 - 1.2)
        assert summary_by_sku["RM-SPICE"]["closing_qty_base"] == 3800
        assert float(summary_by_sku["RM-SPICE"]["closing_qty_display"]) == 3.8

        # Pouches closing: 306 (500 - 194 used)
        assert summary_by_sku["PKG-POUCH-200"]["closing_qty_base"] == 306

        # Cartons closing: 21 (30 - 9 used)
        assert summary_by_sku["PKG-CARTON"]["closing_qty_base"] == 21

        # Finished Goods closing: 88 packets
        assert summary_by_sku["FG-MURUKKU-200"]["closing_qty_base"] == 88

        # ─────────────────────────────────────────────────────────────
        # Ledger Reconciliation Verification
        # ─────────────────────────────────────────────────────────────
        rec_resp = await client.get("/api/stock/reconcile", headers=auth(users["admin"]))
        assert rec_resp.status_code == 200
        rec_data = rec_resp.json()
        assert rec_data["all_reconciled"] is True
        assert rec_data["reconciled_count"] == rec_data["total_items"]

        # ─────────────────────────────────────────────────────────────
        # STEP 9: Generate all Section 7.6 Reports
        # ─────────────────────────────────────────────────────────────
        reports = [
            "sales-register",
            "customer-sales",
            "product-sales",
            "gst-summary",
            "purchase-register",
            "stock-summary",
            "production",
            "outstanding",
        ]
        for r_name in reports:
            # JSON format
            r_json = await client.get(f"/api/reports/{r_name}", headers=auth(users["admin"]))
            assert r_json.status_code == 200, f"Report {r_name} JSON failed"
            # CSV format
            r_csv = await client.get(f"/api/reports/{r_name}?format=csv", headers=auth(users["admin"]))
            assert r_csv.status_code == 200, f"Report {r_name} CSV failed"
            assert "text/csv" in r_csv.headers.get("content-type", "")

        # Owner Dashboard verification
        dash_resp = await client.get("/api/dashboard", headers=auth(users["owner"]))
        assert dash_resp.status_code == 200
        dash_data = dash_resp.json()
        assert dash_data["total_outstanding_rs"] == 3875.0
        assert len(dash_data["variance_alerts"]) >= 3
