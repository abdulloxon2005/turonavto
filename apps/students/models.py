from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

from apps.accounts.models import phone_validator
from apps.core.models import TimeStampedModel
from apps.core.validators import validate_image_size


def student_photo_path(instance, filename):
    return f'students/{instance.pk or "new"}/{filename}'


class Student(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Faol'
        ARCHIVED = 'archived', 'Arxivlangan'

    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, validators=[phone_validator])
    phone2 = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    passport_no = models.CharField(max_length=20, unique=True, null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    photo = models.ImageField(
        upload_to=student_photo_path,
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png']), validate_image_size],
    )
    brought_by_user_id = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='brought_students',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    note = models.TextField(blank=True)

    instructors = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='InstructorStudent',
        through_fields=('student', 'instructor'),
        related_name='assigned_students',
    )

    class Meta:
        ordering = ['full_name']
        indexes = [
            models.Index(fields=['brought_by_user_id']),
            models.Index(fields=['phone']),
        ]

    def __str__(self):
        return self.full_name


class InstructorStudent(models.Model):
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='instructor_student_links'
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='instructor_links')
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='instructor_assignments_made',
    )

    class Meta:
        unique_together = [('instructor', 'student')]

    def __str__(self):
        return f'{self.student} -> {self.instructor}'


class DeleteRequest(models.Model):
    class EntityType(models.TextChoices):
        STUDENT = 'student', "O'quvchi"

    class Status(models.TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        APPROVED = 'approved', 'Tasdiqlandi'
        REJECTED = 'rejected', 'Rad etildi'

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delete_requests_made'
    )
    entity_type = models.CharField(max_length=30, choices=EntityType.choices, default=EntityType.STUDENT)
    entity_id = models.PositiveIntegerField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delete_requests_decided',
    )
    decision_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_entity_type_display()} #{self.entity_id} ({self.get_status_display()})'

    @property
    def student(self):
        if self.entity_type == self.EntityType.STUDENT:
            return Student.objects.filter(pk=self.entity_id).first()
        return None
