from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView

from apps.core.mixins import AdminOrTeacherRequiredMixin

from .models import Notification


class NotificationListView(AdminOrTeacherRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/list.html'
    context_object_name = 'notifications'
    paginate_by = 30

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)
        status = self.request.GET.get('status', '')
        if status == 'unread':
            qs = qs.filter(is_read=False)
        elif status == 'read':
            qs = qs.filter(is_read=True)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))
        return qs


class NotificationMarkReadView(AdminOrTeacherRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])
        next_url = notification.link or 'notifications:list'
        return redirect(next_url)


class NotificationMarkAllReadView(AdminOrTeacherRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return redirect('notifications:list')
