from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from apps.core.mixins import AdminOrTeacherRequiredMixin, AdminRequiredMixin
from apps.students.services import visible_students_queryset

from .forms import ExamAttemptForm
from .models import ExamAttempt
from .services import delete_exam_attempt, record_exam_attempt


def _get_visible_student_or_404(user, pk):
    student = visible_students_queryset(user).filter(pk=pk).first()
    if student is None:
        raise Http404
    return student


class ExamAttemptCreateView(AdminOrTeacherRequiredMixin, View):
    def post(self, request, student_pk):
        student = _get_visible_student_or_404(request.user, student_pk)
        form = ExamAttemptForm(request.POST)
        if form.is_valid():
            record_exam_attempt(
                request.user,
                student=student,
                exam_type=form.cleaned_data['exam_type'],
                exam_date=form.cleaned_data['exam_date'],
                passed=form.cleaned_data['passed'] == '1',
                note=form.cleaned_data['note'],
            )
            messages.success(request, 'Imtihon natijasi qo\'shildi')
        else:
            messages.error(request, "Imtihon natijasini saqlab bo'lmadi, maydonlarni tekshiring")
        return redirect('students:detail', pk=student.pk)


class ExamAttemptDeleteView(AdminRequiredMixin, View):
    def post(self, request, pk):
        attempt = get_object_or_404(ExamAttempt, pk=pk)
        student_pk = attempt.student_id
        delete_exam_attempt(request.user, attempt)
        messages.success(request, "Imtihon natijasi o'chirildi")
        return redirect('students:detail', pk=student_pk)
