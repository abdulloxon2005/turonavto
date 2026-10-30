from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('xabarnomalar/', include('apps.notifications.urls')),
    path('guruhlar/', include('apps.groups.urls')),
    path('oquvchilar/', include('apps.students.urls')),
    path('tolovlar/', include('apps.payments.urls')),
    path('amaliyot/', include('apps.lessons.urls')),
    path('xarajatlar/', include('apps.expenses.urls')),
    path('hisobotlar/', include('apps.reports.urls')),
    path('sozlamalar/', include('apps.site_settings.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
