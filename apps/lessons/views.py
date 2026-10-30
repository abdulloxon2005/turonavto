from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.core.mixins import AdminOrInstructorRequiredMixin
from apps.students.services import visible_students_queryset

from .forms import LessonForm
from .models import Lesson
from .services import create_lesson, mark_attendance, visible_lessons_queryset


class LessonListView(AdminOrInstructorRequiredMixin, ListView):
    model = Lesson
    template_name = 'lessons/lesson_list.html'
    context_object_name = 'lessons'
    paginate_by = 30

    def get_queryset(self):
        qs = visible_lessons_queryset(self.request.user).select_related('student', 'instructor')
        student_id = self.request.GET.get('student')
        if student_id:
            qs = qs.filter(student_id=student_id)
        return qs


class LessonCreateView(AdminOrInstructorRequiredMixin, View):
    template_name = 'lessons/lesson_form.html'

    def get(self, request):
        form = LessonForm(student_queryset=visible_students_queryset(request.user))
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = LessonForm(request.POST, student_queryset=visible_students_queryset(request.user))
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})
        try:
            lesson = create_lesson(
                request.user, student=form.cleaned_data['student'],
                lesson_date=form.cleaned_data['lesson_date'], start_time=form.cleaned_data['start_time'],
                hours=form.cleaned_data['hours'],
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, getattr(exc, 'message', str(exc)))
            return render(request, self.template_name, {'form': form})
        messages.success(request, "Dars qo'shildi")
        return redirect('lessons:list')


class LessonAttendanceView(AdminOrInstructorRequiredMixin, View):
    def post(self, request, pk, value):
        lesson = get_object_or_404(visible_lessons_queryset(request.user), pk=pk)
        attended = {'yes': True, 'no': False, 'unknown': None}.get(value)
        mark_attendance(request.user, lesson, attended)
        messages.success(request, 'Belgilandi')
        return redirect('lessons:list')
