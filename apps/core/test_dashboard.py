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


@pytest.mark.django_db
def test_admin_dashboard_links_sit_next_to_chart(admin_client):
    html = admin_client.get(reverse('core:dashboard')).content.decode()
    chart_pos = html.index('id="debtChart"')
    row_start = html.rindex('align-items-stretch', 0, chart_pos)
    block = html[row_start:]
    for title in ('Hodimlar', 'Hisobotlar', 'Qarzdorlar', 'Xabarnomalar'):
        assert block.count(f'{title}</h6>') == 1, title  # har biri bir martadan (diagramma yonidagi blokda)
    # chap diagramma va o'ng havolalar bitta qatorda
    assert html.index('col-lg-7 col-xl-8') > chart_pos
    assert html.index('>Hodimlar') < html.index('>Xabarnomalar')
    for url in (reverse('accounts:staff_list'), reverse('reports:index'), reverse('payments:debtors'),
                reverse('notifications:list')):
        assert f'href="{url}"' in html[row_start:]


@pytest.mark.django_db
def test_teacher_dashboard_keeps_shortcuts(teacher_client):
    html = teacher_client.get(reverse('core:dashboard')).content.decode()
    for title in ('Guruhlarim</h6>', 'Qarzdorlar</h6>', 'Xabarnomalar</h6>'):
        assert title in html
