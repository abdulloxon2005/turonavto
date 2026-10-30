from datetime import timedelta

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.utils import timezone

from .models import LoginAttempt, User


class PhoneBackend(ModelBackend):
    """Telefon + parol orqali autentifikatsiya, 5 xato urinishdan keyin 15 daqiqa blok."""

    def authenticate(self, request, phone=None, password=None, username=None, **kwargs):
        # Django admin va boshqa standart joylar `username=` nomi bilan yuboradi
        # (USERNAME_FIELD='phone' bo'lsa ham); shu sababli ikkalasini ham qabul qilamiz.
        phone = phone or username
        if phone is None or password is None:
            return None

        attempt, _ = LoginAttempt.objects.get_or_create(phone=phone)
        if attempt.is_locked():
            return None

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            User().set_password(password)  # timing-attack oldini olish
            self._register_failure(attempt)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            if attempt.failed_count or attempt.locked_until:
                attempt.failed_count = 0
                attempt.locked_until = None
                attempt.save(update_fields=['failed_count', 'locked_until', 'updated_at'])
            return user

        self._register_failure(attempt)
        return None

    def _register_failure(self, attempt):
        attempt.failed_count += 1
        if attempt.failed_count >= settings.LOGIN_MAX_ATTEMPTS:
            attempt.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        attempt.save(update_fields=['failed_count', 'locked_until', 'updated_at'])
