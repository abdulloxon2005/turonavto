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


class TheoryLesson(TimeStampedModel):
    group = models.ForeignKey('groups.Group', on_delete=models.PROTECT, related_name='theory_lessons')
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='theory_lessons')
    topic = models.CharField(max_length=255, blank=True)
    lesson_date = models.DateField()
    start_time = models.TimeField()
    hours = models.DecimalField(max_digits=4, decimal_places=1, default=2)

    class Meta:
        ordering = ['-lesson_date', '-start_time']
        indexes = [
            models.Index(fields=['teacher', 'lesson_date']),
            models.Index(fields=['group']),
        ]

    def __str__(self):
        return f'{self.group} — {self.lesson_date} {self.start_time}'


class TheoryLessonAttendance(models.Model):
    theory_lesson = models.ForeignKey(TheoryLesson, on_delete=models.CASCADE, related_name='attendances')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='theory_attendances')
    attended = models.BooleanField(null=True, blank=True, default=None, help_text="Noma'lum / Ha / Yo'q")

    class Meta:
        unique_together = [('theory_lesson', 'student')]

    def __str__(self):
        return f'{self.student} — {self.theory_lesson}'
