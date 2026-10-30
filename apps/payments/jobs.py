"""To'lov moduli fon vazifalari (11-bo'lim): har kuni ishga tushadi."""

import datetime
import logging

from django.utils import timezone

from apps.notifications.services import notify

from .models import PaymentSchedule

logger = logging.getLogger(__name__)


def mark_overdue_schedules():
    today = timezone.localdate()
    items = PaymentSchedule.objects.filter(
        due_date__lt=today,
        status__in=[PaymentSchedule.Status.UNPAID, PaymentSchedule.Status.PARTIAL],
    ).select_related('enrollment__student')

    count = 0
    for item in items:
        item.status = PaymentSchedule.Status.OVERDUE
        item.save(update_fields=['status'])
        count += 1

        student = item.enrollment.student
        owner = student.brought_by_user_id
        notify(
            owner,
            type='overdue',
            title="To'lov muddati o'tdi",
            body=f'{student.full_name} — {item.amount - item.paid_amount} so\'m, muddat: {item.due_date}',
            link=f'/oquvchilar/{student.pk}/',
        )
        from apps.accounts.models import User

        for admin in User.objects.filter(role=User.Role.ADMIN, is_active=True):
            notify(
                admin,
                type='overdue',
                title="To'lov muddati o'tdi",
                body=f'{student.full_name} — {item.amount - item.paid_amount} so\'m',
                link=f'/oquvchilar/{student.pk}/',
            )

    logger.info('Muddati o\'tgan grafik qismlari belgilandi: %s ta', count)
    return count


def remind_upcoming_due(days_before=3):
    from apps.site_settings.models import get_setting

    days_before = get_setting('reminder_days_before', days_before)
    target_date = timezone.localdate() + datetime.timedelta(days=days_before)
    items = PaymentSchedule.objects.filter(
        due_date=target_date,
        status__in=[PaymentSchedule.Status.UNPAID, PaymentSchedule.Status.PARTIAL],
    ).select_related('enrollment__student')

    count = 0
    for item in items:
        student = item.enrollment.student
        owner = student.brought_by_user_id
        notify(
            owner,
            type='due_soon',
            title="To'lov muddati yaqinlashmoqda",
            body=f'{student.full_name} — {item.amount - item.paid_amount} so\'m, muddat: {item.due_date}',
            link=f'/oquvchilar/{student.pk}/',
        )
        count += 1

    logger.info('Oldindan eslatma yuborildi: %s ta', count)
    return count
