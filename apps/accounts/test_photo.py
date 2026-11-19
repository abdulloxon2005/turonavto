import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import User


def png_bytes():
    buf = io.BytesIO()
    Image.new('RGB', (20, 20), 'red').save(buf, 'PNG')
    return buf.getvalue()


@pytest.fixture
def media_root(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.mark.django_db
@pytest.mark.parametrize('debug', [True, False])
def test_staff_photo_upload_is_displayed(admin_client, admin_user, media_root, settings, debug):
    settings.DEBUG = debug
    resp = admin_client.post(reverse('accounts:staff_create'), {
        'full_name': 'Rasmli Hodim', 'phone': '+998901112233', 'role': 'teacher',
        'photo': SimpleUploadedFile('me.png', png_bytes(), content_type='image/png'),
    })
    assert resp.status_code == 302, getattr(resp, 'context', None) and resp.context['form'].errors
    user = User.objects.get(phone='+998901112233')
    assert user.photo
    url = user.photo.url
    html = admin_client.get(reverse('accounts:staff_list')).content.decode()
    assert f'src="{url}"' in html
    img = admin_client.get(url)
    assert img.status_code == 200
    assert b''.join(img.streaming_content)[:4] == b'\x89PNG'


@pytest.mark.django_db
def test_media_requires_login(media_root):
    (media_root / 'staff').mkdir()
    (media_root / 'staff' / 'a.png').write_bytes(png_bytes())
    from django.urls import resolve

    assert resolve('/media/staff/a.png')  # DEBUG dan qat'i nazar mavjud
    anon = Client()
    resp = anon.get('/media/staff/a.png')
    assert resp.status_code == 302 and 'login' in resp['Location']


@pytest.mark.django_db
def test_media_path_traversal_blocked(admin_client, media_root):
    assert admin_client.get('/media/../config/settings.py').status_code in (301, 400, 404)
    assert admin_client.get('/media/%2e%2e/config/settings.py').status_code in (400, 404)
