"""
Generate SANTACRUZ BROTHERS LLC estimate PDFs using reportlab.
Matches the exact format used in cowork sessions.
"""
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# Brand colors
ORANGE     = colors.HexColor('#E8651A')
DARK_GRAY  = colors.HexColor('#404040')
MID_GRAY   = colors.HexColor('#888888')
LIGHT_GRAY = colors.HexColor('#F7F7F7')
LINE_GRAY  = colors.HexColor('#DDDDDD')
WHITE      = colors.white
BLACK      = colors.HexColor('#1A1A1A')


def ps(name, **kw):
    return ParagraphStyle(name, **kw)


def build_estimate_pdf(
    estimate_no: str,
    estimate_date: str,
    valid_through: str,
    client_name: str,
    client_address: str,
    line_items: list[dict],   # [{name, description, qty, rate, amount}]
    total: float,
) -> bytes:
    """
    Generate a PDF estimate and return it as bytes.

    line_items example:
        [
            {
                "name": "Labor – Baseboard Install",
                "description": "308 lin ft custom profile baseboard, installed",
                "qty": "308",
                "rate": "$3.50",
                "amount": "$1,078.00"
            },
            ...
        ]
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=0.65 * inch, rightMargin=0.65 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch
    )

    story = []

    # ── Styles ──
    s_est_title  = ps('EstTitle',  fontName='Helvetica-Bold', fontSize=22, textColor=ORANGE, leading=26)
    s_company    = ps('Company',   fontName='Helvetica-Bold', fontSize=9,  textColor=DARK_GRAY, leading=13)
    s_contact    = ps('Contact',   fontName='Helvetica',      fontSize=8.5,textColor=DARK_GRAY, leading=13)
    s_bill_label = ps('BillLabel', fontName='Helvetica-Bold', fontSize=8,  textColor=MID_GRAY,  leading=12)
    s_bill_name  = ps('BillName',  fontName='Helvetica-Bold', fontSize=10, textColor=BLACK,     leading=14)
    s_bill_addr  = ps('BillAddr',  fontName='Helvetica',      fontSize=9,  textColor=DARK_GRAY, leading=13)
    s_det_val    = ps('DetVal',    fontName='Helvetica',      fontSize=9,  textColor=BLACK,     leading=13)
    s_tbl_hdr    = ps('TblHdr',    fontName='Helvetica-Bold', fontSize=8.5,textColor=DARK_GRAY, leading=12)
    s_tbl_hdr_r  = ps('TblHdrR',  fontName='Helvetica-Bold', fontSize=8.5,textColor=DARK_GRAY, leading=12, alignment=TA_RIGHT)
    s_item_bold  = ps('ItemBold',  fontName='Helvetica-Bold', fontSize=9,  textColor=BLACK,     leading=13)
    s_item_desc  = ps('ItemDesc',  fontName='Helvetica',      fontSize=8.5,textColor=DARK_GRAY, leading=12)
    s_amount     = ps('Amount',    fontName='Helvetica',      fontSize=9,  textColor=BLACK,     leading=13, alignment=TA_RIGHT)
    s_total_lbl  = ps('TotalLbl',  fontName='Helvetica-Bold', fontSize=10, textColor=BLACK,     leading=14, alignment=TA_RIGHT)
    s_total_val  = ps('TotalVal',  fontName='Helvetica-Bold', fontSize=11, textColor=BLACK,     leading=16, alignment=TA_RIGHT)
    s_footer     = ps('Footer',    fontName='Helvetica',      fontSize=8.5,textColor=MID_GRAY,  leading=12)
    s_valid      = ps('Valid',     fontName='Helvetica',      fontSize=8.5,textColor=MID_GRAY,  leading=12)

    # ── HEADER ──
    header_data = [[
        [Paragraph('ESTIMATE', s_est_title),
         Paragraph('SANTACRUZ BROTHERS LLC', s_company),
         Paragraph('PHOENIX, AZ', s_contact),
         Paragraph('ray@santacruzllc.com', s_contact),
         Paragraph('+1 (602) 503-8183', s_contact)],
        Paragraph('', s_contact)
    ]]
    header_table = Table(header_data, colWidths=[4.2 * inch, 2.9 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN',         (0, 0), (-1, -1), 'TOP'),
        ('ALIGN',          (1, 0), (1, 0),   'RIGHT'),
        ('LEFTPADDING',    (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 0),
        ('TOPPADDING',     (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width='100%', thickness=0.5, color=LINE_GRAY, spaceAfter=14))

    # ── BILL TO + ESTIMATE DETAILS ──
    bill_content = [
        Paragraph('Bill to', s_bill_label),
        Spacer(1, 3),
        Paragraph(client_name, s_bill_name),
    ]
    for line in client_address.split('\n'):
        if line.strip():
            bill_content.append(Paragraph(line.strip(), s_bill_addr))

    details_content = [
        Paragraph('Estimate details', s_bill_label),
        Spacer(1, 3),
        Paragraph(f'Estimate no.: <b>{estimate_no}</b>', s_det_val),
        Paragraph(f'Estimate date: <b>{estimate_date}</b>', s_det_val),
        Paragraph(f'Valid through: <b>{valid_through}</b>', s_det_val),
    ]

    bill_table = Table(
        [[bill_content, details_content]],
        colWidths=[4.0 * inch, 3.1 * inch]
    )
    bill_table.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(bill_table)
    story.append(Spacer(1, 18))

    # ── LINE ITEMS TABLE ──
    col_widths = [0.32 * inch, 1.38 * inch, 3.22 * inch, 0.62 * inch, 0.82 * inch, 0.85 * inch]

    rows = [
        [Paragraph('#', s_tbl_hdr),
         Paragraph('Product or service', s_tbl_hdr),
         Paragraph('Description', s_tbl_hdr),
         Paragraph('Qty', s_tbl_hdr_r),
         Paragraph('Rate', s_tbl_hdr_r),
         Paragraph('Amount', s_tbl_hdr_r)],
    ]

    for i, item in enumerate(line_items, start=1):
        rows.append([
            Paragraph(f'{i}.', s_item_desc),
            Paragraph(item.get('name', ''), s_item_bold),
            Paragraph(item.get('description', ''), s_item_desc),
            Paragraph(str(item.get('qty', '')), s_amount),
            Paragraph(str(item.get('rate', '')), s_amount),
            Paragraph(str(item.get('amount', '')), s_amount),
        ])

    line_table = Table(rows, colWidths=col_widths, repeatRows=1)
    line_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), LIGHT_GRAY),
        ('LINEBELOW',     (0, 0), (-1, 0), 0.5, LINE_GRAY),
        ('TOPPADDING',    (0, 0), (-1, 0), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('TOPPADDING',    (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 9),
        ('LINEBELOW',     (0, 1), (-1, -2), 0.5, LINE_GRAY),
        ('LINEBELOW',     (0, -1), (-1, -1), 0.5, LINE_GRAY),
        ('BOX',           (0, 0), (-1, -1), 0.5, LINE_GRAY),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 16))

    # ── TOTAL ──
    total_str = f'${total:,.2f}'
    total_data = [[Paragraph('Total', s_total_lbl), Paragraph(total_str, s_total_val)]]
    total_table = Table(total_data, colWidths=[5.8 * inch, 1.3 * inch])
    total_table.setStyle(TableStyle([
        ('ALIGN',         (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('LINEABOVE',     (0, 0), (-1, 0), 0.5, LINE_GRAY),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 30))

    # ── FOOTER ──
    story.append(HRFlowable(width='100%', thickness=0.5, color=LINE_GRAY, spaceAfter=10))
    footer_data = [[
        [Paragraph('Accepted date', s_footer), Spacer(1, 4), Paragraph('___________________________', s_footer)],
        [Paragraph('Accepted by', s_footer),   Spacer(1, 4), Paragraph('___________________________', s_footer)],
    ]]
    footer_table = Table(footer_data, colWidths=[3.55 * inch, 3.55 * inch])
    footer_table.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(footer_table)

    doc.build(story)
    return buffer.getvalue()
