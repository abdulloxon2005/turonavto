import datetime

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.expenses.models import Expense
from apps.expenses.services import create_expense, expenses_queryset, monthly_totals, total_amount


@pytest.mark.django_db
def test_create_expense_logs_and_saves(admin_user, teacher_user):
    expense = create_expense(
        admin_user, category=Expense.Category.SALARY, amount=500_000,
        expense_date=datetime.date(2026, 1, 15), description="Yanvar oyligi",
        paid_to_user=teacher_user,
    )
    assert expense.pk is not None
    assert expense.amount == 500_000
    assert expense.paid_to_user == teacher_user
    assert expense.paid_to_name == ''


@pytest.mark.django_db
def test_create_expense_rejects_non_positive_amount(admin_user):
    with pytest.raises(ValidationError):
        create_expense(
            admin_user, category=Expense.Category.OTHER, amount=0,
            expense_date=datetime.date.today(), description="Noto'g'ri",
        )


@pytest.mark.django_db
def test_create_expense_requires_description(admin_user):
    with pytest.raises(ValidationError):
        create_expense(
            admin_user, category=Expense.Category.OTHER, amount=1000,
            expense_date=datetime.date.today(), description="",
        )


@pytest.mark.django_db
def test_expenses_queryset_filters_by_category_and_date(admin_user, teacher_user):
    create_expense(
        admin_user, category=Expense.Category.SALARY, amount=500_000,
        expense_date=datetime.date(2026, 1, 10), description="Oylik", paid_to_user=teacher_user,
    )
    create_expense(
        admin_user, category=Expense.Category.RENT, amount=1_000_000,
        expense_date=datetime.date(2026, 2, 10), description="Ijara",
    )

    salary_only = expenses_queryset(category=Expense.Category.SALARY)
    assert salary_only.count() == 1

    jan_only = expenses_queryset(date_from=datetime.date(2026, 1, 1), date_to=datetime.date(2026, 1, 31))
    assert jan_only.count() == 1
    assert total_amount(jan_only) == 500_000


@pytest.mark.django_db
def test_monthly_totals_returns_requested_number_of_months():
    totals = monthly_totals(months=6)
    assert len(totals) == 6


@pytest.mark.django_db
def test_teacher_cannot_access_expense_list(teacher_client):
    resp = teacher_client.get(reverse('expenses:list'))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_can_access_expense_list(admin_client):
    resp = admin_client.get(reverse('expenses:list'))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_admin_can_create_expense_via_view(admin_client, teacher_user):
    resp = admin_client.post(reverse('expenses:create'), {
        'category': Expense.Category.SALARY,
        'amount': 300_000,
        'expense_date': '2026-03-01',
        'description': "Fevral oyligi",
        'paid_to_user': teacher_user.pk,
        'paid_to_name': '',
    })
    assert resp.status_code == 302
    assert Expense.objects.filter(description="Fevral oyligi").exists()


@pytest.mark.django_db
def test_cannot_set_both_staff_and_name(admin_client, teacher_user):
    resp = admin_client.post(reverse('expenses:create'), {
        'category': Expense.Category.OTHER,
        'amount': 100_000,
        'expense_date': '2026-03-01',
        'description': "Xato",
        'paid_to_user': teacher_user.pk,
        'paid_to_name': 'Boshqa ism',
    })
    assert resp.status_code == 200
    assert not Expense.objects.filter(description="Xato").exists()
