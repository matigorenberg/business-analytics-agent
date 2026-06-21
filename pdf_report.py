import datetime
from pathlib import Path
from fpdf import FPDF

_UNICODE_MAP = str.maketrans({
    "‘": "'", "’": "'",   # curly single quotes
    "“": '"', "”": '"',   # curly double quotes
    "–": "-", "—": "--",  # en dash, em dash
    "…": "...",                # ellipsis
    " ": " ",                  # non-breaking space
})

def _ascii(text: str) -> str:
    return text.translate(_UNICODE_MAP)


def generate_pdf(report: dict, charts: list = None) -> bytes:
    pdf = FPDF()
    pdf.set_margins(22, 22, 22)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(15, 17, 23)
    pdf.cell(0, 12, "Business Analytics Report", ln=True)

    # Date
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(139, 148, 158)
    pdf.cell(0, 7, datetime.date.today().strftime("%B %d, %Y"), ln=True)
    pdf.ln(3)

    pdf.set_draw_color(200, 200, 200)
    pdf.line(22, pdf.get_y(), 188, pdf.get_y())
    pdf.ln(7)

    # Executive Summary
    _section_title(pdf, "Executive Summary")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 6, _ascii(report["summary"]))
    pdf.ln(7)

    # Key Findings
    _section_title(pdf, "Key Findings")
    for i, finding in enumerate(report["findings"], 1):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(56, 139, 253)
        pdf.cell(7, 6, f"{i}.")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(0, 6, _ascii(finding))
        pdf.ln(2)
    pdf.ln(4)

    # Recommendations
    _section_title(pdf, "Recommendations")
    for i, rec in enumerate(report["recommendations"], 1):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(63, 185, 80)
        pdf.cell(7, 6, f"{i}.")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(0, 6, _ascii(rec))
        pdf.ln(2)

    # Charts
    if charts:
        pdf.add_page()
        _section_title(pdf, "Analysis Charts")
        pdf.ln(3)
        for chart_path in sorted(charts):
            if Path(chart_path).exists():
                pdf.image(chart_path, w=165)
                pdf.ln(8)

    return bytes(pdf.output())


def _section_title(pdf: FPDF, title: str):
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(139, 148, 158)
    pdf.cell(0, 7, title.upper(), ln=True)
    pdf.set_text_color(30, 30, 30)
