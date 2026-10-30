from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Group(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = 'open', 'Ochiq'
        CLOSED = 'closed', 'Yopiq'
        ARCHIVED = 'archived', 'Arxivlangan'

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, help_text="Masalan: B, C, BC")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    price = models.PositiveIntegerField(help_text="Kurs narxi, so'mda (UZS)")
    max_students = models.PositiveIntegerField(default=25)
    schedule = models.CharField(max_length=255, blank=True, help_text="Masalan: Dush/Chor/Juma 18:00")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    teachers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='GroupTeacher', related_name='teaching_groups'
    )
    instructors = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='GroupInstructor', related_name='instructing_groups'
    )
    students = models.ManyToManyField(
        'students.Student', through='GroupStudent', related_name='groups'
    )

    class Meta:
        ordering = ['-start_date', 'name']

    def __str__(self):
        return f'{self.name} ({self.category})'

    @property
    def active_student_count(self):
        return self.group_students.filter(left_at__isnull=True).count()

    @property
    def is_full(self):
        return self.active_student_count >= self.max_students


class GroupTeacher(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='group_teachers')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_teacher_links')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('group', 'user')]


class GroupInstructor(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='group_instructors')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_instructor_links')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('group', 'user')]


class GroupStudent(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='group_students')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='group_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['group'])]

    def __str__(self):
        return f'{self.student} -> {self.group}'
