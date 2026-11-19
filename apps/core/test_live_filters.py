"""Barcha panellardagi real-time filtrlar uchun testlar.

Har bir filtrlanadigan sahifa:
  * `data-live-filter` formasi va `#live-results` konteynerini beradi (JS shu orqali ishlaydi);
  * filtr parametrlariga ko'ra natijani to'g'ri toraytiradi;
  * paginatsiya havolalarida filtrlar saqlanadi.
"""
import datetime

import pytest
from django.urls import reverse

from apps.core.models import AuditLog
from apps.expenses.models import Expense
from apps.lessons.models import Lesson, TheoryLesson
from apps.notifications.models import Notification
from apps.payments.models import CashClosing

LIVE_PAGES = [
    'accounts:staff_list',
    'groups:list',
    'lessons:list',
    'lessons:theory_list',
    'payments:debtors',
    'payments:cash_list',
    'expenses:list',
    'core:audit_log',
    'core:archive',
    'notifications:list',
    'site_settings:access_control',
    'reports:revenue',
    'reports:groups',
    'reports:staff',
    'reports:debtors',
    'reports:upcoming',
    'reports:cash',
]


def names(response, key):
    return [str(o) for o in response.context[key]]


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', LIVE_PAGES)
def test_admin_pages_are_live_filter_ready(admin_client, url_name):
    html = admin_client.get(reverse(url_name)).content.decode()
    assert 'data-live-filter' in html
    assert 'id="live-results"' in html
    assert 'js/live.js' in html


@pytest.mark.django_db
def test_live_js_is_served(admin_client):
    from django.contrib.staticfiles import finders

    assert finders.find('js/live.js')


# --- Hodimlar ---------------------------------------------------------------

@pytest.mark.django_db
def test_staff_filters(admin_client, teacher_user, instructor_user):
    url = reverse('accounts:staff_list')
    assert len(admin_client.get(url).context['staff_list']) == 2
    assert names(admin_client.get(url, {'role': 'teacher'}), 'staff_list') == [str(teacher_user)]
    assert names(admin_client.get(url, {'role': 'instructor'}), 'staff_list') == [str(instructor_user)]
    assert names(admin_client.get(url, {'q': 'Instructor'}), 'staff_list') == [str(instructor_user)]
    assert names(admin_client.get(url, {'q': '+998900000002'}), 'staff_list') == [str(teacher_user)]
    instructor_user.is_active = False
    instructor_user.save()
    assert names(admin_client.get(url, {'active': '0'}), 'staff_list') == [str(instructor_user)]
    assert names(admin_client.get(url, {'active': '1'}), 'staff_list') == [str(teacher_user)]
    assert len(admin_client.get(url, {'role': 'bogus'}).context['staff_list']) == 2


# --- Guruhlar ---------------------------------------------------------------

@pytest.mark.django_db
def test_group_filters(admin_client, group):
    from apps.groups.models import Group

    other = Group.objects.create(
        name='Boshqa', category='C', start_date=datetime.date(2026, 2, 1), price=1_000_000, max_students=10,
    )
    url = reverse('groups:list')
    assert set(admin_client.get(url).context['groups']) == {group, other}
    assert list(admin_client.get(url, {'q': 'bosh'}).context['groups']) == [other]
    assert list(admin_client.get(url, {'category': 'b'}).context['groups']) == [group]
    assert list(admin_client.get(url, {'q': 'yo\'q-guruh'}).context['groups']) == []


# --- Amaliyot / nazariy darslar ------------------------------------------------

@pytest.fixture
def lessons(db, student, instructor_user, teacher_user, group):
    from apps.students.models import Student

    s2 = Student.objects.create(full_name='Boshqa Oquvchi', phone='+998900000099', brought_by_user_id=teacher_user)
    l1 = Lesson.objects.create(
        instructor=instructor_user, student=student, lesson_date=datetime.date(2026, 3, 1),
        start_time=datetime.time(9, 0), hours=1, attended=True,
    )
    l2 = Lesson.objects.create(
        instructor=instructor_user, student=s2, lesson_date=datetime.date(2026, 4, 1),
        start_time=datetime.time(9, 0), hours=1, attended=False,
    )
    l3 = Lesson.objects.create(
        instructor=instructor_user, student=s2, lesson_date=datetime.date(2026, 5, 1),
        start_time=datetime.time(9, 0), hours=1,
    )
    return l1, l2, l3


@pytest.mark.django_db
def test_practical_lesson_filters(admin_client, lessons, instructor_user, teacher_user):
    l1, l2, l3 = lessons
    url = reverse('lessons:list')
    assert set(admin_client.get(url).context['lessons']) == {l1, l2, l3}
    assert set(admin_client.get(url, {'q': 'boshqa'}).context['lessons']) == {l2, l3}
    assert list(admin_client.get(url, {'attended': 'yes'}).context['lessons']) == [l1]
    assert list(admin_client.get(url, {'attended': 'no'}).context['lessons']) == [l2]
    assert list(admin_client.get(url, {'attended': 'unknown'}).context['lessons']) == [l3]
    assert set(admin_client.get(url, {'date_from': '2026-04-01'}).context['lessons']) == {l2, l3}
    assert list(admin_client.get(url, {'date_from': '2026-03-15', 'date_to': '2026-04-15'}).context['lessons']) == [l2]
    assert set(admin_client.get(url, {'instructor': instructor_user.pk}).context['lessons']) == {l1, l2, l3}
    assert list(admin_client.get(url, {'instructor': teacher_user.pk}).context['lessons']) == []
    # noto'g'ri qiymatlar xato bermaydi
    assert admin_client.get(url, {'date_from': 'abc', 'instructor': 'x'}).status_code == 200


@pytest.mark.django_db
def test_theory_lesson_filters(admin_client, group, teacher_user):
    t1 = TheoryLesson.objects.create(
        group=group, teacher=teacher_user, topic='Yo\'l belgilari', lesson_date=datetime.date(2026, 3, 1),
        start_time=datetime.time(10, 0),
    )
    t2 = TheoryLesson.objects.create(
        group=group, teacher=teacher_user, topic='Svetofor', lesson_date=datetime.date(2026, 6, 1),
        start_time=datetime.time(10, 0),
    )
    url = reverse('lessons:theory_list')
    assert set(admin_client.get(url).context['theory_lessons']) == {t1, t2}
    assert list(admin_client.get(url, {'q': 'svet'}).context['theory_lessons']) == [t2]
    assert list(admin_client.get(url, {'date_to': '2026-04-01'}).context['theory_lessons']) == [t1]
    assert set(admin_client.get(url, {'q': 'Teacher One'}).context['theory_lessons']) == {t1, t2}
    assert set(admin_client.get(url, {'group': group.pk}).context['theory_lessons']) == {t1, t2}


# --- Qarzdorlar -------------------------------------------------------------

@pytest.mark.django_db
def test_debtors_filters(admin_client, enrollment, group, teacher_user):
    url = reverse('payments:debtors')
    resp = admin_client.get(url)
    assert len(resp.context['debtors']) == 1
    assert resp.context['total_debt'] == 3_000_000
    assert len(admin_client.get(url, {'q': 'test stu'}).context['debtors']) == 1
    assert admin_client.get(url, {'q': 'zzz'}).context['debtors'] == []
    assert len(admin_client.get(url, {'group': group.pk}).context['debtors']) == 1
    assert admin_client.get(url, {'group': group.pk + 999}).context['debtors'] == []
    assert admin_client.get(url, {'group': 'abc'}).status_code == 200
    assert admin_client.get(url, {'q': 'zzz'}).context['total_debt'] == 0


@pytest.mark.django_db
def test_debtors_filters_for_teacher(teacher_client, enrollment, group):
    url = reverse('payments:debtors')
    assert len(teacher_client.get(url, {'group': group.pk}).context['debtors']) == 1
    assert teacher_client.get(url, {'q': 'nobody'}).context['debtors'] == []


# --- Kassa -----------------------------------------------------------------

@pytest.mark.django_db
def test_cash_list_filters(admin_client, admin_user, teacher_user):
    c1 = CashClosing.objects.create(
        user=teacher_user, date=datetime.date(2026, 3, 1), expected_amount=100, declared_amount=100,
    )
    c2 = CashClosing.objects.create(
        user=admin_user, date=datetime.date(2026, 4, 1), expected_amount=100, declared_amount=50,
        status=CashClosing.Status.APPROVED,
    )
    url = reverse('payments:cash_list')
    assert set(admin_client.get(url).context['closings']) == {c1, c2}
    assert list(admin_client.get(url, {'user': teacher_user.pk}).context['closings']) == [c1]
    assert list(admin_client.get(url, {'status': 'approved'}).context['closings']) == [c2]
    assert list(admin_client.get(url, {'diff': '1'}).context['closings']) == [c2]
    assert list(admin_client.get(url, {'date_to': '2026-03-31'}).context['closings']) == [c1]
    assert list(admin_client.get(url, {'date_from': '2026-03-15'}).context['closings']) == [c2]
    assert set(admin_client.get(url, {'status': 'bogus'}).context['closings']) == {c1, c2}


# --- Xarajatlar ---------------------------------------------------------------

@pytest.mark.django_db
def test_expense_filters_and_total(admin_client, admin_user, teacher_user):
    e1 = Expense.objects.create(
        category='rent', amount=100, expense_date=datetime.date(2026, 3, 1), description='a',
        created_by=admin_user,
    )
    e2 = Expense.objects.create(
        category='salary', amount=300, expense_date=datetime.date(2026, 4, 1), description='b',
        paid_to_user=teacher_user, created_by=admin_user,
    )
    url = reverse('expenses:list')
    resp = admin_client.get(url)
    assert set(resp.context['expenses']) == {e1, e2} and resp.context['total'] == 400
    resp = admin_client.get(url, {'category': 'rent'})
    assert list(resp.context['expenses']) == [e1] and resp.context['total'] == 100
    assert list(admin_client.get(url, {'paid_to_user': teacher_user.pk}).context['expenses']) == [e2]
    assert list(admin_client.get(url, {'date_from': '2026-03-15'}).context['expenses']) == [e2]
    # jami summa fragment ichida (live-results) bo'lishi kerak
    html = admin_client.get(url, {'category': 'rent'}).content.decode()
    assert html.index('id="live-results"') < html.index('Jami xarajat')


# --- Jurnal / kirish nazorati ----------------------------------------------------

@pytest.mark.django_db
def test_audit_log_filters(admin_client, admin_user, teacher_user):
    a1 = AuditLog.objects.create(user=admin_user, action='x.one', entity_type='Foo', entity_id='1')
    a2 = AuditLog.objects.create(user=teacher_user, action='x.two', entity_type='Bar', entity_id='2')
    url = reverse('core:audit_log')
    assert {a1, a2} <= set(admin_client.get(url).context['logs'])
    assert list(admin_client.get(url, {'action': 'x.one'}).context['logs']) == [a1]
    assert list(admin_client.get(url, {'entity_type': 'Bar'}).context['logs']) == [a2]
    assert list(admin_client.get(url, {'user': teacher_user.pk}).context['logs']) == [a2]
    today = datetime.date.today().isoformat()
    assert {a1, a2} <= set(admin_client.get(url, {'date_from': today, 'date_to': today}).context['logs'])
    future = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
    assert list(admin_client.get(url, {'date_from': future}).context['logs']) == []
    assert admin_client.get(url, {'date_from': 'garbage'}).status_code == 200


@pytest.mark.django_db
def test_access_control_log_filter(admin_client, admin_user, teacher_user):
    l1 = AuditLog.objects.create(user=teacher_user, action='auth.login', entity_type='User', entity_id='1')
    l2 = AuditLog.objects.create(user=admin_user, action='auth.logout', entity_type='User', entity_id='1')
    url = reverse('site_settings:access_control')
    assert {l1, l2} <= set(admin_client.get(url).context['logs'])
    assert list(admin_client.get(url, {'user': teacher_user.pk}).context['logs']) == [l1]


# --- Arxiv ------------------------------------------------------------------------

@pytest.mark.django_db
def test_archive_search(admin_client, student, group, instructor_user):
    from apps.groups.models import Group
    from apps.students.models import Student

    student.status = Student.Status.ARCHIVED
    student.save()
    group.status = Group.Status.ARCHIVED
    group.save()
    instructor_user.is_active = False
    instructor_user.save()

    url = reverse('core:archive')
    resp = admin_client.get(url)
    assert list(resp.context['archived_students']) == [student]
    assert list(resp.context['archived_groups']) == [group]
    assert list(resp.context['blocked_staff']) == [instructor_user]

    resp = admin_client.get(url, {'q': 'Test Student'})
    assert list(resp.context['archived_students']) == [student]
    assert list(resp.context['archived_groups']) == []
    assert list(resp.context['blocked_staff']) == []
    resp = admin_client.get(url, {'q': 'Instructor'})
    assert list(resp.context['blocked_staff']) == [instructor_user]
    assert list(resp.context['archived_students']) == []
    resp = admin_client.get(url, {'q': 'zzz'})
    assert not resp.context['archived_students'] and not resp.context['archived_groups']


# --- Xabarnomalar ---------------------------------------------------------------------

@pytest.mark.django_db
def test_notification_filters(teacher_client, teacher_user, other_teacher_user):
    n1 = Notification.objects.create(user=teacher_user, type='due_soon', title='Muddat yaqin', body='abc')
    n2 = Notification.objects.create(user=teacher_user, type='overdue', title='Kechikdi', body='xyz', is_read=True)
    Notification.objects.create(user=other_teacher_user, type='overdue', title='Muddat boshqa', body='')
    url = reverse('notifications:list')
    assert set(teacher_client.get(url).context['notifications']) == {n1, n2}
    assert list(teacher_client.get(url, {'status': 'unread'}).context['notifications']) == [n1]
    assert list(teacher_client.get(url, {'status': 'read'}).context['notifications']) == [n2]
    assert list(teacher_client.get(url, {'q': 'muddat'}).context['notifications']) == [n1]
    assert list(teacher_client.get(url, {'q': 'xyz'}).context['notifications']) == [n2]


# --- Hisobotlar -------------------------------------------------------------------------

@pytest.mark.django_db
def test_report_exports_are_inside_live_results(admin_client):
    for name in ['reports:revenue', 'reports:groups', 'reports:staff', 'reports:debtors',
                 'reports:upcoming', 'reports:cash']:
        html = admin_client.get(reverse(name)).content.decode()
        assert html.index('id="live-results"') < html.index('format=xlsx'), name


@pytest.mark.django_db
def test_report_filters(admin_client, enrollment, group, teacher_user, admin_user):
    from apps.payments.models import Payment

    resp = admin_client.get(reverse('reports:groups'), {'group': group.pk})
    assert len(resp.context['rows']) == 1
    resp = admin_client.get(reverse('reports:groups'), {'status': 'archived'})
    assert resp.context['rows'] == []
    resp = admin_client.get(reverse('reports:staff'), {'role': 'teacher'})
    assert [r['user'] for r in resp.context['rows']] == [teacher_user]
    resp = admin_client.get(reverse('reports:staff'), {'role': 'instructor'})
    assert resp.context['rows'] == []
    resp = admin_client.get(reverse('reports:debtors'), {'group': group.pk})
    assert resp.status_code == 200
    assert admin_client.get(reverse('reports:upcoming'), {'days': 7}).status_code == 200
    assert admin_client.get(reverse('reports:cash'), {'date_from': '2026-01-01', 'date_to': '2026-12-31'}).status_code == 200
    assert admin_client.get(reverse('reports:revenue'), {'method': 'cash'}).status_code == 200
    assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_report_exports_respect_filters(admin_client, group, enrollment):
    resp = admin_client.get(reverse('reports:groups'), {'group': group.pk, 'format': 'xlsx'})
    assert resp.status_code == 200
    assert 'spreadsheetml' in resp['Content-Type']


# --- Paginatsiya filtrlarni saqlaydi -----------------------------------------------------------

@pytest.mark.django_db
def test_pagination_keeps_filters(admin_client, admin_user):
    for i in range(45):
        AuditLog.objects.create(user=admin_user, action='bulk.action', entity_type='Foo', entity_id=str(i))
    resp = admin_client.get(reverse('core:audit_log'), {'action': 'bulk.action'})
    html = resp.content.decode()
    assert resp.context['page_obj'].paginator.num_pages == 2
    assert 'action=bulk.action' in html and 'page=2' in html
    resp2 = admin_client.get(reverse('core:audit_log'), {'action': 'bulk.action', 'page': 2})
    assert len(resp2.context['logs']) == 5


# --- Rollar bo'yicha kirish ----------------------------------------------------------------------

@pytest.mark.django_db
def test_teacher_pages_with_filters(teacher_client, student, group):
    assert teacher_client.get(reverse('students:list'), {'q': 'test'}).status_code == 200
    assert teacher_client.get(reverse('groups:list'), {'q': 'test'}).status_code == 200
    assert teacher_client.get(reverse('students:my_brought'), {'q': 'test'}).status_code == 200
    html = teacher_client.get(reverse('payments:debtors')).content.decode()
    assert 'data-live-filter' in html
    assert teacher_client.get(reverse('notifications:list')).status_code == 200


@pytest.mark.django_db
def test_instructor_pages_with_filters(instructor_client):
    assert instructor_client.get(reverse('students:list'), {'q': 'x'}).status_code == 200
    assert instructor_client.get(reverse('groups:list'), {'q': 'x'}).status_code == 200
    assert instructor_client.get(reverse('students:my_brought'), {'q': 'x'}).status_code == 200


@pytest.mark.django_db
def test_non_admin_cannot_use_admin_live_pages(teacher_client, instructor_client):
    for name in ['accounts:staff_list', 'core:audit_log', 'core:archive', 'expenses:list',
                 'lessons:list', 'reports:revenue', 'site_settings:access_control']:
        assert teacher_client.get(reverse(name)).status_code == 403, name
        assert instructor_client.get(reverse(name)).status_code == 403, name


@pytest.mark.django_db
def test_students_htmx_fragment_and_filters(admin_client, student, group):
    url = reverse('students:list')
    full = admin_client.get(url, {'q': 'Test'}).content.decode()
    frag = admin_client.get(url, {'q': 'Test'}, HTTP_HX_REQUEST='true').content.decode()
    assert '<html' in full and '<html' not in frag
    assert 'Test Student' in frag
    assert 'Test Student' not in admin_client.get(url, {'q': 'zzzz'}, HTTP_HX_REQUEST='true').content.decode()
    assert 'Test Student' in admin_client.get(url, {'group': group.pk}, HTTP_HX_REQUEST='true').content.decode()
    assert 'Test Student' in admin_client.get(url, {'payment_status': 'unpaid', 'learning_status': 'studying'}, HTTP_HX_REQUEST='true').content.decode()
