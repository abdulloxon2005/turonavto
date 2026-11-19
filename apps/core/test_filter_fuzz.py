"""Filtr parametrlariga g'alati qiymatlar berilganda hech bir sahifa 500 xato bermasligi kerak."""
import itertools

import pytest
from django.urls import reverse

PAGES = [
    'accounts:staff_list', 'groups:list', 'students:list', 'students:my_brought', 'lessons:list',
    'lessons:theory_list', 'payments:debtors', 'payments:cash_list', 'expenses:list', 'core:audit_log',
    'core:archive', 'notifications:list', 'site_settings:access_control', 'reports:revenue',
    'reports:groups', 'reports:staff', 'reports:debtors', 'reports:upcoming', 'reports:cash',
]
PARAMS = ['q', 'group', 'owner', 'teacher', 'user', 'instructor', 'student', 'status', 'role', 'active',
          'category', 'paid_to_user', 'received_by', 'method', 'min_days', 'days', 'attended', 'diff',
          'date_from', 'date_to', 'action', 'entity_type', 'learning_status', 'payment_status',
          'include_partial', 'page', 'format']
VALUES = ['', ' ', 'abc', '-1', '0', '99999999999999999999', '1e5', "'; DROP TABLE x;--", '%00', '😀', '2026-13-45', '<script>']


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', PAGES)
def test_garbage_params_never_500(admin_client, url_name, group, student, enrollment):
    url = reverse(url_name)
    bad = []
    for param, value in itertools.product(PARAMS, VALUES):
        if param == 'format':
            continue  # eksport alohida
        try:
            resp = admin_client.get(url, {param: value})
        except Exception as exc:  # noqa: BLE001
            bad.append((param, value, repr(exc)[:80]))
            continue
        if resp.status_code >= 500:
            bad.append((param, value, resp.status_code))
    assert not bad, bad[:10]


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', ['students:list', 'students:my_brought', 'groups:list', 'payments:debtors',
                                      'lessons:theory_list'])
def test_garbage_params_never_500_for_teacher(teacher_client, url_name, group, student):
    url = reverse(url_name)
    bad = []
    for param, value in itertools.product(PARAMS, VALUES):
        if param == 'format':
            continue
        try:
            resp = teacher_client.get(url, {param: value})
        except Exception as exc:  # noqa: BLE001
            bad.append((param, value, repr(exc)[:80]))
            continue
        if resp.status_code >= 500:
            bad.append((param, value, resp.status_code))
    assert not bad, bad[:10]


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', ['reports:revenue', 'reports:groups', 'reports:staff', 'reports:debtors',
                                      'reports:upcoming', 'reports:cash'])
@pytest.mark.parametrize('fmt', ['xlsx', 'pdf'])
def test_exports_with_garbage_filters(admin_client, url_name, fmt, group, enrollment):
    for params in ({'group': 'abc', 'owner': 'x', 'min_days': '-5', 'days': 'zz', 'received_by': '999999999999999999999',
                    'method': 'bogus', 'date_from': 'nope', 'date_to': '2026-99-99'},
                   {}):
        resp = admin_client.get(reverse(url_name), {**params, 'format': fmt})
        assert resp.status_code == 200, (params, resp.status_code)


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', ['students:list', 'students:my_brought'])
def test_htmx_garbage_filters(admin_client, url_name, student):
    for param, value in itertools.product(PARAMS, VALUES):
        resp = admin_client.get(reverse(url_name), {param: value}, HTTP_HX_REQUEST='true')
        assert resp.status_code < 500, (param, value)


@pytest.mark.django_db
def test_selected_filters_survive_reload(admin_client, group, teacher_user):
    """Filtr URL orqali ochilganda (yangilash/ulashish) tanlangan qiymatlar formada saqlanishi kerak."""
    html = admin_client.get(reverse('reports:groups'), {'group': group.pk, 'status': 'open'}).content.decode()
    assert f'value="{group.pk}" selected' in html
    assert 'value="open" selected' in html
    html = admin_client.get(reverse('reports:staff'), {'role': 'teacher', 'date_from': '2026-02-03'}).content.decode()
    assert 'value="teacher" selected' in html and 'value="2026-02-03"' in html
    html = admin_client.get(reverse('reports:debtors'), {'min_days': '15', 'owner': teacher_user.pk}).content.decode()
    assert 'value="15"' in html and f'value="{teacher_user.pk}" selected' in html
    html = admin_client.get(reverse('reports:upcoming'), {'days': '45'}).content.decode()
    assert 'value="45"' in html
    html = admin_client.get(reverse('payments:debtors'), {'q': 'abc', 'include_partial': '1'}).content.decode()
    assert 'value="abc"' in html and 'checked' in html
    html = admin_client.get(reverse('payments:cash_list'), {'diff': '1', 'status': 'approved'}).content.decode()
    assert 'value="approved" selected' in html and 'name="diff" value="1" checked' in html
    html = admin_client.get(reverse('lessons:list'), {'attended': 'no', 'q': 'zz'}).content.decode()
    assert 'value="no" selected' in html and 'value="zz"' in html
    html = admin_client.get(reverse('accounts:staff_list'), {'role': 'instructor', 'active': '0'}).content.decode()
    assert 'value="instructor" selected' in html and 'value="0" selected' in html
