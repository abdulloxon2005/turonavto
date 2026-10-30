from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.accounts.models import User
from apps.core.mixins import AdminRequiredMixin, AnyRoleRequiredMixin, StaffRequiredMixin

from .forms import DeleteRequestDecisionForm, DeleteRequestForm, StudentForm
from .models import DeleteRequest, Student
from .services import (
    archive_student,
    assign_instructor,
    can_edit_student,
    change_owner,
    create_delete_request,
    create_student,
    decide_delete_request,
    delete_student,
    find_duplicates,
    unarchive_student,
    unassign_instructor,
    update_student,
    visible_students_queryset,
)


def _get_visible_student_or_404(user, pk):
    student = visible_students_queryset(user).filter(pk=pk).first()
    if student is None:
        raise Http404
    return student


class StudentListView(AnyRoleRequiredMixin, ListView):
    model = Student
    template_name = 'students/student_list.html'
    context_object_name = 'students'
    paginate_by = 25

    def get_queryset(self):
        qs = visible_students_queryset(self.request.user).select_related('brought_by_user_id')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = (qs.filter(full_name__icontains=q) | qs.filter(phone__icontains=q)).distinct()
        group_id = self.request.GET.get('group')
        if group_id:
            qs = qs.filter(group_memberships__group_id=group_id, group_memberships__left_at__isnull=True)
        owner_id = self.request.GET.get('owner')
        if owner_id:
            qs = qs.filter(brought_by_user_id_id=owner_id)
        status = self.request.GET.get('status', Student.Status.ACTIVE)
        if status:
            qs = qs.filter(status=status)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_admin():
            from apps.groups.models import Group

            context['group_options'] = Group.objects.all()
            context['owner_options'] = User.objects.exclude(role=User.Role.ADMIN)
        return context


class StudentCreateView(AnyRoleRequiredMixin, View):
    template_name = 'students/student_form.html'

    def get(self, request):
        form = StudentForm(user=request.user, is_create=True)
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = StudentForm(request.POST, request.FILES, user=request.user, is_create=True)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        data = form.cleaned_data
        if not data.get('confirm_duplicate'):
            duplicates = find_duplicates(data['phone'])
            if duplicates.exists():
                messages.warning(
                    request,
                    f"Diqqat: '{data['phone']}' raqami bilan {duplicates.count()} ta o'quvchi allaqachon mavjud "
                    "('{}' ...). Agar baribir davom etmoqchi bo'lsangiz, formani qayta yuboring.".format(
                        duplicates.first().full_name
                    ),
                )
                form.fields['confirm_duplicate'].initial = True
                form.data = form.data.copy()
                form.data['confirm_duplicate'] = 'on'
                return render(request, self.template_name, {'form': form, 'duplicate_warning': True})

        try:
            student = create_student(
                request.user,
                full_name=data['full_name'],
                phone=data['phone'],
                phone2=data['phone2'],
                passport_no=data['passport_no'],
                birth_date=data['birth_date'],
                address=data['address'],
                photo=data.get('photo'),
                note=data['note'],
                group=data.get('group'),
            )
        except ValidationError as exc:
            messages.error(request, exc.message)
            return render(request, self.template_name, {'form': form})
        except IntegrityError:
            form.add_error('passport_no', 'Bu pasport raqami bilan o\'quvchi allaqachon mavjud')
            return render(request, self.template_name, {'form': form})

        messages.success(request, "O'quvchi qo'shildi")
        return redirect('students:detail', pk=student.pk)


class StudentDetailView(AnyRoleRequiredMixin, View):
    template_name = 'students/student_detail.html'

    def get(self, request, pk):
        from apps.payments.services import can_collect_payment, student_debt_summary
        from apps.lessons.services import total_hours_for_student

        student = _get_visible_student_or_404(request.user, pk)
        context = {
            'student': student,
            'can_edit': can_edit_student(request.user, student),
            'memberships': student.group_memberships.filter(left_at__isnull=True).select_related('group'),
            'instructor_links': student.instructor_links.select_related('instructor'),
            'debt_summary': student_debt_summary(student),
            'can_collect_payment': can_collect_payment(request.user, student),
            'total_hours': total_hours_for_student(student),
        }
        if request.user.is_admin():
            enrolled_group_ids = student.enrollments.values_list('group_id', flat=True)
            context['groups_without_enrollment'] = student.group_memberships.filter(
                left_at__isnull=True
            ).exclude(group_id__in=enrolled_group_ids).select_related('group')
            context['owner_options'] = User.objects.exclude(role=User.Role.ADMIN)
            context['instructor_options'] = User.objects.filter(role=User.Role.INSTRUCTOR, is_active=True).exclude(
                instructor_student_links__student=student
            )
        return render(request, self.template_name, context)


class StudentUpdateView(AnyRoleRequiredMixin, View):
    template_name = 'students/student_form.html'

    def get(self, request, pk):
        student = _get_visible_student_or_404(request.user, pk)
        if not can_edit_student(request.user, student):
            raise PermissionDenied("Faqat o'quvchining egasi yoki admin tahrirlay oladi")
        form = StudentForm(instance=student, user=request.user, is_create=False)
        return render(request, self.template_name, {'form': form, 'student': student})

    def post(self, request, pk):
        student = _get_visible_student_or_404(request.user, pk)
        if not can_edit_student(request.user, student):
            raise PermissionDenied("Faqat o'quvchining egasi yoki admin tahrirlay oladi")
        form = StudentForm(request.POST, request.FILES, instance=student, user=request.user, is_create=False)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'student': student})
        data = form.cleaned_data
        try:
            update_student(
                request.user, student,
                full_name=data['full_name'], phone=data['phone'], phone2=data['phone2'],
                passport_no=data['passport_no'], birth_date=data['birth_date'],
                address=data['address'], photo=data.get('photo'), note=data['note'],
            )
        except IntegrityError:
            form.add_error('passport_no', 'Bu pasport raqami bilan o\'quvchi allaqachon mavjud')
            return render(request, self.template_name, {'form': form, 'student': student})
        messages.success(request, "O'quvchi ma'lumotlari yangilandi")
        return redirect('students:detail', pk=student.pk)


class StudentArchiveView(AdminRequiredMixin, View):
    def post(self, request, pk):
        student = get_object_or_404(Student, pk=pk)
        if student.status == Student.Status.ACTIVE:
            archive_student(request.user, student)
            messages.success(request, "O'quvchi arxivlandi")
        else:
            unarchive_student(request.user, student)
            messages.success(request, "O'quvchi qayta faollashtirildi")
        return redirect('students:detail', pk=pk)


class StudentDeleteView(AdminRequiredMixin, View):
    def post(self, request, pk):
        student = get_object_or_404(Student, pk=pk)
        try:
            delete_student(request.user, student)
        except ValidationError as exc:
            messages.error(request, exc.message)
            return redirect('students:detail', pk=pk)
        messages.success(request, "O'quvchi o'chirildi")
        return redirect('students:list')


class StudentOwnerChangeView(AdminRequiredMixin, View):
    def post(self, request, pk):
        student = get_object_or_404(Student, pk=pk)
        new_owner = get_object_or_404(User, pk=request.POST.get('owner_id'))
        change_owner(request.user, student, new_owner)
        messages.success(request, "O'quvchi egasi o'zgartirildi")
        return redirect('students:detail', pk=pk)


class StudentInstructorAssignView(AdminRequiredMixin, View):
    def post(self, request, pk):
        student = get_object_or_404(Student, pk=pk)
        instructor = get_object_or_404(User, pk=request.POST.get('instructor_id'), role=User.Role.INSTRUCTOR)
        assign_instructor(request.user, student, instructor)
        messages.success(request, 'Instruktorga biriktirildi')
        return redirect('students:detail', pk=pk)


class StudentInstructorUnassignView(AdminRequiredMixin, View):
    def post(self, request, pk, instructor_id):
        student = get_object_or_404(Student, pk=pk)
        instructor = get_object_or_404(User, pk=instructor_id)
        unassign_instructor(request.user, student, instructor)
        messages.success(request, 'Biriktirish bekor qilindi')
        return redirect('students:detail', pk=pk)


class DeleteRequestCreateView(StaffRequiredMixin, View):
    template_name = 'students/delete_request_form.html'

    def get(self, request, pk):
        student = _get_visible_student_or_404(request.user, pk)
        if student.brought_by_user_id_id != request.user.id:
            raise PermissionDenied("Faqat o'zingiz qo'shgan o'quvchi uchun so'rov yubora olasiz")
        return render(request, self.template_name, {'form': DeleteRequestForm(), 'student': student})

    def post(self, request, pk):
        student = _get_visible_student_or_404(request.user, pk)
        if student.brought_by_user_id_id != request.user.id:
            raise PermissionDenied("Faqat o'zingiz qo'shgan o'quvchi uchun so'rov yubora olasiz")
        form = DeleteRequestForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'student': student})
        create_delete_request(request.user, student, form.cleaned_data['reason'])
        messages.success(request, "So'rov yuborildi")
        return redirect('students:detail', pk=pk)


class DeleteRequestListView(AdminRequiredMixin, ListView):
    model = DeleteRequest
    template_name = 'students/delete_request_list.html'
    context_object_name = 'delete_requests'
    paginate_by = 25

    def get_queryset(self):
        return DeleteRequest.objects.select_related('requested_by').order_by('-created_at')


class DeleteRequestDecideView(AdminRequiredMixin, View):
    def post(self, request, pk, decision):
        delete_request = get_object_or_404(DeleteRequest, pk=pk)
        form = DeleteRequestDecisionForm(request.POST)
        note = form.data.get('note', '') if form.is_valid() else ''
        try:
            decide_delete_request(request.user, delete_request, approve=(decision == 'approve'), note=note)
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, "So'rov ko'rib chiqildi")
        return redirect('students:delete_requests')
