import datetime

from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.groups.models import Group
from apps.payments.models import CashClosing, Enrollment, Payment, PaymentSchedule
from apps.payments.services import debt_of, enrollment_summary, paid_sum


def revenue_report(date_from, date_to, method=None, received_by=None):
    qs = Payment.objects.filter(
        status=Payment.Status.CONFIRMED, paid_at__date__gte=date_from, paid_at__date__lte=date_to,
    )
    if method:
        qs = qs.filter(method=method)
    if received_by:
        qs = qs.filter(received_by_user_id=received_by)

    total = qs.aggregate(s=Sum('amount'))['s'] or 0

    by_method = {}
    for choice_value, choice_label in Payment.Method.choices:
        amount = qs.filter(method=choice_value).aggregate(s=Sum('amount'))['s'] or 0
        if amount:
            by_method[choice_label] = amount

    by_day = {}
    for p in qs.order_by('paid_at'):
        day = p.paid_at.date()
        by_day[day] = by_day.get(day, 0) + p.amount

    return {
        'total': total,
        'by_method': by_method,
        'by_day': sorted(by_day.items()),
        'payments': qs.select_related('student', 'received_by_user_id').order_by('-paid_at'),
    }


def groups_report(group_id=None, status=None):
    qs = Group.objects.all()
    if group_id:
        qs = qs.filter(pk=group_id)
    if status:
        qs = qs.filter(status=status)

    rows = []
    for group in qs:
        enrollments = group.enrollments.all()
        total_due = sum(e.total_due for e in enrollments)
        total_paid = sum(paid_sum(e) for e in enrollments)
        total_debt = max(total_due - total_paid, 0)
        percent = round(total_paid / total_due * 100, 1) if total_due else 0
        rows.append({
            'group': group, 'price': group.price, 'total_due': total_due,
            'total_paid': total_paid, 'total_debt': total_debt, 'percent': percent,
        })
    return rows


def staff_report(role=None, date_from=None, date_to=None):
    qs = User.objects.exclude(role=User.Role.ADMIN)
    if role:
        qs = qs.filter(role=role)

    rows = []
    for user in qs:
        students_count = user.brought_students.count()
        payments = Payment.objects.filter(received_by_user_id=user, status=Payment.Status.CONFIRMED)
        if date_from:
            payments = payments.filter(paid_at__date__gte=date_from)
        if date_to:
            payments = payments.filter(paid_at__date__lte=date_to)
        collected = payments.aggregate(s=Sum('amount'))['s'] or 0

        debt = 0
        for enrollment in Enrollment.objects.filter(student__brought_by_user_id=user):
            debt += debt_of(enrollment)

        rows.append({
            'user': user, 'students_count': students_count, 'collected': collected, 'debt': debt,
        })
    return rows


def debtors_report(group_id=None, owner_id=None, min_overdue_days=None):
    qs = Enrollment.objects.select_related('student', 'group', 'student__brought_by_user_id')
    if group_id:
        qs = qs.filter(group_id=group_id)
    if owner_id:
        qs = qs.filter(student__brought_by_user_id=owner_id)

    today = timezone.localdate()
    rows = []
    for enrollment in qs:
        summary = enrollment_summary(enrollment)
        if summary['debt'] <= 0:
            continue
        oldest_overdue = enrollment.schedule_items.filter(
            status=PaymentSchedule.Status.OVERDUE
        ).order_by('due_date').first()
        overdue_days = (today - oldest_overdue.due_date).days if oldest_overdue else 0
        if min_overdue_days and overdue_days < min_overdue_days:
            continue
        rows.append({
            'enrollment': enrollment, 'debt': summary['debt'],
            'oldest_due_date': oldest_overdue.due_date if oldest_overdue else None,
            'overdue_days': overdue_days,
        })
    return rows


def upcoming_revenue_report(days=30):
    today = timezone.localdate()
    until = today + datetime.timedelta(days=days)
    items = PaymentSchedule.objects.filter(
        due_date__gte=today, due_date__lte=until,
        status__in=[PaymentSchedule.Status.UNPAID, PaymentSchedule.Status.PARTIAL],
    ).select_related('enrollment__student', 'enrollment__group')

    total = sum(i.remaining for i in items)
    return {'items': items.order_by('due_date'), 'total': total}


def dashboard_overview():
    """Hisobotlar bosh sahifasi uchun umumiy ko'rsatkichlar (faol/yopilgan/yopilmagan/jami qarz)."""
    from apps.students.models import Student
    from apps.students.services import student_enriched_info

    open_count = 0
    closed_count = 0
    total_outstanding = 0
    for student in Student.objects.filter(status=Student.Status.ACTIVE):
        info = student_enriched_info(student)
        if info['total_due'] <= 0:
            continue
        if info['debt'] > 0:
            open_count += 1
            total_outstanding += info['debt']
        else:
            closed_count += 1

    return {
        'active_count': open_count + closed_count,
        'open_count': open_count,
        'closed_count': closed_count,
        'total_outstanding': total_outstanding,
    }


def staff_comparison_chart_data(limit=8):
    """Har bir hodim (egasi) bo'yicha faol o'quvchilar soni va qolgan qarzi (eng qarzdor hodimlar birinchi)."""
    rows = [r for r in staff_report() if r['students_count'] or r['debt']]
    rows.sort(key=lambda r: r['debt'], reverse=True)
    rows = rows[:limit]
    return {
        'labels': [r['user'].full_name for r in rows],
        'active_counts': [r['students_count'] for r in rows],
        'debts': [r['debt'] for r in rows],
    }


def risk_distribution_chart_data():
    """Qarzdorlarni kechikish kunlari bo'yicha risk toifalariga ajratadi."""
    buckets = [
        ('0-30 kun', 0),
        ('30+ kun', 0),
        ('60+ kun', 0),
        ("90+ kun (sud)", 0),
    ]
    counts = dict(buckets)
    for row in debtors_report():
        days = row['overdue_days']
        if days >= 90:
            counts["90+ kun (sud)"] += 1
        elif days >= 60:
            counts['60+ kun'] += 1
        elif days >= 30:
            counts['30+ kun'] += 1
        else:
            counts['0-30 kun'] += 1
    return counts


def cash_report(date_from, date_to):
    qs = CashClosing.objects.filter(date__gte=date_from, date__lte=date_to).select_related('user')
    total_expected = qs.aggregate(s=Sum('expected_amount'))['s'] or 0
    total_declared = qs.aggregate(s=Sum('declared_amount'))['s'] or 0
    return {
        'closings': qs.order_by('-date'),
        'total_expected': total_expected,
        'total_declared': total_declared,
    }
