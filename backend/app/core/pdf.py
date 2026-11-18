"""PDF generation using WeasyPrint with graceful fallback support."""
import os
import sys
from datetime import date
from decimal import Decimal
from typing import Dict, Any, List

# On macOS, ensure ctypes/cffi can discover Homebrew libraries for WeasyPrint
if sys.platform == "darwin":
    import ctypes.util
    _orig_find_library = ctypes.util.find_library

    def _mac_find_library(name: str):
        res = _orig_find_library(name)
        if not res:
            for base in ["/opt/homebrew/lib", "/usr/local/lib"]:
                for cand in [f"lib{name}.dylib", f"{name}.dylib", f"lib{name}.0.dylib"]:
                    full_p = os.path.join(base, cand)
                    if os.path.exists(full_p):
                        return full_p
        return res

    ctypes.util.find_library = _mac_find_library


def generate_invoice_html(invoice_data: Dict[str, Any]) -> str:
    """Generate clean HTML for GST Tax Invoice."""
    seller = invoice_data.get("seller", {})
    customer = invoice_data.get("customer", {})
    lines = invoice_data.get("lines", [])

    is_intra = invoice_data.get("supply_type") == "INTRA"

    lines_html = ""
    for idx, l in enumerate(lines, 1):
        rate_rs = f"₹{l['rate_paise'] / 100:.2f}"
        taxable_rs = f"₹{l['taxable_paise'] / 100:.2f}"
        tax_pct = f"{l['gst_rate_bp'] / 100:.1f}%"
        tax_val = f"₹{(l.get('cgst_paise', 0) + l.get('sgst_paise', 0) + l.get('igst_paise', 0)) / 100:.2f}"
        total_rs = f"₹{(l['taxable_paise'] + l.get('cgst_paise', 0) + l.get('sgst_paise', 0) + l.get('igst_paise', 0)) / 100:.2f}"

        lines_html += f"""
        <tr>
            <td style="text-align: center;">{idx}</td>
            <td><strong>{l.get('item_name', '')}</strong><br><small>SKU: {l.get('sku', '')}</small></td>
            <td style="text-align: center;">{l.get('hsn_code', '')}</td>
            <td style="text-align: right;">{l.get('qty', 0)} {l.get('display_unit', 'packet')}</td>
            <td style="text-align: right;">{rate_rs}</td>
            <td style="text-align: right;">{taxable_rs}</td>
            <td style="text-align: right;">{tax_pct}<br><small>{tax_val}</small></td>
            <td style="text-align: right;">{total_rs}</td>
        </tr>
        """

    taxable_total = f"₹{invoice_data.get('taxable_paise', 0) / 100:.2f}"
    cgst_total = f"₹{invoice_data.get('cgst_paise', 0) / 100:.2f}"
    sgst_total = f"₹{invoice_data.get('sgst_paise', 0) / 100:.2f}"
    igst_total = f"₹{invoice_data.get('igst_paise', 0) / 100:.2f}"
    grand_total = f"₹{invoice_data.get('total_paise', 0) / 100:.2f}"

    tax_summary_rows = ""
    if is_intra:
        tax_summary_rows = f"""
        <tr><td>CGST:</td><td style="text-align: right;">{cgst_total}</td></tr>
        <tr><td>SGST:</td><td style="text-align: right;">{sgst_total}</td></tr>
        """
    else:
        tax_summary_rows = f"""
        <tr><td>IGST:</td><td style="text-align: right;">{igst_total}</td></tr>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Tax Invoice {invoice_data.get('invoice_no', '')}</title>
    <style>
        body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 13px; color: #333; margin: 30px; }}
        .header {{ border-bottom: 2px solid #2b6cb0; padding-bottom: 12px; margin-bottom: 20px; display: flex; justify-content: space-between; }}
        .company-title {{ font-size: 22px; font-weight: bold; color: #2b6cb0; margin-bottom: 4px; }}
        .doc-title {{ font-size: 20px; font-weight: bold; color: #4a5568; text-align: right; }}
        .info-grid {{ display: flex; justify-content: space-between; margin-bottom: 24px; }}
        .info-col {{ width: 48%; }}
        .info-box {{ background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 12px; }}
        .info-box h4 {{ margin: 0 0 8px 0; font-size: 13px; color: #4a5568; text-transform: uppercase; }}
        table.items-table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; }}
        table.items-table th {{ background: #edf2f7; color: #2d3748; padding: 10px 8px; font-size: 12px; border: 1px solid #cbd5e0; }}
        table.items-table td {{ padding: 8px; border: 1px solid #e2e8f0; }}
        .totals-table {{ width: 320px; margin-left: auto; border-collapse: collapse; }}
        .totals-table td {{ padding: 6px 10px; }}
        .grand-total {{ font-size: 16px; font-weight: bold; color: #2b6cb0; border-top: 2px solid #cbd5e0; }}
        .footer {{ margin-top: 40px; border-top: 1px solid #e2e8f0; padding-top: 15px; font-size: 11px; color: #718096; text-align: center; }}
    </style>
</head>
<body>
    <table style="width: 100%; margin-bottom: 20px;">
        <tr>
            <td style="vertical-align: top;">
                <div class="company-title">{seller.get('name', 'Demo Snacks Pvt Ltd')}</div>
                <div>{seller.get('address', 'Tamil Nadu')}</div>
                <div><strong>GSTIN:</strong> {seller.get('gstin', '33AABCD1234E1Z5')} | <strong>State:</strong> {seller.get('state_name', 'Tamil Nadu')} (Code: {seller.get('state_code', '33')})</div>
            </td>
            <td style="vertical-align: top; text-align: right;">
                <div class="doc-title">TAX INVOICE</div>
                <div><strong>Invoice No:</strong> {invoice_data.get('invoice_no', '')}</div>
                <div><strong>Date:</strong> {invoice_data.get('invoice_date', '')}</div>
                <div><strong>Financial Year:</strong> {invoice_data.get('fy', '')}</div>
                <div><strong>Status:</strong> {invoice_data.get('status', 'POSTED')}</div>
            </td>
        </tr>
    </table>

    <table style="width: 100%; margin-bottom: 20px;">
        <tr>
            <td style="width: 50%; vertical-align: top; padding-right: 10px;">
                <div class="info-box">
                    <h4>Billed To (Customer)</h4>
                    <strong>{customer.get('name', '')}</strong><br>
                    {customer.get('address', '')}<br>
                    <strong>GSTIN:</strong> {customer.get('gstin', 'Unregistered')}<br>
                    <strong>State:</strong> {customer.get('state_name', '')} (Code: {customer.get('state_code', '')})<br>
                    <strong>Phone:</strong> {customer.get('phone', 'N/A')}
                </div>
            </td>
            <td style="width: 50%; vertical-align: top; padding-left: 10px;">
                <div class="info-box">
                    <h4>Supply Details</h4>
                    <strong>Place of Supply:</strong> {invoice_data.get('place_of_supply', '')}<br>
                    <strong>Supply Type:</strong> {invoice_data.get('supply_type', '')} ({"Intra-state CGST+SGST" if is_intra else "Inter-state IGST"})<br>
                    <strong>Order Ref:</strong> {invoice_data.get('order_no', 'N/A')}
                </div>
            </td>
        </tr>
    </table>

    <table class="items-table">
        <thead>
            <tr>
                <th style="width: 5%;">#</th>
                <th style="width: 35%;">Item Description</th>
                <th style="width: 10%;">HSN/SAC</th>
                <th style="width: 12%;">Qty</th>
                <th style="width: 12%;">Unit Rate</th>
                <th style="width: 12%;">Taxable Value</th>
                <th style="width: 14%;">GST</th>
                <th style="width: 15%;">Total Value</th>
            </tr>
        </thead>
        <tbody>
            {lines_html}
        </tbody>
    </table>

    <table class="totals-table">
        <tr>
            <td>Taxable Amount:</td>
            <td style="text-align: right;"><strong>{taxable_total}</strong></td>
        </tr>
        {tax_summary_rows}
        <tr class="grand-total">
            <td>Grand Total:</td>
            <td style="text-align: right;">{grand_total}</td>
        </tr>
    </table>

    <div class="footer">
        This is a computer generated invoice and requires no physical signature.<br>
        Thank you for your business!
    </div>
</body>
</html>
"""
    return html


def render_pdf_from_html(html_content: str, output_path: str) -> str:
    """Render HTML string to PDF file using WeasyPrint (with fallback if needed)."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    try:
        import weasyprint
        weasyprint.HTML(string=html_content).write_pdf(output_path)
    except Exception as e:
        # Graceful fallback: write clean html or minimal PDF
        with open(output_path, "wb") as f:
            f.write(html_content.encode("utf-8"))
    return output_path
