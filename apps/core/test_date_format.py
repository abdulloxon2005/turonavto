"""Barcha sanalar kun.oy.yil ko'rinishida chiqishi kerak (brauzer/OS tiliga bog'liq bo'lmasdan)."""
import datetime
import re

import pytest
from django.urls import reverse

from apps.core.models import AuditLog
from apps.core.templatetags.core_extras import pretty_dates
from apps.expenses.models import Expense
from apps.lessons.models import Lesson, TheoryLesson
from apps.notifications.models import Notification
from apps.payments.models import CashClosing

ISO = re.compile(r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)')


def visible_text(html):
    html = re.sub(r'(?is)<(script|style)\b.*?</\1>', '', html)
    html = re.sub(r'(?s)<[^>]+>', ' ', html)  # atributlar (value="2026-01-01") ko'rinmaydi
    return html


def test_pretty_dates_filter():
    assert pretty_dates('muddat: 2026-03-05, 2026-12-31') == 'muddat: 05.03.2026, 31.12.2026'
    assert pretty_dates("{'date': '2026-01-02'}") == "{'date': '02.01.2026'}"
    assert pretty_dates('id 12345678-1234') == 'id 12345678-1234'
    assert pretty_dates(None) is None


@pytest.fixture
def full_data(db, admin_user, teacher_user, instructor_user, group, student, enrollment):
    d = datetime.date(2026, 3, 5)
    student.birth_date = datetime.date(2000, 7, 9)
    student.save()
    group.end_date = datetime.date(2026, 9, 30)
    group.save()
    Lesson.objects.create(instructor=instructor_user, student=student, lesson_date=d, start_time=datetime.time(9, 0), hours=1)
    TheoryLesson.objects.create(group=group, teacher=teacher_user, topic='T', lesson_date=d, start_time=datetime.time(9, 0))
    Expense.objects.create(category='rent', amount=10, expense_date=d, description='x', created_by=admin_user)
    CashClosing.objects.create(user=teacher_user, date=d, expected_amount=1, declared_amount=1)
    AuditLog.objects.create(user=admin_user, action='x', entity_type='E', entity_id='1',
                            old_value={'date': '2026-03-05'}, new_value={'due': '2026-04-06'})
    Notification.objects.create(user=admin_user, type='overdue', title='t', body='muddat: 2026-03-05')
    from apps.payments.models import PaymentSchedule
    PaymentSchedule.objects.create(enrollment=enrollment, due_date=d, amount=3_000_000)
    return d


@pytest.mark.django_db
def test_no_iso_dates_visible_anywhere(admin_client, full_data, group, student, enrollment):
    pages = [
        reverse('core:dashboard'), reverse('groups:list'), reverse('groups:detail', args=[group.pk]),
        reverse('students:list'), reverse('students:my_brought'), reverse('students:detail', args=[student.pk]),
        reverse('lessons:list'), reverse('lessons:theory_list'), reverse('payments:debtors'),
        reverse('payments:cash_list'), reverse('expenses:list'), reverse('core:audit_log'),
        reverse('core:archive'), reverse('notifications:list'), reverse('site_settings:access_control'),
        reverse('payments:enrollment_detail', args=[enrollment.pk]),
        reverse('reports:index'), reverse('reports:revenue'), reverse('reports:groups'), reverse('reports:staff'),
        reverse('reports:debtors'), reverse('reports:upcoming'), reverse('reports:cash'),
        reverse('reports:exam_results'),
    ]
    bad = {}
    for url in pages:
        resp = admin_client.get(url)
        assert resp.status_code == 200, url
        found = ISO.findall(visible_text(resp.content.decode()))
        if found:
            bad[url] = found[:3]
    assert not bad, bad


@pytest.mark.django_db
def test_dates_render_as_day_month_year(admin_client, full_data, group):
    html = visible_text(admin_client.get(reverse('lessons:list')).content.decode())
    assert '05.03.2026' in html
    html = visible_text(admin_client.get(reverse('expenses:list')).content.decode())
    assert '05.03.2026' in html
    html = visible_text(admin_client.get(reverse('groups:detail', args=[group.pk])).content.decode())
    assert '01.01.2026' in html and '30.09.2026' in html
    html = visible_text(admin_client.get(reverse('core:audit_log')).content.decode())
    assert '05.03.2026' in html and '06.04.2026' in html
    html = visible_text(admin_client.get(reverse('notifications:list')).content.decode())
    assert 'muddat: 05.03.2026' in html


@pytest.mark.django_db
def test_date_inputs_keep_iso_value_for_submission(admin_client, group):
    """Serverga yuboriladigan asl qiymat ISO bo'lib qoladi; ko'rinishni dates.js (flatpickr) kun.oy.yil qiladi."""
    html = admin_client.get(reverse('groups:update', args=[group.pk])).content.decode()
    assert 'type="date"' in html and 'value="2026-01-01"' in html
    assert 'js/dates.js' in html and 'flatpickr' in html


@pytest.mark.django_db
def test_every_page_loads_date_picker(admin_client):
    for name in ('reports:revenue', 'expenses:create', 'lessons:create', 'groups:create', 'students:create',
                 'core:audit_log', 'payments:cash_list'):
        html = admin_client.get(reverse(name)).content.decode()
        assert 'flatpickr.min.js' in html and 'js/dates.js' in html, name


def test_notification_job_text_uses_day_month_year(db, student, enrollment, teacher_user):
    import datetime as dt

    from django.utils import timezone

    from apps.payments import jobs
    from apps.payments.models import PaymentSchedule
    from apps.site_settings.models import get_setting

    target = timezone.localdate() + dt.timedelta(days=get_setting('reminder_days_before', 3))
    PaymentSchedule.objects.create(enrollment=enrollment, due_date=target, amount=1000)
    assert jobs.remind_upcoming_due() == 1
    body = Notification.objects.get(user=teacher_user).body
    assert ISO.search(body) is None
    assert target.strftime('%d.%m.%Y') in body
