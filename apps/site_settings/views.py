from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.accounts.models import User
from apps.accounts.services import set_active
from apps.core.mixins import AdminRequiredMixin
from apps.core.models import AuditLog
from apps.core.services import log_action

from .forms import SettingsForm
from .models import get_setting, set_setting


class SettingsEditView(AdminRequiredMixin, View):
    template_name = 'site_settings/edit.html'

    def get(self, request):
        initial = {
            'center_name': get_setting('center_name'),
            'payment_methods': get_setting('payment_methods'),
            'reminder_days_before': get_setting('reminder_days_before'),
        }
        return render(request, self.template_name, {'form': SettingsForm(initial=initial)})

    def post(self, request):
        form = SettingsForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        for key in ('center_name', 'payment_methods', 'reminder_days_before'):
            set_setting(key, form.cleaned_data[key])

        log_action(request.user, action='settings.update', entity_type='Setting', new_value=form.cleaned_data)
        messages.success(request, 'Sozlamalar saqlandi')
        return redirect('site_settings:edit')


class AccessControlView(AdminRequiredMixin, ListView):
    """Hodimlarning tizimga kirish huquqini boshqarish va kirish/chiqish tarixi."""

    model = AuditLog
    template_name = 'site_settings/access_control.html'
    context_object_name = 'logs'
    paginate_by = 30

    def get_queryset(self):
        qs = AuditLog.objects.filter(action__in=['auth.login', 'auth.logout']).select_related('user')
        user_id = self.request.GET.get('user')
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff_list'] = User.objects.exclude(role=User.Role.ADMIN).order_by('full_name')
        context['selected_user'] = self.request.GET.get('user', '')
        return context


class StaffAccessToggleView(AdminRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User.objects.exclude(role=User.Role.ADMIN), pk=pk)
        set_active(request.user, user, not user.is_active)
        messages.success(request, 'Holat yangilandi')
        return redirect('site_settings:access_control')
