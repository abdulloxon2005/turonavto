import uuid

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.core.mixins import AdminOrTeacherRequiredMixin, AdminRequiredMixin, AnyRoleRequiredMixin
from apps.students.services import visible_students_queryset

from .forms import (
    CancelPaymentForm,
    CashApproveForm,
    CashCloseForm,
    DiscountForm,
    EnrollmentForm,
    PaymentForm,
    RefundPaymentForm,
    ScheduleFormSet,
)
from .models import CashClosing, Enrollment, Payment
from .receipts import render_receipt_pdf
from .services import (
    apply_discount,
    approve_cash_closing,
    cancel_payment,
    can_collect_payment,
    close_cash_day,
    compute_expected_amount,
    create_enrollment,
    create_payment,
    debt_of,
    debtors_queryset,
    visible_cash_closings_queryset,
    enrollment_summary,
    refund_payment,
    set_schedule,
    visible_payments_queryset,
)


def _get_visible_student_or_404(user, pk):
    student = visible_students_queryset(user).filter(pk=pk).first()
    if student is None:
        raise Http404
    return student


def _get_visible_enrollment_or_404(user, pk):
    from .services import visible_enrollments_queryset

    enrollment = visible_enrollments_queryset(user).filter(pk=pk).select_related('student', 'group').first()
    if enrollment is None:
        raise Http404
    return enrollment


def _get_visible_payment_or_404(user, pk):
    payment = visible_payments_queryset(user).filter(pk=pk).select_related('student', 'enrollment__group').first()
    if payment is None:
        raise Http404
    return payment


class EnrollmentCreateView(AdminRequiredMixin, View):
    template_name = 'payments/enrollment_form.html'

    def get(self, request, student_id):
        student = get_object_or_404(visible_students_queryset(request.user), pk=student_id)
        form = EnrollmentForm(student=student)
        return render(request, self.template_name, {'form': form, 'student': student})

    def post(self, request, student_id):
        student = get_object_or_404(visible_students_queryset(request.user), pk=student_id)
        form = EnrollmentForm(request.POST, student=student)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'student': student})
        data = form.cleaned_data
        try:
            enrollment = create_enrollment(
                request.user, student=student, group=data['group'], price=data['price'],
                discount=data.get('discount') or 0, discount_reason=data.get('discount_reason', ''),
            )
        except (ValidationError, IntegrityError) as exc:
            messages.error(request, getattr(exc, 'message', "Bu o'quvchi shu guruhga allaqachon yozilgan"))
            return render(request, self.template_name, {'form': form, 'student': student})
        messages.success(request, 'Kursga yozildi')
        return redirect('students:detail', pk=student.pk)


class EnrollmentDetailView(AnyRoleRequiredMixin, View):
    template_name = 'payments/enrollment_detail.html'

    def get(self, request, pk):
        enrollment = _get_visible_enrollment_or_404(request.user, pk)
        summary = enrollment_summary(enrollment)
        context = {
            'enrollment': enrollment,
            'summary': summary,
            'schedule_items': enrollment.schedule_items.all(),
            'payments': enrollment.payments.order_by('-paid_at'),
            'can_collect': can_collect_payment(request.user, enrollment.student),
        }
        return render(request, self.template_name, context)


class EnrollmentScheduleView(AdminRequiredMixin, View):
    template_name = 'payments/schedule_form.html'

    def get(self, request, pk):
        enrollment = get_object_or_404(Enrollment, pk=pk)
        existing = [
            {'amount': i.amount, 'due_date': i.due_date} for i in enrollment.schedule_items.all()
        ]
        formset = ScheduleFormSet(initial=existing or None)
        return render(request, self.template_name, {'formset': formset, 'enrollment': enrollment})

    def post(self, request, pk):
        enrollment = get_object_or_404(Enrollment, pk=pk)
        formset = ScheduleFormSet(request.POST)
        if not formset.is_valid():
            return render(request, self.template_name, {'formset': formset, 'enrollment': enrollment})

        installments = []
        for form in formset:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue
            installments.append((form.cleaned_data['amount'], form.cleaned_data['due_date']))

        if not installments:
            messages.error(request, "Kamida bitta qism kiritilishi kerak")
            return render(request, self.template_name, {'formset': formset, 'enrollment': enrollment})

        try:
            set_schedule(request.user, enrollment, installments)
        except ValidationError as exc:
            messages.error(request, exc.message)
            return render(request, self.template_name, {'formset': formset, 'enrollment': enrollment})

        messages.success(request, "To'lov grafigi saqlandi")
        return redirect('payments:enrollment_detail', pk=enrollment.pk)


class EnrollmentDiscountView(AdminRequiredMixin, View):
    template_name = 'payments/discount_form.html'

    def get(self, request, pk):
        enrollment = get_object_or_404(Enrollment, pk=pk)
        form = DiscountForm(initial={'discount': enrollment.discount, 'discount_reason': enrollment.discount_reason})
        return render(request, self.template_name, {'form': form, 'enrollment': enrollment})

    def post(self, request, pk):
        enrollment = get_object_or_404(Enrollment, pk=pk)
        form = DiscountForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'enrollment': enrollment})
        try:
            apply_discount(request.user, enrollment, form.cleaned_data['discount'], form.cleaned_data['discount_reason'])
        except ValidationError as exc:
            messages.error(request, exc.message)
            return render(request, self.template_name, {'form': form, 'enrollment': enrollment})
        messages.success(request, 'Chegirma qo\'llandi')
        return redirect('payments:enrollment_detail', pk=enrollment.pk)


class PaymentCreateView(AnyRoleRequiredMixin, View):
    template_name = 'payments/payment_form.html'

    def _enrollment_choices(self, student):
        choices = []
        for enrollment in student.enrollments.all():
            debt = debt_of(enrollment)
            if debt > 0:
                choices.append((enrollment.pk, f'{enrollment.group.name} — qarz: {debt:,} so\'m'.replace(',', ' ')))
        return choices

    def get(self, request, student_id):
        student = _get_visible_student_or_404(request.user, student_id)
        if not can_collect_payment(request.user, student):
            raise PermissionDenied("Faqat o'quvchining egasi yoki admin to'lov kirita oladi")
        choices = self._enrollment_choices(student)
        if not choices:
            messages.info(request, "Bu o'quvchining qarzi yo'q yoki hali kursga yozilmagan")
            return redirect('students:detail', pk=student.pk)
        form = PaymentForm(enrollment_choices=choices)
        token = uuid.uuid4().hex
        return render(request, self.template_name, {'form': form, 'student': student, 'idempotency_key': token})

    def post(self, request, student_id):
        student = _get_visible_student_or_404(request.user, student_id)
        if not can_collect_payment(request.user, student):
            raise PermissionDenied("Faqat o'quvchining egasi yoki admin to'lov kirita oladi")
        choices = self._enrollment_choices(student)
        form = PaymentForm(request.POST, enrollment_choices=choices)
        idempotency_key = request.POST.get('idempotency_key') or uuid.uuid4().hex
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'student': student, 'idempotency_key': idempotency_key})

        enrollment = get_object_or_404(Enrollment, pk=form.cleaned_data['enrollment'], student=student)
        try:
            payment, created = create_payment(
                request.user, student=student, enrollment=enrollment,
                amount=form.cleaned_data['amount'], method=form.cleaned_data['method'],
                note=form.cleaned_data.get('note', ''), idempotency_key=idempotency_key,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, getattr(exc, 'message', str(exc)))
            return render(request, self.template_name, {'form': form, 'student': student, 'idempotency_key': idempotency_key})

        if created:
            messages.success(request, f"To'lov qabul qilindi. Chek: {payment.receipt_no}")
        else:
            messages.info(request, "Bu to'lov allaqachon qayd etilgan")
        return redirect('payments:detail', pk=payment.pk)


class PaymentDetailView(AnyRoleRequiredMixin, View):
    template_name = 'payments/payment_detail.html'

    def get(self, request, pk):
        payment = _get_visible_payment_or_404(request.user, pk)
        return render(request, self.template_name, {'payment': payment})


class PaymentReceiptView(AnyRoleRequiredMixin, View):
    def get(self, request, pk):
        payment = _get_visible_payment_or_404(request.user, pk)
        pdf_bytes = render_receipt_pdf(payment)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="chek-{payment.receipt_no}.pdf"'
        return response


class PaymentCancelView(AdminRequiredMixin, View):
    template_name = 'payments/cancel_form.html'

    def get(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        return render(request, self.template_name, {'form': CancelPaymentForm(), 'payment': payment})

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        form = CancelPaymentForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'payment': payment})
        try:
            cancel_payment(request.user, payment, form.cleaned_data['reason'])
        except ValidationError as exc:
            messages.error(request, exc.message)
            return render(request, self.template_name, {'form': form, 'payment': payment})
        messages.success(request, "To'lov bekor qilindi")
        return redirect('payments:detail', pk=payment.pk)


class PaymentRefundView(AdminRequiredMixin, View):
    template_name = 'payments/refund_form.html'

    def get(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        return render(request, self.template_name, {'form': RefundPaymentForm(initial={'amount': payment.amount}), 'payment': payment})

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        form = RefundPaymentForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'payment': payment})
        try:
            refund = refund_payment(request.user, payment, form.cleaned_data['amount'], form.cleaned_data.get('note', ''))
        except ValidationError as exc:
            messages.error(request, exc.message)
            return render(request, self.template_name, {'form': form, 'payment': payment})
        messages.success(request, "Pul qaytarildi")
        return redirect('payments:detail', pk=refund.pk)


class DebtorsListView(AdminOrTeacherRequiredMixin, View):
    template_name = 'payments/debtors_list.html'

    def get(self, request):
        debtors = debtors_queryset(request.user)
        debtors.sort(key=lambda s: s['debt'], reverse=True)
        return render(request, self.template_name, {'debtors': debtors})


class CashClosingListView(AdminRequiredMixin, View):
    template_name = 'payments/cash_list.html'

    def get(self, request):
        closings = visible_cash_closings_queryset(request.user).select_related('user')
        today_closed = closings.filter(user=request.user, date=timezone.localdate()).exists()
        return render(request, self.template_name, {
            'closings': closings,
            'today_closed': today_closed,
            'today_expected': compute_expected_amount(request.user, timezone.localdate()),
        })


class CashClosingCreateView(AdminRequiredMixin, View):
    template_name = 'payments/cash_form.html'

    def get(self, request):
        today = timezone.localdate()
        if CashClosing.objects.filter(user=request.user, date=today).exists():
            messages.info(request, 'Bugungi kassa allaqachon yopilgan')
            return redirect('payments:cash_list')
        expected = compute_expected_amount(request.user, today)
        form = CashCloseForm(initial={'declared_amount': expected})
        return render(request, self.template_name, {'form': form, 'expected': expected})

    def post(self, request):
        form = CashCloseForm(request.POST)
        expected = compute_expected_amount(request.user, timezone.localdate())
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'expected': expected})
        try:
            closing = close_cash_day(request.user, form.cleaned_data['declared_amount'])
        except ValidationError as exc:
            messages.error(request, exc.message)
            return render(request, self.template_name, {'form': form, 'expected': expected})
        messages.success(request, 'Kassa yopildi va adminga yuborildi')
        return redirect('payments:cash_detail', pk=closing.pk)


class CashClosingDetailView(AdminRequiredMixin, View):
    template_name = 'payments/cash_detail.html'

    def get(self, request, pk):
        closing = get_object_or_404(visible_cash_closings_queryset(request.user), pk=pk)
        return render(request, self.template_name, {'closing': closing, 'form': CashApproveForm()})


class CashClosingApproveView(AdminRequiredMixin, View):
    def post(self, request, pk):
        closing = get_object_or_404(CashClosing, pk=pk)
        form = CashApproveForm(request.POST)
        note = form.data.get('note', '') if form.is_valid() else ''
        try:
            approve_cash_closing(request.user, closing, note)
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, 'Kassa tasdiqlandi')
        return redirect('payments:cash_detail', pk=pk)
