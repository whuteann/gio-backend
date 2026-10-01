"""Billing invoice PDFs — one per SubscriptionPayment, generated on
request (not stored — cheap enough to rebuild every view, and avoids ever
serving a stale document if a payment's status changes after generation).

Works identically for a real Xendit-collected payment and a
PAYMENT_GATEWAY_ENABLED=false bypass payment (app/services/subscription_payment.py)
— both are just SubscriptionPayment rows; this only reads the row, it
never talks to Xendit.
"""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

from app.models.payment import SubscriptionPayment
from app.models.user import User

# Gio's own palette (gio-member-app/styles/globals.css) — kept in sync by
# hand since this is the only place backend code renders visual brand
# colour; not worth a shared-constants file for three hex values.
_PRIMARY = colors.HexColor("#33452f")
_GOLD = colors.HexColor("#b9902a")
_MUTED = colors.HexColor("#666f5c")
_BORDER = colors.HexColor("#e6ddc9")

# The product is branded "Auren" to users (app/services/ai_questions.py's
# system messages use the same name) even though the company/account
# behind it is still Gio — these are fixed business details, not
# per-payment data, so they live here rather than in config/the DB.
_BRAND_NAME = "Auren"
_COMPANY_PHONE = "+60 19 986 9932"
_COMPANY_PHONE_TEL = "+60199869932"
_COMPANY_EMAIL = "giovanna.khoo@giobyquartzic.com"
_COMPANY_ADDRESS = "C-2-11, Plaza Damas, No 60, Jalan Damas 1, Sri Hartamas, 50480 Kuala Lumpur, Malaysia"

_BILLING_CYCLE_LABEL = {"MONTHLY": "Monthly", "YEARLY": "Yearly"}


def _status_label(payment: SubscriptionPayment) -> str:
    return {
        "COMPLETED": "Paid",
        "PENDING": "Pending",
        "FAILED": "Failed",
        "EXPIRED": "Expired",
    }.get(payment.status, payment.status.title())


def generate_invoice_pdf(payment: SubscriptionPayment, user: User) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=20 * mm, bottomMargin=22 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
    )
    content_width = doc.width

    styles = getSampleStyleSheet()
    brand_style = ParagraphStyle("Brand", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=22, textColor=_PRIMARY, leading=26)
    contact_style = ParagraphStyle("Contact", parent=styles["Normal"], fontSize=9, textColor=_MUTED, alignment=TA_RIGHT, leading=14)
    invoice_meta_style = ParagraphStyle("InvoiceMeta", parent=styles["Normal"], fontSize=10, textColor=_MUTED, alignment=TA_RIGHT, leading=14)
    invoice_title_style = ParagraphStyle("InvoiceTitle", parent=invoice_meta_style, fontName="Helvetica-Bold", fontSize=13, textColor=_PRIMARY, leading=16)
    label_style = ParagraphStyle("Label", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, textColor=_MUTED, leading=13)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10.5, textColor=_PRIMARY, leading=15)
    status_style = ParagraphStyle("Status", parent=invoice_meta_style, fontName="Helvetica-Bold", fontSize=11)
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, textColor=_MUTED, leading=12)

    invoice_date = (payment.paid_at or payment.created_at).strftime("%d %b %Y")
    cycle_label = _BILLING_CYCLE_LABEL.get(payment.billing_cycle, payment.billing_cycle.title())
    # A short, printable invoice number for the customer-facing document —
    # reference_no is the long internal/Xendit-facing id (behaviour_log_0009.md),
    # not meant for this. Derived, not stored: stable for a given payment
    # since it's just the first 8 hex chars of the payment's own uuid.
    invoice_number = f"INV-{str(payment.id)[:8].upper()}"

    # --- Letterhead: brand name + company contact block, inside a
    # double-ruled box (mirrors the referenced hotel-brand letterhead
    # style) so the document reads as official stationery rather than a
    # bare data dump. ---
    letterhead_row = Table(
        [[
            Paragraph(_BRAND_NAME, brand_style),
            Paragraph(
                f"<a href='tel:{_COMPANY_PHONE_TEL}' color='#666f5c'>{_COMPANY_PHONE}</a><br/>"
                f"<a href='mailto:{_COMPANY_EMAIL}' color='#b9902a'><u>{_COMPANY_EMAIL}</u></a><br/>"
                f"{_COMPANY_ADDRESS}",
                contact_style,
            ),
        ]],
        colWidths=[None, 85 * mm],
    )
    letterhead_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("LEFTPADDING", (0, 0), (0, -1), 16),
        ("RIGHTPADDING", (1, 0), (1, -1), 16),
    ]))

    inner_frame = Table([[letterhead_row]], colWidths=[content_width - 8])
    inner_frame.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, _PRIMARY),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    letterhead = Table([[inner_frame]], colWidths=[content_width])
    letterhead.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, _PRIMARY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    # --- Bill-to / invoice meta / status row, below the letterhead. ---
    meta_row = Table(
        [[
            Paragraph(f"BILL TO<br/><br/>{user.display_name}<br/>{user.email}", label_style),
            Paragraph(f"INVOICE<br/>No. {invoice_number}<br/>{invoice_date}", invoice_meta_style),
            Paragraph(
                f"STATUS<br/><br/><font color='{'#33452f' if payment.status == 'COMPLETED' else '#b9902a'}'>{_status_label(payment)}</font>",
                status_style,
            ),
        ]],
        colWidths=[content_width - 55 * mm - 35 * mm, 55 * mm, 35 * mm],
        hAlign="LEFT",
    )
    meta_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
    ]))

    # All content tables below share one left/right edge — the same
    # content_width the letterhead box uses — instead of auto-sizing to
    # their own content, which previously made each row a different width
    # and tapered the page into a "funnel".
    line_items = Table(
        [
            ["DESCRIPTION", "BILLING CYCLE", "AMOUNT"],
            [f"{_BRAND_NAME} Premium subscription", cycle_label, f"{payment.currency} {payment.amount:.2f}"],
        ],
        colWidths=[content_width - 80 * mm, 40 * mm, 40 * mm],
        hAlign="LEFT",
    )
    line_items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, 1), 10.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 1), (-1, 1), 0.5, _BORDER),
    ]))

    total_table = Table(
        [["TOTAL", f"{payment.currency} {payment.amount:.2f}"]],
        colWidths=[content_width - 40 * mm, 40 * mm],
        hAlign="LEFT",
    )
    total_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("TEXTCOLOR", (0, 0), (-1, -1), _PRIMARY),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
    ]))

    story = [
        letterhead,
        Spacer(1, 14 * mm),
        meta_row,
        Spacer(1, 12 * mm),
        line_items,
        total_table,
        Spacer(1, 20 * mm),
        Paragraph(
            f"Thank you for being part of {_BRAND_NAME}. This invoice was generated automatically and is valid without a signature.",
            footer_style,
        ),
    ]

    doc.build(story)
    return buffer.getvalue()
