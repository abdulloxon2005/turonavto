from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from apps.core.mixins import AdminRequiredMixin
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
