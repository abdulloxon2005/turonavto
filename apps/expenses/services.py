import datetime

from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone

from apps.core.services import log_action

from .models import Expense


def expenses_queryset(*, category=None, paid_to_user=None, date_from=None, date_to=None):
    qs = Expense.objects.select_related('paid_to_user', 'created_by')
    if category:
        qs = qs.filter(category=category)
    if paid_to_user:
        qs = qs.filter(paid_to_user_id=paid_to_user)
    if date_from:
        qs = qs.filter(expense_date__gte=date_from)
    if date_to:
        qs = qs.filter(expense_date__lte=date_to)
    return qs


def total_amount(qs):
    return qs.aggregate(s=Sum('amount'))['s'] or 0


def create_expense(actor, *, category, amount, expense_date, description, paid_to_user=None, paid_to_name=''):
    if amount <= 0:
        raise ValidationError("Summa noldan katta bo'lishi kerak")
    if not description:
        raise ValidationError("Izoh kiritilishi shart")

    expense = Expense.objects.create(
        category=category, amount=amount, expense_date=expense_date, description=description,
        paid_to_user=paid_to_user, paid_to_name=paid_to_name if not paid_to_user else '',
        created_by=actor,
    )
    log_action(
        actor, action='expense.create', entity_type='Expense', entity_id=expense.pk,
        new_value={
            'category': category, 'amount': amount, 'expense_date': expense_date.isoformat(),
            'paid_to_user_id': paid_to_user.pk if paid_to_user else None,
            'paid_to_name': expense.paid_to_name,
        },
    )
    return expense


def monthly_totals(months=6):
    """Oxirgi N oy bo'yicha xarajatlar jami: [(label, total), ...] eng eskisidan boshlab."""

    today = timezone.localdate()
    results = []
    year, month = today.year, today.month
    for _ in range(months):
        start = datetime.date(year, month, 1)
        if month == 12:
            end = datetime.date(year + 1, 1, 1)
        else:
            end = datetime.date(year, month + 1, 1)
        total = Expense.objects.filter(
            expense_date__gte=start, expense_date__lt=end
        ).aggregate(s=Sum('amount'))['s'] or 0
        results.append((start, total))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(results))


def by_category_totals(date_from=None, date_to=None):
    qs = Expense.objects.all()
    if date_from:
        qs = qs.filter(expense_date__gte=date_from)
    if date_to:
        qs = qs.filter(expense_date__lte=date_to)
    rows = []
    for value, label in Expense.Category.choices:
        amount = qs.filter(category=value).aggregate(s=Sum('amount'))['s'] or 0
        if amount:
            rows.append((label, amount))
    return rows
