import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_admin_dashboard_has_only_paid_unpaid_doughnut(admin_client, enrollment):
    resp = admin_client.get(reverse('core:dashboard'))
    html = resp.content.decode()
    assert 'xarajat' not in html.lower()
    assert 'foyda' not in html.lower()
    assert html.count('<canvas') == 1 and 'id="debtChart"' in html
    for gone in ('revenueExpenseChart', 'staffChart', 'expenseCategoryChart'):
        assert gone not in html
    assert "To'langan" in html and "To'lanmagan" in html
    assert "'#22c55e', '#9ca3af'" in html  # yashil / kulrang
    assert resp.context['chart_data'] == {'debtPaid': 0, 'debtRemaining': 3_000_000}
    assert set(resp.context['chart_data']) == {'debtPaid', 'debtRemaining'}


@pytest.mark.django_db
def test_other_dashboards_have_no_expense_words(teacher_client, instructor_client):
    for c in (teacher_client, instructor_client):
        html = c.get(reverse('core:dashboard')).content.decode().lower()
        assert 'xarajat' not in html
