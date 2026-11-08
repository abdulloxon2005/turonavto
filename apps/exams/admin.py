from django.contrib import admin

from .models import ExamAttempt


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam_type', 'exam_date', 'passed', 'recorded_by')
    list_filter = ('exam_type', 'passed')
    search_fields = ('student__full_name',)
