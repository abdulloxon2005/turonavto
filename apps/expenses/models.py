from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Expense(TimeStampedModel):
    """Markaz xarajatlari: ish haqi, ijara va boshqa to'lovlar.

    Audit_log kabi faqat qo'shiladi — xato kiritilgan yozuv Django admin orqali
    tuzatiladi, oddiy interfeysda o'chirish/tahrirlash yo'q.
    """

    class Category(models.TextChoices):
        SALARY = 'salary', 'Ish haqi'
        RENT = 'rent', 'Ijara'
        UTILITIES = 'utilities', 'Kommunal to\'lovlar'
        SUPPLIES = 'supplies', 'Jihoz / materiallar'
        OTHER = 'other', 'Boshqa'

    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    amount = models.PositiveIntegerField()
    expense_date = models.DateField(default=timezone.localdate)
    description = models.CharField(max_length=255)

    paid_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='expenses_received',
        help_text="Agar xodimga to'langan bo'lsa tanlang",
    )
    paid_to_name = models.CharField(
        max_length=150, blank=True,
        help_text="Tizimda yo'q qabul qiluvchi uchun ism (masalan ijara egasi)",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='expenses_created',
    )

    class Meta:
        ordering = ['-expense_date', '-created_at']
        indexes = [
            models.Index(fields=['expense_date']),
            models.Index(fields=['category']),
            models.Index(fields=['paid_to_user']),
        ]

    def __str__(self):
        return f'{self.get_category_display()} — {self.amount} so\'m ({self.expense_date})'

    @property
    def recipient_display(self):
        if self.paid_to_user_id:
            return self.paid_to_user.full_name
        return self.paid_to_name or '—'
