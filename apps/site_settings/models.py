from django.db import models


class Setting(models.Model):
    """Tizim sozlamalari (key -> value), 6-bo'lim sxemasiga mos."""

    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()

    def __str__(self):
        return self.key


DEFAULTS = {
    'center_name': 'Avtomaktab',
    'payment_methods': ['cash', 'card', 'transfer'],
    'reminder_days_before': 3,
}


def get_setting(key, default=None):
    try:
        return Setting.objects.get(key=key).value
    except Setting.DoesNotExist:
        return DEFAULTS.get(key, default)


def set_setting(key, value):
    obj, _ = Setting.objects.update_or_create(key=key, defaults={'value': value})
    return obj
