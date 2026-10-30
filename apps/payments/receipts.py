import io

from django.conf import settings
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps.site_settings.models import get_setting

from .services import debt_of


def _money(value):
    sign = '-' if value < 0 else ''
    return f"{sign}{abs(value):,}".replace(',', ' ') + " so'm"


def render_receipt_pdf(payment):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A5)
    width, height = A5

    center_name = get_setting('center_name', settings.CENTER_NAME)
    y = height - 20 * mm

    c.setFont('Helvetica-Bold', 14)
    c.drawCentredString(width / 2, y, center_name)
    y -= 10 * mm

    c.setFont('Helvetica-Bold', 12)
    title = "QAYTARISH CHEKI" if payment.is_refund else "TO'LOV CHEKI"
    c.drawCentredString(width / 2, y, title)
    y -= 12 * mm

    c.setFont('Helvetica', 10)
    rows = [
        ('Chek raqami', payment.receipt_no),
        ('Sana', payment.paid_at.strftime('%d.%m.%Y %H:%M')),
        ("O'quvchi", payment.student.full_name),
        ('Guruh', payment.enrollment.group.name),
        ('Summa', _money(payment.amount)),
        ('Usul', payment.get_method_display()),
        ('Qabul qildi', payment.received_by_user_id.full_name),
    ]
    if not payment.is_refund:
        rows.append(('Qolgan qarz', _money(debt_of(payment.enrollment))))
    if payment.note:
        rows.append(('Izoh', payment.note))

    for label, value in rows:
        c.drawString(15 * mm, y, f'{label}:')
        c.drawRightString(width - 15 * mm, y, str(value))
        y -= 7 * mm

    y -= 5 * mm
    c.setFont('Helvetica-Oblique', 8)
    c.drawCentredString(width / 2, y, "Elektron chek — imzo talab qilinmaydi")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()
