from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

from .managers import UserManager

phone_validator = RegexValidator(
    regex=r'^\+?\d{9,15}$',
    message="Telefon raqami faqat raqamlardan iborat bo'lishi kerak, masalan +998901234567",
)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        TEACHER = 'teacher', "O'qituvchi"
        INSTRUCTOR = 'instructor', 'Instruktor'

    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, unique=True, validators=[phone_validator])
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=True)

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['full_name', 'role']

    objects = UserManager()

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        return f'{self.full_name} ({self.get_role_display()})'

    @property
    def last_login_at(self):
        return self.last_login

    def is_admin(self):
        return self.role == self.Role.ADMIN

    def is_teacher(self):
        return self.role == self.Role.TEACHER

    def is_instructor(self):
        return self.role == self.Role.INSTRUCTOR


class LoginAttempt(models.Model):
    """Login uchun rate-limit: 5 ta noto'g'ri urinishdan keyin 15 daqiqa bloklash."""

    phone = models.CharField(max_length=20, unique=True)
    failed_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_locked(self):
        return bool(self.locked_until and self.locked_until > timezone.now())

    def seconds_remaining(self):
        if not self.is_locked():
            return 0
        return int((self.locked_until - timezone.now()).total_seconds())
