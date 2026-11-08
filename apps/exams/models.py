from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.students.models import Student


class ExamAttempt(TimeStampedModel):
    class ExamType(models.TextChoices):
        THEORY = 'theory', 'Nazariy'
        PRACTICE = 'practice', 'Amaliy'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exam_attempts')
    exam_type = models.CharField(max_length=20, choices=ExamType.choices)
    exam_date = models.DateField()
    passed = models.BooleanField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='exam_attempts_recorded'
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['student', 'exam_type', 'exam_date']
        indexes = [models.Index(fields=['student', 'exam_type'])]

    def __str__(self):
        return f'{self.student} — {self.get_exam_type_display()} ({self.exam_date})'
