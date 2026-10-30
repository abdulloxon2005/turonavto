from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.students.models import Student


class Lesson(TimeStampedModel):
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='lessons')
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='lessons')
    lesson_date = models.DateField()
    start_time = models.TimeField()
    hours = models.DecimalField(max_digits=4, decimal_places=1, default=1)
    attended = models.BooleanField(null=True, blank=True, default=None, help_text="Noma'lum / Ha / Yo'q")

    class Meta:
        ordering = ['-lesson_date', '-start_time']
        indexes = [
            models.Index(fields=['instructor', 'lesson_date']),
            models.Index(fields=['student']),
        ]

    def __str__(self):
        return f'{self.student} — {self.lesson_date} {self.start_time}'
