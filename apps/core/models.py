from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class TimeStampedModel(models.Model):
    """Barcha jadvallar uchun umumiy created_at/updated_at maydonlari."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Pul bilan bog'liq va boshqaruv amallarining o'zgartirilmas jurnali.

    Faqat qo'shiladi: ilova darajasida update/delete taqiqlanadi (pre_save/pre_delete
    signal orqali apps/core/signals.py da bloklanadi).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=50, null=True, blank=True)
    old_value = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    new_value = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.entity_type}:{self.entity_id}'
