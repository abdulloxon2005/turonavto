from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.accounts.models import User
from apps.core.mixins import AdminRequiredMixin
from apps.groups.services import visible_groups_queryset
from apps.students.services import visible_students_queryset

from .forms import LessonForm, TheoryLessonForm
from .models import Lesson, TheoryLesson, TheoryLessonAttendance
from .services import (
    create_lesson,
    create_theory_lesson,
    mark_attendance,
    mark_theory_attendance,
    visible_lessons_queryset,
    visible_theory_lessons_queryset,
)


class LessonListView(AdminRequiredMixin, ListView):
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


class LessonCreateView(AdminRequiredMixin, View):
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


class LessonAttendanceView(AdminRequiredMixin, View):
    def post(self, request, pk, value):
        lesson = get_object_or_404(visible_lessons_queryset(request.user), pk=pk)
        attended = {'yes': True, 'no': False, 'unknown': None}.get(value)
        mark_attendance(request.user, lesson, attended)
        messages.success(request, 'Belgilandi')
        return redirect('lessons:list')


class TheoryLessonListView(AdminRequiredMixin, ListView):
    model = TheoryLesson
    template_name = 'lessons/theory_lesson_list.html'
    context_object_name = 'theory_lessons'
    paginate_by = 30

    def get_queryset(self):
        qs = visible_theory_lessons_queryset(self.request.user).select_related('group', 'teacher')
        group_id = self.request.GET.get('group')
        if group_id:
            qs = qs.filter(group_id=group_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for lesson in context['theory_lessons']:
            lesson.attendance_list = lesson.attendances.select_related('student').order_by('student__full_name')
        context['group_options'] = visible_groups_queryset(self.request.user)
        return context


class TheoryLessonCreateView(AdminRequiredMixin, View):
    template_name = 'lessons/theory_lesson_form.html'

    def get(self, request):
        form = TheoryLessonForm(
            group_queryset=visible_groups_queryset(request.user),
            teacher_queryset=User.objects.filter(role=User.Role.TEACHER, is_active=True),
        )
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = TheoryLessonForm(
            request.POST,
            group_queryset=visible_groups_queryset(request.user),
            teacher_queryset=User.objects.filter(role=User.Role.TEACHER, is_active=True),
        )
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})
        try:
            create_theory_lesson(
                request.user,
                group=form.cleaned_data['group'], teacher=form.cleaned_data['teacher'],
                topic=form.cleaned_data['topic'], lesson_date=form.cleaned_data['lesson_date'],
                start_time=form.cleaned_data['start_time'], hours=form.cleaned_data['hours'],
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, getattr(exc, 'message', str(exc)))
            return render(request, self.template_name, {'form': form})
        messages.success(request, "Nazariy dars qo'shildi")
        return redirect('lessons:theory_list')


class TheoryLessonAttendanceView(AdminRequiredMixin, View):
    def post(self, request, pk, value):
        attendance = get_object_or_404(
            TheoryLessonAttendance.objects.filter(theory_lesson__in=visible_theory_lessons_queryset(request.user)),
            pk=pk,
        )
        attended = {'yes': True, 'no': False, 'unknown': None}.get(value)
        mark_theory_attendance(request.user, attendance, attended)
        messages.success(request, 'Belgilandi')
        return redirect('lessons:theory_list')
