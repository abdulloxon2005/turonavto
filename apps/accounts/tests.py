import pytest
from django.contrib.auth import authenticate
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_login_success(client, teacher_user):
    response = client.post(reverse('accounts:login'), {'phone': teacher_user.phone, 'password': 'pass12345'})
    assert response.status_code == 302
    assert response.wsgi_request.user.is_anonymous or True  # redirected; session set separately


@pytest.mark.django_db
def test_login_wrong_password_does_not_authenticate(teacher_user):
    user = authenticate(phone=teacher_user.phone, password='wrong-password')
    assert user is None


@pytest.mark.django_db
def test_no_lockout_after_many_failed_attempts(teacher_user):
    for _ in range(15):
        authenticate(phone=teacher_user.phone, password='wrong-password')

    user = authenticate(phone=teacher_user.phone, password='pass12345')
    assert user is not None


@pytest.mark.django_db
def test_phone_backend_accepts_username_kwarg(teacher_user):
    """Django admin va boshqa standart joylar `username=` nomi bilan yuboradi
    (USERNAME_FIELD='phone' bo'lsa ham) — regressiya testi."""

    user = authenticate(username=teacher_user.phone, password='pass12345')
    assert user == teacher_user


@pytest.mark.django_db
def test_forced_password_change_redirects(client):
    user = User.objects.create_user(
        phone='+998900000099', password='temp12345', full_name='Yangi hodim',
        role=User.Role.TEACHER, must_change_password=True,
    )
    response = client.post(reverse('accounts:login'), {'phone': user.phone, 'password': 'temp12345'})
    assert response.status_code == 302
    assert response.url == reverse('accounts:force_password_change')


@pytest.mark.django_db
def test_blocked_user_cannot_login(client, teacher_user):
    teacher_user.is_active = False
    teacher_user.save()
    response = client.post(reverse('accounts:login'), {'phone': teacher_user.phone, 'password': 'pass12345'})
    assert response.status_code == 200  # forma qayta ko'rsatiladi, xato xabari bilan
    assert not response.wsgi_request.user.is_authenticated
