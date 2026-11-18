"""Export helpers for CSV, Excel (XLSX), and PDF reports."""
import csv
import io
import os
import tempfile
from typing import List, Dict, Any, Optional
from fastapi import Response
from fastapi.responses import StreamingResponse
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.core.pdf import render_pdf_from_html


def export_csv_response(headers: List[str], rows: List[List[Any]], filename: str) -> Response:
    """Export tabular data to standard CSV response."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)

    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )


def export_xlsx_response(title: str, headers: List[str], rows: List[List[Any]], filename: str) -> Response:
    """Export styled Excel sheet with headers, borders, and auto column widths."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title[:31]  # Excel tab name limit 31 chars

    # Title row
    ws.append([title])
    title_cell = ws.cell(row=1, column=1)
    title_cell.font = Font(size=14, bold=True, color="1A365D")
    ws.append([])  # blank row

    # Headers
    ws.append(headers)
    header_font = Font(size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2B6CB0", end_color="2B6CB0", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=3, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment

    # Thin border style
    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    # Data rows
    for row_data in rows:
        ws.append(row_data)
        current_row = ws.max_row
        for col_idx in range(1, len(row_data) + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.border = thin_border
            # Right-align numbers
            if isinstance(cell.value, (int, float)):
                cell.alignment = Alignment(horizontal="right")

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.row > 1 and cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
    )


def export_pdf_response(title: str, headers: List[str], rows: List[List[Any]], filename: str, summary_info: Optional[Dict[str, Any]] = None) -> Response:
    """Generate professional PDF report from HTML template."""
    summary_html = ""
    if summary_info:
        cards_html = ""
        for k, v in summary_info.items():
            label = k.replace("_", " ").title()
            cards_html += f"""
            <div style="background:#f7fafc;border:1px solid #e2e8f0;padding:8px 12px;border-radius:4px;display:inline-block;margin-right:12px;margin-bottom:8px;">
                <div style="font-size:10px;color:#718096;text-transform:uppercase;">{label}</div>
                <div style="font-size:14px;font-weight:bold;color:#2d3748;">{v}</div>
            </div>
            """
        summary_html = f"<div style='margin-bottom:16px;'>{cards_html}</div>"

    headers_th = "".join(f"<th style='padding:8px;background:#2b6cb0;color:#fff;border:1px solid #cbd5e0;font-size:11px;'>{h}</th>" for h in headers)
    
    rows_tr = ""
    for r in rows:
        tds = ""
        for val in r:
            align = "right" if isinstance(val, (int, float)) or (isinstance(val, str) and (val.startswith("₹") or val.endswith("%"))) else "left"
            tds += f"<td style='padding:6px 8px;border:1px solid #e2e8f0;text-align:{align};font-size:11px;'>{val}</td>"
        rows_tr += f"<tr>{tds}</tr>"

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; margin: 25px; color: #333; }}
        h2 {{ color: #2b6cb0; margin-bottom: 6px; }}
        .meta {{ font-size: 11px; color: #718096; margin-bottom: 16px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        .footer {{ margin-top: 30px; font-size: 10px; color: #a0aec0; text-align: right; }}
    </style>
</head>
<body>
    <h2>{title}</h2>
    <div class="meta">Generated: {str(os.getenv('RUN_DATE', 'Demo Snacks Pvt Ltd'))}</div>
    {summary_html}
    <table>
        <thead><tr>{headers_th}</tr></thead>
        <tbody>{rows_tr}</tbody>
    </table>
    <div class="footer">Order-to-Audit System • Demo Snacks Pvt Ltd</div>
</body>
</html>
"""
    tmp_path = os.path.join(tempfile.gettempdir(), f"{filename}.pdf")
    render_pdf_from_html(html, tmp_path)

    with open(tmp_path, "rb") as f:
        pdf_bytes = f.read()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
    )
