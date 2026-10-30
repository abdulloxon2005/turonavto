from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.accounts.models import User
from apps.core.mixins import AdminRequiredMixin, AnyRoleRequiredMixin

from .forms import GroupForm
from .models import Group
from .services import (
    add_student_to_group,
    archive_group,
    assign_instructor,
    assign_teacher,
    close_group,
    create_group,
    delete_group,
    remove_instructor,
    remove_student_from_group,
    remove_teacher,
    reopen_group,
    update_group,
    visible_groups_queryset,
)


class GroupListView(AnyRoleRequiredMixin, ListView):
    model = Group
    template_name = 'groups/group_list.html'
    context_object_name = 'groups'
    paginate_by = 20

    def get_queryset(self):
        qs = visible_groups_queryset(self.request.user)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(name__icontains=q)
        status = self.request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)
        return qs


class GroupCreateView(AdminRequiredMixin, View):
    template_name = 'groups/group_form.html'

    def get(self, request):
        return render(request, self.template_name, {'form': GroupForm()})

    def post(self, request):
        form = GroupForm(request.POST)
        if form.is_valid():
            group = create_group(request.user, **form.cleaned_data)
            messages.success(request, "Guruh yaratildi")
            return redirect('groups:detail', pk=group.pk)
        return render(request, self.template_name, {'form': form})


def _get_visible_group_or_404(user, pk):
    group = visible_groups_queryset(user).filter(pk=pk).first()
    if group is None:
        raise Http404
    return group


class GroupDetailView(AnyRoleRequiredMixin, View):
    template_name = 'groups/group_detail.html'

    def get(self, request, pk):
        from apps.payments.services import enrollment_summary

        group = _get_visible_group_or_404(request.user, pk)
        memberships = group.group_students.filter(left_at__isnull=True).select_related('student')
        enrollment_summaries = [enrollment_summary(e) for e in group.enrollments.all()]
        context = {
            'group': group,
            'memberships': memberships,
            'teachers': User.objects.filter(group_teacher_links__group=group),
            'instructors': User.objects.filter(group_instructor_links__group=group),
            'total_paid': sum(s['paid'] for s in enrollment_summaries),
            'total_debt': sum(s['debt'] for s in enrollment_summaries),
        }
        if request.user.is_admin():
            context['available_teachers'] = User.objects.filter(role=User.Role.TEACHER, is_active=True).exclude(
                group_teacher_links__group=group
            )
            context['available_instructors'] = User.objects.filter(role=User.Role.INSTRUCTOR, is_active=True).exclude(
                group_instructor_links__group=group
            )
            context['other_open_groups'] = Group.objects.filter(status=Group.Status.OPEN).exclude(pk=group.pk)
        return render(request, self.template_name, context)


class GroupUpdateView(AdminRequiredMixin, UpdateView):
    model = Group
    form_class = GroupForm
    template_name = 'groups/group_form.html'

    def form_valid(self, form):
        update_group(self.request.user, self.object, **form.cleaned_data)
        messages.success(self.request, "Guruh yangilandi")
        return redirect('groups:detail', pk=self.object.pk)


class GroupStatusActionView(AdminRequiredMixin, View):
    action_map = {
        'close': close_group,
        'archive': archive_group,
        'reopen': reopen_group,
    }

    def post(self, request, pk, action):
        group = get_object_or_404(Group, pk=pk)
        func = self.action_map.get(action)
        if not func:
            raise Http404
        func(request.user, group)
        messages.success(request, 'Holat yangilandi')
        return redirect('groups:detail', pk=group.pk)


class GroupDeleteView(AdminRequiredMixin, View):
    def post(self, request, pk):
        group = get_object_or_404(Group, pk=pk)
        try:
            delete_group(request.user, group)
        except ValidationError as exc:
            messages.error(request, exc.message)
            return redirect('groups:detail', pk=pk)
        messages.success(request, "Guruh o'chirildi")
        return redirect('groups:list')


class GroupStaffAssignView(AdminRequiredMixin, View):
    def post(self, request, pk):
        group = get_object_or_404(Group, pk=pk)
        user = get_object_or_404(User, pk=request.POST.get('user_id'))
        role_kind = request.POST.get('kind')  # 'teacher' or 'instructor'
        action = request.POST.get('action')  # 'add' or 'remove'

        if role_kind == 'teacher':
            if action == 'add':
                assign_teacher(request.user, group, user)
            else:
                remove_teacher(request.user, group, user)
        elif role_kind == 'instructor':
            if action == 'add':
                assign_instructor(request.user, group, user)
            else:
                remove_instructor(request.user, group, user)
        else:
            raise Http404
        messages.success(request, 'Yangilandi')
        return redirect('groups:detail', pk=pk)


class GroupStudentSearchView(AdminRequiredMixin, View):
    """Guruhga biriktirish uchun hali a'zo bo'lmagan o'quvchilarni qidirish (htmx)."""

    def get(self, request, pk):
        from apps.students.models import Student

        group = get_object_or_404(Group, pk=pk)
        q = request.GET.get('q', '').strip()
        results = Student.objects.filter(status=Student.Status.ACTIVE).exclude(
            group_memberships__group=group, group_memberships__left_at__isnull=True
        )
        if q:
            results = (results.filter(full_name__icontains=q) | results.filter(phone__icontains=q)).distinct()
        results = results[:15]
        return render(request, 'groups/_student_search_results.html', {'group': group, 'results': results})


class GroupStudentAddView(AdminRequiredMixin, View):
    def post(self, request, pk):
        from apps.students.models import Student

        group = get_object_or_404(Group, pk=pk)
        student = get_object_or_404(Student, pk=request.POST.get('student_id'))
        try:
            add_student_to_group(request.user, group, student)
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, "O'quvchi guruhga qo'shildi")
        return redirect('groups:detail', pk=pk)


class GroupStudentRemoveView(AdminRequiredMixin, View):
    def post(self, request, pk, student_id):
        group = get_object_or_404(Group, pk=pk)
        from apps.students.models import Student

        student = get_object_or_404(Student, pk=student_id)
        try:
            remove_student_from_group(request.user, group, student)
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, "O'quvchi guruhdan chiqarildi")
        return redirect('groups:detail', pk=pk)


class GroupStudentMoveView(AdminRequiredMixin, View):
    def post(self, request, pk, student_id):
        from apps.students.models import Student

        from .services import move_student

        from_group = get_object_or_404(Group, pk=pk)
        student = get_object_or_404(Student, pk=student_id)
        to_group = get_object_or_404(Group, pk=request.POST.get('to_group_id'))
        try:
            move_student(request.user, student, from_group, to_group)
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, f"O'quvchi {to_group.name} guruhiga ko'chirildi")
        return redirect('groups:detail', pk=pk)
