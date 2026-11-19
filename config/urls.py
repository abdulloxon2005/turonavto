from django.conf import settings
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('xabarnomalar/', include('apps.notifications.urls')),
    path('guruhlar/', include('apps.groups.urls')),
    path('oquvchilar/', include('apps.students.urls')),
    path('tolovlar/', include('apps.payments.urls')),
    path('amaliyot/', include('apps.lessons.urls')),
    path('imtihonlar/', include('apps.exams.urls')),
    path('xarajatlar/', include('apps.expenses.urls')),
    path('hisobotlar/', include('apps.reports.urls')),
    path('sozlamalar/', include('apps.site_settings.urls')),
]

# Yuklangan fayllar (hodim/o'quvchi rasmlari). `static()` faqat DEBUG=True da ishlaydi, shuning uchun
# DEBUG=False bo'lganda rasmlar chiqmay qolardi. Production'da nginx `/media/` ni o'zi beradi (Django'ga
# yetib kelmaydi); nginx'siz ishga tushirilganda esa bu yo'l faqat tizimga kirgan foydalanuvchilarga beradi.
urlpatterns += [
    re_path(
        r'^%s(?P<path>.*)$' % settings.MEDIA_URL.lstrip('/'),
        login_required(serve),
        {'document_root': settings.MEDIA_ROOT},
    ),
]
