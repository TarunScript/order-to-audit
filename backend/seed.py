"""Idempotent seed script to load Section 10 PRD data."""
import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.core.auth import get_password_hash
from app.models import (
    Setting,
    User,
    Item,
    ItemUnit,
    PriceList,
    Bom,
    BomLine,
    Customer,
    Supplier,
    StockLedger,
    ItemBalance,
)


async def seed_data():
    """Populate initial seed data matching Section 10 of the PRD."""
    async with async_session_maker() as session:
        # ── 1. Settings ─────────────────────────────────────────────────
        settings_data = [
            ("company_name", "Demo Snacks Pvt Ltd"),
            ("seller_gstin", "33AABCD1234E1Z5"),
            ("seller_state_code", "33"),
            ("seller_state_name", "Tamil Nadu"),
            ("seller_address", "42 Industrial Estate, Thuvakudi, Tiruchirappalli, Tamil Nadu 620015"),
            ("tolerance_bp", "300"),  # 3% = 300 basis points
        ]
        for key, val in settings_data:
            existing = await session.execute(select(Setting).where(Setting.key == key))
            if not existing.scalar_one_or_none():
                session.add(Setting(key=key, value=val))
        await session.flush()

        # ── 2. Users ────────────────────────────────────────────────────
        users_data = [
            ("salesman_a", "password123", "salesman", "Salesman A (Tamil Nadu)"),
            ("salesman_b", "password123", "salesman", "Salesman B (Karnataka)"),
            ("admin", "password123", "admin", "Admin & Billing Desk"),
            ("production", "password123", "production", "Production Supervisor"),
            ("auditor", "password123", "auditor", "Statutory Auditor"),
            ("owner", "password123", "owner", "Managing Director"),
        ]
        user_map = {}
        for username, pwd, role, name in users_data:
            existing = await session.execute(select(User).where(User.username == username))
            u = existing.scalar_one_or_none()
            if not u:
                u = User(
                    username=username,
                    password_hash=get_password_hash(pwd),
                    role=role,
                    full_name=name,
                    active=True,
                )
                session.add(u)
                await session.flush()
            user_map[username] = u

        # ── 3. Items & Units ───────────────────────────────────────────
        # Base units: raw (g/ml), packaging/FG (piece)
        items_data = [
            # sku, name, type, base_unit, display_unit, hsn, gst_bp, units_spec
            (
                "RM-FLOUR",
                "Flour",
                "RAW",
                "g",
                "kg",
                "11010000",
                0,
                [("kg", 1000), ("g", 1)],
            ),
            (
                "RM-OIL",
                "Cooking oil",
                "RAW",
                "ml",
                "L",
                "15079010",
                500,
                [("L", 1000), ("ml", 1)],
            ),
            (
                "RM-SPICE",
                "Salt and spice mix",
                "RAW",
                "g",
                "kg",
                "09109929",
                500,
                [("kg", 1000), ("g", 1)],
            ),
            (
                "PKG-POUCH-200",
                "200 g pouch",
                "PACKAGING",
                "piece",
                "piece",
                "39232990",
                1800,
                [("piece", 1)],
            ),
            (
                "PKG-CARTON",
                "Carton",
                "PACKAGING",
                "piece",
                "piece",
                "48191010",
                1200,
                [("piece", 1)],
            ),
            (
                "FG-MURUKKU-200",
                "Murukku 200 g",
                "FINISHED",
                "piece",
                "packet",
                "21069099",
                500,
                [("packet", 1), ("carton", 20)],
            ),
        ]

        item_map = {}
        for sku, name, itype, b_unit, d_unit, hsn, gst_bp, units in items_data:
            existing = await session.execute(select(Item).where(Item.sku == sku))
            item = existing.scalar_one_or_none()
            if not item:
                item = Item(
                    sku=sku,
                    name=name,
                    type=itype,
                    base_unit=b_unit,
                    display_unit=d_unit,
                    hsn_code=hsn,
                    gst_rate_bp=gst_bp,
                    active=True,
                )
                session.add(item)
                await session.flush()

                # Add units
                for u_name, factor in units:
                    session.add(ItemUnit(item_id=item.id, unit=u_name, factor_to_base=factor))

                # Initialize balance
                session.add(ItemBalance(item_id=item.id, qty_base=0, value_paise=0))
                await session.flush()

            item_map[sku] = item

        # ── 4. Price List ──────────────────────────────────────────────
        # Murukku 200 g price: ₹50.00 = 5000 paise
        fg_item = item_map["FG-MURUKKU-200"]
        existing_price = await session.execute(
            select(PriceList).where(PriceList.item_id == fg_item.id)
        )
        if not existing_price.scalar_one_or_none():
            session.add(
                PriceList(
                    item_id=fg_item.id,
                    price_paise=5000,
                    effective_from=date(2026, 4, 1),
                )
            )
            await session.flush()

        # ── 5. BOM Murukku 200 g ───────────────────────────────────────
        # Yield 200 packets per batch:
        # flour 40 kg (40,000 g), oil 10 L (10,000 ml), spice mix 1.2 kg (1,200 g),
        # pouches 200, cartons 10
        existing_bom = await session.execute(
            select(Bom).where(Bom.product_item_id == fg_item.id, Bom.version == 1)
        )
        bom = existing_bom.scalar_one_or_none()
        if not bom:
            bom = Bom(
                product_item_id=fg_item.id,
                version=1,
                yield_packets=200,
                active=True,
            )
            session.add(bom)
            await session.flush()

            bom_lines_spec = [
                ("RM-FLOUR", 40000),
                ("RM-OIL", 10000),
                ("RM-SPICE", 1200),
                ("PKG-POUCH-200", 200),
                ("PKG-CARTON", 10),
            ]
            for sku, qty in bom_lines_spec:
                session.add(
                    BomLine(
                        bom_id=bom.id,
                        item_id=item_map[sku].id,
                        qty_base=qty,
                    )
                )
            await session.flush()

        # ── 6. Supplier ────────────────────────────────────────────────
        existing_supp = await session.execute(
            select(Supplier).where(Supplier.name == "Madurai Agro Traders")
        )
        if not existing_supp.scalar_one_or_none():
            supp = Supplier(
                name="Madurai Agro Traders",
                gstin="33SUPPL0000S1Z1",
                phone="9876543210",
                address="12 Rice Mill Street, Madurai, Tamil Nadu 625001",
                active=True,
            )
            session.add(supp)
            await session.flush()

        # ── 7. Customers ───────────────────────────────────────────────
        customers_spec = [
            (
                "Retailer A",
                "RETAILER",
                "33AAAAA0000A1Z5",
                33,
                "Tamil Nadu",
                "10 Bazaar Street, Tiruchirappalli, Tamil Nadu",
                "9443322110",
                user_map["salesman_a"].id,
                30,
            ),
            (
                "Distributor B",
                "DISTRIBUTOR",
                "29BBBBB0000B1Z5",
                29,
                "Karnataka",
                "45 Commercial Road, Bengaluru, Karnataka",
                "9880011223",
                user_map["salesman_b"].id,
                45,
            ),
        ]
        for name, ctype, gstin, state_code, state_name, addr, phone, sm_id, cdays in customers_spec:
            existing_c = await session.execute(select(Customer).where(Customer.name == name))
            if not existing_c.scalar_one_or_none():
                cust = Customer(
                    name=name,
                    type=ctype,
                    gstin=gstin,
                    state_code=state_code,
                    state_name=state_name,
                    address=addr,
                    phone=phone,
                    salesman_id=sm_id,
                    credit_days=cdays,
                    active=True,
                )
                session.add(cust)
                await session.flush()

        # ── 8. Opening stock ledger rows ───────────────────────────────
        # Section 10:
        # flour 100 kg at ₹42/kg (100,000 g, 4.200000 p/g, 420,000 paise)
        # oil 30 L at ₹140/L (30,000 ml, 14.000000 p/ml, 420,000 paise)
        # spice mix 5 kg at ₹200/kg (5,000 g, 20.000000 p/g, 100,000 paise)
        # pouches 500 at ₹2.50 (500 piece, 250.000000 p/piece, 125,000 paise)
        # cartons 30 at ₹15 (30 piece, 1500.000000 p/piece, 45,000 paise)
        # finished Murukku 50 packets at ₹30.00 (50 piece, 3000.000000 p/piece, 150,000 paise)
        opening_spec = [
            ("RM-FLOUR", 100000, Decimal("4.200000"), 420000),
            ("RM-OIL", 30000, Decimal("14.000000"), 420000),
            ("RM-SPICE", 5000, Decimal("20.000000"), 100000),
            ("PKG-POUCH-200", 500, Decimal("250.000000"), 125000),
            ("PKG-CARTON", 30, Decimal("1500.000000"), 45000),
            ("FG-MURUKKU-200", 50, Decimal("3000.000000"), 150000),
        ]

        admin_user = user_map["admin"]
        now = datetime.now(timezone.utc)

        for sku, qty, unit_cost, total_paise in opening_spec:
            item = item_map[sku]
            existing_ledger = await session.execute(
                select(StockLedger).where(
                    StockLedger.item_id == item.id,
                    StockLedger.movement_type == "OPENING",
                )
            )
            if not existing_ledger.scalar_one_or_none():
                ledger_entry = StockLedger(
                    item_id=item.id,
                    movement_type="OPENING",
                    qty_base=qty,
                    unit_cost=unit_cost,
                    value_paise=total_paise,
                    source_type="OPENING_BALANCE",
                    source_id=0,
                    posted_by=admin_user.id,
                    posted_at=now,
                    note=f"Opening balance for {sku}",
                )
                session.add(ledger_entry)

                # Update item_balances cache
                bal_row = await session.execute(
                    select(ItemBalance).where(ItemBalance.item_id == item.id)
                )
                ib = bal_row.scalar_one_or_none()
                if ib:
                    ib.qty_base += qty
                    ib.value_paise += total_paise
                else:
                    session.add(ItemBalance(item_id=item.id, qty_base=qty, value_paise=total_paise))

        await session.commit()
        print("Seed data successfully inserted or verified.")


if __name__ == "__main__":
    asyncio.run(seed_data())
