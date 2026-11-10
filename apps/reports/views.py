import datetime

from django.shortcuts import render
from django.utils import timezone
from django.views import View

from apps.accounts.models import User
from apps.core.mixins import AdminRequiredMixin
from apps.groups.models import Group
from apps.payments.models import Payment

from .exporters import export_pdf, export_xlsx
from .services import (
    cash_report,
    dashboard_overview,
    debtors_report,
    groups_report,
    risk_distribution_chart_data,
    revenue_report,
    staff_comparison_chart_data,
    staff_report,
    upcoming_revenue_report,
)


def _parse_date(value, default):
    if not value:
        return default
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return default


def _fmt_date(value):
    if not value:
        return '—'
    return value.strftime('%d.%m.%Y')


class ReportsIndexView(AdminRequiredMixin, View):
    template_name = 'reports/index.html'

    def get(self, request):
        import json

        overview = dashboard_overview()
        staff_chart = staff_comparison_chart_data()
        risk_chart = risk_distribution_chart_data()

        chart_data = {
            'staffLabels': staff_chart['labels'],
            'staffActiveCounts': staff_chart['active_counts'],
            'staffDebts': staff_chart['debts'],
            'riskLabels': list(risk_chart.keys()),
            'riskValues': list(risk_chart.values()),
        }
        return render(request, self.template_name, {
            'overview': overview,
            'chart_data': json.dumps(chart_data),
        })


class RevenueReportView(AdminRequiredMixin, View):
    template_name = 'reports/revenue.html'

    def get(self, request):
        today = timezone.localdate()
        date_from = _parse_date(request.GET.get('date_from'), today.replace(day=1))
        date_to = _parse_date(request.GET.get('date_to'), today)
        method = request.GET.get('method') or None
        received_by = request.GET.get('received_by') or None

        data = revenue_report(date_from, date_to, method=method, received_by=received_by)

        fmt = request.GET.get('format')
        if fmt:
            headers = ['Sana', 'O\'quvchi', 'Summa', 'Usul', 'Qabul qildi']
            rows = [
                [p.paid_at.strftime('%d.%m.%Y %H:%M'), p.student.full_name, p.amount,
                 p.get_method_display(), p.received_by_user_id.full_name]
                for p in data['payments']
            ]
            title = f'Tushum hisoboti ({_fmt_date(date_from)} — {_fmt_date(date_to)})'
            if fmt == 'xlsx':
                return export_xlsx('tushum', title, headers, rows)
            return export_pdf('tushum', title, headers, rows)

        context = {
            'data': data, 'date_from': date_from, 'date_to': date_to,
            'method': method, 'received_by': received_by,
            'methods': Payment.Method.choices,
            'staff_options': User.objects.exclude(role=User.Role.ADMIN),
        }
        return render(request, self.template_name, context)


class GroupsReportView(AdminRequiredMixin, View):
    template_name = 'reports/groups.html'

    def get(self, request):
        group_id = request.GET.get('group') or None
        status = request.GET.get('status') or None
        rows = groups_report(group_id=group_id, status=status)

        fmt = request.GET.get('format')
        if fmt:
            headers = ['Guruh', 'Narx', 'Jami', "To'langan", 'Qarz', 'Foiz']
            export_rows = [
                [r['group'].name, r['price'], r['total_due'], r['total_paid'], r['total_debt'], f"{r['percent']}%"]
                for r in rows
            ]
            if fmt == 'xlsx':
                return export_xlsx('guruhlar', 'Guruhlar bo\'yicha hisobot', headers, export_rows)
            return export_pdf('guruhlar', 'Guruhlar bo\'yicha hisobot', headers, export_rows)

        context = {'rows': rows, 'group_id': group_id, 'status': status, 'groups': Group.objects.all()}
        return render(request, self.template_name, context)


class StaffReportView(AdminRequiredMixin, View):
    template_name = 'reports/staff.html'

    def get(self, request):
        role = request.GET.get('role') or None
        today = timezone.localdate()
        date_from = _parse_date(request.GET.get('date_from'), today.replace(day=1))
        date_to = _parse_date(request.GET.get('date_to'), today)
        rows = staff_report(role=role, date_from=date_from, date_to=date_to)

        fmt = request.GET.get('format')
        if fmt:
            headers = ['Hodim', 'Rol', "O'quvchilar", 'Undirgan', 'Qarz']
            export_rows = [
                [r['user'].full_name, r['user'].get_role_display(), r['students_count'], r['collected'], r['debt']]
                for r in rows
            ]
            title = f'Hodimlar bo\'yicha hisobot ({_fmt_date(date_from)} — {_fmt_date(date_to)})'
            if fmt == 'xlsx':
                return export_xlsx('hodimlar', title, headers, export_rows)
            return export_pdf('hodimlar', title, headers, export_rows)

        context = {'rows': rows, 'role': role, 'date_from': date_from, 'date_to': date_to}
        return render(request, self.template_name, context)


class DebtorsReportView(AdminRequiredMixin, View):
    template_name = 'reports/debtors.html'

    def get(self, request):
        group_id = request.GET.get('group') or None
        owner_id = request.GET.get('owner') or None
        min_days = request.GET.get('min_days')
        min_days = int(min_days) if min_days else None

        rows = debtors_report(group_id=group_id, owner_id=owner_id, min_overdue_days=min_days)

        fmt = request.GET.get('format')
        if fmt:
            headers = ["O'quvchi", 'Guruh', 'Qarz', 'Eng eski muddat', 'Kechikish (kun)', 'Egasi']
            export_rows = [
                [r['enrollment'].student.full_name, r['enrollment'].group.name, r['debt'],
                 _fmt_date(r['oldest_due_date']), r['overdue_days'], r['enrollment'].student.brought_by_user_id.full_name]
                for r in rows
            ]
            if fmt == 'xlsx':
                return export_xlsx('qarzdorlar', 'Qarzdorlar hisoboti', headers, export_rows)
            return export_pdf('qarzdorlar', 'Qarzdorlar hisoboti', headers, export_rows)

        context = {
            'rows': rows, 'group_id': group_id, 'owner_id': owner_id, 'min_days': min_days,
            'groups': Group.objects.all(), 'staff_options': User.objects.exclude(role=User.Role.ADMIN),
        }
        return render(request, self.template_name, context)


class UpcomingRevenueReportView(AdminRequiredMixin, View):
    template_name = 'reports/upcoming.html'

    def get(self, request):
        days = int(request.GET.get('days') or 30)
        data = upcoming_revenue_report(days=days)

        fmt = request.GET.get('format')
        if fmt:
            headers = ['Muddat', "O'quvchi", 'Guruh', 'Qolgan summa']
            export_rows = [
                [_fmt_date(i.due_date), i.enrollment.student.full_name, i.enrollment.group.name, i.remaining]
                for i in data['items']
            ]
            if fmt == 'xlsx':
                return export_xlsx('kutilayotgan', 'Kutilayotgan tushum', headers, export_rows)
            return export_pdf('kutilayotgan', 'Kutilayotgan tushum', headers, export_rows)

        return render(request, self.template_name, {'data': data, 'days': days})


class CashReportView(AdminRequiredMixin, View):
    template_name = 'reports/cash.html'

    def get(self, request):
        today = timezone.localdate()
        date_from = _parse_date(request.GET.get('date_from'), today.replace(day=1))
        date_to = _parse_date(request.GET.get('date_to'), today)
        data = cash_report(date_from, date_to)

        fmt = request.GET.get('format')
        if fmt:
            headers = ['Sana', 'Hodim', 'Tizim hisobi', "E'lon qilingan", 'Farq', 'Holat']
            export_rows = [
                [_fmt_date(c.date), c.user.full_name, c.expected_amount, c.declared_amount, c.difference, c.get_status_display()]
                for c in data['closings']
            ]
            title = f'Kassa hisoboti ({_fmt_date(date_from)} — {_fmt_date(date_to)})'
            if fmt == 'xlsx':
                return export_xlsx('kassa', title, headers, export_rows)
            return export_pdf('kassa', title, headers, export_rows)

        return render(request, self.template_name, {'data': data, 'date_from': date_from, 'date_to': date_to})


class ExamResultsReportView(AdminRequiredMixin, View):
    template_name = 'reports/exam_results.html'

    def get(self, request):
        from apps.exams.services import graduated_students_with_exam_summary

        rows = graduated_students_with_exam_summary()
        return render(request, self.template_name, {'rows': rows})
