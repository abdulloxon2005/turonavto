from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.groups.models import Group
from apps.students.models import Student


class Enrollment(TimeStampedModel):
    """O'quvchining ma'lum guruhdagi shartnomasi — qarz hisob-kitobining asosi."""

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='enrollments')
    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name='enrollments')
    price = models.PositiveIntegerField(help_text="Kurs narxi, so'mda")
    discount = models.PositiveIntegerField(default=0)
    discount_reason = models.CharField(max_length=255, blank=True)
    total_due = models.PositiveIntegerField(help_text='price - discount')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='enrollments_created'
    )

    class Meta:
        unique_together = [('student', 'group')]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student} — {self.group}'


class PaymentSchedule(models.Model):
    class Status(models.TextChoices):
        UNPAID = 'unpaid', "To'lanmagan"
        PARTIAL = 'partial', 'Qisman'
        PAID = 'paid', "To'langan"
        OVERDUE = 'overdue', "Muddati o'tgan"

    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='schedule_items')
    due_date = models.DateField()
    amount = models.PositiveIntegerField()
    paid_amount = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID)

    class Meta:
        ordering = ['due_date']
        indexes = [models.Index(fields=['due_date', 'status'])]

    def __str__(self):
        return f'{self.enrollment} — {self.due_date} — {self.amount}'

    @property
    def remaining(self):
        return self.amount - self.paid_amount


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = 'cash', 'Naqd'
        CARD = 'card', 'Karta'
        TRANSFER = 'transfer', "O'tkazma"
        CLICK = 'click', 'Click'
        PAYME = 'payme', 'Payme'

    class Status(models.TextChoices):
        CONFIRMED = 'confirmed', 'Tasdiqlangan'
        CANCELLED = 'cancelled', 'Bekor qilingan'

    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name='payments')
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='payments')
    amount = models.IntegerField(help_text="Musbat — to'lov, manfiy — qaytarish")
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CASH)
    received_by_user_id = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='payments_received'
    )
    paid_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    receipt_no = models.CharField(max_length=30, unique=True)
    note = models.CharField(max_length=255, blank=True)

    cancel_reason = models.CharField(max_length=255, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payments_cancelled',
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)

    is_refund = models.BooleanField(default=False)
    refund_of = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='refunds'
    )

    idempotency_key = models.CharField(max_length=64, null=True, blank=True, unique=True)
    external_id = models.CharField(max_length=100, blank=True, help_text='Click/Payme uchun (2-bosqich)')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_at']
        indexes = [
            models.Index(fields=['student', 'paid_at']),
            models.Index(fields=['received_by_user_id', 'paid_at']),
        ]

    def __str__(self):
        return f'{self.receipt_no} — {self.amount}'


class CashClosing(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        APPROVED = 'approved', 'Tasdiqlandi'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cash_closings')
    date = models.DateField()
    expected_amount = models.IntegerField(help_text="Tizim hisobi bo'yicha")
    declared_amount = models.IntegerField(help_text="Hodim e'lon qilgan summa")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cash_closings_approved',
    )
    approve_note = models.CharField(max_length=255, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'date')]
        ordering = ['-date']

    def __str__(self):
        return f'{self.user} — {self.date}'

    @property
    def difference(self):
        return self.declared_amount - self.expected_amount
