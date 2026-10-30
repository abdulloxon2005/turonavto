from django import template

register = template.Library()

STATUS_BADGES = {
    'unpaid': 'bg-secondary',
    'partial': 'bg-warning text-dark',
    'paid': 'bg-success',
    'overdue': 'bg-danger',
    'confirmed': 'bg-success',
    'cancelled': 'bg-danger',
    'active': 'bg-success',
    'archived': 'bg-secondary',
    'open': 'bg-success',
    'closed': 'bg-secondary',
    'pending': 'bg-warning text-dark',
    'approved': 'bg-success',
    'rejected': 'bg-danger',
}

STATUS_LABELS = {
    'unpaid': "To'lanmagan",
    'partial': 'Qisman',
    'paid': "To'langan",
    'overdue': "Muddati o'tgan",
    'confirmed': 'Tasdiqlangan',
    'cancelled': 'Bekor qilingan',
    'active': 'Faol',
    'archived': 'Arxivlangan',
    'open': 'Ochiq',
    'closed': 'Yopiq',
    'pending': 'Kutilmoqda',
    'approved': 'Tasdiqlandi',
    'rejected': 'Rad etildi',
}


@register.filter
def money(value):
    """1234567 -> 1 234 567 so'm"""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return value
    text = f'{abs(value):,}'.replace(',', ' ')
    sign = '-' if value < 0 else ''
    return f"{sign}{text} so'm"


@register.filter
def status_badge(value):
    return STATUS_BADGES.get(value, 'bg-secondary')


@register.filter
def status_label(value):
    return STATUS_LABELS.get(value, value)
