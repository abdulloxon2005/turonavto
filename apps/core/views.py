import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from .mixins import AdminRequiredMixin
from .models import AuditLog


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['role'] = user.role

        if user.is_admin():
            context.update(self._admin_stats())
        elif user.is_teacher():
            context['stats'] = self._teacher_stats(user)
        elif user.is_instructor():
            context['stats'] = self._instructor_stats(user)
        return context

    def _admin_stats(self):
        from apps.accounts.models import User
        from apps.expenses.services import by_category_totals, monthly_totals as expense_monthly_totals
        from apps.groups.models import Group
        from apps.payments.models import Enrollment, Payment
        from apps.payments.services import debtors_queryset
        from apps.reports.services import staff_report
        from apps.students.models import Student

        today = timezone.localdate()
        month_start = today.replace(day=1)

        students_count = Student.objects.filter(status=Student.Status.ACTIVE).count()
        teachers_count = User.objects.filter(role=User.Role.TEACHER, is_active=True).count()
        instructors_count = User.objects.filter(role=User.Role.INSTRUCTOR, is_active=True).count()
        open_groups_count = Group.objects.filter(status=Group.Status.OPEN).count()

        confirmed_payments = Payment.objects.filter(status=Payment.Status.CONFIRMED)
        month_revenue = confirmed_payments.filter(paid_at__date__gte=month_start).aggregate(
            s=Sum('amount')
        )['s'] or 0
        total_collected_all_time = confirmed_payments.aggregate(s=Sum('amount'))['s'] or 0
        total_debt = sum(d['debt'] for d in debtors_queryset(self.request.user))
        total_due_all = Enrollment.objects.aggregate(s=Sum('total_due'))['s'] or 0

        month_expenses = sum(
            total for _, total in expense_monthly_totals(months=1)
        )

        # Oxirgi 6 oy: tushum va xarajat
        revenue_by_month = []
        month_cursor_year, month_cursor_month = today.year, today.month
        for _ in range(6):
            start = datetime.date(month_cursor_year, month_cursor_month, 1)
            if month_cursor_month == 12:
                end = datetime.date(month_cursor_year + 1, 1, 1)
            else:
                end = datetime.date(month_cursor_year, month_cursor_month + 1, 1)
            amount = confirmed_payments.filter(
                paid_at__date__gte=start, paid_at__date__lt=end
            ).aggregate(s=Sum('amount'))['s'] or 0
            revenue_by_month.append((start, amount))
            month_cursor_month -= 1
            if month_cursor_month == 0:
                month_cursor_month = 12
                month_cursor_year -= 1
        revenue_by_month.reverse()
        expense_by_month = expense_monthly_totals(months=6)

        month_labels = [d.strftime('%Y-%m') for d, _ in revenue_by_month]
        revenue_values = [amount for _, amount in revenue_by_month]
        expense_values = [amount for _, amount in expense_by_month]

        top_staff = sorted(staff_report(), key=lambda r: r['collected'], reverse=True)[:5]
        staff_labels = [row['user'].full_name for row in top_staff]
        staff_values = [row['collected'] for row in top_staff]

        expense_categories = by_category_totals(date_from=month_start)

        chart_data = {
            'monthLabels': month_labels,
            'revenueValues': revenue_values,
            'expenseValues': expense_values,
            'debtPaid': max(total_due_all - total_debt, 0),
            'debtRemaining': total_debt,
            'staffLabels': staff_labels,
            'staffValues': staff_values,
            'expenseCategoryLabels': [label for label, _ in expense_categories],
            'expenseCategoryValues': [amount for _, amount in expense_categories],
        }

        return {
            'admin_stats': {
                'students_count': students_count,
                'teachers_count': teachers_count,
                'instructors_count': instructors_count,
                'open_groups_count': open_groups_count,
                'month_revenue': month_revenue,
                'total_collected_all_time': total_collected_all_time,
                'total_debt': total_debt,
                'month_expenses': month_expenses,
                'month_profit': month_revenue - month_expenses,
            },
            'chart_data': chart_data,
        }

    def _teacher_stats(self, user):
        from apps.payments.services import debtors_queryset, visible_payments_queryset
        from apps.payments.models import Payment
        from apps.students.models import Student

        today = timezone.localdate()
        month_start = today.replace(day=1)

        students_count = Student.objects.filter(brought_by_user_id=user).count()
        payments = visible_payments_queryset(user).filter(status=Payment.Status.CONFIRMED)
        total_collected = payments.aggregate(s=Sum('amount'))['s'] or 0
        month_revenue = payments.filter(paid_at__date__gte=month_start).aggregate(s=Sum('amount'))['s'] or 0
        total_debt = sum(d['debt'] for d in debtors_queryset(user))

        return {
            'students_count': students_count,
            'total_collected': total_collected,
            'month_revenue': month_revenue,
            'total_debt': total_debt,
        }

    def _instructor_stats(self, user):
        from apps.lessons.services import total_hours_for_instructor
        from apps.payments.services import debtors_queryset
        from apps.payments.models import Payment

        today = timezone.localdate()
        month_start = today.replace(day=1)

        payments_today = Payment.objects.filter(
            received_by_user_id=user, status=Payment.Status.CONFIRMED, paid_at__date=today,
        ).aggregate(s=Sum('amount'))['s'] or 0
        payments_month = Payment.objects.filter(
            received_by_user_id=user, status=Payment.Status.CONFIRMED, paid_at__date__gte=month_start,
        ).aggregate(s=Sum('amount'))['s'] or 0
        debtors_count = len(debtors_queryset(user))
        month_hours = total_hours_for_instructor(user, since=month_start)

        return {
            'collected_today': payments_today,
            'collected_month': payments_month,
            'debtors_count': debtors_count,
            'month_hours': month_hours,
        }


class AuditLogListView(AdminRequiredMixin, ListView):
    model = AuditLog
    template_name = 'core/audit_log.html'
    context_object_name = 'logs'
    paginate_by = 40

    def get_queryset(self):
        qs = AuditLog.objects.select_related('user')
        action = self.request.GET.get('action')
        entity_type = self.request.GET.get('entity_type')
        user_id = self.request.GET.get('user')
        if action:
            qs = qs.filter(action=action)
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['actions'] = AuditLog.objects.order_by().values_list('action', flat=True).distinct()
        context['entity_types'] = AuditLog.objects.order_by().values_list('entity_type', flat=True).distinct()
        from apps.accounts.models import User
        context['users'] = User.objects.all()
        return context


class BackupListView(AdminRequiredMixin, View):
    template_name = 'core/backup_list.html'

    def get(self, request):
        from django.shortcuts import render

        files = sorted(
            settings.BACKUP_DIR.glob('backup_*.sqlite3'), key=lambda p: p.stat().st_mtime, reverse=True
        ) if settings.BACKUP_DIR.exists() else []
        return render(request, self.template_name, {'files': files})

    def post(self, request):
        from .jobs import backup_database

        backup_database()
        messages.success(request, 'Zaxira nusxa olindi')
        return redirect('core:backup_list')


class BackupDownloadView(AdminRequiredMixin, View):
    def get(self, request, filename):
        import re

        if not re.fullmatch(r'backup_\d{8}_\d{6}\.sqlite3', filename):
            raise Http404
        path = settings.BACKUP_DIR / filename
        if not path.is_file():
            raise Http404
        return FileResponse(open(path, 'rb'), as_attachment=True, filename=filename)


class ArchiveView(AdminRequiredMixin, TemplateView):
    """Arxivlangan o'quvchilar, guruhlar va bloklangan xodimlarni bitta joyda ko'rsatadi."""

    template_name = 'core/archive.html'

    def get_context_data(self, **kwargs):
        from apps.accounts.models import User
        from apps.groups.models import Group
        from apps.students.models import Student

        context = super().get_context_data(**kwargs)
        context['archived_students'] = Student.objects.filter(
            status=Student.Status.ARCHIVED
        ).select_related('brought_by_user_id').order_by('full_name')
        context['archived_groups'] = Group.objects.filter(
            status=Group.Status.ARCHIVED
        ).order_by('-start_date', 'name')
        context['blocked_staff'] = User.objects.exclude(
            role=User.Role.ADMIN
        ).filter(is_active=False).order_by('full_name')
        return context


class ArchiveRestoreStudentView(AdminRequiredMixin, View):
    def post(self, request, pk):
        from apps.students.models import Student
        from apps.students.services import unarchive_student

        student = get_object_or_404(Student, pk=pk, status=Student.Status.ARCHIVED)
        unarchive_student(request.user, student)
        messages.success(request, "O'quvchi arxivdan chiqarildi")
        return redirect('core:archive')


class ArchiveDeleteStudentView(AdminRequiredMixin, View):
    def post(self, request, pk):
        from apps.students.models import Student
        from apps.students.services import delete_student

        student = get_object_or_404(Student, pk=pk, status=Student.Status.ARCHIVED)
        try:
            delete_student(request.user, student)
            messages.success(request, "O'quvchi butunlay o'chirildi")
        except (ValidationError, ProtectedError):
            messages.error(
                request,
                "Bu o'quvchini butunlay o'chirib bo'lmaydi, chunki unga bog'liq yozuvlar "
                "(to'lovlar va h.k.) mavjud",
            )
        return redirect('core:archive')


class ArchiveRestoreGroupView(AdminRequiredMixin, View):
    def post(self, request, pk):
        from apps.groups.models import Group
        from apps.groups.services import reopen_group

        group = get_object_or_404(Group, pk=pk, status=Group.Status.ARCHIVED)
        reopen_group(request.user, group)
        messages.success(request, 'Guruh arxivdan chiqarildi')
        return redirect('core:archive')


class ArchiveDeleteGroupView(AdminRequiredMixin, View):
    def post(self, request, pk):
        from apps.groups.models import Group
        from apps.groups.services import delete_group

        group = get_object_or_404(Group, pk=pk, status=Group.Status.ARCHIVED)
        try:
            delete_group(request.user, group)
            messages.success(request, 'Guruh butunlay o\'chirildi')
        except (ValidationError, ProtectedError):
            messages.error(
                request,
                "Bu guruhni butunlay o'chirib bo'lmaydi, chunki unga bog'liq yozuvlar "
                "(a'zolar, to'lovlar va h.k.) mavjud",
            )
        return redirect('core:archive')


class ArchiveRestoreStaffView(AdminRequiredMixin, View):
    def post(self, request, pk):
        from apps.accounts.models import User
        from apps.accounts.services import set_active

        user = get_object_or_404(User.objects.exclude(role=User.Role.ADMIN), pk=pk, is_active=False)
        set_active(request.user, user, True)
        messages.success(request, 'Xodim arxivdan (blokdan) chiqarildi')
        return redirect('core:archive')


class ArchiveDeleteStaffView(AdminRequiredMixin, View):
    def post(self, request, pk):
        from apps.accounts.models import User
        from apps.accounts.services import delete_staff

        user = get_object_or_404(User.objects.exclude(role=User.Role.ADMIN), pk=pk, is_active=False)
        try:
            delete_staff(request.user, user)
            messages.success(request, 'Xodim butunlay o\'chirildi')
        except ProtectedError:
            messages.error(
                request,
                "Bu xodimni butunlay o'chirib bo'lmaydi, chunki unga bog'liq yozuvlar "
                "(to'lovlar, o'quvchilar va h.k.) mavjud",
            )
        return redirect('core:archive')
