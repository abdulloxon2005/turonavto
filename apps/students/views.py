from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.accounts.models import User
from apps.core.mixins import AdminOrTeacherRequiredMixin, AdminRequiredMixin, AnyRoleRequiredMixin, StaffRequiredMixin

from .forms import DeleteRequestDecisionForm, DeleteRequestForm, StudentForm, StudentWordImportForm
from .models import DeleteRequest, Student
from .services import (
    archive_student,
    assign_instructor,
    bulk_import_students_from_word,
    can_edit_student,
    change_owner,
    create_delete_request,
    create_student,
    decide_delete_request,
    delete_student,
    expel_student,
    find_duplicates,
    generate_student_import_sample_docx,
    student_enriched_info,
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
            qs = (
                qs.filter(full_name__icontains=q)
                | qs.filter(phone__icontains=q)
                | qs.filter(passport_no__icontains=q)
            ).distinct()
        group_id = self.request.GET.get('group')
        if group_id:
            qs = qs.filter(group_memberships__group_id=group_id, group_memberships__left_at__isnull=True)
        owner_id = self.request.GET.get('owner')
        if owner_id:
            qs = qs.filter(brought_by_user_id_id=owner_id)
        status = self.request.GET.get('status', Student.Status.ACTIVE)
        if status:
            qs = qs.filter(status=status)

        learning_filter = self.request.GET.get('learning_status', '').strip()
        payment_filter = self.request.GET.get('payment_status', '').strip()
        if learning_filter or payment_filter:
            matching_ids = []
            for s in qs.distinct():
                info = student_enriched_info(s)
                if learning_filter and info['learning_status'] != learning_filter:
                    continue
                if payment_filter and info['payment_status'] != payment_filter:
                    continue
                matching_ids.append(s.pk)
            qs = qs.filter(pk__in=matching_ids)

        return qs.distinct()

    def get_context_data(self, **kwargs):
        from apps.groups.models import Group
        from apps.payments.services import can_collect_payment

        context = super().get_context_data(**kwargs)
        for s in context['students']:
            s.enriched = student_enriched_info(s)
            s.can_collect = can_collect_payment(self.request.user, s)

        all_visible = list(
            visible_students_queryset(self.request.user)
            .filter(status=Student.Status.ACTIVE)
            .select_related('brought_by_user_id')
        )
        all_enriched = [student_enriched_info(s) for s in all_visible]
        context['stats'] = {
            'total': len(all_enriched),
            'studying': sum(1 for item in all_enriched if item['learning_status'] == 'studying'),
            'finished': sum(1 for item in all_enriched if item['learning_status'] == 'finished'),
            'debtors_count': sum(1 for item in all_enriched if item['payment_status'] == 'debtor'),
            'total_paid': sum(item['paid'] for item in all_enriched),
            'total_debt': sum(item['debt'] for item in all_enriched),
        }
        context['learning_filter'] = self.request.GET.get('learning_status', '').strip()
        context['payment_filter'] = self.request.GET.get('payment_status', '').strip()

        if self.request.user.is_admin():
            context['group_options'] = Group.objects.all()
            context['owner_options'] = User.objects.exclude(role=User.Role.ADMIN)
        elif self.request.user.is_teacher():
            context['group_options'] = Group.objects.filter(group_teachers__user=self.request.user).distinct()
        elif self.request.user.is_instructor():
            context['group_options'] = Group.objects.filter(group_instructors__user=self.request.user).distinct()
        return context


class MyBroughtStudentsView(AnyRoleRequiredMixin, View):
    """Foydalanuvchi o'zi olib kelgan o'quvchilarning alohida ro'yxati, o'qish va to'lov holatlari bilan."""

    template_name = 'students/my_brought_students.html'

    def get(self, request):
        from apps.groups.models import Group

        qs = Student.objects.filter(brought_by_user_id=request.user).select_related('brought_by_user_id')
        q = request.GET.get('q', '').strip()
        if q:
            qs = (
                qs.filter(full_name__icontains=q)
                | qs.filter(phone__icontains=q)
                | qs.filter(passport_no__icontains=q)
            ).distinct()
        group_id = request.GET.get('group', '').strip()
        if group_id:
            qs = qs.filter(group_memberships__group_id=group_id)

        all_brought = list(Student.objects.filter(brought_by_user_id=request.user))
        all_enriched = [student_enriched_info(s) for s in all_brought]

        stats = {
            'total': len(all_enriched),
            'studying': sum(1 for item in all_enriched if item['learning_status'] == 'studying'),
            'finished': sum(1 for item in all_enriched if item['learning_status'] == 'finished'),
            'total_paid': sum(item['paid'] for item in all_enriched),
            'total_debt': sum(item['debt'] for item in all_enriched),
        }

        items = [student_enriched_info(s) for s in qs.distinct()]

        learning_filter = request.GET.get('learning_status', '').strip()
        if learning_filter:
            items = [i for i in items if i['learning_status'] == learning_filter]

        payment_filter = request.GET.get('payment_status', '').strip()
        if payment_filter:
            items = [i for i in items if i['payment_status'] == payment_filter]

        if request.user.is_teacher():
            group_options = Group.objects.filter(group_teachers__user=request.user).distinct()
        elif request.user.is_instructor():
            group_options = Group.objects.filter(group_instructors__user=request.user).distinct()
        else:
            group_options = Group.objects.all()

        context = {
            'items': items,
            'stats': stats,
            'learning_filter': learning_filter,
            'payment_filter': payment_filter,
            'group_options': group_options,
        }
        return render(request, self.template_name, context)


class StudentCreateView(AdminOrTeacherRequiredMixin, View):
    template_name = 'students/student_form.html'

    def get(self, request):
        initial = {}
        group_id = request.GET.get('group')
        if group_id:
            initial['group'] = group_id
        form = StudentForm(user=request.user, is_create=True, initial=initial)
        return render(request, self.template_name, {'form': form, 'preset_group_id': group_id})

    def post(self, request):
        form = StudentForm(request.POST, request.FILES, user=request.user, is_create=True)
        preset_group_id = request.POST.get('preset_group_id') or request.GET.get('group')
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'preset_group_id': preset_group_id})

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
                return render(
                    request,
                    self.template_name,
                    {'form': form, 'duplicate_warning': True, 'preset_group_id': preset_group_id},
                )

        try:
            student = create_student(
                request.user,
                full_name=data['full_name'],
                phone=data['phone'],
                phone2=data['phone2'],
                birth_date=data['birth_date'],
                address=data['address'],
                photo=data.get('photo'),
                note=data['note'],
                group=data.get('group'),
            )
        except ValidationError as exc:
            messages.error(request, exc.message)
            return render(request, self.template_name, {'form': form, 'preset_group_id': preset_group_id})

        messages.success(request, "O'quvchi qo'shildi")
        if preset_group_id and data.get('group'):
            return redirect('groups:detail', pk=data['group'].pk)
        return redirect('students:detail', pk=student.pk)


class StudentWordImportView(AdminOrTeacherRequiredMixin, View):
    template_name = 'students/student_import.html'

    def get(self, request):
        initial = {}
        group_id = request.GET.get('group')
        if group_id:
            initial['group'] = group_id
        form = StudentWordImportForm(user=request.user, initial=initial)
        return render(request, self.template_name, {'form': form, 'preset_group_id': group_id})

    def post(self, request):
        form = StudentWordImportForm(request.POST, request.FILES, user=request.user)
        preset_group_id = request.POST.get('preset_group_id') or request.GET.get('group')
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'preset_group_id': preset_group_id})

        group = form.cleaned_data['group']
        word_file = form.cleaned_data['word_file']
        try:
            created_students, errors = bulk_import_students_from_word(request.user, word_file, group)
        except ValidationError as exc:
            messages.error(request, exc.message)
            return render(request, self.template_name, {'form': form, 'preset_group_id': preset_group_id})

        if created_students:
            messages.success(
                request,
                f"Word fayl orqali {len(created_students)} ta o'quvchi '{group.name}' guruhiga muvaffaqiyatli qo'shildi!",
            )
        if errors:
            for err in errors[:10]:
                messages.warning(request, err)
            if len(errors) > 10:
                messages.warning(request, f"... va yana {len(errors) - 10} ta qatorda xatolik bo'ldi.")
        if not created_students and not errors:
            messages.info(request, "Word fayldagi jadvalda qo'shish uchun yangi qatorlar topilmadi.")

        if created_students:
            return redirect('groups:detail', pk=group.pk)
        return render(
            request,
            self.template_name,
            {'form': form, 'preset_group_id': preset_group_id, 'import_errors': errors},
        )


class StudentWordSampleView(AnyRoleRequiredMixin, View):
    def get(self, request):
        content = generate_student_import_sample_docx()
        response = HttpResponse(
            content,
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        response['Content-Disposition'] = 'attachment; filename="oquvchilar_namuna.docx"'
        return response


class StudentDetailView(AnyRoleRequiredMixin, View):
    template_name = 'students/student_detail.html'

    def get(self, request, pk):
        from apps.payments.models import Payment
        from apps.payments.services import can_collect_payment, student_debt_summary
        from apps.lessons.services import total_hours_for_student
        from apps.exams.services import exam_summary_for_student

        student = _get_visible_student_or_404(request.user, pk)
        payments = (
            Payment.objects.filter(student=student)
            .select_related('enrollment__group', 'received_by_user_id')
            .order_by('-paid_at')
        )
        enriched = student_enriched_info(student)
        context = {
            'student': student,
            'can_edit': can_edit_student(request.user, student) and not request.user.is_teacher(),
            'memberships': student.group_memberships.filter(left_at__isnull=True).select_related('group'),
            'instructor_links': student.instructor_links.select_related('instructor'),
            'debt_summary': student_debt_summary(student),
            'enriched': enriched,
            'payments': payments,
            'can_collect_payment': can_collect_payment(request.user, student),
            'total_hours': total_hours_for_student(student),
            'exam_summary': exam_summary_for_student(student),
            'can_record_exam': (request.user.is_admin() or request.user.is_teacher()) and enriched['learning_status'] == 'finished',
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
        update_student(
            request.user, student,
            full_name=data['full_name'], phone=data['phone'], phone2=data['phone2'],
            passport_no=student.passport_no, birth_date=data['birth_date'],
            address=data['address'], photo=data.get('photo'), note=data['note'],
        )
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


class StudentExpelView(AdminRequiredMixin, View):
    def post(self, request, pk):
        student = get_object_or_404(Student, pk=pk)
        if student.status == Student.Status.EXPELLED:
            unarchive_student(request.user, student)
            messages.success(request, "O'quvchi qayta faollashtirildi")
        else:
            expel_student(request.user, student)
            messages.success(request, "O'quvchi chetlatildi")
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
