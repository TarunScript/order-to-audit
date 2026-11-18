# Order-to-Audit System

> Production, Inventory, GST Billing, and Costing ERP Monolith for South Indian Snack Manufacturers.
> Project: NIT Tiruchirappalli, Centre for Digital Infrastructure.

---

## 1. Quick Start

Run the entire system (PostgreSQL 16, Python 3.12 FastAPI, and React 18 TypeScript PWA) with a single command:

```bash
docker compose up --build
```

- **Frontend Web App**: [http://localhost:5173](http://localhost:5173)
- **FastAPI Documentation**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- **Database**: PostgreSQL on port `5432` (`ota` / `ota_secret`)

### Resetting Demo Data
To reset the database back to PRD Section 10 seed state at any time via CLI:

```bash
python3 backend/reset_demo.py
```

### Running Automated Test Suite
```bash
cd backend
python3 -m pytest
```
All 24 unit, integration, and benchmark acceptance tests pass in under 7 seconds.

---

## 2. Tech Stack & Architectural Rationale

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (AsyncIO), Alembic, Pydantic v2. Chosen for high-throughput transactional posting, declarative schema constraints, strict type safety, and automatic OpenAPI generation.
- **Database**: PostgreSQL 16. Enforces append-only integrity via database triggers blocking `UPDATE`/`DELETE` on `stock_ledger` and mutations to `POSTED` tax invoices.
- **Frontend**: React 18, TypeScript, Vite 5, Tailwind CSS, built as an installable PWA with Service Worker offline caching and IndexedDB outbox synchronization.
- **Financial & Stock Integrity**: Zero floats. All money is stored as integer paise (`BIGINT`, `1 INR = 100 paise`). All inventory is stored as integer base units (`g`, `ml`, `piece`). Unit costs use `NUMERIC(18,6)` with half-up rounding.

---

## 3. Test Credentials (All Roles)

| Role | Username | Password | Purpose & Screen Scope |
| --- | --- | --- | --- |
| **Salesman (TN)** | `salesman_a` | `password123` | Mobile-first (360px) order taking for assigned Retailer A, offline outbox, customer sales |
| **Salesman (KA)** | `salesman_b` | `password123` | Mobile-first order taking for assigned Distributor B |
| **Admin & Billing** | `admin` | `password123` | Orders queue, stock verification, GST tax invoicing, PDF export, WhatsApp sharing, dispatch, payments & ageing |
| **Production Supervisor**| `production` | `password123` | Raw material purchases, BOM production runs, live variance alerts, overheads allocation |
| **Statutory Auditor** | `auditor` | `password123` | Read-only access to stock ledgers, mathematical reconciliation, GSTR reports, export to CSV/XLSX/PDF |
| **Managing Director** | `owner` | `password123` | Executive dashboard, today's orders, open variance alerts, unit margins, top debtors |

*Note: The login page includes quick-fill preset buttons for each role for instant one-click demonstration.*

---

## 4. Benchmark Acceptance Results (PRD Section 11)

The full 9-step benchmark scenario was executed via API integration test (`tests/test_benchmark.py`). Every single expected value matches:

| Metric / Check | PRD Expected Value | System Output | Status |
| --- | --- | --- | --- |
| **Flour Closing Stock** | 120 kg (100 + 60 - 40) | 120,000 g (120.0 kg) | ✅ Exact Match |
| **Cooking Oil Closing Stock** | 19.5 L (30 - 10.5) | 19,500 ml (19.5 L) | ✅ Exact Match |
| **Spice Mix Closing Stock** | 3.8 kg (5 - 1.2) | 3,800 g (3.8 kg) | ✅ Exact Match |
| **200g Pouches Closing Stock** | 306 pouches (194 used) | 306 pouches | ✅ Exact Match |
| **Cartons Closing Stock** | 21 cartons (9 used) | 21 cartons | ✅ Exact Match |
| **Finished Goods after Run** | 238 packets | 238 packets | ✅ Exact Match |
| **Finished Goods after Dispatch** | 88 packets (238 - 150) | 88 packets | ✅ Exact Match |
| **Yield Variance** | 188 vs 200 = -6%, flagged | -600 bp (-6.0%), Flagged | ✅ Exact Match |
| **Cooking Oil Variance** | 10.5 vs 10 L = +5%, flagged | +500 bp (+5.0%), Flagged | ✅ Exact Match |
| **Flour & Spice Variance** | 0%, not flagged | 0 bp (0.0%), Not Flagged | ✅ Exact Match |
| **Pouch Variance** | 194 vs 200 = -3%, NOT flagged | -300 bp (-3.0%), Not Flagged | ✅ Exact Match |
| **Carton Variance** | 9 vs 10 = -10%, flagged | -1000 bp (-10.0%), Flagged | ✅ Exact Match |
| **Retailer A Invoice** | Taxable ₹7,500.00 + CGST ₹187.50 + SGST ₹187.50 = ₹7,875.00 | 750000p + 18750p + 18750p = 787500p (₹7,875.00) | ✅ Exact Match |
| **Retailer A Outstanding** | ₹3,875.00 (after ₹4,000 payment) | 387500 paise (₹3,875.00) | ✅ Exact Match |
| **Distributor B Stock Check** | Requested 120, Available 88, Shortage 32 | Requested 120, Available 88, Shortage 32 (Approval Blocked) | ✅ Exact Match |
| **Distributor B Invoice Preview** | IGST 5%: Taxable ₹6,000.00 + IGST ₹300.00 = ₹6,300.00 | Taxable 600000p + IGST 30000p = 630000p (₹6,300.00) | ✅ Exact Match |
| **Flour WAC after Purchase** | ₹43.125 / kg ((100×42 + 60×45)/160) | 4.312500 p/g (₹43.125/kg) | ✅ Exact Match |
| **Run Material Cost** | ₹4,055.00 (1725 + 1470 + 240 + 485 + 135) | 405500 paise (₹4,055.00) | ✅ Exact Match |
| **Run Overheads** | ₹1,800.00 (Labour 1200 + Power 600) | 180000 paise (₹1,800.00) | ✅ Exact Match |
| **Cost Per Packet** | ₹5,855.00 / 188 = ₹31.14 (3114 paise) | 3114 paise (₹31.14) | ✅ Exact Match |
| **Margin Per Packet** | ₹18.86 (1886 paise vs ₹50.00 retail) | 1886 paise (₹18.86) | ✅ Exact Match |
| **Stock Ledger Reconciliation** | Ledger sum == Item balances for all items | All 6 items reconciled (0 mismatches) | ✅ Exact Match |

### Benchmark Differences Explanation
- **Pouch Variance (-3%)**: 194 pouches were used vs 200 expected. The variance is exactly $-3\%$ ($-300\text{ bp}$). Since the PRD specifies that variance flags trigger **strictly greater** than tolerance ($|\text{variance}| > \text{tolerance}$), $-300\text{ bp}$ equals the $300\text{ bp}$ tolerance and is correctly **NOT flagged**.
- **Carton Variance (-10%)**: 9 cartons were consumed vs 10 expected ($-10\%$ or $-1000\text{ bp}$). Since $|-1000| > 300$, it is correctly **flagged**. Every BOM line is comprehensively validated, ensuring full audit visibility.

---

## 5. Features Built Against Tiers

### Must-Have Tier (Completed 100%)
- Single command `docker compose up` launch.
- Integer paise everywhere; unit costs in `NUMERIC(18,6)` with half-up rounding.
- Append-only `stock_ledger` with transactional posting engine (`post_purchase`, `post_production_run`, `post_dispatch`, `post_credit_note`, `post_adjustment`, `cancel_production_run`).
- Real-time stock balance reconciliation endpoint (`/api/stock/reconcile`) proving zero drift.
- Production run form with batch scaling, BOM prefill, live line-by-line variance, overhead allocation, packet cost valuation.
- Salesman mobile order taking (< 1 minute flow, tap steppers, pre-tax totals).
- Admin verification queue, live stock shortage detection in RED, price/quantity edits, order approval/rejection.
- GST tax invoicing (INTRA state CGST+SGST vs INTER state IGST), FY sequence allocation, WeasyPrint PDF generation, WhatsApp and mailto links.
- Dispatch recording to relieve finished goods stock; invoice cancellation via Credit Notes.
- Customer payments, net outstanding ledger, and 0-30, 31-60, 61-90, 90+ days ageing analysis.
- Statutory and operational reports (Sales Register, Customer Sales, Product Sales, GSTR-1 & 3B Summary, Purchase Register, Stock Summary & Ledger, Production Report, Outstanding) with CSV, XLSX, and PDF multi-format export.
- Executive owner dashboard with today's orders, pending approvals, low-stock markers, open variance alerts, unit margins, top debtors.
- Role-Based Access Control (RBAC) enforced on every API route and UI navigation.

### Should-Have & Stretch Tier (Completed)
- **Offline Order Capture**: PWA with IndexedDB outbox. Salesmen can book orders without an active internet connection. On network reconnection, outbox automatically flushes to the backend with client UUID deduplication.
- **Low Stock Markers**: Amber alerts on stock summary and executive dashboard when closing stock breaches reorder thresholds.
- **Audit Logging**: Structured JSON logging of before-and-after states for invoice updates, order edits, and production overhead adjustments.
- **Database Immutability Triggers**: Postgres triggers preventing direct updates or deletions on posted tax invoices and stock movements.

---

## 6. Assumptions

1. **Opening Balances Valuation**: Finished Murukku opening inventory (50 packets) is valued at an assumed baseline cost of ₹30.00/packet (150,000 paise total), documented in `seed.py`.
2. **Salesman Price Override**: If a specific customer price override is configured, the mobile order flow honors it; otherwise, the standard active price list rate (₹50.00/pkt) is applied.
3. **Reversal Movements**: Cancelling a production run creates linked `REVERSAL` ledger entries that mirror the original issue and receipt lines, preserving audit integrity without destroying history.

---

## 7. Known Gaps

1. **Live E-Way Bill / E-Invoice Portal Integration**: Government portal sandbox integration is mocked; payload complies with GSTR-1 schema.
2. **Payment Gateway**: Payments are currently recorded as bank instruments (NEFT, UPI, Cheque, Cash) rather than real-time credit card gateway webhooks.
3. **Multi-Warehouse Transfer**: Single factory warehouse model is implemented; inter-depot branch transfers can be accommodated by adding a `warehouse_id` foreign key.

---

## 8. Scalability & Extensibility Note (Interview Readiness)

To add another pack size (e.g. **Murukku 500 g**) without database schema alterations:
1. Create a new Item with sku `FG-MURUKKU-500`, base unit `piece`, display unit `packet`.
2. Insert conversion factor in `item_units` ($1\text{ carton} = 8\text{ packets}$).
3. Create a BOM entry linked to `FG-MURUKKU-500` with recipe quantities scaled by pack weight ($2.5\times$ base BOM quantities for the same 200-packet batch yield).
4. Add price list entry for `FG-MURUKKU-500` (e.g. ₹120.00).
5. All costing, variance, order Taking, stock checks, and tax billing automatically work without requiring code modifications.
