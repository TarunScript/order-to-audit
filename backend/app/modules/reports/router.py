"""Reports router with multi-format export (JSON, CSV, XLSX, PDF)."""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_roles
from app.core.database import get_db
from app.models import User
from app.modules.reports.generators import (
    get_sales_register_data,
    get_customer_sales_data,
    get_product_sales_data,
    get_gst_summary_data,
    get_purchase_register_data,
    get_stock_report_data,
    get_production_report_data,
    get_all_customers_outstanding_data,
)
from app.modules.reports.exporters import (
    export_csv_response,
    export_xlsx_response,
    export_pdf_response,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/{name}")
async def get_report(
    name: str,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    as_of: Optional[date] = None,
    format: str = Query("json", pattern="^(json|csv|xlsx|pdf)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "production", "auditor", "owner")),
):
    """Generate auditor-ready reports in JSON, CSV, Excel (XLSX), or PDF format."""
    # Production role may only access production report
    if current_user.role == "production" and name not in ["production", "production-runs", "production-report"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Production supervisor only has access to the production report", "details": None},
        )

    norm_name = name.lower().replace("_", "-")

    # ─────────────────────────────────────────────────────────────────
    # 1. SALES REGISTER
    # ─────────────────────────────────────────────────────────────────
    if norm_name in ["sales-register", "sales"]:
        data = await get_sales_register_data(db, from_date, to_date)
        if format == "json":
            return data
        headers = ["Invoice No", "Date", "Customer", "GSTIN", "Place of Supply", "Supply Type", "Taxable (₹)", "CGST (₹)", "SGST (₹)", "IGST (₹)", "Total (₹)", "Status"]
        rows = [
            [r["invoice_no"], r["invoice_date"], r["customer_name"], r["customer_gstin"], r["place_of_supply"], r["supply_type"], f"₹{r['taxable_rs']:.2f}", f"₹{r['cgst_rs']:.2f}", f"₹{r['sgst_rs']:.2f}", f"₹{r['igst_rs']:.2f}", f"₹{r['total_rs']:.2f}", r["status"]]
            for r in data["rows"]
        ]
        if format == "csv":
            return export_csv_response(headers, rows, "sales_register")
        if format == "xlsx":
            return export_xlsx_response("Sales Register", headers, rows, "sales_register")
        if format == "pdf":
            summary = {"Total Invoices": data["summary"]["total_invoices"], "Grand Total": f"₹{data['summary']['grand_total_rs']:.2f}"}
            return export_pdf_response("Sales Register", headers, rows, "sales_register", summary)

    # ─────────────────────────────────────────────────────────────────
    # 2. CUSTOMER-WISE SALES
    # ─────────────────────────────────────────────────────────────────
    elif norm_name in ["customer-sales", "customer-wise-sales"]:
        data = await get_customer_sales_data(db, from_date, to_date)
        if format == "json":
            return data
        headers = ["Customer", "GSTIN", "State", "Invoices Count", "Taxable (₹)", "CGST (₹)", "SGST (₹)", "IGST (₹)", "Total (₹)"]
        rows = [
            [r["customer_name"], r["gstin"], r["state_name"], r["invoice_count"], f"₹{r['taxable_rs']:.2f}", f"₹{r['cgst_rs']:.2f}", f"₹{r['sgst_rs']:.2f}", f"₹{r['igst_rs']:.2f}", f"₹{r['total_rs']:.2f}"]
            for r in data["rows"]
        ]
        if format == "csv":
            return export_csv_response(headers, rows, "customer_sales")
        if format == "xlsx":
            return export_xlsx_response("Customer-wise Sales", headers, rows, "customer_sales")
        if format == "pdf":
            summary = {"Total Customers": data["summary"]["total_customers"], "Grand Total": f"₹{data['summary']['grand_total_rs']:.2f}"}
            return export_pdf_response("Customer-wise Sales", headers, rows, "customer_sales", summary)

    # ─────────────────────────────────────────────────────────────────
    # 3. PRODUCT-WISE SALES
    # ─────────────────────────────────────────────────────────────────
    elif norm_name in ["product-sales", "product-wise-sales"]:
        data = await get_product_sales_data(db, from_date, to_date)
        if format == "json":
            return data
        headers = ["SKU", "Product Name", "Unit", "Total Qty", "Taxable (₹)", "Tax (₹)", "Total (₹)"]
        rows = [
            [r["sku"], r["item_name"], r["display_unit"], r["total_qty"], f"₹{r['taxable_rs']:.2f}", f"₹{r['tax_rs']:.2f}", f"₹{r['total_rs']:.2f}"]
            for r in data["rows"]
        ]
        if format == "csv":
            return export_csv_response(headers, rows, "product_sales")
        if format == "xlsx":
            return export_xlsx_response("Product-wise Sales", headers, rows, "product_sales")
        if format == "pdf":
            summary = {"Total Products": data["summary"]["total_products"], "Grand Total": f"₹{data['summary']['grand_total_rs']:.2f}"}
            return export_pdf_response("Product-wise Sales", headers, rows, "product_sales", summary)

    # ─────────────────────────────────────────────────────────────────
    # 4. GST SUMMARY (GSTR-1 & GSTR-3B)
    # ─────────────────────────────────────────────────────────────────
    elif norm_name in ["gst-summary", "gst", "gstr-1"]:
        data = await get_gst_summary_data(db, from_date, to_date)
        if format == "json":
            return data
        headers = ["GSTIN", "Customer", "Invoice No", "Date", "Place of Supply", "Rate", "Taxable (₹)", "CGST (₹)", "SGST (₹)", "IGST (₹)", "Invoice Value (₹)"]
        rows = [
            [r["gstin"], r["customer_name"], r["invoice_no"], r["invoice_date"], r["place_of_supply"], r["rate_pct"], f"₹{r['taxable_rs']:.2f}", f"₹{r['cgst_rs']:.2f}", f"₹{r['sgst_rs']:.2f}", f"₹{r['igst_rs']:.2f}", f"₹{r['invoice_value_rs']:.2f}"]
            for r in data["gstr_1_b2b_invoices"]
        ]
        if format == "csv":
            return export_csv_response(headers, rows, "gst_summary")
        if format == "xlsx":
            return export_xlsx_response("GSTR-1 B2B Invoices", headers, rows, "gst_summary")
        if format == "pdf":
            summary = {
                "3.1(a) Taxable Value": f"₹{data['gstr_3b_table_3_1_a']['total_taxable_value_rs']:.2f}",
                "Total GST Tax": f"₹{data['gstr_3b_table_3_1_a']['total_tax_rs']:.2f}",
            }
            return export_pdf_response("GST Outward Supplies (GSTR-1)", headers, rows, "gst_summary", summary)

    # ─────────────────────────────────────────────────────────────────
    # 5. PURCHASE REGISTER
    # ─────────────────────────────────────────────────────────────────
    elif norm_name in ["purchase-register", "purchases"]:
        data = await get_purchase_register_data(db, from_date, to_date)
        if format == "json":
            return data
        headers = ["Bill No", "Date", "Supplier", "GSTIN", "Items Summary", "Total Value (₹)", "Status"]
        rows = [
            [r["bill_no"], r["purchase_date"], r["supplier_name"], r["supplier_gstin"], r["items_summary"], f"₹{r['total_value_rs']:.2f}", r["status"]]
            for r in data["rows"]
        ]
        if format == "csv":
            return export_csv_response(headers, rows, "purchase_register")
        if format == "xlsx":
            return export_xlsx_response("Purchase Register", headers, rows, "purchase_register")
        if format == "pdf":
            summary = {"Total Purchases": data["summary"]["total_purchases"], "Grand Total": f"₹{data['summary']['grand_total_rs']:.2f}"}
            return export_pdf_response("Purchase Register", headers, rows, "purchase_register", summary)

    # ─────────────────────────────────────────────────────────────────
    # 6. STOCK SUMMARY & RECONCILIATION
    # ─────────────────────────────────────────────────────────────────
    elif norm_name in ["stock-summary", "stock", "stock-report"]:
        data = await get_stock_report_data(db, from_date, to_date)
        if format == "json":
            return data
        headers = ["SKU", "Item Name", "Type", "Unit", "Opening Qty", "Receipts Qty", "Issues Qty", "Adjustments Qty", "Closing Qty", "Closing Value (₹)", "Low Stock Alert"]
        rows = [
            [r["sku"], r["name"], r["type"], r["display_unit"], r["opening_qty_display"], r["receipts_qty_display"], r["issues_qty_display"], r["adjustments_qty_display"], r["closing_qty_display"], f"₹{r['closing_value_rs']:.2f}", "LOW STOCK" if r["is_low_stock"] else "OK"]
            for r in data["rows"]
        ]
        if format == "csv":
            return export_csv_response(headers, rows, "stock_summary")
        if format == "xlsx":
            return export_xlsx_response("Stock Summary & Reconciliation", headers, rows, "stock_summary")
        if format == "pdf":
            return export_pdf_response("Stock Summary & Movements", headers, rows, "stock_summary")

    # ─────────────────────────────────────────────────────────────────
    # 7. PRODUCTION REPORT
    # ─────────────────────────────────────────────────────────────────
    elif norm_name in ["production", "production-runs", "production-report"]:
        data = await get_production_report_data(db, from_date, to_date)
        if format == "json":
            return data
        headers = ["Run No", "Date", "Product", "Batch Factor", "Expected Output", "Actual Good Output", "Yield Var %", "Yield Flagged", "Material Cost (₹)", "Overheads (₹)", "Cost/Packet (₹)"]
        rows = [
            [r["run_no"], r["run_date"], r["product_name"], r["batch_factor"], r["expected_output"], r["actual_good_output"], r["yield_variance_pct"], "YES (FLAGGED)" if r["yield_flagged"] else "NO", f"₹{r['material_cost_rs']:.2f}", f"₹{r['overheads_rs']:.2f}", f"₹{r['cost_per_packet_rs']:.2f}"]
            for r in data["rows"]
        ]
        if format == "csv":
            return export_csv_response(headers, rows, "production_report")
        if format == "xlsx":
            return export_xlsx_response("Production & Variance Report", headers, rows, "production_report")
        if format == "pdf":
            return export_pdf_response("Production Runs & Variance Report", headers, rows, "production_report")

    # ─────────────────────────────────────────────────────────────────
    # 8. OUTSTANDING WITH AGEING
    # ─────────────────────────────────────────────────────────────────
    elif norm_name in ["outstanding", "customer-outstanding", "ageing"]:
        data = await get_all_customers_outstanding_data(db, as_of)
        if format == "json":
            return data
        headers = ["Customer", "Credit Days", "Total Invoiced (₹)", "Total Paid (₹)", "Total Outstanding (₹)", "0-30 Days (₹)", "31-60 Days (₹)", "61-90 Days (₹)", "90+ Days (₹)"]
        rows = [
            [r["customer_name"], r["credit_days"], f"₹{r['total_invoiced_rs']:.2f}", f"₹{r['total_paid_rs']:.2f}", f"₹{r['outstanding_rs']:.2f}", f"₹{r['bucket_0_30_rs']:.2f}", f"₹{r['bucket_31_60_rs']:.2f}", f"₹{r['bucket_61_90_rs']:.2f}", f"₹{r['bucket_90_plus_rs']:.2f}"]
            for r in data["rows"]
        ]
        if format == "csv":
            return export_csv_response(headers, rows, "customer_outstanding_ageing")
        if format == "xlsx":
            return export_xlsx_response("Customer Outstanding & Ageing", headers, rows, "customer_outstanding_ageing")
        if format == "pdf":
            summary = {"Total Outstanding": f"₹{data['summary']['total_outstanding_rs']:.2f}"}
            return export_pdf_response("Customer Outstanding & Ageing Analysis", headers, rows, "customer_outstanding_ageing", summary)

    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPORT_NOT_FOUND", "message": f"Report '{name}' not found", "details": None},
        )
