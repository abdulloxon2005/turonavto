from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.services import log_action

from .models import CashClosing, Enrollment, Payment, PaymentSchedule


def visible_enrollments_queryset(user):
    from django.db.models import Q

    if user.is_admin():
        return Enrollment.objects.all()
    if user.is_teacher():
        return Enrollment.objects.filter(
            Q(student__brought_by_user_id=user) | Q(group__group_teachers__user=user)
        ).distinct()
    if user.is_instructor():
        return Enrollment.objects.filter(
            Q(student__brought_by_user_id=user)
            | Q(student__instructor_links__instructor=user)
            | Q(group__group_instructors__user=user)
        ).distinct()
    return Enrollment.objects.filter(student__brought_by_user_id=user)


def visible_payments_queryset(user):
    if user.is_admin():
        return Payment.objects.all()
    return Payment.objects.filter(student__brought_by_user_id=user)


def can_collect_payment(user, student):
    return user.is_admin() or student.brought_by_user_id_id == user.id


def paid_sum(enrollment):
    total = enrollment.payments.filter(status=Payment.Status.CONFIRMED).aggregate(s=Sum('amount'))['s']
    return total or 0


def debt_of(enrollment):
    return max(enrollment.total_due - paid_sum(enrollment), 0)


def compute_status(enrollment):
    paid = paid_sum(enrollment)
    debt = enrollment.total_due - paid
    if debt <= 0:
        return PaymentSchedule.Status.PAID
    if enrollment.schedule_items.filter(status=PaymentSchedule.Status.OVERDUE).exists():
        return PaymentSchedule.Status.OVERDUE
    if paid > 0:
        return PaymentSchedule.Status.PARTIAL
    return PaymentSchedule.Status.UNPAID


def next_due_date(enrollment):
    item = enrollment.schedule_items.exclude(status=PaymentSchedule.Status.PAID).order_by('due_date').first()
    return item.due_date if item else None


def enrollment_summary(enrollment):
    paid = paid_sum(enrollment)
    debt = max(enrollment.total_due - paid, 0)
    return {
        'enrollment': enrollment,
        'total_due': enrollment.total_due,
        'paid': paid,
        'debt': debt,
        'status': compute_status(enrollment),
        'next_due_date': next_due_date(enrollment),
    }


def student_debt_summary(student):
    """Bir o'quvchining barcha enrollmentlari bo'yicha jamlangan qarz ma'lumoti."""

    enrollments = list(student.enrollments.all())
    summaries = [enrollment_summary(e) for e in enrollments]
    total_debt = sum(s['debt'] for s in summaries)
    statuses = [s['status'] for s in summaries]
    if not summaries:
        overall_status = None
    elif PaymentSchedule.Status.OVERDUE in statuses:
        overall_status = PaymentSchedule.Status.OVERDUE
    elif all(s == PaymentSchedule.Status.PAID for s in statuses):
        overall_status = PaymentSchedule.Status.PAID
    elif any(s in (PaymentSchedule.Status.PARTIAL, PaymentSchedule.Status.PAID) for s in statuses):
        overall_status = PaymentSchedule.Status.PARTIAL
    else:
        overall_status = PaymentSchedule.Status.UNPAID
    return {'enrollments': summaries, 'total_debt': total_debt, 'status': overall_status}


@transaction.atomic
def create_enrollment(actor, *, student, group, price, discount=0, discount_reason=''):
    if discount and not discount_reason:
        raise ValidationError("Chegirma sababi ko'rsatilishi shart")
    total_due = max(price - discount, 0)
    enrollment = Enrollment.objects.create(
        student=student, group=group, price=price, discount=discount,
        discount_reason=discount_reason, total_due=total_due, created_by=actor,
    )
    log_action(
        actor, action='enrollment.create', entity_type='Enrollment', entity_id=enrollment.pk,
        new_value={'student_id': student.pk, 'group_id': group.pk, 'price': price, 'discount': discount},
    )
    return enrollment


@transaction.atomic
def apply_discount(actor, enrollment, discount, reason):
    if not reason:
        raise ValidationError("Chegirma sababi ko'rsatilishi shart")
    if discount >= enrollment.price:
        raise ValidationError("Chegirma kurs narxidan kichik bo'lishi kerak")
    already_paid = paid_sum(enrollment)
    new_total_due = enrollment.price - discount
    if new_total_due < already_paid:
        raise ValidationError("Chegirma allaqachon to'langan summadan ko'p qarzni kamaytira olmaydi")

    old_value = {'discount': enrollment.discount, 'total_due': enrollment.total_due}
    enrollment.discount = discount
    enrollment.discount_reason = reason
    enrollment.total_due = new_total_due
    enrollment.save(update_fields=['discount', 'discount_reason', 'total_due'])

    log_action(
        actor, action='enrollment.discount', entity_type='Enrollment', entity_id=enrollment.pk,
        old_value=old_value, new_value={'discount': discount, 'total_due': new_total_due, 'reason': reason},
    )
    return enrollment


@transaction.atomic
def set_schedule(actor, enrollment, installments):
    """installments: [(amount, due_date), ...]. Yig'indisi total_due ga teng bo'lishi shart."""

    total = sum(amount for amount, _ in installments)
    if total != enrollment.total_due:
        raise ValidationError(
            f"Grafik summalari yig'indisi ({total}) jami to'lov summasiga ({enrollment.total_due}) teng emas"
        )
    enrollment.schedule_items.all().delete()
    for amount, due_date in installments:
        PaymentSchedule.objects.create(enrollment=enrollment, amount=amount, due_date=due_date)

    _reallocate_schedule(enrollment)

    log_action(
        actor, action='enrollment.set_schedule', entity_type='Enrollment', entity_id=enrollment.pk,
        new_value={'installments': [[a, d.isoformat()] for a, d in installments]},
    )
    return enrollment


def _reallocate_schedule(enrollment):
    """Tasdiqlangan to'lovlarni eng eski muddatdan boshlab grafik qismlariga taqsimlaydi."""

    items = list(enrollment.schedule_items.order_by('due_date'))
    if not items:
        return
    remaining = paid_sum(enrollment)
    today = timezone.localdate()
    for item in items:
        allocated = min(remaining, item.amount)
        remaining -= allocated
        item.paid_amount = allocated
        if allocated >= item.amount:
            item.status = PaymentSchedule.Status.PAID
        elif item.due_date < today and allocated < item.amount:
            item.status = PaymentSchedule.Status.OVERDUE
        elif allocated > 0:
            item.status = PaymentSchedule.Status.PARTIAL
        else:
            item.status = PaymentSchedule.Status.UNPAID
        item.save(update_fields=['paid_amount', 'status'])


def generate_receipt_no():
    year = timezone.localdate().year
    count = Payment.objects.filter(paid_at__year=year).count()
    return f'{year}-{count + 1:06d}'


@transaction.atomic
def create_payment(actor, *, student, enrollment, amount, method, paid_at=None, note='', idempotency_key=None):
    if idempotency_key:
        existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing, False

    if not can_collect_payment(actor, student):
        raise PermissionDenied("Faqat o'quvchining egasi yoki admin to'lov kirita oladi")
    if enrollment.student_id != student.id:
        raise ValidationError("Enrollment bu o'quvchiga tegishli emas")
    if amount <= 0:
        raise ValidationError("Summa noldan katta bo'lishi kerak")
    if student.status != student.Status.ACTIVE:
        raise ValidationError("Arxivlangan o'quvchi uchun to'lov kiritib bo'lmaydi")
    if not actor.is_admin() and is_cash_day_closed(actor):
        raise ValidationError("Bugungi kassa kuni yopilgan, to'lov kirita olmaysiz")

    enrollment = Enrollment.objects.select_for_update().get(pk=enrollment.pk)
    current_debt = debt_of(enrollment)
    if amount > current_debt:
        raise ValidationError(f"Summa qolgan qarzdan ({current_debt}) oshmasligi kerak")

    for attempt in range(5):
        receipt_no = generate_receipt_no()
        try:
            with transaction.atomic():
                payment = Payment.objects.create(
                    enrollment=enrollment,
                    student=student,
                    amount=amount,
                    method=method,
                    received_by_user_id=actor,
                    paid_at=paid_at or timezone.now(),
                    receipt_no=receipt_no,
                    note=note,
                    idempotency_key=idempotency_key or None,
                )
            break
        except IntegrityError:
            if attempt == 4:
                raise
            continue

    _reallocate_schedule(enrollment)

    log_action(
        actor, action='payment.create', entity_type='Payment', entity_id=payment.pk,
        new_value={'student_id': student.pk, 'amount': amount, 'method': method, 'receipt_no': receipt_no},
    )
    return payment, True


@transaction.atomic
def cancel_payment(actor, payment, reason):
    if payment.status == Payment.Status.CANCELLED:
        raise ValidationError('Bu to\'lov allaqachon bekor qilingan')
    if not reason:
        raise ValidationError('Bekor qilish sababi ko\'rsatilishi shart')
    if payment.refunds.filter(status=Payment.Status.CONFIRMED).exists():
        raise ValidationError(
            "Bu to'lov bo'yicha qaytarish amalga oshirilgan, avval uni bekor qilib bo'lmaydi"
        )

    payment.status = Payment.Status.CANCELLED
    payment.cancel_reason = reason
    payment.cancelled_by = actor
    payment.cancelled_at = timezone.now()
    payment.save(update_fields=['status', 'cancel_reason', 'cancelled_by', 'cancelled_at'])

    _reallocate_schedule(payment.enrollment)

    log_action(
        actor, action='payment.cancel', entity_type='Payment', entity_id=payment.pk,
        new_value={'reason': reason},
    )
    return payment


@transaction.atomic
def refund_payment(actor, payment, amount, note=''):
    if payment.status != Payment.Status.CONFIRMED:
        raise ValidationError("Faqat tasdiqlangan to'lovni qaytarish mumkin")
    already_refunded = payment.refunds.filter(status=Payment.Status.CONFIRMED).aggregate(
        s=Sum('amount')
    )['s'] or 0
    refundable = payment.amount + already_refunded  # already_refunded manfiy saqlanadi
    if amount <= 0 or amount > refundable:
        raise ValidationError("Qaytarish summasi noto'g'ri")

    receipt_no = None
    for attempt in range(5):
        receipt_no = generate_receipt_no()
        try:
            with transaction.atomic():
                refund = Payment.objects.create(
                    enrollment=payment.enrollment,
                    student=payment.student,
                    amount=-amount,
                    method=payment.method,
                    received_by_user_id=actor,
                    paid_at=timezone.now(),
                    receipt_no=receipt_no,
                    note=note,
                    is_refund=True,
                    refund_of=payment,
                )
            break
        except IntegrityError:
            if attempt == 4:
                raise
            continue

    _reallocate_schedule(payment.enrollment)

    log_action(
        actor, action='payment.refund', entity_type='Payment', entity_id=payment.pk,
        new_value={'refund_payment_id': refund.pk, 'amount': amount},
    )
    return refund


def debtors_queryset(user):
    """Qarzdor o'quvchilar ro'yxati (enrollment darajasida)."""

    enrollments = visible_enrollments_queryset(user).select_related('student', 'group')
    result = []
    for enrollment in enrollments:
        summary = enrollment_summary(enrollment)
        if summary['debt'] > 0:
            result.append(summary)
    return result


# --- Kassa yopish (9.8-bo'lim) ---

def visible_cash_closings_queryset(user):
    if user.is_admin():
        return CashClosing.objects.all()
    return CashClosing.objects.filter(user=user)


def compute_expected_amount(user, day):
    total = Payment.objects.filter(
        received_by_user_id=user, paid_at__date=day, status=Payment.Status.CONFIRMED,
    ).aggregate(s=Sum('amount'))['s']
    return total or 0


def is_cash_day_closed(user, day=None):
    day = day or timezone.localdate()
    return CashClosing.objects.filter(user=user, date=day).exists()


@transaction.atomic
def close_cash_day(actor, declared_amount, day=None):
    day = day or timezone.localdate()
    if CashClosing.objects.filter(user=actor, date=day).exists():
        raise ValidationError('Bugungi kassa allaqachon yopilgan')

    expected_amount = compute_expected_amount(actor, day)
    try:
        closing = CashClosing.objects.create(
            user=actor, date=day, expected_amount=expected_amount, declared_amount=declared_amount,
        )
    except IntegrityError:
        raise ValidationError('Bugungi kassa allaqachon yopilgan')

    log_action(
        actor, action='cash_closing.create', entity_type='CashClosing', entity_id=closing.pk,
        new_value={'expected': expected_amount, 'declared': declared_amount},
    )

    from apps.accounts.models import User
    from apps.notifications.services import notify

    for admin in User.objects.filter(role=User.Role.ADMIN, is_active=True):
        notify(
            admin, type='cash_closing', title='Kassa yopishga yuborildi',
            body=f'{actor.full_name} — {day}: {declared_amount} so\'m',
            link=f'/tolovlar/kassa/{closing.pk}/',
        )
        if closing.difference != 0:
            notify(
                admin, type='cash_mismatch', title='Kassada farq aniqlandi',
                body=f'{actor.full_name} — {day}: farq {closing.difference} so\'m',
                link=f'/tolovlar/kassa/{closing.pk}/',
            )
    return closing


@transaction.atomic
def approve_cash_closing(actor, closing, note=''):
    if closing.status == CashClosing.Status.APPROVED:
        raise ValidationError('Allaqachon tasdiqlangan')
    if closing.difference != 0 and not note:
        raise ValidationError("Farq mavjud, izoh kiritilishi shart")

    closing.status = CashClosing.Status.APPROVED
    closing.approved_by = actor
    closing.approve_note = note
    closing.approved_at = timezone.now()
    closing.save(update_fields=['status', 'approved_by', 'approve_note', 'approved_at'])

    log_action(
        actor, action='cash_closing.approve', entity_type='CashClosing', entity_id=closing.pk,
        new_value={'note': note},
    )
    return closing
