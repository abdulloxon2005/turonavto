import datetime

import pytest
from django.contrib.sessions.models import Session
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User


@pytest.fixture
def staff(db):
    return User.objects.create_user(
        phone='+998900000777', password='pass12345', full_name='T', role='teacher', must_change_password=False,
    )


def login(staff):
    c = Client()
    assert c.post(reverse('accounts:login'), {'phone': staff.phone, 'password': 'pass12345'}).status_code == 302
    return c


def expire(client):
    Session.objects.filter(session_key=client.cookies['sessionid'].value).update(
        expire_date=timezone.now() - datetime.timedelta(seconds=1)
    )


def test_timeout_is_30_minutes(settings):
    assert settings.SESSION_IDLE_TIMEOUT_SECONDS == 1800
    assert settings.SESSION_COOKIE_AGE == 1800
    assert settings.SESSION_SAVE_EVERY_REQUEST is True


@pytest.mark.django_db
def test_session_expiry_is_30_minutes_after_login(staff):
    c = login(staff)
    s = Session.objects.get(session_key=c.cookies['sessionid'].value)
    left = (s.expire_date - timezone.now()).total_seconds()
    assert 29 * 60 < left <= 30 * 60
    assert int(c.cookies['sessionid']['max-age']) == 1800


@pytest.mark.django_db
def test_activity_extends_session(staff):
    c = login(staff)
    key = c.cookies['sessionid'].value
    Session.objects.filter(session_key=key).update(expire_date=timezone.now() + datetime.timedelta(minutes=5))
    assert c.get(reverse('core:dashboard')).status_code == 200
    left = (Session.objects.get(session_key=key).expire_date - timezone.now()).total_seconds()
    assert left > 29 * 60  # har so'rovda 30 daqiqaga yangilandi


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', ['core:dashboard', 'groups:list', 'students:list', 'payments:debtors'])
def test_idle_30_minutes_requires_login_again(staff, url_name):
    c = login(staff)
    expire(c)
    resp = c.get(reverse(url_name))
    assert resp.status_code == 302 and reverse('accounts:login') in resp['Location']


@pytest.mark.django_db
def test_idle_htmx_request_redirects_whole_page(staff):
    c = login(staff)
    expire(c)
    resp = c.get(reverse('students:list'), HTTP_HX_REQUEST='true')
    assert resp.status_code == 204
    assert reverse('accounts:login') in resp['HX-Redirect']


@pytest.mark.django_db
def test_keepalive_endpoint(staff):
    assert Client().get(reverse('core:keepalive')).status_code == 401
    assert login(staff).get(reverse('core:keepalive')).status_code == 204


@pytest.mark.django_db
def test_expired_login_message_and_idle_script(staff):
    resp = Client().get(reverse('accounts:login'), {'expired': 1})
    assert 'Qayta kiring' in resp.content.decode()
    html = login(staff).get(reverse('core:dashboard')).content.decode()
    assert 'id="idle-config"' in html and 'data-timeout="1800"' in html and 'js/idle.js' in html
    assert 'idle.js' not in Client().get(reverse('accounts:login')).content.decode()


def test_idle_script_exists():
    from django.contrib.staticfiles import finders

    assert finders.find('js/idle.js')
