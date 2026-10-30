from django.contrib import admin

from .models import Lesson


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('student', 'instructor', 'lesson_date', 'start_time', 'hours', 'attended')
    list_filter = ('attended',)
    search_fields = ('student__full_name', 'instructor__full_name')
