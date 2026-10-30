from django.core.exceptions import PermissionDenied
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from .models import AuditLog


@receiver(pre_save, sender=AuditLog)
def block_audit_update(sender, instance, **kwargs):
    if instance.pk and AuditLog.objects.filter(pk=instance.pk).exists():
        raise PermissionDenied('audit_log yozuvlari o\'zgartirilmaydi')


@receiver(pre_delete, sender=AuditLog)
def block_audit_delete(sender, instance, **kwargs):
    raise PermissionDenied('audit_log yozuvlari o\'chirilmaydi')
