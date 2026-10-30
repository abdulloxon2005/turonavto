import datetime

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from apps.payments.jobs import mark_overdue_schedules
from apps.payments.models import CashClosing, Payment, PaymentSchedule
from apps.payments.services import (
    apply_discount,
    cancel_payment,
    close_cash_day,
    create_payment,
    debt_of,
    is_cash_day_closed,
    refund_payment,
    set_schedule,
)


# --- Qarz formulasi: Qarz = narx - chegirma - tasdiqlangan to'lovlar ---
# (bekor qilingan to'lovlar hisobga olinmaydi; qaytarish qarzni oshiradi)

@pytest.mark.django_db
@pytest.mark.parametrize('price, discount, payments, expected_debt', [
    (3_000_000, 0, [], 3_000_000),
    (3_000_000, 0, [1_000_000], 2_000_000),
    (3_000_000, 0, [1_000_000, 2_000_000], 0),
    (3_000_000, 500_000, [], 2_500_000),
    (3_000_000, 500_000, [2_500_000], 0),
    (3_000_000, 1_000_000, [1_000_000, 500_000], 500_000),
    (2_000_000, 0, [2_000_000], 0),
    (5_000_000, 1_000_000, [1_000_000, 1_000_000, 1_000_000], 1_000_000),
    (1_000_000, 0, [250_000, 250_000, 250_000, 250_000], 0),
    (4_000_000, 2_000_000, [], 2_000_000),
])
def test_debt_formula_scenarios(admin_user, student, group, price, discount, payments, expected_debt):
    from apps.payments.models import Enrollment

    enrollment = Enrollment.objects.create(
        student=student, group=group, price=price, discount=discount,
        total_due=price - discount, created_by=admin_user,
    )
    for amount in payments:
        create_payment(admin_user, student=student, enrollment=enrollment, amount=amount, method='cash')

    assert debt_of(enrollment) == expected_debt


@pytest.mark.django_db
def test_cancelled_payment_excluded_from_debt(admin_user, student, enrollment):
    payment, _ = create_payment(admin_user, student=student, enrollment=enrollment, amount=1_000_000, method='cash')
    assert debt_of(enrollment) == 2_000_000

    cancel_payment(admin_user, payment, 'Xato kiritildi')
    assert debt_of(enrollment) == 3_000_000
    payment.refresh_from_db()
    assert payment.status == Payment.Status.CANCELLED
    assert payment.cancel_reason == 'Xato kiritildi'
    assert payment.cancelled_by == admin_user
    # To'lov o'chirilmaydi, faqat bekor qilinadi
    assert Payment.objects.filter(pk=payment.pk).exists()


@pytest.mark.django_db
def test_refund_creates_separate_negative_record(admin_user, student, enrollment):
    payment, _ = create_payment(admin_user, student=student, enrollment=enrollment, amount=2_000_000, method='cash')
    refund = refund_payment(admin_user, payment, 500_000)

    assert refund.amount == -500_000
    assert refund.is_refund is True
    assert refund.refund_of == payment
    assert debt_of(enrollment) == 1_500_000
    # Asl to'lov o'zgarmaydi
    payment.refresh_from_db()
    assert payment.amount == 2_000_000
    assert payment.status == Payment.Status.CONFIRMED


@pytest.mark.django_db
def test_refund_cannot_exceed_remaining_refundable_amount(admin_user, student, enrollment):
    payment, _ = create_payment(admin_user, student=student, enrollment=enrollment, amount=1_000_000, method='cash')
    refund_payment(admin_user, payment, 600_000)

    # Birinchi qaytarishdan keyin faqat 400_000 qoladi — undan ko'pini qaytarib bo'lmaydi
    with pytest.raises(ValidationError):
        refund_payment(admin_user, payment, 600_000)

    # Qolgan summani aniq qaytarish esa ishlashi kerak
    second_refund = refund_payment(admin_user, payment, 400_000)
    assert second_refund.amount == -400_000
    assert debt_of(enrollment) == 3_000_000


@pytest.mark.django_db
def test_cannot_cancel_payment_with_confirmed_refund(admin_user, student, enrollment):
    payment, _ = create_payment(admin_user, student=student, enrollment=enrollment, amount=1_000_000, method='cash')
    refund_payment(admin_user, payment, 400_000)

    with pytest.raises(ValidationError):
        cancel_payment(admin_user, payment, "Xato kiritildi")

    payment.refresh_from_db()
    assert payment.status == Payment.Status.CONFIRMED


@pytest.mark.django_db
def test_overpayment_rejected(admin_user, student, enrollment):
    with pytest.raises(ValidationError):
        create_payment(admin_user, student=student, enrollment=enrollment, amount=5_000_000, method='cash')


@pytest.mark.django_db
def test_zero_or_negative_amount_rejected(admin_user, student, enrollment):
    with pytest.raises(ValidationError):
        create_payment(admin_user, student=student, enrollment=enrollment, amount=0, method='cash')


# --- Idempotentlik ---

@pytest.mark.django_db
def test_idempotency_key_prevents_duplicate_payment(admin_user, student, enrollment):
    key = 'test-idem-key-1'
    payment1, created1 = create_payment(
        admin_user, student=student, enrollment=enrollment, amount=1_000_000, method='cash',
        idempotency_key=key,
    )
    payment2, created2 = create_payment(
        admin_user, student=student, enrollment=enrollment, amount=1_000_000, method='cash',
        idempotency_key=key,
    )
    assert created1 is True
    assert created2 is False
    assert payment1.pk == payment2.pk
    assert Payment.objects.filter(enrollment=enrollment).count() == 1
    assert debt_of(enrollment) == 2_000_000


# --- Chek raqami ---

@pytest.mark.django_db
def test_receipt_number_unique_and_formatted(admin_user, student, enrollment):
    p1, _ = create_payment(admin_user, student=student, enrollment=enrollment, amount=500_000, method='cash')
    p2, _ = create_payment(admin_user, student=student, enrollment=enrollment, amount=500_000, method='cash')
    assert p1.receipt_no != p2.receipt_no
    year = datetime.date.today().year
    assert p1.receipt_no.startswith(f'{year}-')
    assert len(p1.receipt_no.split('-')[1]) == 6


# --- Egalik qoidasi: faqat egasi yoki admin to'lov kirita oladi ---

@pytest.mark.django_db
def test_other_teacher_cannot_collect_payment(other_teacher_user, student, enrollment):
    with pytest.raises(PermissionDenied):
        create_payment(
            other_teacher_user, student=student, enrollment=enrollment, amount=100_000, method='cash',
        )


@pytest.mark.django_db
def test_owner_teacher_can_collect_payment(teacher_user, student, enrollment):
    payment, created = create_payment(
        teacher_user, student=student, enrollment=enrollment, amount=100_000, method='cash',
    )
    assert created is True
    assert payment.received_by_user_id == teacher_user


# --- Chegirma ---

@pytest.mark.django_db
def test_discount_requires_reason(admin_user, enrollment):
    with pytest.raises(ValidationError):
        apply_discount(admin_user, enrollment, 100_000, '')


@pytest.mark.django_db
def test_discount_cannot_undercut_already_paid(admin_user, student, enrollment):
    create_payment(admin_user, student=student, enrollment=enrollment, amount=2_000_000, method='cash')
    with pytest.raises(ValidationError):
        apply_discount(admin_user, enrollment, 2_500_000, 'Katta chegirma')


# --- Bo'lib to'lash grafigi ---

@pytest.mark.django_db
def test_schedule_sum_must_match_total_due(admin_user, enrollment):
    with pytest.raises(ValidationError):
        set_schedule(admin_user, enrollment, [(1_000_000, datetime.date(2026, 2, 1))])


@pytest.mark.django_db
def test_schedule_allocation_oldest_first(admin_user, student, enrollment):
    from django.utils import timezone

    today = timezone.localdate()
    set_schedule(admin_user, enrollment, [
        (1_000_000, today + datetime.timedelta(days=10)),
        (2_000_000, today + datetime.timedelta(days=40)),
    ])
    create_payment(admin_user, student=student, enrollment=enrollment, amount=1_500_000, method='cash')

    first, second = enrollment.schedule_items.order_by('due_date')
    assert first.paid_amount == 1_000_000
    assert first.status == PaymentSchedule.Status.PAID
    assert second.paid_amount == 500_000
    assert second.status == PaymentSchedule.Status.PARTIAL


# --- Muddati o'tganlarni avtomatik belgilash (fon vazifasi) ---

@pytest.mark.django_db
def test_schedule_is_marked_overdue_immediately_when_past_due(admin_user, enrollment):
    """To'lov kirmagan holda ham, grafik qismi o'tmishdagi muddat bilan yaratilsa,
    taqsimlash (_reallocate_schedule) uni darhol overdue deb belgilaydi."""

    set_schedule(admin_user, enrollment, [
        (3_000_000, datetime.date(2020, 1, 1)),
    ])
    item = enrollment.schedule_items.first()
    assert item.status == PaymentSchedule.Status.OVERDUE


@pytest.mark.django_db
def test_overdue_job_marks_schedule_left_in_unpaid_state(admin_user, enrollment):
    """Fon vazifasi (mark_overdue_schedules) hali UNPAID/PARTIAL holatda qolgan,
    lekin muddati o'tgan qismlarni ham to'g'ri belgilaydi (masalan, boshqa sabablarga
    ko'ra qayta hisoblanmagan eski yozuvlar)."""

    item = PaymentSchedule.objects.create(
        enrollment=enrollment, amount=3_000_000, due_date=datetime.date(2020, 1, 1),
    )
    assert item.status == PaymentSchedule.Status.UNPAID

    count = mark_overdue_schedules()
    assert count == 1
    item.refresh_from_db()
    assert item.status == PaymentSchedule.Status.OVERDUE


# --- Kassa yopish ---

@pytest.mark.django_db
def test_cash_day_closing_blocks_further_payments(admin_user, teacher_user, student, enrollment):
    create_payment(teacher_user, student=student, enrollment=enrollment, amount=500_000, method='cash')
    close_cash_day(teacher_user, declared_amount=500_000)

    assert is_cash_day_closed(teacher_user) is True
    with pytest.raises(ValidationError):
        create_payment(teacher_user, student=student, enrollment=enrollment, amount=100_000, method='cash')


@pytest.mark.django_db
def test_cash_closing_computes_expected_from_confirmed_payments(admin_user, teacher_user, student, enrollment):
    create_payment(teacher_user, student=student, enrollment=enrollment, amount=500_000, method='cash')
    closing = close_cash_day(teacher_user, declared_amount=500_000)
    assert closing.expected_amount == 500_000
    assert closing.difference == 0
    assert closing.status == CashClosing.Status.PENDING


@pytest.mark.django_db
def test_cash_closing_cannot_be_duplicated_same_day(teacher_user):
    close_cash_day(teacher_user, declared_amount=0)
    with pytest.raises(ValidationError):
        close_cash_day(teacher_user, declared_amount=0)


@pytest.mark.django_db
def test_approve_cash_closing_requires_note_on_mismatch(admin_user, teacher_user):
    from apps.payments.services import approve_cash_closing

    closing = close_cash_day(teacher_user, declared_amount=100_000)  # expected=0, farq bor
    with pytest.raises(ValidationError):
        approve_cash_closing(admin_user, closing, note='')

    approved = approve_cash_closing(admin_user, closing, note='Tekshirildi')
    assert approved.status == CashClosing.Status.APPROVED
    assert approved.approved_by == admin_user


@pytest.mark.django_db
def test_approve_cash_closing_no_note_required_without_mismatch(admin_user, teacher_user):
    from apps.payments.services import approve_cash_closing

    closing = close_cash_day(teacher_user, declared_amount=0)  # expected=0, farq yo'q
    approved = approve_cash_closing(admin_user, closing)
    assert approved.status == CashClosing.Status.APPROVED


@pytest.mark.django_db
def test_cannot_approve_already_approved_closing(admin_user, teacher_user):
    from apps.payments.services import approve_cash_closing

    closing = close_cash_day(teacher_user, declared_amount=0)
    approve_cash_closing(admin_user, closing)
    with pytest.raises(ValidationError):
        approve_cash_closing(admin_user, closing)


# --- Ko'rinish (visibility) qoidalari ---

@pytest.mark.django_db
def test_admin_sees_all_payments(admin_user, teacher_user, other_teacher_user, student, enrollment):
    from apps.payments.services import visible_payments_queryset

    create_payment(teacher_user, student=student, enrollment=enrollment, amount=100_000, method='cash')
    assert visible_payments_queryset(admin_user).count() == 1
    assert visible_payments_queryset(teacher_user).count() == 1
    assert visible_payments_queryset(other_teacher_user).count() == 0


@pytest.mark.django_db
def test_debtors_queryset_scoped_to_owner(admin_user, teacher_user, other_teacher_user, enrollment):
    from apps.payments.services import debtors_queryset

    assert len(debtors_queryset(teacher_user)) == 1
    assert len(debtors_queryset(other_teacher_user)) == 0
    assert len(debtors_queryset(admin_user)) == 1


# --- Holat hisoblash: unpaid / partial / paid / overdue ---

@pytest.mark.django_db
def test_compute_status_transitions(admin_user, student, enrollment):
    from apps.payments.services import compute_status

    assert compute_status(enrollment) == PaymentSchedule.Status.UNPAID

    create_payment(admin_user, student=student, enrollment=enrollment, amount=1_000_000, method='cash')
    assert compute_status(enrollment) == PaymentSchedule.Status.PARTIAL

    create_payment(admin_user, student=student, enrollment=enrollment, amount=2_000_000, method='cash')
    assert compute_status(enrollment) == PaymentSchedule.Status.PAID


@pytest.mark.django_db
def test_student_debt_summary_aggregates_enrollments(admin_user, student, enrollment):
    from apps.payments.services import student_debt_summary

    summary = student_debt_summary(student)
    assert summary['total_debt'] == 3_000_000
    assert summary['status'] == PaymentSchedule.Status.UNPAID
    assert len(summary['enrollments']) == 1
