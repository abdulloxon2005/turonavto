from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError


def site_context(request):
    try:
        from apps.site_settings.models import get_setting

        center_name = get_setting('center_name', settings.CENTER_NAME)
    except (OperationalError, ProgrammingError):
        # Migratsiya hali qo'llanilmagan bo'lishi mumkin (masalan birinchi ishga tushirishda).
        center_name = settings.CENTER_NAME

    context = {'CENTER_NAME': center_name}
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        from apps.notifications.models import Notification

        context['unread_notifications_count'] = Notification.objects.filter(
            user=user, is_read=False
        ).count()
        context['recent_notifications'] = Notification.objects.filter(user=user).order_by('-created_at')[:8]
    return context
